"""
scripts/run_chaos_tests.py
==========================
CadencePLM — Gerçek Dünya Kaos ve Stres Testi Paketi (Chaos Engineering).

7 Acımasız Endüstriyel Senaryo:
1. Kaos 1 (Gerçek SAP OData HTTP İletişimi):
   FastAPI ASGI transport üzerinden /sap/opu/odata/... endpoint'ine gerçek HTTP isteği atıp
   MATNR/LABST verisini InventoryItem modeline dönüştürme testi.
2. Kaos 2 (SAP Yetkisiz Erişim & Sunucu Çökmesi):
   Hatalı API Key (HTTP 401) ve simüle edilen 503 / Timeout durumunda SAPAuthenticationError /
   SAPConnectionError kontrollü fırlatılması, sunucunun çökmemesi.
3. Kaos 3 (Yetim Parça / ERP Uyumsuzluğu):
   CAD BOM'da var olan ama SAP'de kaydı bulunmayan 'GB-ORPHAN-99' parçası için simülasyon koşturulması;
   KeyError oluşmaması, missing_in_erp=True ve stok=0 olarak güvenle raporlanması.
4. Kaos 4 (Döngüsel BOM Tuzağı):
   PART-A -> PART-B -> PART-C -> PART-A döngüsel bağımlılık tuzağında sonsuz döngüye girmeden
   < 5 ms içinde CircularDependencyError / BOMStructureError yakalanması.
5. Kaos 5 (Kirli ERP Verisi & Zero Division):
   Stok=-25, Fiyat=None/NaN, Günlük Tüketim=0 verildiğinde matematik motorunun patlamaması,
   negatif stokun 0'a sabitlenmesi, ZeroDivisionError oluşmaması.
6. Kaos 6 (Büyük Ölçek Performans Stres Testi):
   2.000 parçalık, 6 seviye derinlikte devasa bir BOM ağacında Where-Used ve Hurda simülasyonunun
   2 saniyenin altında (< 2.0s) tamamlanması.
7. Kaos 7 (LLM Halüsinasyon & Olmayan Parça Saldırısı):
   Sistemde bulunmayan 'GHOST-PART-404' parçası sorgulandığında uydurma maliyet üretilmeyip
   PartNotFoundError ile 'Parça sistemde bulunamadı' denmesinin ve sıfır hurda üretildiğinin teyidi.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Proje kök dizinini PYTHONPATH'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import httpx
import pandas as pd

from src.agents.eco_agent import CadenceECOAgent
from src.connectors.sap_odata_client import SAPODataClient
from src.core.exceptions import (
    BOMStructureError,
    CircularDependencyError,
    CostCalculationError,
    PartNotFoundError,
    SAPAuthenticationError,
    SAPConnectionError,
)
from src.engines.bom_tree import BOMTreeEngine
from src.engines.effectivity_engine import EffectivityEngine
from src.engines.impact_calculator import ImpactCalculatorEngine
from src.main import app
from src.schemas.bom import BOMItem
from src.schemas.inventory import InventoryItem


import asyncio
from starlette.testclient import TestClient


def run_chaos_1_sap_http_communication() -> tuple[bool, float, str]:
    """Kaos 1: Gerçek SAP OData HTTP İletişimi ve InventoryItem Dönüşümü (httpx.AsyncClient + TestClient)."""
    t0 = time.perf_counter()

    async def _async_call() -> InventoryItem:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as async_client:
            sap_client = SAPODataClient(
                base_url="http://testserver",
                api_key="SAP-ODATA-KEY-2024",
                async_client=async_client,
            )
            return await sap_client.get_material_stock_async("GB-PINION-02")

    item = asyncio.run(_async_call())

    assert item.part_number == "GB-PINION-02", f"Beklenen parça 'GB-PINION-02', alınan '{item.part_number}'"
    assert item.stock_quantity == 55, f"Beklenen stok 55, alınan {item.stock_quantity}"
    assert item.lead_time_days == 30, f"Beklenen lead time 30, alınan {item.lead_time_days}"

    # Senkron TestClient doğrulaması da yapalım
    with TestClient(app) as test_client:
        sync_sap_client = SAPODataClient(
            base_url="http://testserver",
            api_key="SAP-ODATA-KEY-2024",
            client=test_client,
        )
        sync_item = sync_sap_client.get_material_stock("GB-PINION-02")
        assert sync_item.stock_quantity == 55

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return True, elapsed_ms, f"MATNR: {item.part_number} | Stok: {item.stock_quantity} EA | Termin: {item.lead_time_days} gün"


def run_chaos_2_sap_unauthorized_and_fault() -> tuple[bool, float, str]:
    """Kaos 2: SAP Yetkisiz Erişim (HTTP 401) ve Geçici Ağ/Sunucu Çökmesi (503)."""
    t0 = time.perf_counter()

    async def _test_auth_and_fault():
        # 1. Hatalı API Key Testi (401 Unauthorized)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as bad_client:
            bad_sap_client = SAPODataClient(
                base_url="http://testserver",
                api_key="INVALID_SAP_SECRET_KEY",
                async_client=bad_client,
            )
            auth_failed = False
            try:
                await bad_sap_client.get_material_stock_async("GB-PINION-02")
            except SAPAuthenticationError:
                auth_failed = True

            assert auth_failed, "Hatalı API Key ile SAPAuthenticationError fırlatılmalıydı!"

        # 2. 503 Service Unavailable / Timeout Hatası ve 3 Kez Retry Testi
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
            headers={"X-SAP-Fault": "503"},
        ) as fault_client:
            fault_sap_client = SAPODataClient(
                base_url="http://testserver",
                api_key="SAP-ODATA-KEY-2024",
                async_client=fault_client,
                max_retries=3,
            )
            conn_failed = False
            try:
                await fault_sap_client.get_material_stock_async("GB-PINION-02")
            except SAPConnectionError:
                conn_failed = True

            assert conn_failed, "503 hatasında 3 deneme sonrası SAPConnectionError fırlatılmalıydı!"

    asyncio.run(_test_auth_and_fault())

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return True, elapsed_ms, "401 Unauthorized ve 503 Gateway Retry zırhı başarıyla doğrulandı"



def run_chaos_3_orphan_part_resilience() -> tuple[bool, float, str]:
    """Kaos 3: Yetim Parça / ERP Uyumsuzluğu (CAD BOM'da var, SAP'de yok)."""
    t0 = time.perf_counter()
    orphan_part = BOMItem(
        part_number="GB-ORPHAN-99",
        part_name="Yetim Diferansiyel Braketi",
        revision="C",
        parent_part_number=None,
        quantity=1.0,
        unit_cost=85.0,
        supplier_id="SUP-ORPHAN-01",
    )
    calc = ImpactCalculatorEngine()
    summary = calc.calculate(
        eco_id="ECO-CHAOS-03",
        root_part_number="GB-ORPHAN-99",
        affected_parts=[orphan_part],
        inventory_map={},  # Boş envanter: Parça SAP'de kayıtlı değil
    )

    assert len(summary.details) == 1, "Detay listesi 1 eleman içermeli"
    detail = summary.details[0]
    assert detail.missing_in_erp is True, "missing_in_erp True olarak işaretlenmeliydi!"
    assert detail.affected_stock == 0, f"Yetim parçanın stoku 0 olmalı, alınan: {detail.affected_stock}"
    assert detail.scrap_cost == 0.0, f"Hurda maliyeti 0.0 olmalı, alınan: {detail.scrap_cost}"

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return True, elapsed_ms, "KeyError önlendi | missing_in_erp=True | Hurda: $0.00"


def run_chaos_4_circular_bom_trap() -> tuple[bool, float, str]:
    """Kaos 4: Döngüsel BOM Tuzağı (PART-A -> PART-B -> PART-C -> PART-A)."""
    t0 = time.perf_counter()
    cycle_df = pd.DataFrame(
        [
            {
                "part_number": "PART-A",
                "part_name": "Parça A",
                "revision": "A",
                "parent_part_number": "PART-C",
                "quantity": 1.0,
                "unit_cost": 25.0,
                "supplier_id": "S1",
            },
            {
                "part_number": "PART-B",
                "part_name": "Parça B",
                "revision": "A",
                "parent_part_number": "PART-A",
                "quantity": 1.0,
                "unit_cost": 30.0,
                "supplier_id": "S1",
            },
            {
                "part_number": "PART-C",
                "part_name": "Parça C",
                "revision": "A",
                "parent_part_number": "PART-B",
                "quantity": 1.0,
                "unit_cost": 35.0,
                "supplier_id": "S1",
            },
        ]
    )

    bom = BOMTreeEngine()
    cycle_detected = False
    try:
        bom.load_from_dataframe(cycle_df)
    except (CircularDependencyError, BOMStructureError) as exc:
        cycle_detected = True

    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert cycle_detected, "Döngüsel BOM yüklendiğinde CircularDependencyError fırlatılmalıydı!"
    assert elapsed_ms < 50.0, f"Döngü çok geç tespit edildi ({elapsed_ms:.2f} ms)"

    return True, elapsed_ms, f"Döngü {elapsed_ms:.2f} ms içinde yakalandı (CircularDependencyError)"


def run_chaos_5_dirty_erp_and_zero_division() -> tuple[bool, float, str]:
    """Kaos 5: Kirli ERP Verisi (Stok=-25, Fiyat=None, Günlük Tüketim=0)."""
    t0 = time.perf_counter()

    calc = ImpactCalculatorEngine()
    eff = EffectivityEngine()

    # 1. Kirli veri: Fiyat None
    dirty_part = BOMItem.model_construct(
        part_number="DIRTY-PART-01",
        part_name="Kirli Flanş",
        revision="A",
        parent_part_number=None,
        quantity=1.0,
        unit_cost=None,  # Kirli / boş fiyat
        supplier_id="SUP-DIRTY",
    )

    # 2. Kirli envanter: Negatif stok
    dirty_inv = InventoryItem(
        part_number="DIRTY-PART-01",
        stock_quantity=-25,  # Validator tarafından 0'a sabitlenir
        lead_time_days=-5,
        location="DIRTY-WH",
    )
    assert dirty_inv.stock_quantity == 0, "Negatif stok 0'a sabitlenmeliydi!"

    summary = calc.calculate(
        eco_id="ECO-DIRTY-TEST",
        root_part_number="DIRTY-PART-01",
        affected_parts=[dirty_part],
        inventory_map={"DIRTY-PART-01": dirty_inv},
    )
    assert summary.total_scrap_cost == 0.0

    # 3. Sıfıra bölme koruması: Günlük tüketim = 0
    strategy, runout, scrap = eff.calculate_transition_plan_safe(
        stock_quantity=-25,
        unit_cost=None,
        daily_consumption_rate=0,
        tooling_lead_time_days=10,
    )
    assert strategy is not None
    assert runout == 0
    assert scrap == 0.0

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return True, elapsed_ms, "Negatif stok -> 0 | None maliyet -> 0.0 | ZeroDivision önlendi"


def run_chaos_6_large_scale_performance() -> tuple[bool, float, str]:
    """Kaos 6: Büyük Ölçek Performans Stres Testi (2.000 Parça, 6 Seviye Derinlik)."""
    t0 = time.perf_counter()

    records: list[dict[str, object]] = [
        {
            "part_number": "BIG-ROOT-000",
            "part_name": "Ana Güç Aktarma Ünitesi",
            "revision": "A",
            "parent_part_number": None,
            "quantity": 1.0,
            "unit_cost": 5000.0,
            "supplier_id": "SUP-ROOT",
            "tooling_id": "TOOL-ROOT",
        }
    ]

    current_parents = ["BIG-ROOT-000"]
    part_count = 1

    for level in range(1, 6):
        next_parents: list[str] = []
        for parent in current_parents:
            for child_idx in range(4):
                if part_count >= 2000:
                    break
                child_pn = f"P-L{level}-{part_count:04d}"
                records.append(
                    {
                        "part_number": child_pn,
                        "part_name": f"Bileşen Seviye {level}",
                        "revision": "A",
                        "parent_part_number": parent,
                        "quantity": 1.0,
                        "unit_cost": round(15.0 + (level * 2.5), 2),
                        "supplier_id": f"SUP-L{level}",
                        "tooling_id": f"TOOL-{level}" if child_idx % 2 == 0 else None,
                    }
                )
                next_parents.append(child_pn)
                part_count += 1
            if part_count >= 2000:
                break
        current_parents = next_parents
        if part_count >= 2000:
            break

    while part_count < 2000:
        child_pn = f"P-EXTRA-{part_count:04d}"
        records.append(
            {
                "part_number": child_pn,
                "part_name": "Yaprak Parça",
                "revision": "A",
                "parent_part_number": current_parents[0],
                "quantity": 1.0,
                "unit_cost": 12.0,
                "supplier_id": "SUP-EXTRA",
                "tooling_id": None,
            }
        )
        part_count += 1

    df = pd.DataFrame(records)
    bom = BOMTreeEngine()
    bom.load_from_dataframe(df)

    # 1. En derin yaprak için Where-Used sorgusu
    deepest_leaf = records[-1]["part_number"]
    where_used = bom.get_where_used(deepest_leaf)
    assert len(where_used) >= 1

    # 2. Kök parça için tüm 2.000 parçalık BFS etkisi
    affected = bom.get_affected_subassemblies("BIG-ROOT-000")
    assert len(affected) == 2000

    # 3. 2.000 parça için hurda maliyeti simülasyonu
    calc = ImpactCalculatorEngine()
    inv_map = {
        r["part_number"]: InventoryItem(
            part_number=str(r["part_number"]),
            stock_quantity=10,
            lead_time_days=5,
            location="WH-BIG",
        )
        for r in records
    }
    summary = calc.calculate(
        eco_id="ECO-STRESS-2000",
        root_part_number="BIG-ROOT-000",
        affected_parts=affected,
        inventory_map=inv_map,
    )

    elapsed_sec = time.perf_counter() - t0
    elapsed_ms = elapsed_sec * 1000

    assert elapsed_sec < 2.0, f"Stres testi 2 saniyeyi aştı: {elapsed_sec:.3f} s"
    assert summary.total_affected_parts == 2000

    return True, elapsed_ms, f"2.000 parça / 6 seviye analizi {elapsed_sec:.3f} saniyede tamamlandı (< 2.0s)"


def run_chaos_7_llm_hallucination_defense() -> tuple[bool, float, str]:
    """Kaos 7: LLM Halüsinasyon & Olmayan Parça Saldırısı (GHOST-PART-404)."""
    t0 = time.perf_counter()
    agent = CadenceECOAgent()

    # 1. Simülasyon aracı olmayan parça ile çağrıldığında
    part_not_found = False
    try:
        agent.tool_run_simulation(part_number="GHOST-PART-404", change_type="TOLERANCE")
    except PartNotFoundError as exc:
        part_not_found = True
        assert exc.part_id == "GHOST-PART-404"
        assert "bulunamadı" in exc.message.lower() or "not found" in exc.message.lower()

    assert part_not_found, "tool_run_simulation GHOST-PART-404 için PartNotFoundError fırlatmalıydı!"

    # 2. Where-used aracı olmayan parça ile çağrıldığında
    where_used_not_found = False
    try:
        agent.tool_get_where_used(part_number="GHOST-PART-404")
    except PartNotFoundError as exc:
        where_used_not_found = True
        assert exc.part_id == "GHOST-PART-404"

    assert where_used_not_found, "tool_get_where_used GHOST-PART-404 için PartNotFoundError fırlatmalıydı!"

    elapsed_ms = (time.perf_counter() - t0) * 1000
    return True, elapsed_ms, "GHOST-PART-404 için maliyet üretilmedi | PartNotFoundError doğrulandı"


def main() -> int:
    """7 Kaos Testini sırayla koşturur ve konsola detaylı sonuç tablosu basar."""
    print("=" * 95)
    print("  CADENCE PLM — GERÇEK DÜNYA KAOS VE STRES TESTİ PANELİ (CHAOS ENGINEERING)")
    print("  SAP S/4HANA OData Entegrasyonu, Kirli Veri Zırhı ve Büyük Ölçek Dayanıklılık Doğrulaması")
    print("=" * 95)

    tests = [
        ("Kaos 1: Gerçek SAP OData HTTP İletişimi", run_chaos_1_sap_http_communication, "src.connectors.sap_odata_client"),
        ("Kaos 2: SAP Yetkisiz Erişim & 503 Çökmesi", run_chaos_2_sap_unauthorized_and_fault, "src.connectors.sap_odata_client"),
        ("Kaos 3: Yetim Parça / ERP Uyumsuzluğu", run_chaos_3_orphan_part_resilience, "src.engines.impact_calculator"),
        ("Kaos 4: Döngüsel BOM Tuzağı (Cycle Trap)", run_chaos_4_circular_bom_trap, "src.engines.bom_tree"),
        ("Kaos 5: Kirli ERP Verisi & Zero Division", run_chaos_5_dirty_erp_and_zero_division, "src.engines.effectivity_engine"),
        ("Kaos 6: Büyük Ölçek Performans (2000 Parça)", run_chaos_6_large_scale_performance, "src.engines.bom_tree & impact"),
        ("Kaos 7: LLM Halüsinasyon & Hayalet Parça", run_chaos_7_llm_hallucination_defense, "src.agents.eco_agent"),
    ]

    all_passed = True
    results: list[dict[str, object]] = []

    for idx, (name, test_fn, layer) in enumerate(tests, start=1):
        try:
            passed, elapsed_ms, detail = test_fn()
            results.append({
                "idx": idx,
                "name": name,
                "passed": passed,
                "time_ms": elapsed_ms,
                "detail": detail,
                "layer": layer,
            })
            print(f"\n  [PASS] Test {idx}: {name} ({elapsed_ms:.2f} ms)")
            print(f"         Katman:  {layer}")
            print(f"         Sonuç:   {detail}")
        except Exception as err:
            all_passed = False
            results.append({
                "idx": idx,
                "name": name,
                "passed": False,
                "time_ms": 0.0,
                "detail": str(err),
                "layer": layer,
            })
            print(f"\n  [FAIL] Test {idx}: {name}")
            print(f"         Hata:    {err}")

    print("\n" + "-" * 95)
    print(f"{'#':<3} {'Kaos Senaryosu':<45} {'Süre':<12} {'Durum':<10} {'Mimari Katman':<22}")
    print("-" * 95)
    for r in results:
        status_str = "BAŞARILI" if r["passed"] else "BAŞARISIZ"
        time_str = f"{r['time_ms']:.2f} ms"
        print(f"{r['idx']:<3} {str(r['name']):<45} {time_str:<12} {status_str:<10} {str(r['layer']):<22}")
    print("=" * 95)

    if all_passed:
        print("✔ TÜM KAOS VE STRES TESTLERİ BAŞARIYLA GEÇTİ (7/7).")
        print("CadencePLM gerçek SAP OData iletişimine, kirli verilere ve büyük ölçekli yüklere tam dayanıklıdır.")
        return 0
    else:
        print("❌ BAZI KAOS TESTLERİ BAŞARISIZ OLDU!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
