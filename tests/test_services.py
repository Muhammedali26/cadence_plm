"""
tests/test_services.py
======================
ECOParser ve CadenceOrchestrator servis katmanı birim testleri.

Kural (.antigravityrules §1 & §4):
- Servis katmanı deterministik ayrıştırma ve motor orkestrasyonunu doğrular.
- Tüm hata sınırları (ECOParsingError, PartNotFoundError vb.) test edilir.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src.core.exceptions import ECOParsingError, PartNotFoundError
from src.schemas.eco import ECOChangeType, ECORequest
from src.schemas.simulation import SimulationSummary
from src.services.eco_parser import ECOParser
from src.services.orchestrator import CadenceOrchestrator


# ===========================================================================
# 1. ECOParser Testleri
# ===========================================================================

class TestECOParser:
    """ECOParser sınıfı için ayrıştırma doğrulamaları."""

    @pytest.fixture()
    def parser(self) -> ECOParser:
        # Offline / deterministik regex testleri için API key'siz başlatılır
        return ECOParser(api_key=None)

    def test_user_example_shaft_tolerance(self, parser: ECOParser) -> None:
        """Kullanıcı istek örneği: 'GB-SHAFT-01 milinin toleransını revize ediyoruz, yeni rev B olacak'."""
        text = "GB-SHAFT-01 milinin toleransını revize ediyoruz, yeni rev B olacak"
        eco = parser.parse(text)

        assert isinstance(eco, ECORequest)
        assert eco.affected_part_number == "GB-SHAFT-01"
        assert eco.target_revision == "B"
        assert eco.change_type == ECOChangeType.TOLERANCE
        assert eco.raw_text == text

    def test_material_change_extraction(self, parser: ECOParser) -> None:
        """Malzeme değişikliği anahtar kelime tespiti."""
        text = "GBX-1210 parçası için titanyum alaşım malzeme revizyonu yapıldı, hedef revizyon C."
        eco = parser.parse(text)

        assert eco.affected_part_number == "GBX-1210"
        assert eco.target_revision == "C"
        assert eco.change_type == ECOChangeType.MATERIAL

    def test_geometry_change_extraction(self, parser: ECOParser) -> None:
        """Geometri değişikliği anahtar kelime tespiti."""
        text = "GBX-1110 parçası gövde geometrisi yeniden tasarlandı. Yeni revizyon Rev-02."
        eco = parser.parse(text)

        assert eco.affected_part_number == "GBX-1110"
        assert eco.target_revision == "Rev-02"
        assert eco.change_type == ECOChangeType.GEOMETRY

    def test_obsolete_change_extraction(self, parser: ECOParser) -> None:
        """Kullanım dışı / obsolete tespiti."""
        text = "P-101 parçası obsolete edildi ve kullanımdan kaldırıldı, revizyon D."
        eco = parser.parse(text)

        assert eco.affected_part_number == "P-101"
        assert eco.target_revision == "D"
        assert eco.change_type == ECOChangeType.OBSOLETE

    def test_explicit_eco_id_in_text(self, parser: ECOParser) -> None:
        """Metin içinde açıkça ECO-2024-0099 belirtildiğinde ID korunmalı."""
        text = "ECO-2024-0099: GBX-1210 parçasında tolerans değişikliği, yeni rev B."
        eco = parser.parse(text)

        assert eco.eco_id == "ECO-2024-0099"
        assert eco.affected_part_number == "GBX-1210"

    def test_explicit_eco_id_parameter_override(self, parser: ECOParser) -> None:
        """Parametre olarak eco_id verildiğinde o değer kullanılmalı."""
        text = "GBX-1210 milinin toleransını revize ediyoruz, yeni rev B olacak"
        eco = parser.parse(text, eco_id="ECO-CUSTOM-77")

        assert eco.eco_id == "ECO-CUSTOM-77"

    def test_empty_text_raises_eco_parsing_error(self, parser: ECOParser) -> None:
        """Boş metin ECOParsingError fırlatmalı."""
        with pytest.raises(ECOParsingError, match="boş olamaz"):
            parser.parse("   ")

    def test_missing_part_number_raises_eco_parsing_error(self, parser: ECOParser) -> None:
        """Parça numarası içermeyen anlamsız metin hata fırlatmalı."""
        with pytest.raises(ECOParsingError, match="parça numarası tespit edilemedi"):
            parser.parse("Hava bugün çok güzel, kahve içelim.")

    def test_missing_revision_raises_eco_parsing_error(self, parser: ECOParser) -> None:
        """Revizyon içermeyen metin hata fırlatmalı."""
        with pytest.raises(ECOParsingError, match="hedef revizyon tespit edilemedi"):
            parser.parse("GBX-1210 parçası üzerinde bir şeyler değiştirildi.")


# ===========================================================================
# 2. CadenceOrchestrator Testleri
# ===========================================================================

class TestCadenceOrchestrator:
    """CadenceOrchestrator uçtan uca simülasyon testleri."""

    @pytest.fixture()
    def orchestrator(self) -> CadenceOrchestrator:
        return CadenceOrchestrator()

    @pytest.fixture()
    def sample_dfs(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        ebom_df = pd.read_csv("data/sample_ebom.csv")
        inv_df = pd.read_csv("data/sample_inventory.csv")
        return ebom_df, inv_df

    def test_orchestrator_gearbox_shaft_full_simulation(
        self,
        orchestrator: CadenceOrchestrator,
        sample_dfs: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """
        Dişli mili GBX-1210 serbest metin ECO'su ile tam orkestrasyon:
        - 5 etkilenen parça
        - 32,650.00 USD hurda maliyeti
        - 3 adet etkilenen kalıp
        - 28 gün lead time
        """
        ebom_df, inv_df = sample_dfs
        text = "GBX-1210 ana dişli milinin toleransını revize ediyoruz, yeni rev C olacak."

        summary = orchestrator.run_simulation(
            raw_eco_text=text,
            ebom_df=ebom_df,
            inventory_df=inv_df,
            eco_id="ECO-TEST-SIM",
        )

        assert isinstance(summary, SimulationSummary)
        assert summary.eco_id == "ECO-TEST-SIM"
        assert summary.root_part_number == "GBX-1210"
        assert summary.total_affected_parts == 5
        assert summary.total_scrap_cost == 32650.00
        assert summary.total_impacted_toolings == 3
        assert summary.max_transition_lead_time_days == 28

    def test_orchestrator_pinion_simulation(
        self,
        orchestrator: CadenceOrchestrator,
        sample_dfs: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """GB-PINION-02 için orkestrasyon simülasyonu."""
        ebom_df, inv_df = sample_dfs
        text = "GB-PINION-02 pinyon dişlisinde tolerans revizyonu yapıldı, hedef revizyon B."

        summary = orchestrator.run_simulation(
            raw_eco_text=text,
            ebom_df=ebom_df,
            inventory_df=inv_df,
        )

        assert summary.root_part_number == "GB-PINION-02"
        assert summary.total_affected_parts == 1
        assert summary.total_scrap_cost == 55 * 135.00  # 7425.00
        assert summary.max_transition_lead_time_days == 30

    def test_orchestrator_unrecognized_part_raises_part_not_found(
        self,
        orchestrator: CadenceOrchestrator,
        sample_dfs: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """BOM'da olmayan bir parça numarası PartNotFoundError fırlatmalı."""
        ebom_df, inv_df = sample_dfs
        text = "P-NONEXISTENT-99 parçasında tolerans revizyonu yapıldı, yeni rev B."

        with pytest.raises(PartNotFoundError) as exc_info:
            orchestrator.run_simulation(text, ebom_df, inv_df)
        assert exc_info.value.part_id == "P-NONEXISTENT-99"

    def test_orchestrator_invalid_eco_text_raises_parsing_error(
        self,
        orchestrator: CadenceOrchestrator,
        sample_dfs: tuple[pd.DataFrame, pd.DataFrame],
    ) -> None:
        """Geçersiz ECO açıklaması ECOParsingError fırlatmalı."""
        ebom_df, inv_df = sample_dfs
        with pytest.raises(ECOParsingError):
            orchestrator.run_simulation("Geçersiz metin", ebom_df, inv_df)
