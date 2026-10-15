"""
scripts/run_demo.py
===================
CadencePLM - ECO Simülasyon ve Etki Analizi Demo Betiği.

Kullanım:
    python scripts/run_demo.py
    python scripts/run_demo.py "GBX-1210 ana dişli milinin toleransını revize ediyoruz, yeni rev C olacak"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Proje kök dizinini sys.path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schemas.simulation import SimulationSummary
from src.services.orchestrator import CadenceOrchestrator


def print_banner() -> None:
    banner = """
================================================================================
          CADENCE PLM - ENGINEERING CHANGE ORDER (ECO) IMPACT ENGINE
                    Deterministik BOM & Finansal Simülasyon
================================================================================
"""
    print(banner.strip())


def print_summary_table(summary: SimulationSummary, raw_text: str) -> None:
    width = 78
    sep = "+" + "-" * (width - 2) + "+"

    print(f"\n[Girdi ECO Talebi]: \"{raw_text}\"")
    print(f"[Simülasyon ID]   : {summary.eco_id}")
    print(f"[Hedef Kök Parça] : {summary.root_part_number}\n")

    print(sep)
    print(f"| {'ENDÜSTRİYEL ETKİ ÖZETİ':<{width - 4}} |")
    print(sep)
    print(f"| {'Metrik':<44} | {'Değer':<27} |")
    print(sep)
    print(f"| {'Etkilenen Parça Sayısı':<44} | {f'{summary.total_affected_parts} adet':<27} |")
    print(f"| {'Toplam Hurda Maliyeti ($)':<44} | {f'${summary.total_scrap_cost:,.2f}':<27} |")
    print(f"| {'Etkilenen Tedarikçi Kalıp Sayısı':<44} | {f'{summary.total_impacted_toolings} adet':<27} |")
    print(f"| {'Tahmini Geçiş Süresi (Kritik Yol)':<44} | {f'{summary.max_transition_lead_time_days} gün':<27} |")
    print(f"| {'Önerilen Yürürlük Stratejisi':<44} | {summary.recommended_strategy.value:<27} |")
    if summary.run_out_days > 0:
        print(f"| {'Stok Tükenme Süresi (USE_UP)':<44} | {f'{summary.run_out_days} gün':<27} |")
    if summary.rework_analysis and summary.rework_analysis.is_reworkable:
        rf = summary.rework_analysis
        print(f"| {'Rework ile Kurtarılabilirlik':<44} | {f'Mümkün ({rf.operation_type})':<27} |")
        print(f"| {'Birim Rework Maliyeti ($)':<44} | {f'${rf.rework_cost_per_unit:,.2f}':<27} |")
        print(f"| {'Rework Net Tasarrufu ($)':<44} | {f'${rf.net_savings:,.2f}':<27} |")
    print(sep)

    if summary.where_used_parents:
        print("\n" + sep)
        print(f"| {'WHERE-USED (KULLANILDIĞI ÜST SİSTEMLER)':<{width - 4}} |")
        print(sep)
        print(f"| {'Seviye':<10} | {'Üst Parça No':<18} | {'Üst Montaj Adı':<42} |")
        print(sep)
        for w in summary.where_used_parents:
            print(f"| {f'Seviye {w.assembly_level}':<10} | {w.parent_part_number:<18} | {(w.parent_part_name[:40] + '..') if len(w.parent_part_name) > 42 else w.parent_part_name:<42} |")
        print(sep)

    if summary.details:
        print("\n" + sep)
        print(f"| {'ETKİLENEN PARÇA DETAYLARI':<{width - 4}} |")
        print(sep)
        header = f"| {'Parça No':<14} | {'Parça Adı':<22} | {'Hurda':<8} | {'Birim ($)':<9} | {'Tutar ($)':<12} |"
        print(header)
        print(sep)
        for d in summary.details:
            tooling_info = " [Kalıp Etkisi]" if d.tooling_affected else ""
            line = (
                f"| {d.part_number:<14} | "
                f"{(d.part_name[:20] + '..') if len(d.part_name) > 22 else d.part_name:<22} | "
                f"{d.affected_stock:<8} | "
                f"${d.unit_cost:<8.2f} | "
                f"${d.scrap_cost:<11.2f} |"
            )
            print(line)
        print(sep)


def main() -> None:
    print_banner()

    ebom_path = PROJECT_ROOT / "data" / "sample_ebom.csv"
    inv_path = PROJECT_ROOT / "data" / "sample_inventory.csv"

    if not ebom_path.exists() or not inv_path.exists():
        print(f"[HATA]: Örnek veri dosyaları bulunamadı: {ebom_path}, {inv_path}")
        sys.exit(1)

    print(f"[Yükleniyor] EBOM      : {ebom_path}")
    print(f"[Yükleniyor] Envanter  : {inv_path}")

    ebom_df = pd.read_csv(ebom_path)
    inventory_df = pd.read_csv(inv_path)

    # Örnek metin (varsayılan veya argümandan gelen)
    if len(sys.argv) > 1:
        eco_text = " ".join(sys.argv[1:])
    else:
        eco_text = "GB-PINION-02 dişli revizyonu nedeniyle parça toleransı değişti"

    print("[Çalıştırılıyor] CadenceOrchestrator simülasyonu...")
    orchestrator = CadenceOrchestrator()
    summary = orchestrator.run_simulation(
        raw_eco_text=eco_text,
        ebom_df=ebom_df,
        inventory_df=inventory_df,
    )

    print_summary_table(summary, eco_text)
    print("\n>>> [AŞAMA 6 BAŞARILI]: ECO simülasyonu deterministik olarak tamamlandı.\n")


if __name__ == "__main__":
    main()
