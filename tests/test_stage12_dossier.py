"""
tests/test_stage12_dossier.py
=============================
Aşama 12: Resmi Endüstriyel Değişiklik Raporu (ECO Dossier) Birim Testleri.

Test Senaryoları:
1. ECODossierGenerator HTML içeriği üretimi (Başlık, Yönetici Özeti, Where-Used, Kalıp Matrisi, İmza Alanları).
2. Dosyaya kaydetme (reports/ dizinine HTML dosyası yazılması).
3. Rework kurtarma tasarrufunun ve hurda maliyetinin HTML içine doğru yansıması.
4. Rework edilemeyen parçalarda alternatif hurda metinlerinin doğru üretilmesi.
5. Where-Used hiyerarşisinin görsel ağaç bileşenleri olarak render edilmesi.
6. Özel dosya yolu desteği ve dizin otomatik oluşturma.
"""

from __future__ import annotations

from pathlib import Path
import pytest

from src.schemas.rework import ReworkFeasibility, ReworkOperationType
from src.schemas.simulation import (
    EffectivityStrategy,
    PartImpactDetail,
    SimulationSummary,
    WhereUsedDetail,
)
from src.services.dossier_generator import ECODossierGenerator


@pytest.fixture()
def sample_simulation_summary() -> SimulationSummary:
    """Testler için örnek simülasyon özeti."""
    return SimulationSummary(
        eco_id="ECO-2026-TEST01",
        root_part_number="GB-PINION-02",
        total_affected_parts=3,
        total_scrap_cost=25600.0,
        total_impacted_toolings=1,
        max_transition_lead_time_days=21,
        recommended_strategy=EffectivityStrategy.USE_UP_STOCK,
        run_out_days=14,
        details=[
            PartImpactDetail(
                part_number="GB-PINION-02",
                part_name="Ayna Pinyon Dişlisi",
                affected_stock=180,
                unit_cost=135.0,
                scrap_cost=24300.0,
                tooling_affected=True,
                supplier_id="SUP-BOSCH-01",
                lead_time_days=21,
            ),
            PartImpactDetail(
                part_number="GBX-1300",
                part_name="Diferansiyel Çıkış Grubu",
                affected_stock=5,
                unit_cost=260.0,
                scrap_cost=1300.0,
                tooling_affected=False,
                supplier_id="CAD-INTERNAL",
                lead_time_days=14,
            ),
        ],
        where_used_parents=[
            WhereUsedDetail(
                parent_part_number="GBX-1300",
                parent_part_name="Diferansiyel Çıkış Grubu",
                assembly_level=1,
            ),
            WhereUsedDetail(
                parent_part_number="GBX-1000",
                parent_part_name="Şanzıman Ana Montajı",
                assembly_level=2,
            ),
        ],
        rework_analysis=ReworkFeasibility(
            is_reworkable=True,
            operation_type=ReworkOperationType.CNC_TURNING,
            rework_cost_per_unit=20.25,
            net_savings=20655.0,
        ),
    )


class TestECODossierGenerator:
    """ECODossierGenerator servis testleri."""

    def test_generate_html_contains_required_sections(
        self,
        sample_simulation_summary: SimulationSummary,
    ) -> None:
        """HTML çıktısının zorunlu tüm endüstriyel bölümleri içerdiğini doğrular."""
        generator = ECODossierGenerator()
        html_out = generator.generate_html(sample_simulation_summary)

        # 1. Başlık ve PPAP Standardı
        assert "IATF 16949 / PPAP ENGINEERING CHANGE NOTIFICATION (ECN) IMPACT DOSSIER" in html_out
        assert "ECO-2026-TEST01" in html_out

        # 2. Yönetici Özeti ve Finansal Değerler
        assert "Yönetici Özeti" in html_out
        assert "$25,600.00" in html_out  # Hurda maliyeti
        assert "$20,655.00" in html_out  # Rework tasarrufu

        # 3. Where-Used Montaj Etki Şeması
        assert "Where-Used Montaj Etki Şeması" in html_out
        assert "GBX-1300" in html_out
        assert "GBX-1000" in html_out
        assert "Diferansiyel Çıkış Grubu" in html_out

        # 4. Tedarikçi & Kalıp Risk Matrisi
        assert "Tedarikçi &amp; Kalıp Risk Matrisi" in html_out or "Tedarikçi & Kalıp Risk Matrisi" in html_out
        assert "SUP-BOSCH-01" in html_out
        assert "KALIP ETKİLENDİ" in html_out

        # 5. İmza ve Onay Bölümü
        assert "İmza &amp; Onay Bölümü" in html_out or "İmza & Onay Bölümü" in html_out
        assert "Ar-Ge &amp; Ürün Geliştirme Direktörü" in html_out or "Ar-Ge" in html_out
        assert "Satınalma &amp; Tedarik Zinciri Müdürü" in html_out or "Satınalma" in html_out
        assert "Kalite Güvence &amp; PPAP Müdürü" in html_out or "Kalite" in html_out

    def test_generate_dossier_creates_file_on_disk(
        self,
        sample_simulation_summary: SimulationSummary,
        tmp_path: Path,
    ) -> None:
        """generate_dossier metodunun dosyayı diske yazdığını doğrular."""
        generator = ECODossierGenerator(reports_dir=tmp_path)
        report_file = generator.generate_dossier(sample_simulation_summary)

        assert report_file.exists()
        assert report_file.is_file()
        assert "ECO-2026-TEST01" in report_file.name

        content = report_file.read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "CadencePLM" in content

    def test_non_reworkable_summary_rendering(self) -> None:
        """Rework imkanı olmayan parçalarda uygun uyarı metninin render edilmesi."""
        summary = SimulationSummary(
            eco_id="ECO-MAT-01",
            root_part_number="GBX-CASTING",
            total_affected_parts=1,
            total_scrap_cost=5000.0,
            total_impacted_toolings=0,
            max_transition_lead_time_days=30,
            details=[],
            rework_analysis=ReworkFeasibility(
                is_reworkable=False,
                operation_type=ReworkOperationType.NONE,
                rework_cost_per_unit=0.0,
                net_savings=0.0,
            ),
        )

        generator = ECODossierGenerator()
        html_out = generator.generate_html(summary)

        assert "Hurda Kaçılmaz" in html_out or "Hurda Kaçınılmaz" in html_out
        assert "$0.00 KURTARMA" in html_out

    def test_custom_output_path(
        self,
        sample_simulation_summary: SimulationSummary,
        tmp_path: Path,
    ) -> None:
        """Özel bir dosya yolu verildiğinde oraya yazılması."""
        custom_file = tmp_path / "custom_folder" / "my_report.html"
        generator = ECODossierGenerator()
        returned_file = generator.generate_dossier(
            sample_simulation_summary,
            output_path=custom_file,
        )

        assert returned_file == custom_file.resolve()
        assert custom_file.exists()
        assert custom_file.stat().st_size > 500
