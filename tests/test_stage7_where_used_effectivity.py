"""
tests/test_stage7_where_used_effectivity.py
===========================================
Aşama 7: Where-Used hiyerarşisi ve Yürürlük (Effectivity) motoru birim testleri.

Kural (.antigravityrules §1 & §4):
- Deterministik yukarı yönlü gezinti (bottom-up traversal) doğrulanır.
- EffectivityEngine stok tükenme süresi ve kalıp teslim süresi karşılaştırması
  matematiksel olarak doğrulanır.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import CostCalculationError, PartNotFoundError
from src.engines.bom_tree import BOMTreeEngine
from src.engines.effectivity_engine import EffectivityEngine
from src.schemas.simulation import (
    EffectivityStrategy,
    SimulationSummary,
    WhereUsedDetail,
)


# ===========================================================================
# 1. Where-Used (Yukarı Yönlü / Bottom-Up Gezinti) Testleri
# ===========================================================================

class TestWhereUsedTraversal:
    """BOMTreeEngine.get_where_used testleri."""

    @pytest.fixture()
    def gearbox_tree(self) -> BOMTreeEngine:
        engine = BOMTreeEngine()
        engine.load_from_csv("data/sample_ebom.csv")
        return engine

    def test_pinion_where_used_two_levels(self, gearbox_tree: BOMTreeEngine) -> None:
        """
        GB-PINION-02 parçası:
        Seviye 1: GBX-1300 (Diferansiyel Çıkış Grubu)
        Seviye 2: GBX-1000 (Şanzıman Ana Montajı)
        """
        where_used = gearbox_tree.get_where_used("GB-PINION-02")

        assert len(where_used) == 2
        assert all(isinstance(w, WhereUsedDetail) for w in where_used)

        level_1 = where_used[0]
        assert level_1.parent_part_number == "GBX-1300"
        assert level_1.assembly_level == 1
        assert "Diferansiyel" in level_1.parent_part_name

        level_2 = where_used[1]
        assert level_2.parent_part_number == "GBX-1000"
        assert level_2.assembly_level == 2
        assert "Şanzıman" in level_2.parent_part_name

    def test_gear_drive_where_used_three_levels(self, gearbox_tree: BOMTreeEngine) -> None:
        """
        GBX-1211 (1. Vites Tahrik Dişlisi):
        Seviye 1: GBX-1210 (Ana Dişli Mili)
        Seviye 2: GBX-1200 (Giriş Mili ve Dişli Grubu)
        Seviye 3: GBX-1000 (Şanzıman Ana Montajı)
        """
        where_used = gearbox_tree.get_where_used("GBX-1211")

        assert len(where_used) == 3
        levels = [w.assembly_level for w in where_used]
        parent_pns = [w.parent_part_number for w in where_used]

        assert levels == [1, 2, 3]
        assert parent_pns == ["GBX-1210", "GBX-1200", "GBX-1000"]

    def test_root_part_has_empty_where_used(self, gearbox_tree: BOMTreeEngine) -> None:
        """Kök parçanın (GBX-1000) üst ebeveyni olmadığından boş liste dönmelidir."""
        where_used = gearbox_tree.get_where_used("GBX-1000")
        assert where_used == []

    def test_nonexistent_part_raises_part_not_found(self, gearbox_tree: BOMTreeEngine) -> None:
        """Tanımsız parça PartNotFoundError fırlatmalıdır."""
        with pytest.raises(PartNotFoundError) as exc_info:
            gearbox_tree.get_where_used("NON_EXISTENT_PART")
        assert exc_info.value.part_id == "NON_EXISTENT_PART"


# ===========================================================================
# 2. EffectivityEngine (Yürürlük Stratejisi) Testleri
# ===========================================================================

class TestEffectivityEngine:
    """EffectivityEngine matematiksel geçiş planlama testleri."""

    @pytest.fixture()
    def effectivity_engine(self) -> EffectivityEngine:
        return EffectivityEngine(default_daily_consumption_rate=5)

    def test_use_up_stock_when_runout_less_than_leadtime(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        """
        Stok: 50 adet, Günlük tüketim: 5 adet -> Tükenme süresi: 10 gün.
        Kalıp teslim süresi: 25 gün.
        10 gün <= 25 gün -> USE_UP_STOCK önerilmeli, hurda maliyeti 0.00 USD olmalı.
        """
        strategy, run_out_days, scrap_cost = effectivity_engine.calculate_transition_plan(
            stock_quantity=50,
            unit_cost=100.0,
            tooling_lead_time_days=25,
            daily_consumption_rate=5,
        )

        assert strategy == EffectivityStrategy.USE_UP_STOCK
        assert run_out_days == 10
        assert scrap_cost == 0.0

    def test_immediate_cutoff_when_runout_exceeds_leadtime(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        """
        Stok: 200 adet, Günlük tüketim: 5 adet -> Tükenme süresi: 40 gün.
        Kalıp teslim süresi: 14 gün.
        40 gün > 14 gün -> IMMEDIATE_CUTOFF önerilmeli, tüm stok hurdaya çıkmalı.
        Hurda = 200 * 25.50 = 5100.00 USD.
        """
        strategy, run_out_days, scrap_cost = effectivity_engine.calculate_transition_plan(
            stock_quantity=200,
            unit_cost=25.50,
            tooling_lead_time_days=14,
            daily_consumption_rate=5,
        )

        assert strategy == EffectivityStrategy.IMMEDIATE_CUTOFF
        assert run_out_days == 0
        assert scrap_cost == 5100.00

    def test_zero_stock_yields_use_up_zero_scrap(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        """Mevcut stok sıfır ise USE_UP_STOCK ile anında sıfır maliyetle geçilir."""
        strategy, run_out_days, scrap_cost = effectivity_engine.calculate_transition_plan(
            stock_quantity=0,
            unit_cost=50.0,
            tooling_lead_time_days=10,
        )
        assert strategy == EffectivityStrategy.USE_UP_STOCK
        assert run_out_days == 0
        assert scrap_cost == 0.0

    def test_negative_stock_raises_cost_calculation_error(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        with pytest.raises(CostCalculationError, match="Negatif stok"):
            effectivity_engine.calculate_transition_plan(
                stock_quantity=-10,
                unit_cost=50.0,
                tooling_lead_time_days=10,
            )

    def test_negative_unit_cost_raises_cost_calculation_error(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        with pytest.raises(CostCalculationError, match="Negatif birim maliyet"):
            effectivity_engine.calculate_transition_plan(
                stock_quantity=10,
                unit_cost=-5.0,
                tooling_lead_time_days=10,
            )

    def test_zero_daily_consumption_rate_raises_error(
        self, effectivity_engine: EffectivityEngine
    ) -> None:
        with pytest.raises(CostCalculationError, match="sıfır veya negatif olamaz"):
            effectivity_engine.calculate_transition_plan(
                stock_quantity=10,
                unit_cost=5.0,
                tooling_lead_time_days=10,
                daily_consumption_rate=0,
            )


# ===========================================================================
# 3. SimulationSummary Şema Genişletme Testleri
# ===========================================================================

def test_simulation_summary_new_fields_defaults() -> None:
    """Yeni eklenen alanlar geriye dönük uyumlu varsayılan değerlere sahip olmalıdır."""
    summary = SimulationSummary(
        eco_id="ECO-T",
        root_part_number="P-01",
        total_affected_parts=1,
        total_scrap_cost=100.0,
        total_impacted_toolings=1,
        max_transition_lead_time_days=10,
    )
    assert summary.where_used_parents == []
    assert summary.recommended_strategy == EffectivityStrategy.IMMEDIATE_CUTOFF
    assert summary.run_out_days == 0
