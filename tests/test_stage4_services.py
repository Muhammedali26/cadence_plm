import pytest
import pandas as pd
from src.services.eco_parser import ECOParser
from src.services.orchestrator import CadenceOrchestrator
from src.schemas.simulation import SimulationSummary

def test_eco_parser_extraction():
    parser = ECOParser()
    raw_text = "GB-PINION-02 dişli parçasının aşınma toleransı daraltıldı. Yeni revizyon C olarak güncellenecek."
    eco = parser.parse(raw_text)
    
    assert eco.affected_part_number == "GB-PINION-02"
    assert eco.target_revision == "C"

def test_full_orchestration_run():
    orchestrator = CadenceOrchestrator()
    ebom_df = pd.read_csv("data/sample_ebom.csv")
    inv_df = pd.read_csv("data/sample_inventory.csv")
    
    eco_text = "GB-PINION-02 parçasında tolerans revizyonu yapıldı, yeni revizyon B."
    summary = orchestrator.run_simulation(eco_text, ebom_df, inv_df)
    
    assert isinstance(summary, SimulationSummary)
    assert summary.total_affected_parts > 0
    assert summary.total_scrap_cost > 0.0
    assert summary.max_transition_lead_time_days > 0