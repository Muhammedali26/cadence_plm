"""
tests/test_stage13_agent_api.py
===============================
Aşama 13: Otonom Karar Ajanı FastAPI REST API Entegrasyon Testleri.

Kurallar (.antigravityrules §1, §3 & §4):
- Canlı OpenAI GPT-4o ajanının POST /api/v1/agent/analyze endpoint'i üzerinden
  doğrulanması (httpx.AsyncClient ve ASGITransport ile).
- JSON body ve Form verisi isteklerinin doğrulanması.
- 200 OK yanıt yapısının AgentAnalyzeResponse modeliyle uyumu.
- Hatalı isteklerde 400 (Domain hatası), 422 (Pydantic validasyon) ve 502 (OpenAI hatası)
  durum kodlarının doğrulanması.
"""

from __future__ import annotations

import httpx
from httpx import ASGITransport, AsyncClient
import pytest

from openai import APIConnectionError
from src.api.v1.simulation_router import get_eco_agent
from src.main import app
from src.schemas.agent_api import AgentAnalyzeResponse


@pytest.fixture()
def transport() -> ASGITransport:
    return ASGITransport(app=app)


# ===========================================================================
# 1. Başarılı Ajan Analizi Testleri (HTTP 200)
# ===========================================================================

@pytest.mark.asyncio
async def test_agent_analyze_json_success(transport: ASGITransport) -> None:
    """
    POST /api/v1/agent/analyze endpoint'ine JSON gövdesiyle istek atılır.
    Canlı GPT-4o motorları otonom tetiklemeli ve 200 OK ile sentez raporu dönmelidir.
    """
    payload = {
        "eco_text": "GB-PINION-02 pinyon dişlisinin temas yüzeyi toleransı daraltıldı, yeni revizyon B olarak güncellenecek.",
        "custom_context": "Bursa fabrikasında stok tüketimi önceliklidir.",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/agent/analyze", json=payload)

    assert resp.status_code == 200
    data = resp.json()

    # Pydantic v2 model doğrulama
    validated = AgentAnalyzeResponse.model_validate(data)
    assert validated.status == "SUCCESS"
    assert validated.target_part_number == "GB-PINION-02"
    assert validated.change_type == "TOLERANCE"
    assert validated.total_scrap_cost == 7425.0
    assert validated.net_savings == 6311.25
    assert validated.is_reworkable is True
    assert validated.recommended_strategy == "USE_UP_STOCK"
    assert validated.run_out_days == 11
    assert validated.max_transition_lead_time_days == 30
    assert "tool_run_simulation" in validated.tools_called
    assert len(validated.executive_summary) > 50


@pytest.mark.asyncio
async def test_agent_analyze_form_data_success(transport: ASGITransport) -> None:
    """
    POST /api/v1/agent/analyze endpoint'ine form verisiyle istek atıldığında
    başarıyla işlendiği doğrulanır.
    """
    form_data = {
        "eco_text": "GB-PINION-02 pinyon dişlisi aşınma toleransı daraltıldı, yeni revizyon B.",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/agent/analyze", data=form_data)

    assert resp.status_code == 200
    data = resp.json()
    assert data["target_part_number"] == "GB-PINION-02"
    assert data["total_scrap_cost"] == 7425.0


# ===========================================================================
# 2. Hata Yönetimi Testleri (HTTP 400, 422, 502)
# ===========================================================================

@pytest.mark.asyncio
async def test_agent_analyze_validation_error_422(transport: ASGITransport) -> None:
    """Metin 10 karakterden kısa olduğunda HTTP 422 dönmelidir."""
    payload = {"eco_text": "kısa"}

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/agent/analyze", json=payload)

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_agent_analyze_nonexistent_part_error_400(transport: ASGITransport) -> None:
    """BOM'da olmayan geçersiz bir parça istendiğinde HTTP 400 dönmelidir."""
    payload = {
        "eco_text": "GBX-9999 olmayan parça toleransı değişti, hedef revizyon B.",
    }

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/v1/agent/analyze", json=payload)

    assert resp.status_code == 400
    assert "bulunamadı" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_agent_analyze_openai_gateway_error_502(transport: ASGITransport) -> None:
    """OpenAI servisi bağlantı hatası verdiğinde HTTP 502 Bad Gateway dönmelidir."""

    class FailingMockAgent:
        def analyze_eco_unstructured(self, text: str):
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            raise APIConnectionError(request=request)

    app.dependency_overrides[get_eco_agent] = lambda: FailingMockAgent()

    try:
        payload = {
            "eco_text": "GB-PINION-02 dişli tolerans revizyonu B yapılacak.",
        }
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/agent/analyze", json=payload)

        assert resp.status_code == 502
        assert "OpenAI servisine bağlanılamadı" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_eco_agent, None)
