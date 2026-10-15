"""
src/services/dossier_generator.py
=================================
Resmi Endüstriyel Değişiklik Raporu (ECO Dossier) Üreticisi.

IATF 16949 / PPAP Uyumlu Mühendislik Değişiklik Bildirimi (ECN) Etki Raporu.

Kurallar (.antigravityrules §1, §2, §3):
- Deterministik, temiz ve saf Python servis mantığı.
- Sıfır LLM, sıfır harici şablon motoru (Jinja2 zorunluluğu olmaksızın saf,
  tip güvenli HTML/CSS üretimi).
- `Any` tipi kesinlikle yasaktır.
- Çıktı: 'reports/ECO_IMPACT_REPORT_{eco_id}.html'.
"""

from __future__ import annotations

from datetime import datetime, timezone
import html
import os
from pathlib import Path

from src.schemas.rework import ReworkFeasibility, ReworkOperationType
from src.schemas.simulation import (
    EffectivityStrategy,
    PartImpactDetail,
    SimulationSummary,
    WhereUsedDetail,
)

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
_DEFAULT_REPORTS_DIR: Path = _PROJECT_ROOT / "reports"


class ECODossierGenerator:
    """
    IATF 16949 / PPAP standartlarına uygun kurumsal ECN (Engineering Change Notification)
    etki değerlendirme raporu (Dossier) üreten servis sınıfı.
    """

    def __init__(self, reports_dir: Path | str | None = None) -> None:
        self.reports_dir: Path = (
            Path(reports_dir) if reports_dir is not None else _DEFAULT_REPORTS_DIR
        )
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def generate_html(
        self,
        summary: SimulationSummary,
        rework: ReworkFeasibility | None = None,
        where_used: list[WhereUsedDetail] | None = None,
        eco_description: str | None = None,
    ) -> str:
        """
        Simülasyon özeti, rework analizi ve where-used hiyerarşisinden zengin,
        kurumsal IATF 16949 uyumlu HTML rapor içeriği üretir.
        """
        active_rework = rework or summary.rework_analysis
        active_where_used = (
            where_used if where_used is not None else summary.where_used_parents
        )
        timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        eco_desc = eco_description or f"Engineering Change Request for root {summary.root_part_number}"

        # Finansal Trade-Off Değerleri
        total_scrap = summary.total_scrap_cost
        savings = active_rework.net_savings if (active_rework and active_rework.is_reworkable) else 0.0
        rework_cost_unit = (
            active_rework.rework_cost_per_unit
            if (active_rework and active_rework.is_reworkable)
            else 0.0
        )
        rework_op = (
            active_rework.operation_type
            if (active_rework and active_rework.is_reworkable)
            else "NONE"
        )
        is_reworkable = active_rework.is_reworkable if active_rework else False

        net_exposure = max(0.0, round(total_scrap - savings, 2))
        savings_percentage = (
            round((savings / total_scrap) * 100, 1) if total_scrap > 0 else 0.0
        )

        # HTML Bileşenleri
        kpi_cards_html = self._build_kpi_cards_html(
            summary=summary,
            total_scrap=total_scrap,
            savings=savings,
            net_exposure=net_exposure,
            is_reworkable=is_reworkable,
            rework_op=rework_op,
            rework_cost_unit=rework_cost_unit,
            savings_pct=savings_percentage,
        )

        where_used_html = self._build_where_used_flow_html(
            root_part=summary.root_part_number,
            where_used=active_where_used,
        )

        risk_matrix_html = self._build_risk_matrix_table_html(summary.details)

        strategy_html = self._build_strategy_html(summary)

        signoff_html = self._build_signoff_section_html()

        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ECN Dossier - {html.escape(summary.eco_id)} | CadencePLM</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0e17;
            --bg-secondary: #111827;
            --bg-card: rgba(17, 24, 39, 0.75);
            --border-card: rgba(255, 255, 255, 0.08);
            --border-highlight: rgba(14, 165, 233, 0.3);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --text-muted: #64748b;
            --accent-cyan: #0ea5e9;
            --accent-blue: #3b82f6;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --accent-purple: #8b5cf6;
            --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-primary);
            color: var(--text-primary);
            font-family: var(--font-sans);
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
            background-image: 
                radial-gradient(circle at 15% 10%, rgba(14, 165, 233, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 30%, rgba(139, 92, 246, 0.06) 0%, transparent 45%);
            background-attachment: fixed;
            padding: 40px 20px;
        }}

        .dossier-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        /* Document Header & Control Bar */
        .control-bar {{
            background: rgba(15, 23, 42, 0.8);
            backdrop-filter: blur(12px);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .brand-meta {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .brand-badge {{
            background: linear-gradient(135deg, #0ea5e9, #2563eb);
            color: #ffffff;
            font-weight: 800;
            font-size: 13px;
            padding: 6px 14px;
            border-radius: 6px;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}

        .doc-meta {{
            font-size: 13px;
            color: var(--text-secondary);
            font-family: var(--font-mono);
        }}

        .status-chip {{
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}

        .status-chip.pending {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .status-chip.iatf {{
            background: rgba(14, 165, 233, 0.12);
            color: #38bdf8;
            border: 1px solid rgba(14, 165, 233, 0.25);
        }}

        /* Dossier Main Header */
        .dossier-header {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: 16px;
            padding: 36px 40px;
            margin-bottom: 28px;
            position: relative;
            overflow: hidden;
        }}

        .dossier-header::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 5px;
            height: 100%;
            background: linear-gradient(180deg, var(--accent-cyan), var(--accent-blue));
        }}

        .header-title-sub {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: var(--accent-cyan);
            font-weight: 700;
            margin-bottom: 8px;
        }}

        .header-title {{
            font-size: 26px;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.5px;
            margin-bottom: 12px;
            line-height: 1.3;
        }}

        .header-description {{
            font-size: 15px;
            color: var(--text-secondary);
            max-width: 900px;
        }}

        /* Grid & Cards */
        .section-title {{
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .section-title .icon {{
            color: var(--accent-cyan);
        }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 18px;
            margin-bottom: 32px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 22px;
            transition: transform 0.2s ease, border-color 0.2s ease;
            position: relative;
        }}

        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: var(--border-highlight);
        }}

        .kpi-label {{
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .kpi-value {{
            font-size: 28px;
            font-weight: 800;
            font-family: var(--font-mono);
            letter-spacing: -0.5px;
            margin-bottom: 6px;
        }}

        .kpi-value.scrap {{ color: var(--accent-rose); }}
        .kpi-value.savings {{ color: var(--accent-emerald); }}
        .kpi-value.neutral {{ color: #ffffff; }}
        .kpi-value.exposure {{ color: var(--accent-amber); }}

        .kpi-subtext {{
            font-size: 12px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        /* Financial Trade-Off Banner */
        .financial-comparison {{
            background: linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(14, 165, 233, 0.05));
            border: 1px solid rgba(16, 185, 129, 0.25);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
        }}

        .comp-info h4 {{
            font-size: 16px;
            color: #ffffff;
            font-weight: 700;
            margin-bottom: 4px;
        }}

        .comp-info p {{
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .comp-badge {{
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.4);
            padding: 10px 20px;
            border-radius: 8px;
            font-family: var(--font-mono);
            font-size: 18px;
            font-weight: 700;
            text-align: right;
        }}

        /* Where-Used Flow Section */
        .where-used-box {{
            background: var(--bg-card);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 32px;
        }}

        .tree-flow {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 14px;
        }}

        .tree-node {{
            background: rgba(30, 41, 59, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 10px;
            padding: 14px 20px;
            min-width: 190px;
        }}

        .tree-node.target {{
            background: rgba(244, 63, 94, 0.12);
            border-color: rgba(244, 63, 94, 0.35);
        }}

        .tree-node.root {{
            background: rgba(14, 165, 233, 0.12);
            border-color: rgba(14, 165, 233, 0.35);
        }}

        .tree-node .level {{
            font-size: 11px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }}

        .tree-node .part-no {{
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 15px;
            color: #ffffff;
        }}

        .tree-node .part-name {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .tree-arrow {{
            color: var(--accent-cyan);
            font-size: 20px;
            font-weight: bold;
        }}

        /* Table */
        .table-card {{
            background: var(--bg-card);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            overflow: hidden;
            margin-bottom: 32px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }}

        thead th {{
            background: rgba(30, 41, 59, 0.6);
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
            padding: 14px 18px;
            border-bottom: 1px solid var(--border-card);
        }}

        tbody td {{
            padding: 14px 18px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            color: var(--text-primary);
        }}

        tbody tr:hover {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .td-mono {{
            font-family: var(--font-mono);
            font-weight: 600;
        }}

        .badge-risk {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            display: inline-block;
        }}

        .badge-risk.high {{
            background: rgba(244, 63, 94, 0.15);
            color: #fb7185;
            border: 1px solid rgba(244, 63, 94, 0.3);
        }}

        .badge-risk.med {{
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-risk.low {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .badge-tooling {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        }}

        .badge-tooling.impacted {{
            background: rgba(239, 68, 68, 0.12);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.25);
        }}

        .badge-tooling.safe {{
            background: rgba(100, 116, 139, 0.15);
            color: #94a3b8;
            border: 1px solid rgba(100, 116, 139, 0.25);
        }}

        /* Strategy Section */
        .strategy-box {{
            background: var(--bg-card);
            backdrop-filter: blur(14px);
            border: 1px solid var(--border-card);
            border-radius: 14px;
            padding: 24px;
            margin-bottom: 32px;
        }}

        /* Sign-Off / Approval Section */
        .signoff-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 16px;
        }}

        .signoff-card {{
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid var(--border-card);
            border-radius: 12px;
            padding: 22px;
            position: relative;
        }}

        .signoff-role {{
            font-size: 14px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 4px;
        }}

        .signoff-dept {{
            font-size: 12px;
            color: var(--accent-cyan);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 18px;
        }}

        .signoff-line {{
            height: 1px;
            background: rgba(255, 255, 255, 0.15);
            margin: 40px 0 12px 0;
            position: relative;
        }}

        .signoff-meta {{
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            font-family: var(--font-mono);
        }}

        .stamp-box {{
            display: inline-block;
            border: 2px dashed rgba(16, 185, 129, 0.4);
            color: #34d399;
            font-size: 10px;
            font-weight: 700;
            padding: 4px 8px;
            border-radius: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 10px;
        }}

        /* Footer */
        .dossier-footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--border-card);
            font-family: var(--font-mono);
        }}

        /* Print Media Styles */
        @media print {{
            body {{
                background: #ffffff !important;
                color: #000000 !important;
                padding: 0 !important;
            }}
            .dossier-header, .kpi-card, .table-card, .signoff-card, .control-bar {{
                background: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                color: #000000 !important;
                box-shadow: none !important;
            }}
            .header-title, .section-title, .kpi-value, .tree-node .part-no {{
                color: #000000 !important;
            }}
            .kpi-value.scrap {{ color: #dc2626 !important; }}
            .kpi-value.savings {{ color: #16a34a !important; }}
            table thead th {{
                background: #f1f5f9 !important;
                color: #334155 !important;
            }}
            tbody td {{
                color: #0f172a !important;
                border-bottom: 1px solid #e2e8f0 !important;
            }}
        }}
    </style>
</head>
<body>

<div class="dossier-container">

    <!-- Document Control Bar -->
    <div class="control-bar">
        <div class="brand-meta">
            <span class="brand-badge">CadencePLM</span>
            <span class="doc-meta">DOC ID: <strong>ECN-DOC-{html.escape(summary.eco_id)}</strong></span>
        </div>
        <div style="display: flex; gap: 10px; align-items: center;">
            <span class="status-chip iatf">IATF 16949 / PPAP LEVEL 3</span>
            <span class="status-chip pending">PENDING EXECUTIVE SIGN-OFF</span>
        </div>
    </div>

    <!-- Dossier Main Header -->
    <header class="dossier-header">
        <div class="header-title-sub">IATF 16949 / PPAP ENGINEERING CHANGE NOTIFICATION (ECN) IMPACT DOSSIER</div>
        <h1 class="header-title">Mühendislik Değişiklik Talebi ve Çok Boyutlu Etki Analiz Raporu</h1>
        <p class="header-description">
            Hedef Kök Montaj: <strong style="color: #fff;">{html.escape(summary.root_part_number)}</strong> | 
            Oluşturulma: <span style="font-family: var(--font-mono);">{timestamp_str}</span> | 
            Talep Özeti: <em>{html.escape(eco_desc)}</em>
        </p>
    </header>

    <!-- Executive KPI Cards -->
    <h2 class="section-title"><span class="icon">●</span> Yönetici Özeti & Finansal Metrikler</h2>
    <div class="kpi-grid">
        {kpi_cards_html}
    </div>

    <!-- Financial Trade-Off Banner -->
    <div class="financial-comparison">
        <div class="comp-info">
            <h4>Endüstriyel Kurtarma Stratejisi: Hurda vs. Rework (Talaşlı İmalat)</h4>
            <p>
                { "Parça tolerans ve ölçüsel olarak kurtarılabilir durumdadır. Parçaları hurdaya çıkarmak yerine CNC Talaşlı İmalat ile operasyonel kurtarma önerilmektedir."
                  if is_reworkable else
                  "Malzeme veya kritik yapı değişikliği nedeniyle kurtarma uygulanamaz; parçalar kontrollü hurdaya ayrılmalıdır." }
            </p>
        </div>
        <div class="comp-badge">
            { f"+${savings:,.2f} TASARRUF (%{savings_percentage})" if is_reworkable else "$0.00 KURTARMA" }
        </div>
    </div>

    <!-- Where-Used Assembly Flow -->
    <h2 class="section-title"><span class="icon">●</span> Where-Used Montaj Etki Şeması (Bottom-Up Traversal)</h2>
    <div class="where-used-box">
        <p style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px;">
            Değişiklik talep edilen parçadan ana kök montaja kadar olan yukarı yönlü hiyerarşik montaj bağı:
        </p>
        {where_used_html}
    </div>

    <!-- Supplier & Tooling Risk Matrix -->
    <h2 class="section-title"><span class="icon">●</span> Tedarikçi & Kalıp Risk Matrisi (BOM Detayları)</h2>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th>Parça Kodu</th>
                    <th>Parça Adı</th>
                    <th>Tedarikçi</th>
                    <th>Stok (Adet)</th>
                    <th>Birim ($)</th>
                    <th>Hurda ($)</th>
                    <th>Kalıp Durumu</th>
                    <th>Temin (Gün)</th>
                    <th>Risk Skoru</th>
                </tr>
            </thead>
            <tbody>
                {risk_matrix_html}
            </tbody>
        </table>
    </div>

    <!-- Cutover / Effectivity Strategy -->
    <h2 class="section-title"><span class="icon">●</span> Yürürlük ve Stok Geçiş Stratejisi (Effectivity Strategy)</h2>
    <div class="strategy-box">
        {strategy_html}
    </div>

    <!-- Sign-off & Approvals Section -->
    <h2 class="section-title"><span class="icon">●</span> İmza & Onay Bölümü (Executive Sign-Off & PPAP Release)</h2>
    <div class="signoff-grid">
        {signoff_html}
    </div>

    <!-- Footer -->
    <footer class="dossier-footer">
        CADENCE PLM AUTOMOTIVE PLATFORM — ISO 10303-21 / IATF 16949 COMPLIANT — CONFIDENTIAL & PROPRIETARY
    </footer>

</div>

</body>
</html>
"""

    def _build_kpi_cards_html(
        self,
        summary: SimulationSummary,
        total_scrap: float,
        savings: float,
        net_exposure: float,
        is_reworkable: bool,
        rework_op: str,
        rework_cost_unit: float,
        savings_pct: float,
    ) -> str:
        rework_label = f"Kurtarılabilir ({rework_op})" if is_reworkable else "Hurda Kaçınılmaz"
        rework_class = "savings" if is_reworkable else "scrap"

        cards = [
            f"""<div class="kpi-card">
                <div class="kpi-label">Toplam Hurda Maliyeti</div>
                <div class="kpi-value scrap">${total_scrap:,.2f}</div>
                <div class="kpi-subtext">Stoktaki brüt potansiyel kayıp</div>
            </div>""",
            f"""<div class="kpi-card">
                <div class="kpi-label">Rework Kurtarma Tasarrufu</div>
                <div class="kpi-value savings">${savings:,.2f}</div>
                <div class="kpi-subtext">Kurtarma Oranı: %{savings_pct}</div>
            </div>""",
            f"""<div class="kpi-card">
                <div class="kpi-label">Net Mali Risk Marjı</div>
                <div class="kpi-value exposure">${net_exposure:,.2f}</div>
                <div class="kpi-subtext">Rework sonrası net maruziyet</div>
            </div>""",
            f"""<div class="kpi-card">
                <div class="kpi-label">Rework Durumu & Operasyon</div>
                <div class="kpi-value {rework_class}" style="font-size: 20px;">{rework_label}</div>
                <div class="kpi-subtext">Birim Rework: ${rework_cost_unit:,.2f}</div>
            </div>""",
            f"""<div class="kpi-card">
                <div class="kpi-label">Etkilenen Parça & Kalıp</div>
                <div class="kpi-value neutral">{summary.total_affected_parts} Parça / {summary.total_impacted_toolings} Kalıp</div>
                <div class="kpi-subtext">Entegre alt montaj toplamı</div>
            </div>""",
            f"""<div class="kpi-card">
                <div class="kpi-label">Kritik Yol Temin Süresi</div>
                <div class="kpi-value neutral">{summary.max_transition_lead_time_days} Gün</div>
                <div class="kpi-subtext">Maksimum tedarik teslim süresi</div>
            </div>""",
        ]
        return "\n".join(cards)

    def _build_where_used_flow_html(
        self,
        root_part: str,
        where_used: list[WhereUsedDetail],
    ) -> str:
        if not where_used:
            return f"""<div class="tree-flow">
                <div class="tree-node root">
                    <div class="level">Kök Montaj</div>
                    <div class="part-no">{html.escape(root_part)}</div>
                    <div class="part-name">Bağımsız Kök Sistem</div>
                </div>
            </div>"""

        nodes: list[str] = [
            f"""<div class="tree-node target">
                <div class="level">Hedef Değişiklik</div>
                <div class="part-no">{html.escape(root_part)}</div>
                <div class="part-name">Değiştirilen Parça</div>
            </div>"""
        ]

        for idx, item in enumerate(where_used):
            arrow = '<div class="tree-arrow">➔</div>'
            is_last = idx == len(where_used) - 1
            node_class = "root" if is_last else "sub"
            level_text = f"Seviye {item.assembly_level} Üst Montaj"

            nodes.append(arrow)
            nodes.append(
                f"""<div class="tree-node {node_class}">
                    <div class="level">{level_text}</div>
                    <div class="part-no">{html.escape(item.parent_part_number)}</div>
                    <div class="part-name">{html.escape(item.parent_part_name)}</div>
                </div>"""
            )

        return f'<div class="tree-flow">{" ".join(nodes)}</div>'

    def _build_risk_matrix_table_html(self, details: list[PartImpactDetail]) -> str:
        if not details:
            return '<tr><td colspan="9" style="text-align: center; color: var(--text-muted);">Etkilenen parça bulunamadı.</td></tr>'

        rows: list[str] = []
        for det in details:
            # Risk seviyesi belirleme
            if det.tooling_affected or det.lead_time_days >= 30:
                risk_badge = '<span class="badge-risk high">YÜKSEK RİSK</span>'
            elif det.affected_stock > 50 or det.scrap_cost > 1000:
                risk_badge = '<span class="badge-risk med">ORTA RİSK</span>'
            else:
                risk_badge = '<span class="badge-risk low">DÜŞÜK RİSK</span>'

            tooling_badge = (
                '<span class="badge-tooling impacted">KALIP ETKİLENDİ</span>'
                if det.tooling_affected
                else '<span class="badge-tooling safe">GÜVENLİ</span>'
            )

            rows.append(
                f"""<tr>
                    <td class="td-mono">{html.escape(det.part_number)}</td>
                    <td>{html.escape(det.part_name)}</td>
                    <td class="td-mono">{html.escape(det.supplier_id)}</td>
                    <td class="td-mono" style="text-align: right;">{det.affected_stock}</td>
                    <td class="td-mono" style="text-align: right;">${det.unit_cost:,.2f}</td>
                    <td class="td-mono" style="text-align: right; color: var(--accent-rose);">${det.scrap_cost:,.2f}</td>
                    <td style="text-align: center;">{tooling_badge}</td>
                    <td class="td-mono" style="text-align: center;">{det.lead_time_days} gün</td>
                    <td style="text-align: center;">{risk_badge}</td>
                </tr>"""
            )
        return "\n".join(rows)

    def _build_strategy_html(self, summary: SimulationSummary) -> str:
        strategy = summary.recommended_strategy
        if strategy == EffectivityStrategy.USE_UP_STOCK:
            title = "Önerilen Strateji: USE_UP_STOCK (Stok Tüketimi ile Geçiş)"
            badge_class = "style='color: var(--accent-emerald); font-weight: 700;'"
            desc = (
                f"Yeni revizyona geçiş öncesi mevcut <strong>{summary.run_out_days} günlük</strong> stok tükenene "
                "kadar montaj hattında tüketime devam edilmesi önerilir. Bu sayede hurda maliyeti minimize edilir "
                f"ve tedarik süresi ({summary.max_transition_lead_time_days} gün) boyunca hat duruşu engellenir."
            )
        else:
            title = "Önerilen Strateji: IMMEDIATE_CUTOFF (Derhal Kesinti)"
            badge_class = "style='color: var(--accent-rose); font-weight: 700;'"
            desc = (
                "Kritik tolerans veya kalite gereksinimleri nedeniyle mevcut parçaların kullanımı derhal durdurulmalı, "
                "stoktaki parçalar karantinaya alınarak yeni revizyon parçalarının devreye alınması sağlanmalıdır."
            )

        return f"""
        <h4 {badge_class}>{title}</h4>
        <p style="font-size: 14px; color: var(--text-secondary); margin-top: 6px;">{desc}</p>
        """

    def _build_signoff_section_html(self) -> str:
        signatories = [
            ("Ar-Ge & Ürün Geliştirme Direktörü", "Mühendislik & Yapısal Onay", "Dr. M. Akın / Chief Engineer"),
            ("Satınalma & Tedarik Zinciri Müdürü", "Tedarik & Kalıp Maliyet Onayı", "E. Yılmaz / Head of Procurement"),
            ("Kalite Güvence & PPAP Müdürü", "IATF 16949 & PPAP Seviye 3 Onayı", "S. Demir / Quality Director"),
        ]

        cards: list[str] = []
        for role, dept, signatory_name in signatories:
            cards.append(
                f"""<div class="signoff-card">
                    <div class="signoff-role">{role}</div>
                    <div class="signoff-dept">{dept}</div>
                    <div style="font-size: 13px; color: var(--text-secondary);">{signatory_name}</div>
                    <div class="signoff-line"></div>
                    <div class="signoff-meta">
                        <span>İmza: _______________</span>
                        <span>Tarih: ____/____/2026</span>
                    </div>
                    <div class="stamp-box">✔ ELEKTRONİK ONAY HAZIR (PPAP-OK)</div>
                </div>"""
            )
        return "\n".join(cards)

    def generate_dossier(
        self,
        summary: SimulationSummary,
        rework: ReworkFeasibility | None = None,
        where_used: list[WhereUsedDetail] | None = None,
        output_path: Path | str | None = None,
        eco_description: str | None = None,
    ) -> Path:
        """
        HTML dosyasını oluşturur ve belirtilen veya varsayılan konuma kaydeder.

        Parameters
        ----------
        summary : SimulationSummary
            Simülasyon özeti nesnesi.
        rework : ReworkFeasibility, optional
            Rework kurtarma analizi (None ise summary.rework_analysis kullanılır).
        where_used : list[WhereUsedDetail], optional
            Where-used montaj listesi (None ise summary.where_used_parents kullanılır).
        output_path : Path | str, optional
            Özel çıktı dosya yolu. Belirtilmezse 'reports/ECO_IMPACT_REPORT_{eco_id}.html'.
        eco_description : str, optional
            Rapor başlığı için ECO metin açıklaması.

        Returns
        -------
        Path
            Oluşturulan HTML dosyasının mutlak yolu.
        """
        html_content = self.generate_html(
            summary=summary,
            rework=rework,
            where_used=where_used,
            eco_description=eco_description,
        )

        if output_path is not None:
            target_file = Path(output_path)
            target_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in summary.eco_id)
            target_file = self.reports_dir / f"ECO_IMPACT_REPORT_{safe_id}.html"

        target_file.write_text(html_content, encoding="utf-8")
        return target_file.resolve()

    # Alias metodlar
    generate_report = generate_dossier
