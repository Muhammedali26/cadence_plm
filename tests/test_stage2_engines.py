import pytest
import pandas as pd
from src.engines.bom_tree import BOMTreeEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.schemas.inventory import InventoryItem
from src.core.exceptions import BOMStructureError

def test_circular_dependency_detection():
    # Döngüsel ilişki: P1 -> P2 -> P1
    cyclic_data = pd.DataFrame([
        {"part_number": "P1", "part_name": "Part 1", "revision": "A", "parent_part_number": "P2", "quantity": 1, "unit_cost": 10, "supplier_id": "S1", "tooling_id": None},
        {"part_number": "P2", "part_name": "Part 2", "revision": "A", "parent_part_number": "P1", "quantity": 1, "unit_cost": 20, "supplier_id": "S1", "tooling_id": None}
    ])
    engine = BOMTreeEngine()
    
    with pytest.raises(BOMStructureError):
        engine.load_from_dataframe(cyclic_data)
        engine.get_affected_subassemblies("P1")

def test_impact_calculation_accuracy():
    # Hiyerarşik parça listesi
    tree_data = pd.DataFrame([
        {"part_number": "P_ROOT", "part_name": "Root Assembly", "revision": "A", "parent_part_number": None, "quantity": 1, "unit_cost": 500, "supplier_id": "S1", "tooling_id": "T1"},
        {"part_number": "P_CHILD", "part_name": "Child Component", "revision": "A", "parent_part_number": "P_ROOT", "quantity": 2, "unit_cost": 12.333, "supplier_id": "S2", "tooling_id": "T2"}
    ])
    tree_engine = BOMTreeEngine()
    tree_engine.load_from_dataframe(tree_data)
    affected = tree_engine.get_affected_subassemblies("P_CHILD")

    # Envanter haritası
    inventory = {
        "P_CHILD": InventoryItem(part_number="P_CHILD", stock_quantity=100, lead_time_days=20, location="WAREHOUSE-A")
    }

    calc_engine = ImpactCalculatorEngine()
    summary = calc_engine.calculate(
        eco_id="ECO-TEST",
        root_part_number="P_CHILD",
        affected_parts=affected,
        inventory_map=inventory
    )

    # Motor 12.333 birim maliyetini kural gereği 12.33'e kilitledi: 100 * 12.33 = 1233.00
    assert summary.total_scrap_cost == 1233.0
    assert summary.total_impacted_toolings == 1
    assert summary.max_transition_lead_time_days == 20