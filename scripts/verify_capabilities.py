"""
scripts/verify_capabilities.py
==============================
CadencePLM Çekirdek Yetenek ve Mimari Sınır Denetim Betiği (Product Verification Script).

Bu betik, CadencePLM'in 5 temel çekirdek yeteneğini bağımsız olarak doğrular:
1. Serbest metinden hedef parça ve ECO parametresi çıkarma başarımı.
2. Where-Used hiyerarşik montaj zinciri tespiti (DAG traversal).
3. Rework (talaşlı imalat kurtarma) net tasarruf ve fizibilite doğrulaması.
4. ISO 10303-21 STEP AP214 CAD montaj ağacı ayrıştırma testi.
5. Sınır ve Güvenilirlik Testi (Fail-Safe): Tanımsız parça, negatif maliyet veya geçersiz girdide
   sistemin çökmeyip kurumsal istisnaları (PartNotFoundError, CostCalculationError) fırlatması.

Çalıştırma:
    python scripts/verify_capabilities.py
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import time
from typing import NamedTuple

# Proje kök dizinini sys.path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Windows terminal UTF-8 uyumluluğu
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pandas as pd

from src.core.exceptions import (
    BOMStructureError,
    CostCalculationError,
    ECOParsingError,
    PartNotFoundError,
)
from src.engines.bom_tree import BOMTreeEngine
from src.engines.cad_parser import parse_step_assembly
from src.engines.rework_optimizer import ReworkOptimizerEngine
from src.schemas.eco import ECOChangeType
from src.services.eco_parser import ECOParser

# ---------------------------------------------------------------------------
# ANSI Terminal Renk Sabitleri
# ---------------------------------------------------------------------------

USE_COLOR = sys.stdout.isatty() or os.name == "nt"

RESET = "\033[0m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
GREEN = "\033[32m" if USE_COLOR else ""
RED = "\033[31m" if USE_COLOR else ""
CYAN = "\033[36m" if USE_COLOR else ""
YELLOW = "\033[33m" if USE_COLOR else ""
BLUE = "\033[34m" if USE_COLOR else ""
DIM = "\033[2m" if USE_COLOR else ""


class TestResult(NamedTuple):
    test_id: int
    name: str
    expected: str
    actual: str
    passed: bool
    duration_ms: float
    details: str


def run_test_1() -> TestResult:
    """1. Test: Serbest metinden hedef parça çıkarma başarımı."""
    start = time.perf_counter()
    parser = ECOParser(api_key=None)  # Deterministik yerel regex motoru
    sample_text = (
        "GB-PINION-02 pinyon dişlisinin temas yüzeyi toleransı daraltıldı, "
        "yeni rev B olarak güncellenecek."
    )
    eco = parser.parse(sample_text)
    duration = (time.perf_counter() - start) * 1000

    change_type_str = getattr(eco.change_type, "value", str(eco.change_type))
    passed = (
        eco.affected_part_number == "GB-PINION-02"
        and eco.target_revision == "B"
        and change_type_str == "TOLERANCE"
    )

    expected = "Part: GB-PINION-02 | Rev: B | Type: TOLERANCE"
    actual = f"Part: {eco.affected_part_number} | Rev: {eco.target_revision} | Type: {change_type_str}"
    details = f"Ayrıştırılan ECO ID: {eco.eco_id}"

    return TestResult(1, "Serbest Metin ECO Ayrıştırma", expected, actual, passed, duration, details)


def run_test_2() -> TestResult:
    """2. Test: Where-Used üst montaj zinciri tespiti."""
    start = time.perf_counter()
    bom_engine = BOMTreeEngine()
    ebom_path = PROJECT_ROOT / "data" / "sample_ebom.csv"
    ebom_df = pd.read_csv(ebom_path)
    bom_engine.load_from_dataframe(ebom_df)

    where_used = bom_engine.get_where_used("GB-PINION-02")
    duration = (time.perf_counter() - start) * 1000

    chain_parts = [item.parent_part_number for item in where_used]
    chain_levels = [item.assembly_level for item in where_used]

    # Beklenen: Seviye 1: GBX-1300, Seviye 2: GBX-1000
    passed = (
        len(where_used) == 2
        and chain_parts == ["GBX-1300", "GBX-1000"]
        and chain_levels == [1, 2]
    )

    expected = "GB-PINION-02 -> L1: GBX-1300 -> L2: GBX-1000 (2 Seviye)"
    actual = f"GB-PINION-02 -> {' -> '.join([f'L{lvl}: {pn}' for pn, lvl in zip(chain_parts, chain_levels)])}"
    details = f"Toplam ebeveyn montaj: {len(where_used)} adet"

    return TestResult(2, "Where-Used Montaj Zinciri (DAG)", expected, actual, passed, duration, details)


def run_test_3() -> TestResult:
    """3. Test: Rework tasarruf hesaplama doğrulaması."""
    start = time.perf_counter()
    optimizer = ReworkOptimizerEngine()
    # GB-PINION-02: unit_cost=135.0, stock_quantity=55, change_type=TOLERANCE
    feasibility = optimizer.evaluate_rework(
        part_number="GB-PINION-02",
        unit_cost=135.0,
        stock_quantity=55,
        change_type="TOLERANCE",
        part_name="Ayna Pinyon Dişlisi",
    )
    duration = (time.perf_counter() - start) * 1000

    # Beklenen:
    # rework_cost = round(135.0 * 0.15, 2) = 20.25
    # net_savings = round((135.0 - 20.25) * 55, 2) = 6311.25
    passed = (
        feasibility.is_reworkable is True
        and feasibility.operation_type == "CNC_TURNING"
        and feasibility.rework_cost_per_unit == 20.25
        and feasibility.net_savings == 6311.25
    )

    expected = "is_reworkable: True | CNC_TURNING | Birim: $20.25 | Net: $6,311.25"
    actual = (
        f"is_reworkable: {feasibility.is_reworkable} | {feasibility.operation_type} | "
        f"Birim: ${feasibility.rework_cost_per_unit:,.2f} | Net: ${feasibility.net_savings:,.2f}"
    )
    details = "Brüt Hurda: $7,425.00 -> Kurtarılan Sermaye: %85 net"

    return TestResult(3, "Rework vs. Scrap Optimizasyonu", expected, actual, passed, duration, details)


def run_test_4() -> TestResult:
    """4. Test: STEP AP214 montaj ayrıştırma testi."""
    start = time.perf_counter()
    step_path = PROJECT_ROOT / "data" / "sample_gearbox.step"
    items = parse_step_assembly(step_path)
    duration = (time.perf_counter() - start) * 1000

    part_numbers = {item.part_number for item in items}
    root_item = next((item for item in items if item.parent_part_number is None), None)

    # 12 parça ayrıştırılmalı, kök GBX-1000 olmalı
    passed = (
        len(items) == 12
        and root_item is not None
        and root_item.part_number == "GBX-1000"
        and "GB-PINION-02" in part_numbers
    )

    expected = "12 BOMItem | Kök: GBX-1000 (parent=None) | GB-PINION-02 dahil"
    actual = f"{len(items)} BOMItem | Kök: {root_item.part_number if root_item else 'YOK'} | GB-PINION-02: {'Mevcut' if 'GB-PINION-02' in part_numbers else 'YOK'}"
    details = f"ISO 10303-21 STEP dosya boyutu: {step_path.stat().st_size} bayt"

    return TestResult(4, "ISO 10303-21 STEP AP214 CAD Parser", expected, actual, passed, duration, details)


def run_test_5() -> TestResult:
    """5. Test (Sınır Testi): Bilinçsiz / geçersiz girdide fail-safe çalışma garantisi."""
    start = time.perf_counter()
    bom_engine = BOMTreeEngine()
    ebom_path = PROJECT_ROOT / "data" / "sample_ebom.csv"
    bom_engine.load_from_dataframe(pd.read_csv(ebom_path))

    optimizer = ReworkOptimizerEngine()

    # 1. Kontrol: Var olmayan parçada PartNotFoundError fırlatılıyor mu?
    part_not_found_caught = False
    try:
        bom_engine.get_where_used("INVALID-PART-999")
    except PartNotFoundError:
        part_not_found_caught = True

    # 2. Kontrol: Negatif maliyette CostCalculationError fırlatılıyor mu?
    cost_error_caught = False
    try:
        optimizer.evaluate_rework(
            part_number="GB-PINION-02",
            unit_cost=-50.0,
            stock_quantity=10,
        )
    except CostCalculationError:
        cost_error_caught = True

    # 3. Kontrol: Boş metinde ECOParsingError fırlatılıyor mu?
    parsing_error_caught = False
    try:
        ECOParser().parse("   ")
    except ECOParsingError:
        parsing_error_caught = True

    duration = (time.perf_counter() - start) * 1000
    passed = part_not_found_caught and cost_error_caught and parsing_error_caught

    expected = "PartNotFoundError + CostCalculationError + ECOParsingError fırlatıldı"
    actual = f"PNF: {part_not_found_caught} | CCE: {cost_error_caught} | EPE: {parsing_error_caught}"
    details = "Sistem asla sessizce çökmez; kurumsal exception sözleşmelerini uygular"

    return TestResult(5, "Mimari Sınır ve Fail-Safe Denetimi", expected, actual, passed, duration, details)


def main() -> int:
    print(f"\n{BOLD}{CYAN}{'=' * 85}{RESET}")
    print(f"{BOLD}{CYAN}  CADENCE PLM — ÇEKİRDEK YETENEK VE MİMARİ SINIR DENETİM KİTİ (VERIFICATION){RESET}")
    print(f"{DIM}  Tier-1 İmalat Mühendisliği & Değişiklik Yönetimi (ECO) Canlı Doğrulama Paneli{RESET}")
    print(f"{BOLD}{CYAN}{'=' * 85}{RESET}\n")

    tests = [
        run_test_1,
        run_test_2,
        run_test_3,
        run_test_4,
        run_test_5,
    ]

    results: list[TestResult] = []
    for test_fn in tests:
        res = test_fn()
        results.append(res)
        status_tag = f"{GREEN}[PASS]{RESET}" if res.passed else f"{RED}[FAIL]{RESET}"
        print(f"  {status_tag} {BOLD}Test {res.test_id}: {res.name}{RESET} {DIM}({res.duration_ms:.2f} ms){RESET}")
        print(f"         {DIM}Beklenen:{RESET}  {res.expected}")
        print(f"         {DIM}Gerçekleşen:{RESET} {res.actual}")
        print(f"         {DIM}Detay:{RESET}     {res.details}\n")

    all_passed = all(r.passed for r in results)
    total_time = sum(r.duration_ms for r in results)

    # Özet Yetenek Matrisi Tablosu
    print(f"{BOLD}{CYAN}{'-' * 85}{RESET}")
    print(f"{BOLD}{'#':<4} {'Yetenek / Test Modülü':<38} {'Süre':<10} {'Durum':<10} {'Mimari Katman'}{RESET}")
    print(f"{CYAN}{'-' * 85}{RESET}")

    layers = [
        "src.services.eco_parser",
        "src.engines.bom_tree",
        "src.engines.rework_optimizer",
        "src.engines.cad_parser",
        "src.core.exceptions",
    ]

    for r, layer in zip(results, layers):
        status_str = f"{GREEN}BAŞARILI{RESET}" if r.passed else f"{RED}BAŞARISIZ{RESET}"
        print(f"{r.test_id:<4} {r.name:<38} {r.duration_ms:>6.2f} ms  {status_str:<18} {DIM}{layer}{RESET}")

    print(f"{BOLD}{CYAN}{'=' * 85}{RESET}")

    if all_passed:
        print(f"{BOLD}{GREEN}✔ TÜM YETENEK TESTLERİ BAŞARIYLA GEÇTİ (5/5). Toplam Süre: {total_time:.2f} ms{RESET}")
        print(f"{DIM}CadencePLM deterministik motorları ve hata bariyerleri endüstriyel üretime hazırdır.{RESET}\n")
        return 0
    else:
        failed_count = sum(1 for r in results if not r.passed)
        print(f"{BOLD}{RED}✘ {failed_count} TEST BAŞARISIZ OLDU. Lütfen yukarıdaki detayları inceleyin.{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
