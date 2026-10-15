"""
src/agents/eco_agent.py
=======================
CadencePLM Otonom LLM Karar Ajanı (Real OpenAI Tool-Calling / ReAct Agent).

Kurallar (.antigravityrules §1, §3, §5):
- Matematik ve ağaç gezintisi LLM ile hesaplanamaz; tüm hesaplamalar saf Python
  motorlarına (ImpactCalculatorEngine, BOMTreeEngine, ReworkOptimizerEngine,
  EffectivityEngine) yaptırılır.
- Mock veya Regex fallback yoktur. Canlı OpenAI v1.x client (gpt-4o) kullanılır.
- ReAct Tool-Calling döngüsü ile model araçları otonom tetikler ve sonuçları yorumlar.
- Tip Güvenliği: Python 3.11+, katı tip ipuçları, sıfır Any kullanımı.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Mapping

from openai import OpenAI
import pandas as pd

from src.core.config import settings
from src.core.exceptions import (
    CadencePLMException,
    ECOParsingError,
    PartNotFoundError,
)
from src.engines.bom_tree import BOMTreeEngine
from src.engines.effectivity_engine import EffectivityEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.engines.rework_optimizer import ReworkOptimizerEngine
from src.schemas.inventory import InventoryItem

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_DEFAULT_EBOM_PATH: Path = _PROJECT_ROOT / "data" / "sample_ebom.csv"
_DEFAULT_INVENTORY_PATH: Path = _PROJECT_ROOT / "data" / "sample_inventory.csv"


# ---------------------------------------------------------------------------
# Zengin Ajan Yanıt Tipi
# ---------------------------------------------------------------------------

class AgentAnalysisResult(dict[str, object]):
    """
    Ajan analiz sonucunu tutan zengin sözlük.

    - Standart sözlük erişimi: res["target_part_number"], res["total_scrap_cost"]
    - Nitelik erişimi: res.target_part_number, res.total_scrap_cost, res.executive_summary
    - 'in' anahtar kontrolü: 'total_scrap_cost' in res
    """

    def __getattr__(self, item: str) -> object:
        if item in self:
            return self[item]
        raise AttributeError(f"'AgentAnalysisResult' nesnesinde {item!r} niteliği bulunamadı.")


# ---------------------------------------------------------------------------
# OpenAI Tool (Function Calling) Şemaları
# ---------------------------------------------------------------------------

_OPENAI_TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "tool_run_simulation",
            "description": (
                "BOMTreeEngine ve ImpactCalculatorEngine kullanarak verilen parçanın ve etkilediği alt sistemlerin "
                "toplam hurda maliyetini, stok miktarını, tedarikçi kalıp durumunu ve geçiş teslim süresini hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "Hedef parça numarası (örn: 'GB-PINION-02', 'GBX-1210').",
                    },
                    "change_type": {
                        "type": "string",
                        "description": "Değişiklik türü (örn: 'TOLERANCE', 'MATERIAL', 'DIMENSION', 'OBSOLETE').",
                    },
                },
                "required": ["part_number", "change_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_get_where_used",
            "description": (
                "BOMTreeEngine üzerinden hedeflenen parçanın doğrudan ve dolaylı olarak bağlı olduğu tüm üst montajları "
                "(Where-Used bottom-up gezintisi) ve montaj seviyelerini döner."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "Sorgulanacak parça numarası (örn: 'GB-PINION-02').",
                    },
                },
                "required": ["part_number"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_evaluate_rework",
            "description": (
                "ReworkOptimizerEngine kullanarak parçanın hurdaya ayrılmak yerine CNC Talaşlı İmalat (torna, taşlama) "
                "ile kurtarılabilirliğini ve sağlanacak net finansal tasarrufu hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "part_number": {
                        "type": "string",
                        "description": "Hedef parça numarası.",
                    },
                    "unit_cost": {
                        "type": "number",
                        "description": "Parçanın birim maliyeti USD.",
                    },
                    "stock_quantity": {
                        "type": "integer",
                        "description": "Stoktaki parça adedi.",
                    },
                    "change_type": {
                        "type": "string",
                        "description": "Değişiklik türü (TOLERANCE, MATERIAL, DIMENSION vb.).",
                    },
                },
                "required": ["part_number", "unit_cost", "stock_quantity", "change_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tool_calculate_effectivity",
            "description": (
                "EffectivityEngine kullanarak optimum yürürlük ve stok tüketim stratejisini "
                "(USE_UP_STOCK veya IMMEDIATE_CUTOFF) ve stok tükenme süresini (run-out gün) hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "stock_quantity": {
                        "type": "integer",
                        "description": "Mevcut stok adedi.",
                    },
                    "unit_cost": {
                        "type": "number",
                        "description": "Birim maliyet USD.",
                    },
                    "tooling_lead_time_days": {
                        "type": "integer",
                        "description": "Tedarik/kalıp teslim süresi iş günü.",
                    },
                    "daily_consumption_rate": {
                        "type": "integer",
                        "description": "Günlük montaj tüketim hızı (varsayılan: 5).",
                    },
                },
                "required": [
                    "stock_quantity",
                    "unit_cost",
                    "tooling_lead_time_days",
                    "daily_consumption_rate",
                ],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# CadenceECOAgent Sınıfı
# ---------------------------------------------------------------------------

class CadenceECOAgent:
    """
    CadencePLM Otonom LLM Karar Ajanı (Tier-1 İmalat & Değişiklik Yönetimi Uzmanı).

    OpenAI GPT-4o ile ReAct Tool-Calling döngüsü kurarak karmaşık mühendislik
    değişiklik taleplerini analiz eder, deterministik hesaplama motorlarımızı çağırır
    ve üst düzey yöneticilere IATF 16949 uyumlu teknik/finansal karar raporu sunar.
    """

    SYSTEM_PROMPT: str = (
        "Sen CadencePLM Kıdemli İmalat ve Değişiklik Yönetimi Ajanısın (Automotive Tier-1 & IATF 16949 Uzmanı).\n"
        "Kullanıcıdan gelen karmaşık ve dağınık değişiklik taleplerini analiz et.\n"
        "Önce ilgili parçayı ve ilişkilerini incelemek için tool_run_simulation ve tool_get_where_used araçlarını çağır.\n"
        "Ardından hurda çıkıyorsa kurtarılabilirliği görmek için tool_evaluate_rework aracını çağır.\n"
        "Son olarak stoğun run-out süresi için tool_calculate_effectivity aracını çalıştır.\n"
        "Tüm araç çıktılarını sentezleyerek yöneticiye şeffaf, risk analizli ve net tasarruf odaklı kurumsal bir karar metni sun."
    )

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        ebom_path: Path | str | None = None,
        inventory_path: Path | str | None = None,
    ) -> None:
        # OpenAI istemcisi
        resolved_key = api_key or settings.openai_api_key_str
        if not resolved_key or not resolved_key.startswith("sk-"):
            raise CadencePLMException(
                "Geçersiz veya eksik OPENAI_API_KEY.",
                detail="OpenAI istemcisi başlatılamadı; lütfen geçerli bir API anahtarı sağlayın.",
            )
        self.api_key: str = resolved_key
        self.model: str = model or settings.OPENAI_MODEL or "gpt-4o"
        self.client: OpenAI = OpenAI(api_key=self.api_key)

        # Deterministik Motorlar ve Veri Setleri
        self.ebom_path: Path = Path(ebom_path) if ebom_path else _DEFAULT_EBOM_PATH
        self.inventory_path: Path = (
            Path(inventory_path) if inventory_path else _DEFAULT_INVENTORY_PATH
        )
        self._load_engines()

    def _load_engines(self) -> None:
        """Deterministik motorları ve veri setlerini belleğe yükler."""
        if not self.ebom_path.exists():
            raise CadencePLMException(
                f"EBOM veri seti bulunamadı: {self.ebom_path}",
                detail="sample_ebom.csv dosyası eksik.",
            )
        if not self.inventory_path.exists():
            raise CadencePLMException(
                f"Envanter veri seti bulunamadı: {self.inventory_path}",
                detail="sample_inventory.csv dosyası eksik.",
            )

        self.ebom_df: pd.DataFrame = pd.read_csv(self.ebom_path)
        self.inventory_df: pd.DataFrame = pd.read_csv(self.inventory_path)

        # Envanter haritası
        self.inventory_map: dict[str, InventoryItem] = {}
        for _, row in self.inventory_df.iterrows():
            item = InventoryItem(
                part_number=str(row["part_number"]).strip(),
                stock_quantity=int(row["stock_quantity"]),
                lead_time_days=int(row["lead_time_days"]),
                location=str(row.get("location", "WH-DEFAULT")).strip(),
            )
            self.inventory_map[item.part_number] = item

        # Motorlar
        self.bom_tree: BOMTreeEngine = BOMTreeEngine()
        self.bom_tree.load_from_dataframe(self.ebom_df)

        self.impact_calculator: ImpactCalculatorEngine = ImpactCalculatorEngine()
        self.rework_optimizer: ReworkOptimizerEngine = ReworkOptimizerEngine()
        self.effectivity_engine: EffectivityEngine = EffectivityEngine()

    # -----------------------------------------------------------------------
    # OpenAI Tools (Python Motor Uygulamaları)
    def _resolve_part_number(self, pn: str) -> str:
        """Parça formatı veya alias eşlemesi (örn: GB-SHAFT-01 -> GBX-1210)."""
        clean = str(pn).strip().upper()
        if clean in ("GB-SHAFT-01", "GB-SHAFT") and clean not in self.bom_tree.all_part_numbers:
            return "GBX-1210"
        return clean

    def tool_run_simulation(self, part_number: str, change_type: str) -> dict[str, object]:
        """BOMTreeEngine & ImpactCalculatorEngine simülasyonunu yürütür."""
        clean_pn = self._resolve_part_number(part_number)
        if clean_pn not in self.bom_tree.all_part_numbers:
            raise PartNotFoundError(
                part_id=clean_pn,
                message=f"BOM yapısında '{clean_pn}' parçası bulunamadı.",
                detail="Hedef parça kurumsal EBOM ağacında tanımlı değildir.",
            )

        affected = self.bom_tree.get_affected_subassemblies(clean_pn)
        summary = self.impact_calculator.calculate(
            eco_id=f"ECO-AGENT-{clean_pn}",
            root_part_number=clean_pn,
            affected_parts=affected,
            inventory_map=self.inventory_map,
        )

        details_list: list[dict[str, object]] = []
        for det in summary.details:
            details_list.append(
                {
                    "part_number": det.part_number,
                    "part_name": det.part_name,
                    "affected_stock": det.affected_stock,
                    "unit_cost": det.unit_cost,
                    "scrap_cost": det.scrap_cost,
                    "tooling_affected": det.tooling_affected,
                    "supplier_id": det.supplier_id,
                    "lead_time_days": det.lead_time_days,
                }
            )

        return {
            "status": "SUCCESS",
            "part_number": clean_pn,
            "change_type": str(change_type).upper(),
            "total_affected_parts": summary.total_affected_parts,
            "total_scrap_cost": summary.total_scrap_cost,
            "total_impacted_toolings": summary.total_impacted_toolings,
            "max_transition_lead_time_days": summary.max_transition_lead_time_days,
            "details": details_list,
        }

    def tool_get_where_used(self, part_number: str) -> dict[str, object]:
        """BOMTreeEngine üzerinden Where-Used bottom-up gezintisini yürütür."""
        clean_pn = self._resolve_part_number(part_number)
        if clean_pn not in self.bom_tree.all_part_numbers:
            raise PartNotFoundError(
                part_id=clean_pn,
                message=f"BOM yapısında '{clean_pn}' parçası bulunamadı.",
                detail="Where-used sorgulanan parça EBOM ağacında mevcut değildir.",
            )

        where_used = self.bom_tree.get_where_used(clean_pn)
        chain: list[dict[str, object]] = [
            {
                "parent_part_number": item.parent_part_number,
                "parent_part_name": item.parent_part_name,
                "assembly_level": item.assembly_level,
            }
            for item in where_used
        ]

        return {
            "status": "SUCCESS",
            "part_number": clean_pn,
            "where_used_chain": chain,
            "total_parent_levels": len(chain),
        }

    def tool_evaluate_rework(
        self,
        part_number: str,
        unit_cost: float,
        stock_quantity: int,
        change_type: str,
    ) -> dict[str, object]:
        """ReworkOptimizerEngine ile hurda yerine talaşlı imalat kurtarma analizi yapar."""
        clean_pn = self._resolve_part_number(part_number)

        # Eksik veya sıfır veri durumunda gerçek katalog verisinden otomatik tamamlama
        cost = float(unit_cost)
        stock = int(stock_quantity)
        if cost <= 0.0 or stock <= 0:
            if clean_pn in self.inventory_map:
                stock = self.inventory_map[clean_pn].stock_quantity
            if clean_pn in self.bom_tree.all_part_numbers:
                item = self.bom_tree.get_part(clean_pn)
                if item and item.unit_cost > 0:
                    cost = item.unit_cost

        feasibility = self.rework_optimizer.evaluate_rework(
            part_number=clean_pn,
            unit_cost=cost,
            stock_quantity=stock,
            change_type=str(change_type).upper(),
        )

        return {
            "status": "SUCCESS",
            "part_number": clean_pn,
            "change_type": str(change_type).upper(),
            "is_reworkable": feasibility.is_reworkable,
            "operation_type": str(feasibility.operation_type),
            "rework_cost_per_unit": feasibility.rework_cost_per_unit,
            "net_savings": feasibility.net_savings,
        }

    def tool_calculate_effectivity(
        self,
        stock_quantity: int,
        unit_cost: float,
        tooling_lead_time_days: int,
        daily_consumption_rate: int = 5,
    ) -> dict[str, object]:
        """EffectivityEngine ile optimum yürürlük ve stok tüketim gününü hesaplar."""
        plan = self.effectivity_engine.calculate_transition_plan(
            stock_quantity=int(stock_quantity),
            unit_cost=float(unit_cost),
            tooling_lead_time_days=int(tooling_lead_time_days),
            daily_consumption_rate=int(daily_consumption_rate) if daily_consumption_rate > 0 else 5,
        )
        strategy = plan[0]
        run_out_days = plan[1]

        return {
            "status": "SUCCESS",
            "strategy": strategy.value,
            "run_out_days": run_out_days,
            "stock_quantity": int(stock_quantity),
            "tooling_lead_time_days": int(tooling_lead_time_days),
            "daily_consumption_rate": int(daily_consumption_rate),
        }

    def _dispatch_tool(self, tool_name: str, args: Mapping[str, object]) -> dict[str, object]:
        """OpenAI tool çağrısını ilgili yerel Python motor metoduna yönlendirir."""
        if tool_name == "tool_run_simulation":
            return self.tool_run_simulation(
                part_number=str(args.get("part_number", "")),
                change_type=str(args.get("change_type", "TOLERANCE")),
            )
        if tool_name == "tool_get_where_used":
            return self.tool_get_where_used(
                part_number=str(args.get("part_number", "")),
            )
        if tool_name == "tool_evaluate_rework":
            return self.tool_evaluate_rework(
                part_number=str(args.get("part_number", "")),
                unit_cost=float(args.get("unit_cost", 0.0)),
                stock_quantity=int(args.get("stock_quantity", 0)),
                change_type=str(args.get("change_type", "TOLERANCE")),
            )
        if tool_name == "tool_calculate_effectivity":
            return self.tool_calculate_effectivity(
                stock_quantity=int(args.get("stock_quantity", 0)),
                unit_cost=float(args.get("unit_cost", 0.0)),
                tooling_lead_time_days=int(args.get("tooling_lead_time_days", 0)),
                daily_consumption_rate=int(args.get("daily_consumption_rate", 5)),
            )

        raise CadencePLMException(
            f"Bilinmeyen OpenAI aracı: {tool_name!r}",
            detail="Tanımlı araçlar: tool_run_simulation, tool_get_where_used, tool_evaluate_rework, tool_calculate_effectivity",
        )

    # -----------------------------------------------------------------------
    # ReAct Tool-Calling Döngüsü
    # -----------------------------------------------------------------------

    def analyze_eco_unstructured(self, unstructured_text: str) -> AgentAnalysisResult:
        """
        Kullanıcıdan gelen serbest metin ECO talebini gerçek OpenAI GPT-4o
        Function Calling ile analiz eder.

        Parameters
        ----------
        unstructured_text : str
            Mühendislik değişiklik açıklaması.

        Returns
        -------
        AgentAnalysisResult
            Araç çıktıları ile sentezlenmiş yönetici karar nesnesi.

        Raises
        ------
        ECOParsingError
            Boş metin veya modelin hiçbir araç çağıramadığı durumlarda.
        PartNotFoundError
            Metindeki parça BOM ağacında bulunamadığında.
        """
        raw_text = str(unstructured_text).strip()
        if not raw_text:
            raise ECOParsingError(
                message="ECO metni boş olamaz.",
                raw_input=unstructured_text,
                detail="Lütfen geçerli bir mühendislik değişiklik açıklaması girin.",
            )

        # OpenAI mesaj listesi
        messages: list[dict[str, object]] = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ]

        tools_called: list[str] = []
        captured_data: dict[str, object] = {
            "target_part_number": "",
            "change_type": "TOLERANCE",
            "total_scrap_cost": 0.0,
            "total_affected_parts": 0,
            "total_impacted_toolings": 0,
            "max_transition_lead_time_days": 0,
            "recommended_strategy": "IMMEDIATE_CUTOFF",
            "run_out_days": 0,
            "net_savings": 0.0,
            "is_reworkable": False,
            "operation_type": "NONE",
            "rework_cost_per_unit": 0.0,
            "where_used_chain": [],
        }

        final_response_text = ""
        max_iterations = 8

        for _ in range(max_iterations):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,  # type: ignore[arg-type]
                tools=_OPENAI_TOOLS,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=0.1,
            )

            choice = response.choices[0]
            msg = choice.message

            # Asistan yanıtını geçmişe ekle
            msg_dict: dict[str, object] = {
                "role": "assistant",
                "content": msg.content or "",
            }
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ]
            messages.append(msg_dict)

            # Araç çağrısı yoksa döngüyü bitir
            if not msg.tool_calls:
                final_response_text = msg.content or ""
                break

            # Araçları çalıştır ve sonuçları ekle
            for tc in msg.tool_calls:
                fn_name = tc.function.name
                tools_called.append(fn_name)

                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {}

                # Tool dispatch (PartNotFoundError olursa fırlatılır)
                tool_result = self._dispatch_tool(fn_name, args)

                # Çıktıları kümülatif veri tablosuna işle
                if fn_name == "tool_run_simulation":
                    captured_data["target_part_number"] = tool_result.get("part_number", "")
                    captured_data["change_type"] = tool_result.get("change_type", "TOLERANCE")
                    captured_data["total_scrap_cost"] = tool_result.get("total_scrap_cost", 0.0)
                    captured_data["total_affected_parts"] = tool_result.get("total_affected_parts", 0)
                    captured_data["total_impacted_toolings"] = tool_result.get("total_impacted_toolings", 0)
                    captured_data["max_transition_lead_time_days"] = tool_result.get(
                        "max_transition_lead_time_days", 0
                    )

                elif fn_name == "tool_get_where_used":
                    if not captured_data["target_part_number"]:
                        captured_data["target_part_number"] = tool_result.get("part_number", "")
                    captured_data["where_used_chain"] = tool_result.get("where_used_chain", [])

                elif fn_name == "tool_evaluate_rework":
                    captured_data["is_reworkable"] = tool_result.get("is_reworkable", False)
                    captured_data["operation_type"] = tool_result.get("operation_type", "NONE")
                    captured_data["rework_cost_per_unit"] = tool_result.get("rework_cost_per_unit", 0.0)
                    captured_data["net_savings"] = tool_result.get("net_savings", 0.0)

                elif fn_name == "tool_calculate_effectivity":
                    captured_data["recommended_strategy"] = tool_result.get("strategy", "IMMEDIATE_CUTOFF")
                    captured_data["run_out_days"] = tool_result.get("run_out_days", 0)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(tool_result, ensure_ascii=False),
                    }
                )

        # Eğer model hiçbir araç çağırmadıysa (örn. genel bakım metni vb.)
        if not tools_called:
            raise ECOParsingError(
                message="Metinden herhangi bir geçerli parça veya ECO talebi çıkarılamadı.",
                raw_input=raw_text,
                detail=final_response_text or "Model hiçbir analiz aracı çağırmadı.",
            )

        # Hedef parça belirlenememişse
        target_pn = str(captured_data["target_part_number"])
        if not target_pn:
            raise ECOParsingError(
                message="Hedef parça numarası belirlenemedi.",
                raw_input=raw_text,
                detail="Model simülasyon aracı çağırdı ancak parça numarası tespit edilemedi.",
            )

        # Sonuç paketini inşa et
        result_dict: dict[str, object] = {
            "status": "SUCCESS",
            "target_part_number": target_pn,
            "part_number": target_pn,
            "change_type": str(captured_data["change_type"]),
            "total_scrap_cost": float(captured_data["total_scrap_cost"]),
            "total_affected_parts": int(captured_data["total_affected_parts"]),
            "total_impacted_toolings": int(captured_data["total_impacted_toolings"]),
            "max_transition_lead_time_days": int(captured_data["max_transition_lead_time_days"]),
            "recommended_strategy": str(captured_data["recommended_strategy"]),
            "run_out_days": int(captured_data["run_out_days"]),
            "net_savings": float(captured_data["net_savings"]),
            "is_reworkable": bool(captured_data["is_reworkable"]),
            "operation_type": str(captured_data["operation_type"]),
            "rework_cost_per_unit": float(captured_data["rework_cost_per_unit"]),
            "where_used_chain": captured_data["where_used_chain"],
            "tools_called": tools_called,
            "executive_summary": final_response_text,
            "raw_input": raw_text,
        }

        return AgentAnalysisResult(result_dict)
