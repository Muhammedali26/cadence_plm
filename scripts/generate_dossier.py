"""
scripts/generate_dossier.py
===========================
CadencePLM - Resmi Endüstriyel Değişiklik Raporu (ECO Dossier) Üretim Betiği.

IATF 16949 / PPAP uyumlu ECN etki dosyasını (HTML) otomatik olarak
'reports/' klasörüne üretir.

Kullanım:
    python scripts/generate_dossier.py
    python scripts/generate_dossier.py "GB-PINION-02 dişli tolerans revizyonu"
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Proje kök dizinini sys.path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.services.dossier_generator import ECODossierGenerator
from src.services.orchestrator import CadenceOrchestrator


def main() -> None:
    # 1. ECO metnini belirle
    default_text = "GB-PINION-02 pinyon dişlisinin toleransını revize ediyoruz, yeni rev B olacak"
    eco_text = sys.argv[1] if len(sys.argv) > 1 else default_text

    print("=" * 80)
    print("   CADENCE PLM - IATF 16949 / PPAP ECO IMPACT DOSSIER GENERATOR")
    print("=" * 80)
    print(f"\n[Girdi ECO Metni]: \"{eco_text}\"")

    # 2. Veri setlerini yükle
    ebom_path = PROJECT_ROOT / "data" / "sample_ebom.csv"
    inv_path = PROJECT_ROOT / "data" / "sample_inventory.csv"

    if not ebom_path.exists() or not inv_path.exists():
        print(f"[HATA]: Örnek veri setleri bulunamadı! ({ebom_path}, {inv_path})")
        sys.exit(1)

    print("[1/3] Kurumsal EBOM ve SAP Stok verileri yükleniyor...")
    ebom_df = pd.read_csv(ebom_path)
    inv_df = pd.read_csv(inv_path)

    # 3. Orkestratör ile simülasyonu çalıştır
    print("[2/3] Simülasyon motorları (BOM Tree, Where-Used, Rework, Impact) çalıştırılıyor...")
    orchestrator = CadenceOrchestrator()
    summary = orchestrator.run_simulation(
        raw_eco_text=eco_text,
        ebom_df=ebom_df,
        inventory_df=inv_df,
    )

    # 4. Dossier üret
    print("[3/3] IATF 16949 ECN Impact Dossier HTML raporu derleniyor...")
    generator = ECODossierGenerator()
    report_file = generator.generate_dossier(
        summary=summary,
        eco_description=eco_text,
    )

    print("\n" + "=" * 80)
    print("                  RESMİ ECO RAPORU BAŞARIYLA OLUŞTURULDU")
    print("=" * 80)
    print(f"Rapor Dosyası     : {report_file}")
    print(f"Simülasyon ID     : {summary.eco_id}")
    print(f"Hedef Parça       : {summary.root_part_number}")
    print(f"Etkilenen Parça   : {summary.total_affected_parts} adet")
    print(f"Toplam Hurda ($)  : ${summary.total_scrap_cost:,.2f}")
    if summary.rework_analysis and summary.rework_analysis.is_reworkable:
        rf = summary.rework_analysis
        print(f"Rework Tasarrufu  : +${rf.net_savings:,.2f} ({rf.operation_type})")
        net = max(0.0, summary.total_scrap_cost - rf.net_savings)
        print(f"Net Risk Marjı    : ${net:,.2f}")
    else:
        print("Rework Durumu     : Hurda Kaçınılmaz (Kurtarma Yok)")
    print(f"Önerilen Strateji : {summary.recommended_strategy.value}")
    print(f"Kritik Yol Süresi : {summary.max_transition_lead_time_days} gün")
    print("=" * 80)
    print(f"\n>>> [AŞAMA 12 TAMAMLANDI]: Tarayıcınızda açıp inceleyebilirsiniz: file:///{report_file.as_posix()}\n")


if __name__ == "__main__":
    main()
