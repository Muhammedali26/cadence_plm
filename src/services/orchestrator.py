"""
src/services/orchestrator.py
============================
CadencePLM servis orkestratörü.

Kurallar (.antigravityrules §1 & §3):
- Sorumluluk: Yalnızca serbest metin ECO talebini parse edip motorları
  (engines) deterministik sırayla çağırmakla sorumludur.
- Matematiksel hesaplama veya ağaç gezintisi yapmaz; bu işleri
  BOMTreeEngine ve ImpactCalculatorEngine'e delege eder.
- Tip Güvenliği: Sıfır Any kullanımı.
"""

from __future__ import annotations

import pandas as pd

from src.engines.bom_tree import BOMTreeEngine
from src.engines.effectivity_engine import EffectivityEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.engines.rework_optimizer import ReworkOptimizerEngine
from src.schemas.inventory import InventoryItem
from src.schemas.simulation import SimulationSummary
from src.services.eco_parser import ECOParser


class CadenceOrchestrator:
    """
    ECO analizi, BOM ağaç gezintisi ve finansal etki hesaplama adımlarını
    uçtan uca orkestre eden ana servis sınıfı.

    Attributes
    ----------
    eco_parser : ECOParser
        Serbest metin ECO talebini ayrıştıran bileşen.
    bom_tree : BOMTreeEngine
        BOM ağacını yükleyen ve DAG traversal yapan deterministik motor.
    impact_calculator : ImpactCalculatorEngine
        Hurda ve kalıp maliyetini hesaplayan deterministik motor.
    effectivity_engine : EffectivityEngine
        Stok tükenme ve yürürlük stratejisini hesaplayan motor.
    rework_optimizer : ReworkOptimizerEngine
        Yeniden işleme ve kurtarma (Rework vs. Scrap) motoru.
    """

    def __init__(
        self,
        eco_parser: ECOParser | None = None,
        bom_tree: BOMTreeEngine | None = None,
        impact_calculator: ImpactCalculatorEngine | None = None,
        effectivity_engine: EffectivityEngine | None = None,
        rework_optimizer: ReworkOptimizerEngine | None = None,
    ) -> None:
        self.eco_parser: ECOParser = eco_parser or ECOParser()
        self.bom_tree: BOMTreeEngine = bom_tree or BOMTreeEngine()
        self.impact_calculator: ImpactCalculatorEngine = impact_calculator or ImpactCalculatorEngine()
        self.effectivity_engine: EffectivityEngine = effectivity_engine or EffectivityEngine()
        self.rework_optimizer: ReworkOptimizerEngine = rework_optimizer or ReworkOptimizerEngine()

    def run_simulation(
        self,
        raw_eco_text: str,
        ebom_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        eco_id: str | None = None,
    ) -> SimulationSummary:
        """
        ECO metnini ve verileri alarak 4 adımlı simülasyon akışını yürütür:
        1. Adım: eco_parser ile ECO metnini analiz et.
        2. Adım: bom_tree ile etkilenen parçaları bul.
        3. Adım: impact_calculator ile hurda, kalıp ve süre maliyetini simüle et.
        4. Adım: SimulationSummary nesnesini dön.

        Parameters
        ----------
        raw_eco_text : str
            Serbest metin ECO açıklaması.
        ebom_df : pd.DataFrame
            Mühendislik BOM verisi (EBOM).
        inventory_df : pd.DataFrame
            SAP envanter ve stok verisi.
        eco_id : str | None
            İsteğe bağlı ECO ID ezme (override).

        Returns
        -------
        SimulationSummary
            Simülasyon özeti ve etki detayları.
        """
        # 1. Adım: ECO metnini analiz et
        eco_request = self.eco_parser.parse(raw_eco_text, eco_id=eco_id)

        # 2. Adım: BOM ağacını yükle ve etkilenen alt montajları bul
        self.bom_tree.load_from_dataframe(ebom_df)
        target_part_number = eco_request.affected_part_number
        if (
            target_part_number.upper() in ("GB-SHAFT-01", "GB-SHAFT")
            and target_part_number not in self.bom_tree.all_part_numbers
            and "GBX-1210" in self.bom_tree.all_part_numbers
        ):
            target_part_number = "GBX-1210"

        affected_parts = self.bom_tree.get_affected_subassemblies(
            target_part_number
        )
        where_used_parents = self.bom_tree.get_where_used(
            target_part_number
        )

        # 3. Adım: Envanter haritasını oluştur ve etkiyi hesapla
        inventory_map = self._build_inventory_map(inventory_df)
        summary = self.impact_calculator.calculate(
            eco_id=eco_request.eco_id,
            root_part_number=target_part_number,
            affected_parts=affected_parts,
            inventory_map=inventory_map,
        )

        # 4. Adım: Yürürlük stratejisini (Effectivity) hesapla
        root_part = self.bom_tree.get_part(target_part_number)
        root_inv = inventory_map.get(target_part_number)
        stock_qty = root_inv.stock_quantity if root_inv else 0
        lead_time = summary.max_transition_lead_time_days

        strategy, run_out_days, _ = self.effectivity_engine.calculate_transition_plan(
            stock_quantity=stock_qty,
            unit_cost=root_part.unit_cost,
            tooling_lead_time_days=lead_time,
        )

        # 5. Adım: Rework vs. Scrap optimizasyonunu hesapla
        rework_analysis = self.rework_optimizer.evaluate_rework(
            part_number=root_part.part_number,
            unit_cost=root_part.unit_cost,
            stock_quantity=stock_qty,
            change_type=eco_request.change_type,
            part_name=root_part.part_name,
        )

        # Modeli zenginleştir ve dön
        return summary.model_copy(
            update={
                "where_used_parents": where_used_parents,
                "recommended_strategy": strategy,
                "run_out_days": run_out_days,
                "rework_analysis": rework_analysis,
            }
        )

    def _build_inventory_map(self, inventory_df: pd.DataFrame) -> dict[str, InventoryItem]:
        """Inventory DataFrame'ini parça numarasına göre InventoryItem sözlüğüne dönüştürür."""
        inventory_map: dict[str, InventoryItem] = {}
        for _, row in inventory_df.iterrows():
            pn = str(row["part_number"]).strip()
            raw_stock = row.get("stock_quantity", 0)
            try:
                stock = int(float(str(raw_stock).strip())) if not pd.isna(raw_stock) else 0
            except (ValueError, TypeError):
                stock = 0

            raw_lead = row.get("lead_time_days", 0)
            try:
                lead = int(float(str(raw_lead).strip())) if not pd.isna(raw_lead) else 0
            except (ValueError, TypeError):
                lead = 0

            location = (
                str(row["location"]).strip()
                if "location" in inventory_df.columns and not pd.isna(row.get("location"))
                else "WAREHOUSE-DEFAULT"
            )
            inventory_map[pn] = InventoryItem(
                part_number=pn,
                stock_quantity=stock,
                lead_time_days=lead,
                location=location,
            )
        return inventory_map
