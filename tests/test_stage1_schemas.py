import pytest
from pydantic import ValidationError
from src.schemas.bom import BOMItem
from src.schemas.inventory import InventoryItem
from src.schemas.eco import ECORequest, ECOChangeType
from src.schemas.simulation import PartImpactDetail, SimulationSummary

def test_bom_item_valid_and_invalid():
    # Geçerli model
    item = BOMItem(
        part_number="GB-SHAFT-01",
        part_name="Drive Shaft",
        revision="A",
        parent_part_number=None,
        quantity=1.0,
        unit_cost=150.50,
        supplier_id="SUP-BOSCH-01",
        tooling_id="TOOL-99"
    )
    assert item.part_number == "GB-SHAFT-01"

    # Tip uyumsuzluğu testi (unit_cost sayı olmalı)
    with pytest.raises(ValidationError):
        BOMItem(
            part_number="FAIL",
            part_name="Fail",
            revision="A",
            quantity="sayi_degil",  # Hatalı tip
            unit_cost="ucretsiz",   # Hatalı tip
            supplier_id="SUP-01"
        )

def test_eco_enum_validation():
    # Geçersiz Enum değeri patlamalı
    with pytest.raises(ValidationError):
        ECORequest(
            eco_id="ECO-001",
            raw_text="Test",
            affected_part_number="P1",
            target_revision="B",
            change_type="RANDOMLY_TYPED", # Tanımsız enum
            description="Desc"
        )

def test_simulation_summary_structure():
    detail = PartImpactDetail(
        part_number="P1",
        part_name="Part 1",
        affected_stock=100,
        unit_cost=10.0,
        scrap_cost=1000.0,
        tooling_affected=True,
        supplier_id="S1",
        lead_time_days=15
    )
    summary = SimulationSummary(
        eco_id="ECO-001",
        root_part_number="P1",
        total_affected_parts=1,
        total_scrap_cost=1000.0,
        total_impacted_toolings=1,
        max_transition_lead_time_days=15,
        details=[detail]
    )
    assert summary.total_scrap_cost == 1000.0
    assert len(summary.details) == 1