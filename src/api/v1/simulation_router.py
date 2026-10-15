"""
src/api/v1/simulation_router.py
===============================
Simülasyon ve Otonom Karar Ajanı API Router'ı.

Kurallar (.antigravityrules §1, §3 & §5):
- Sadece HTTP istek ve yanıt yönetiminden sorumludur.
- CAD/CSV/Excel dosyaları işlenirken sunucuda geçici dosya çöpü bırakılmaz;
  bellek içi (io.BytesIO) akış kullanılır.
- İş mantığı doğrudan servise (CadenceOrchestrator) ve ajana (CadenceECOAgent) delege edilir (Depends).
- Tip Güvenliği: Sıfır Any tipi.
"""

from __future__ import annotations

import io

from openai import APIConnectionError, APIError, AuthenticationError, RateLimitError
import pandas as pd
from pydantic import ValidationError
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)

from src.agents.eco_agent import CadenceECOAgent
from src.core.exceptions import (
    BOMStructureError,
    CadencePLMException,
    CostCalculationError,
    ECOParsingError,
    PartNotFoundError,
)
from src.schemas.agent_api import AgentAnalyzeRequest, AgentAnalyzeResponse
from src.schemas.simulation import SimulationSummary
from src.services.orchestrator import CadenceOrchestrator

router = APIRouter(tags=["Simulation"])


# ---------------------------------------------------------------------------
# Bağımlılık Sağlayıcıları (Dependency Injection)
# ---------------------------------------------------------------------------

def get_orchestrator() -> CadenceOrchestrator:
    """CadenceOrchestrator bağımlılık enjeksiyon sağlayıcısı."""
    return CadenceOrchestrator()


def get_eco_agent() -> CadenceECOAgent:
    """CadenceECOAgent bağımlılık enjeksiyon sağlayıcısı."""
    return CadenceECOAgent()


async def parse_agent_request(request: Request) -> AgentAnalyzeRequest:
    """
    İstek gövdesini hem application/json hem de form-data olarak güvenle ayrıştırır.
    """
    content_type = request.headers.get("content-type", "")
    try:
        if "application/json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"İstek gövdesi okunamadı veya geçersiz JSON/Form: {err}",
        ) from err

    try:
        return AgentAnalyzeRequest.model_validate(data)
    except ValidationError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=err.errors(),
        ) from err


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/simulate",
    response_model=SimulationSummary,
    status_code=status.HTTP_200_OK,
    summary="ECO Mühendislik Değişiklik Simülasyonu",
    description=(
        "Serbest metin ECO talebini, EBOM ve Envanter CSV dosyalarını alarak "
        "deterministik hurda maliyeti, kalıp etkisi ve geçiş teslim süresini hesaplar."
    ),
)
async def simulate_eco(
    ebom_file: UploadFile = File(
        ...,
        description="Mühendislik BOM (EBOM) CSV dosyası",
    ),
    inventory_file: UploadFile = File(
        ...,
        description="SAP Envanter ve Stok CSV dosyası",
    ),
    eco_text: str = Form(
        ...,
        min_length=3,
        description="Serbest metin ECO açıklaması (örn: 'GBX-1210 milinin toleransı revize edilecek, yeni rev C')",
    ),
    orchestrator: CadenceOrchestrator = Depends(get_orchestrator),
) -> SimulationSummary:
    """
    ECO simülasyonu çalıştırır.

    1. Dosyaları bellek içi (in-memory) okur.
    2. Pandas DataFrame'e dönüştürür.
    3. CadenceOrchestrator üzerinden simülasyonu yürütür.
    """
    try:
        ebom_bytes = await ebom_file.read()
        if not ebom_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Yüklenen EBOM CSV dosyası boş.",
            )
        ebom_df = pd.read_csv(io.BytesIO(ebom_bytes))
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"EBOM CSV dosyası ayrıştırılamadı: {err}",
        ) from err

    try:
        inventory_bytes = await inventory_file.read()
        if not inventory_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Yüklenen Envanter CSV dosyası boş.",
            )
        inventory_df = pd.read_csv(io.BytesIO(inventory_bytes))
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Envanter CSV dosyası ayrıştırılamadı: {err}",
        ) from err

    return orchestrator.run_simulation(
        raw_eco_text=eco_text,
        ebom_df=ebom_df,
        inventory_df=inventory_df,
    )


@router.post(
    "/agent/analyze",
    response_model=AgentAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Otonom ECO Karar Ajanı Analizi (OpenAI Tool-Calling)",
    description=(
        "Serbest metin ECO talebini canlı OpenAI GPT-4o ve CadencePLM motorları ile "
        "ReAct döngüsünde analiz eder; hurda, kalıp, where-used ve rework kararlarını sentezler."
    ),
)
async def analyze_with_agent(
    payload: AgentAnalyzeRequest = Depends(parse_agent_request),
    agent: CadenceECOAgent = Depends(get_eco_agent),
) -> AgentAnalyzeResponse:
    """
    Otonom ECO Karar Ajanı endpoint'i.

    1. Gelen JSON veya Form verisini AgentAnalyzeRequest olarak çözümler.
    2. CadenceECOAgent ile canlı OpenAI ReAct tool-calling analizini yürütür.
    3. Hata durumlarında uygun HTTP 400 veya 502 durum kodlarını döndürür.
    4. Başarılı sonuçta AgentAnalyzeResponse nesnesi döner.
    """
    input_text = payload.eco_text
    if payload.custom_context:
        input_text = f"{input_text}\n[Ek Bağlam]: {payload.custom_context}"

    try:
        res = agent.analyze_eco_unstructured(input_text)
        return AgentAnalyzeResponse(
            status=str(res.get("status", "SUCCESS")),
            target_part_number=str(res.target_part_number),
            change_type=str(res.change_type),
            total_scrap_cost=float(res.total_scrap_cost),
            net_savings=float(res.net_savings),
            is_reworkable=bool(res.is_reworkable),
            recommended_strategy=str(res.recommended_strategy),
            run_out_days=int(res.run_out_days),
            max_transition_lead_time_days=int(res.max_transition_lead_time_days),
            where_used_chain=list(res.where_used_chain),
            tools_called=list(res.tools_called),
            executive_summary=str(res.executive_summary),
        )
    except (APIConnectionError, RateLimitError, AuthenticationError, APIError) as api_err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI servisine bağlanılamadı veya kota aşıldı: {api_err}",
        ) from api_err
    except (
        PartNotFoundError,
        ECOParsingError,
        BOMStructureError,
        CostCalculationError,
        CadencePLMException,
    ) as domain_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=getattr(domain_err, "message", str(domain_err)),
        ) from domain_err
    except HTTPException:
        raise
    except Exception as unexpected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ajan analizinde beklenmeyen hata: {unexpected}",
        ) from unexpected
