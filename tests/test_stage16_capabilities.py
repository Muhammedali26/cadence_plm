"""
tests/test_stage16_capabilities.py
==================================
Ürün Hakimiyet Kiti (Product Command Kit) ve Doğrulama Betiği Testleri.

Kurallar (.antigravityrules §1, §4):
- docs/CAPABILITIES_AND_BOUNDARIES.md dosyasının varlığı ve zorunlu başlıkları test edilir.
- docs/BUYER_PLAYBOOK.md dosyasının varlığı, ROI formülü ve müşteri itirazları test edilir.
- scripts/verify_capabilities.py betiğinin başarıyla çalıştığı ve 0 koduyla tamamlandığı test edilir.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestProductCommandKitDocs:
    """Dokümantasyon bütünlüğü ve kapsam testleri."""

    def test_capabilities_and_boundaries_doc_exists_and_complete(self) -> None:
        doc_path = PROJECT_ROOT / "docs" / "CAPABILITIES_AND_BOUNDARIES.md"
        assert doc_path.exists(), "CAPABILITIES_AND_BOUNDARIES.md bulunamadı."
        content = doc_path.read_text(encoding="utf-8")

        # Bölüm 1 Kontrolleri
        assert "BÖLÜM 1: ÇEKİRDEK YETENEKLER" in content
        assert "Serbest Metin ECO Ayrıştırma" in content
        assert "Where-Used" in content
        assert "rework_cost_per_unit" in content
        assert "USE_UP_STOCK" in content
        assert "IMMEDIATE_CUTOFF" in content
        assert "STEP AP214" in content
        assert "IATF 16949" in content

        # Bölüm 2 Kontrolleri
        assert "BÖLÜM 2: SİSTEM SINIRLARI" in content
        assert "Halüsinasyon" in content
        assert "Read-Only" in content or "Salt-Okunur" in content

        # Bölüm 3 Kontrolleri
        assert "BÖLÜM 3: VERİ GİRDİ FORMATLARI" in content
        assert "FastMCP" in content

    def test_buyer_playbook_doc_exists_and_complete(self) -> None:
        doc_path = PROJECT_ROOT / "docs" / "BUYER_PLAYBOOK.md"
        assert doc_path.exists(), "BUYER_PLAYBOOK.md bulunamadı."
        content = doc_path.read_text(encoding="utf-8")

        # Roller
        assert "VP of Engineering" in content
        assert "Fabrika Müdürü" in content
        assert "Satınalma" in content

        # ROI ve İtirazlar
        assert "60.000" in content
        assert "ROI" in content
        assert "Teamcenter" in content
        assert "Halüsinasyon" in content or "halüsinasyon" in content

        # 3 Altın Demo Senaryosu
        assert "DEMO SENARYOSU" in content or "Demo Planı" in content or "Vaka 1" in content
        assert "GB-PINION-02" in content
        assert "GB-SHAFT-01" in content


class TestVerifyCapabilitiesScript:
    """Doğrulama scripti çalıştırma testi."""

    def test_verify_capabilities_script_execution(self) -> None:
        script_path = PROJECT_ROOT / "scripts" / "verify_capabilities.py"
        assert script_path.exists(), "verify_capabilities.py bulunamadı."

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(PROJECT_ROOT),
        )

        assert result.returncode == 0, f"Script başarısız oldu:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        assert "TÜM YETENEK TESTLERİ BAŞARIYLA GEÇTİ" in result.stdout
        assert "Test 1" in result.stdout
        assert "Test 2" in result.stdout
        assert "Test 3" in result.stdout
        assert "Test 4" in result.stdout
        assert "Test 5" in result.stdout
