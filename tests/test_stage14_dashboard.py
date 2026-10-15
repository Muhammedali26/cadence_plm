"""
tests/test_stage14_dashboard.py
===============================
Aşama 14: İnteraktif Yönetici Kokpiti (Streamlit Dashboard) testleri.

Kurallar (.antigravityrules §1, §3, §5):
- Streamlit ve Plotly kütüphanelerinin varlığı doğrulanır.
- ui/app.py dosyasının varlığı, içe aktarılabilirliği ve senaryo tanımları test edilir.
- ECODossierGenerator ve CadenceOrchestrator entegrasyonu test edilir.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from src.engines.bom_tree import BOMTreeEngine
from src.schemas.rework import ReworkFeasibility
from src.schemas.simulation import SimulationSummary, WhereUsedDetail
from src.services.dossier_generator import ECODossierGenerator
from src.services.orchestrator import CadenceOrchestrator


class TestStage14DashboardEnvironment:
    """Streamlit ve Plotly bağımlılık testleri."""

    def test_streamlit_and_plotly_installed(self) -> None:
        """Streamlit ve Plotly kütüphaneleri başarıyla yüklü olmalıdır."""
        import plotly.graph_objects as go
        import streamlit as st

        assert hasattr(st, "metric")
        assert hasattr(st, "download_button")
        assert hasattr(go, "Figure")

    def test_ui_app_file_exists(self) -> None:
        """ui/app.py dosyası var olmalı ve senaryoları içermelidir."""
        app_path = Path(__file__).resolve().parent.parent / "ui" / "app.py"
        assert app_path.exists(), "ui/app.py dosyası bulunamadı."

        content = app_path.read_text(encoding="utf-8")
        assert "CadencePLM - Otonom Mühendislik Değişiklik Yönetimi (ECO) Kokpiti" in content
        assert "Senaryo 1: GB-PINION-02 Tolerans Daralması (Kurtarılabilir)" in content
        assert "Senaryo 2: GB-SHAFT-01 Mil Malzeme Alaşımı Değişimi (Hurda Kaçınılmaz)" in content
        assert "ECODossierGenerator" in content
        assert "st.metric" in content
        assert "st.download_button" in content
        assert "st.plotly_chart" in content


class TestDashboardSimulationIntegration:
    """Dashboard'ın kullandığı simülasyon ve dosya üretici entegrasyon testleri."""

    @pytest.fixture()
    def sample_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        ebom_path = Path("data/sample_ebom.csv")
        inv_path = Path("data/sample_inventory.csv")
        return pd.read_csv(ebom_path), pd.read_csv(inv_path)

    def test_scenario_1_simulation_run(self, sample_data: tuple[pd.DataFrame, pd.DataFrame]) -> None:
        """Senaryo 1 (GB-PINION-02) orkestrasyonu başarıyla sonuçlanmalıdır."""
        ebom_df, inv_df = sample_data
        orchestrator = CadenceOrchestrator()
        text = "GB-PINION-02 pinyon dişlisinde tolerans daralması yapıldı, yeni rev B."
        summary = orchestrator.run_simulation(raw_eco_text=text, ebom_df=ebom_df, inventory_df=inv_df)

        assert summary.root_part_number == "GB-PINION-02"
        assert summary.total_scrap_cost > 0.0
        assert summary.rework_analysis is not None
        assert summary.rework_analysis.is_reworkable is True
        assert summary.rework_analysis.net_savings > 0.0

    def test_scenario_2_simulation_run(self, sample_data: tuple[pd.DataFrame, pd.DataFrame]) -> None:
        """Senaryo 2 (GB-SHAFT-01 / GBX-1210) malzeme değişimi hurda kaçınılmaz olmalıdır."""
        ebom_df, inv_df = sample_data
        orchestrator = CadenceOrchestrator()
        text = "GB-SHAFT-01 mil malzeme alaşımı değişimi yapıldı (42CrMo4 çeliği), hedef revizyon C."
        summary = orchestrator.run_simulation(raw_eco_text=text, ebom_df=ebom_df, inventory_df=inv_df)

        assert summary.root_part_number == "GBX-1210"
        assert summary.total_scrap_cost > 0.0
        assert summary.rework_analysis is not None
        assert summary.rework_analysis.is_reworkable is False
        assert summary.rework_analysis.net_savings == 0.0

    def test_dossier_generation_for_dashboard_download(self, sample_data: tuple[pd.DataFrame, pd.DataFrame]) -> None:
        """Dashboard'da indirme butonuna sunulan HTML dossier üretimi."""
        ebom_df, inv_df = sample_data
        orchestrator = CadenceOrchestrator()
        text = "GB-PINION-02 tolerans revizyonu yapıldı, hedef revizyon B."
        summary = orchestrator.run_simulation(raw_eco_text=text, ebom_df=ebom_df, inventory_df=inv_df)

        generator = ECODossierGenerator()
        html = generator.generate_html(
            summary=summary,
            rework=summary.rework_analysis,
            where_used=summary.where_used_parents,
            eco_description=text,
        )

        assert "<!DOCTYPE html>" in html
        assert "IATF 16949" in html
        assert "GB-PINION-02" in html
        assert "</html>" in html.lower()
