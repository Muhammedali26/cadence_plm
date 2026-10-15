"""
tests/test_stage16_chaos.py
===========================
Aşama 16: SAP S/4HANA OData HTTP Konnektörü, Kirli Veri Zırhı ve Kaos Testleri.

7 Acımasız Endüstriyel Senaryo (Chaos Engineering):
1. Gerçek SAP OData HTTP İletişimi (httpx.AsyncClient + TestClient)
2. SAP Yetkisiz Erişim (HTTP 401) ve 503 Gateway Retry Zırhı
3. Yetim Parça (Orphan Part / ERP Uyumsuzluğu - KeyError Önleme)
4. Döngüsel BOM Tuzağı (CircularDependencyError Milisaniyede Yakalama)
5. Kirli ERP Verisi & Zero Division Önleme
6. Büyük Ölçek Performans Stres Testi (2.000 Parça, 6 Seviye < 2.0s)
7. LLM Halüsinasyon & Hayalet Parça Savunması (PartNotFoundError)
"""

from __future__ import annotations

import pytest

from scripts.run_chaos_tests import (
    run_chaos_1_sap_http_communication,
    run_chaos_2_sap_unauthorized_and_fault,
    run_chaos_3_orphan_part_resilience,
    run_chaos_4_circular_bom_trap,
    run_chaos_5_dirty_erp_and_zero_division,
    run_chaos_6_large_scale_performance,
    run_chaos_7_llm_hallucination_defense,
)


class TestStage16ChaosEngineering:
    """Aşama 16 Kaos Mühendisliği ve Stres Test Paketi (Pytest Entegrasyonu)."""

    def test_kaos_1_real_sap_odata_http_communication(self) -> None:
        """Kaos 1: httpx.AsyncClient üzerinden SAP OData endpoint'i ve InventoryItem dönüşümü."""
        passed, elapsed_ms, detail = run_chaos_1_sap_http_communication()
        assert passed is True
        assert elapsed_ms < 1000.0
        assert "GB-PINION-02" in detail

    def test_kaos_2_sap_unauthorized_and_503_retry(self) -> None:
        """Kaos 2: Hatalı API Key (401) ve 503 Retry zırhı."""
        passed, elapsed_ms, detail = run_chaos_2_sap_unauthorized_and_fault()
        assert passed is True
        assert "401" in detail and "503" in detail

    def test_kaos_3_orphan_part_resilience(self) -> None:
        """Kaos 3: Yetim Parça - CAD BOM'da var, SAP'de yok -> KeyError engellenmeli, missing_in_erp=True."""
        passed, elapsed_ms, detail = run_chaos_3_orphan_part_resilience()
        assert passed is True
        assert "missing_in_erp=True" in detail

    def test_kaos_4_circular_bom_trap(self) -> None:
        """Kaos 4: Döngüsel BOM Tuzağı -> Sonsuz döngüye girmeden milisaniyeler içinde CircularDependencyError."""
        passed, elapsed_ms, detail = run_chaos_4_circular_bom_trap()
        assert passed is True
        assert elapsed_ms < 50.0  # Milisaniyeler içinde yakalanmalı
        assert "CircularDependencyError" in detail

    def test_kaos_5_dirty_erp_data_and_zero_division(self) -> None:
        """Kaos 5: Kirli ERP Verisi (Negatif Stok, None Maliyet, 0 Günlük Tüketim)."""
        passed, elapsed_ms, detail = run_chaos_5_dirty_erp_and_zero_division()
        assert passed is True
        assert "ZeroDivision" in detail

    def test_kaos_6_large_scale_performance_stress_test(self) -> None:
        """Kaos 6: 2.000 Parçalık, 6 Seviye Derinlikte Devasa BOM Ağacı (< 2.0s)."""
        passed, elapsed_ms, detail = run_chaos_6_large_scale_performance()
        assert passed is True
        assert elapsed_ms < 2000.0  # 2 saniyenin altında bitmeli

    def test_kaos_7_llm_hallucination_ghost_part_defense(self) -> None:
        """Kaos 7: Sistemde olmayan GHOST-PART-404 için PartNotFoundError üretilmesi ve sıfır hurda teyidi."""
        passed, elapsed_ms, detail = run_chaos_7_llm_hallucination_defense()
        assert passed is True
        assert "PartNotFoundError" in detail
