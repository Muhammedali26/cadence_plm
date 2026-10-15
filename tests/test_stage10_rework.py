"""
tests/test_stage10_rework.py
============================
Aşama 10: Endüstriyel Kurtarma (Rework vs. Scrap) Motoru birim testleri.

Kurallar (.antigravityrules §1, §2, §4):
- ReworkFeasibility şeması doğrulanır.
- ReworkOptimizerEngine deterministik talaşlı imalat (CNC_TURNING) hesabı doğrulanır:
  * TOLERANCE / DIMENSION için işlenebilir metal parça: unit_cost * 0.15 ve net_savings.
  * MATERIAL için kurtarma imkansız (is_reworkable = False, hurda kaçınılmaz).
- Negatif girdi koruması (CostCalculationError) doğrulanır.
- SimulationSummary ve CadenceOrchestrator entegrasyonu doğrulanır.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import CostCalculationError
from src.engines.rework_optimizer import ReworkOptimizerEngine
from src.mcp_servers.fastmcp_gateway import tool_run_impact_simulation
from src.schemas.eco import ECOChangeType
from src.schemas.rework import ReworkFeasibility, ReworkOperationType
from src.schemas.simulation import SimulationSummary
from src.services.orchestrator import CadenceOrchestrator


# ===========================================================================
# 1. Şema Doğrulama Testleri
# ===========================================================================

class TestReworkFeasibilitySchema:
    """ReworkFeasibility Pydantic v2 şema testleri."""

    def test_valid_rework_feasibility(self) -> None:
        """Geçerli parametrelerle ReworkFeasibility oluşturulması."""
        rf = ReworkFeasibility(
            is_reworkable=True,
            operation_type=ReworkOperationType.CNC_TURNING.value,
            rework_cost_per_unit=20.25,
            net_savings=6311.25,
        )
        assert rf.is_reworkable is True
        assert rf.operation_type == "CNC_TURNING"
        assert rf.rework_cost_per_unit == 20.25
        assert rf.net_savings == 6311.25

    def test_simulation_summary_optional_rework_field(self) -> None:
        """SimulationSummary modelinde rework_analysis varsayılanı None olmalıdır."""
        summary = SimulationSummary(
            eco_id="ECO-T1",
            root_part_number="P-1",
            total_affected_parts=1,
            total_scrap_cost=100.0,
            total_impacted_toolings=1,
            max_transition_lead_time_days=10,
        )
        assert summary.rework_analysis is None

        # Rework analizi ile güncellenebilmeli
        rf = ReworkFeasibility(
            is_reworkable=True,
            operation_type="CNC_TURNING",
            rework_cost_per_unit=15.0,
            net_savings=850.0,
        )
        updated = summary.model_copy(update={"rework_analysis": rf})
        assert updated.rework_analysis is not None
        assert updated.rework_analysis.is_reworkable is True


# ===========================================================================
# 2. ReworkOptimizerEngine Mantıksal Testleri
# ===========================================================================

class TestReworkOptimizerEngine:
    """ReworkOptimizerEngine çekirdek matematik ve kural testleri."""

    @pytest.fixture()
    def optimizer(self) -> ReworkOptimizerEngine:
        return ReworkOptimizerEngine()

    def test_pinion_tolerance_reworkable(self, optimizer: ReworkOptimizerEngine) -> None:
        """
        GB-PINION-02 (Ayna Pinyon Dişlisi):
        - unit_cost: 135.0
        - stock_quantity: 55
        - change_type: 'TOLERANCE'
        Beklenen:
        - rework_cost_per_unit = 135.0 * 0.15 = 20.25
        - net_savings = (135.0 - 20.25) * 55 = 114.75 * 55 = 6311.25
        - operation_type = 'CNC_TURNING'
        - is_reworkable = True
        """
        res = optimizer.evaluate_rework(
            part_number="GB-PINION-02",
            unit_cost=135.0,
            stock_quantity=55,
            change_type="TOLERANCE",
            part_name="Ayna Pinyon Dişlisi",
        )

        assert res.is_reworkable is True
        assert res.operation_type == "CNC_TURNING"
        assert res.rework_cost_per_unit == 20.25
        assert res.net_savings == 6311.25

    def test_shaft_dimension_reworkable(self, optimizer: ReworkOptimizerEngine) -> None:
        """
        GB-SHAFT-01 / GBX-1210 (Ana Dişli Mili):
        - unit_cost: 180.0
        - stock_quantity: 50
        - change_type: 'DIMENSION'
        Beklenen:
        - rework_cost_per_unit = 180.0 * 0.15 = 27.0
        - net_savings = (180.0 - 27.0) * 50 = 153.0 * 50 = 7650.0
        - is_reworkable = True
        """
        res = optimizer.evaluate_rework(
            part_number="GB-SHAFT-01",
            unit_cost=180.0,
            stock_quantity=50,
            change_type="DIMENSION",
            part_name="Ana Dişli Mili",
        )

        assert res.is_reworkable is True
        assert res.operation_type == "CNC_TURNING"
        assert res.rework_cost_per_unit == 27.0
        assert res.net_savings == 7650.0

    def test_material_change_not_reworkable(self, optimizer: ReworkOptimizerEngine) -> None:
        """
        Değişiklik tipi MATERIAL olduğunda parça ne olursa olsun kurtarma imkansızdır.
        """
        res = optimizer.evaluate_rework(
            part_number="GB-PINION-02",
            unit_cost=135.0,
            stock_quantity=55,
            change_type=ECOChangeType.MATERIAL,
            part_name="Ayna Pinyon Dişlisi",
        )

        assert res.is_reworkable is False
        assert res.operation_type == "NONE"
        assert res.rework_cost_per_unit == 0.0
        assert res.net_savings == 0.0

    def test_non_machinable_part_not_reworkable(self, optimizer: ReworkOptimizerEngine) -> None:
        """
        Conta, rulman, segman gibi parçalar torna ile işlenemez (kurtarılamaz).
        """
        res = optimizer.evaluate_rework(
            part_number="GBX-1120",
            unit_cost=15.50,
            stock_quantity=150,
            change_type="TOLERANCE",
            part_name="Gövde Sızdırmazlık Contası",
        )

        assert res.is_reworkable is False
        assert res.operation_type == "NONE"
        assert res.rework_cost_per_unit == 0.0
        assert res.net_savings == 0.0

    def test_zero_stock_yields_zero_savings(self, optimizer: ReworkOptimizerEngine) -> None:
        """Stok sıfırken net tasarruf sıfır olmalıdır."""
        res = optimizer.evaluate_rework(
            part_number="GB-PINION-02",
            unit_cost=100.0,
            stock_quantity=0,
            change_type="TOLERANCE",
        )

        assert res.is_reworkable is True
        assert res.rework_cost_per_unit == 15.0
        assert res.net_savings == 0.0

    def test_negative_unit_cost_raises_error(self, optimizer: ReworkOptimizerEngine) -> None:
        """Negatif birim maliyet CostCalculationError fırlatmalıdır."""
        with pytest.raises(CostCalculationError):
            optimizer.evaluate_rework(
                part_number="GB-PINION-02",
                unit_cost=-50.0,
                stock_quantity=10,
                change_type="TOLERANCE",
            )

    def test_negative_stock_raises_error(self, optimizer: ReworkOptimizerEngine) -> None:
        """Negatif stok miktarı CostCalculationError fırlatmalıdır."""
        with pytest.raises(CostCalculationError):
            optimizer.evaluate_rework(
                part_number="GB-PINION-02",
                unit_cost=50.0,
                stock_quantity=-10,
                change_type="TOLERANCE",
            )


# ===========================================================================
# 3. Orkestratör ve FastMCP Entegrasyon Testleri
# ===========================================================================

class TestReworkIntegration:
    """Orkestratör ve FastMCP araçlarında rework analizi doğrulanması."""

    def test_orchestrator_populates_rework_analysis(self) -> None:
        """CadenceOrchestrator simülasyon çıktısında rework_analysis bulunmalıdır."""
        orchestrator = CadenceOrchestrator()
        ebom_df = pd.read_csv("data/sample_ebom.csv")
        inv_df = pd.read_csv("data/sample_inventory.csv")

        eco_text = "GB-PINION-02 ayna pinyon dişlisinde tolerans revizyonu yapıldı, rev B."
        summary = orchestrator.run_simulation(eco_text, ebom_df, inv_df)

        assert summary.rework_analysis is not None
        assert summary.rework_analysis.is_reworkable is True
        assert summary.rework_analysis.operation_type == "CNC_TURNING"
        assert summary.rework_analysis.net_savings == 6311.25

    def test_fastmcp_tool_simulation_includes_rework(self) -> None:
        """tool_run_impact_simulation çıktısında rework_analysis bulunmalıdır."""
        sim = tool_run_impact_simulation(
            eco_id="ECO-REW-01",
            part_number="GB-PINION-02",
            change_type="TOLERANCE",
        )

        assert "rework_analysis" in sim
        rework_data = sim["rework_analysis"]
        assert isinstance(rework_data, dict)
        assert rework_data.get("is_reworkable") is True
        assert rework_data.get("operation_type") == "CNC_TURNING"
        assert rework_data.get("net_savings") == 6311.25
