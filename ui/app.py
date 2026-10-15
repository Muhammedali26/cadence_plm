"""
ui/app.py
=========
CadencePLM - Otonom Mühendislik Değişiklik Yönetimi (ECO) Kokpiti.

Streamlit ve Plotly ile güçlendirilmiş, IATF 16949 / PPAP Seviye 3 uyumlu,
canlı OpenAI GPT-4o ReAct karar motoru interaktif yönetici kokpiti.

Çalıştırma:
    streamlit run ui/app.py
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

# Proje kök dizinini sys.path'e ekle
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.agents.eco_agent import AgentAnalysisResult, CadenceECOAgent
from src.core.config import settings
from src.core.exceptions import (
    CadencePLMException,
    CostCalculationError,
    ECOParsingError,
    PartNotFoundError,
)
from src.schemas.simulation import SimulationSummary
from src.services.dossier_generator import ECODossierGenerator
from src.services.orchestrator import CadenceOrchestrator

# ---------------------------------------------------------------------------
# Sayfa Konfigürasyonu & Tema
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CadencePLM - ECO Yönetici Kokpiti",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Özel Endüstriyel Stil CSS
st.markdown(
    """
    <style>
        /* Genel Arka Plan ve Tipografi */
        .main {
            background-color: #0b0f19;
            color: #f1f5f9;
        }

        /* Başlık Rozetleri */
        .badge-tag {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-right: 8px;
            margin-bottom: 8px;
        }
        .badge-iatf {
            background: rgba(14, 165, 233, 0.15);
            color: #38bdf8;
            border: 1px solid rgba(14, 165, 233, 0.35);
        }
        .badge-openai {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.35);
        }
        .badge-ppap {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.35);
        }

        /* Yönetici Özeti Kartı */
        .executive-container {
            background: #111827;
            border: 1px solid #1f2937;
            border-left: 6px solid #0ea5e9;
            border-radius: 12px;
            padding: 24px;
            margin-top: 14px;
            margin-bottom: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
        }

        /* Where-Used Akış Şeması */
        .tree-flow-banner {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 8px;
            padding: 14px 20px;
            font-family: monospace;
            font-size: 15px;
            color: #38bdf8;
            font-weight: 600;
            margin-bottom: 16px;
            display: flex;
            align-items: center;
            overflow-x: auto;
        }

        /* Where-Used Hiyerarşi Akış Kartları */
        .flow-node {
            background: rgba(30, 41, 59, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 8px;
            padding: 12px 18px;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .flow-node.target {
            border-color: rgba(244, 63, 94, 0.6);
            background: rgba(244, 63, 94, 0.12);
        }
        .flow-node.root {
            border-color: rgba(14, 165, 233, 0.6);
            background: rgba(14, 165, 233, 0.12);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Oturum Durumu (Session State) Başlatma
# ---------------------------------------------------------------------------

SCENARIO_1 = (
    "GB-PINION-02 tolerans daralması nedeniyle pinyon dişlisinde temas yüzeyi revizyonu yapıldı. "
    "Yeni hedef revizyon B olarak güncellenecek."
)
SCENARIO_2 = (
    "GB-SHAFT-01 mil malzeme alaşımı değişimi (42CrMo4 çeliği) yapıldı, aşınma direnci artırılacak. "
    "Hedef revizyon C olarak güncellenecek."
)

if "eco_input" not in st.session_state:
    st.session_state.eco_input = SCENARIO_1

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "simulation_summary" not in st.session_state:
    st.session_state.simulation_summary = None


# ---------------------------------------------------------------------------
# Sol Kenar Çubuğu (Sidebar)
# ---------------------------------------------------------------------------

with st.sidebar:
    st.image(
        "https://img.shields.io/badge/CadencePLM-Tier--1%20Powertrain-0ea5e9?style=for-the-badge&logo=gear&logoColor=white",
        use_container_width=True,
    )
    st.title("🎛️ Yönetici Paneli")
    st.caption("Otonom Mühendislik Değişiklik Yönetimi (ECO)")

    st.markdown("---")
    st.subheader("📋 Hazır Senaryolar")

    if st.button("Senaryo 1: GB-PINION-02 Tolerans Daralması (Kurtarılabilir)", use_container_width=True):
        st.session_state.eco_input = SCENARIO_1
        st.rerun()

    if st.button("Senaryo 2: GB-SHAFT-01 Mil Malzeme Alaşımı Değişimi (Hurda Kaçınılmaz)", use_container_width=True):
        st.session_state.eco_input = SCENARIO_2
        st.rerun()

    st.markdown("---")
    st.subheader("✏️ Manuel Serbest Metin ECO Girdisi")
    user_eco_text = st.text_area(
        "Mühendislik Değişiklik Talebi (Serbest Metin):",
        value=st.session_state.eco_input,
        height=140,
        placeholder="Örn: GB-PINION-02 tolerans daralması nedeniyle yeni revizyon B...",
    )
    st.session_state.eco_input = user_eco_text

    run_button = st.button("🚀 Simülasyonu ve Ajanı Başlat", type="primary", use_container_width=True)

    st.markdown("---")
    st.markdown("### 🔍 Sistem Teşhis & Durum")
    st.markdown(
        f"""
        - **LLM Model:** `{settings.OPENAI_MODEL or 'gpt-4o'}`
        - **Karar Mimarisi:** `ReAct Tool-Calling`
        - **Kalite Standardı:** `IATF 16949 / PPAP L3`
        - **BOM Kataloğu:** `12 Parça Hiyerarşik EBOM`
        - **SAP Envanter:** `sample_inventory.csv`
        """
    )


# ---------------------------------------------------------------------------
# Ana Başlık Paneli
# ---------------------------------------------------------------------------

st.title("⚙️ CadencePLM - Otonom Mühendislik Değişiklik Yönetimi (ECO) Kokpiti")
st.markdown(
    """
    <div>
        <span class="badge-tag badge-iatf">IATF 16949:2016 Compliant</span>
        <span class="badge-tag badge-ppap">AIAG / VDA PPAP Seviye 3</span>
        <span class="badge-tag badge-openai">OpenAI GPT-4o ReAct Engine</span>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")


# ---------------------------------------------------------------------------
# Analiz Yürütme Mantığı
# ---------------------------------------------------------------------------

if run_button:
    if not user_eco_text or len(user_eco_text.strip()) < 5:
        st.warning("⚠️ Lütfen analiz için en az 5 karakterlik geçerli bir ECO metni girin.")
    else:
        with st.spinner("🤖 OpenAI GPT-4o Ajanı motorları tetikliyor (BOM Tree, Where-Used, Rework, Effectivity)..."):
            try:
                # 1. Canlı ReAct Tool-Calling Ajanını Çağır
                agent = CadenceECOAgent()
                result: AgentAnalysisResult = agent.analyze_eco_unstructured(user_eco_text)
                st.session_state.analysis_result = result

                # 2. Resmi Raporlama için Orkestratör Simülasyonunu Çalıştır
                orchestrator = CadenceOrchestrator()
                sim_summary = orchestrator.run_simulation(
                    raw_eco_text=user_eco_text,
                    ebom_df=agent.ebom_df,
                    inventory_df=agent.inventory_df,
                )
                st.session_state.simulation_summary = sim_summary
                st.success("✅ Ajan analizi ve deterministik simülasyon başarıyla tamamlandı!")

            except PartNotFoundError as p_err:
                st.error(f"❌ Parça Bulunamadı: {p_err.message} (Detay: {p_err.detail or 'EBOM kataloğunda yok'})")
                st.session_state.analysis_result = None
            except ECOParsingError as ep_err:
                st.error(f"❌ ECO Ayrıştırma Hatası: {ep_err.message}")
                st.session_state.analysis_result = None
            except CostCalculationError as cc_err:
                st.error(f"❌ Maliyet Hesaplama Hatası: {cc_err.message}")
                st.session_state.analysis_result = None
            except CadencePLMException as plm_err:
                st.error(f"❌ CadencePLM Hatası: {plm_err.message} ({plm_err.detail})")
                st.session_state.analysis_result = None
            except Exception as unexp_err:
                err_msg = str(unexp_err)
                if "api_key" in err_msg.lower() or "openai" in err_msg.lower():
                    st.error(f"❌ OpenAI API Hatası: {err_msg} — Lütfen OPENAI_API_KEY ve internet bağlantısını kontrol edin.")
                else:
                    st.error(f"❌ Beklenmeyen Sistem Hatası: {unexp_err}")
                st.session_state.analysis_result = None


# ---------------------------------------------------------------------------
# Dashboard Görselleştirme Paneli
# ---------------------------------------------------------------------------

res: AgentAnalysisResult | None = st.session_state.analysis_result
summary: SimulationSummary | None = st.session_state.simulation_summary

if res is not None and summary is not None:
    # 1. Dört Büyük KPI Kartı (st.metric)
    st.markdown("### 📊 Yönetici Finansal & Operasyonel KPI Kartları")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    total_scrap = float(res.total_scrap_cost)
    savings = float(res.net_savings)
    run_out = int(res.run_out_days)
    lead_time = int(res.max_transition_lead_time_days)
    where_used_levels = len(res.where_used_chain) if res.where_used_chain else 1

    with kpi_col1:
        st.metric(
            label="Toplam Hurda Maliyeti ($)",
            value=f"${total_scrap:,.2f}",
            delta=f"-${total_scrap:,.2f} Risk" if total_scrap > 0 else "Sıfır Hurda",
            delta_color="inverse",
        )

    with kpi_col2:
        st.metric(
            label="Kurtarma (Rework) Tasarrufu ($)",
            value=f"${savings:,.2f}",
            delta=f"+${savings:,.2f} Net Tasarruf" if savings > 0 else "Kurtarma Yok",
            delta_color="normal",
        )

    with kpi_col3:
        st.metric(
            label="Tahmini Geçiş / Run-Out Süresi (Gün)",
            value=f"{run_out} Gün",
            delta=f"{res.recommended_strategy}",
            delta_color="off",
        )

    with kpi_col4:
        st.metric(
            label="Etkilenen Montaj Seviyesi Sayısı",
            value=f"{where_used_levels} Seviye",
            delta=f"Kritik Kalıp: {lead_time} Gün",
            delta_color="off",
        )

    st.markdown("---")

    # 2. Grafikler ve Hiyerarşi Akışı
    col_chart, col_hierarchy = st.columns([1, 1])

    with col_chart:
        st.markdown("### 💰 Hurda Maliyeti vs. Net Tasarruf")
        net_exposure = max(0.0, total_scrap - savings)

        tab_bar, tab_donut = st.tabs(["📊 Karşılaştırmalı Bar Grafiği", "🍩 Finansal Dağılım (Donut)"])

        with tab_bar:
            fig_bar = go.Figure()
            fig_bar.add_trace(
                go.Bar(
                    name="Mali Büyüklükler",
                    x=["Brüt Hurda Maliyeti", "Rework Tasarrufu", "Net Risk Maruziyeti"],
                    y=[total_scrap, savings, net_exposure],
                    marker_color=["#f43f5e", "#10b981", "#f59e0b"],
                    text=[f"${total_scrap:,.2f}", f"${savings:,.2f}", f"${net_exposure:,.2f}"],
                    textposition="auto",
                )
            )
            fig_bar.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=20, b=20),
                yaxis_title="USD ($)",
                height=320,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with tab_donut:
            fig_donut = go.Figure(
                data=[
                    go.Pie(
                        labels=["Kurtarılan Değer (Rework)", "Net Hurda / Risk"],
                        values=[savings, net_exposure] if (savings + net_exposure) > 0 else [0, 1],
                        hole=0.6,
                        marker_colors=["#10b981", "#f43f5e"],
                        textinfo="label+percent",
                    )
                ]
            )
            fig_donut.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=20, r=20, t=20, b=20),
                height=320,
                showlegend=True,
            )
            st.plotly_chart(fig_donut, use_container_width=True)

    with col_hierarchy:
        st.markdown("### 🔗 Where-Used Hiyerarşi & Ağaç Akışı")

        # Ağaç akış yolu metni: GB-PINION-02 -> GBX-1300 -> GBX-1000
        chain_tokens: list[str] = [str(res.target_part_number)]
        if res.where_used_chain:
            for item in res.where_used_chain:
                p_num = str(item.get("parent_part_number", ""))
                if p_num and p_num not in chain_tokens:
                    chain_tokens.append(p_num)

        tree_flow_str = " ➔ ".join(chain_tokens)
        st.markdown(
            f"""
            <div class="tree-flow-banner">
                <span>🌲 Ağaç Akışı: &nbsp;</span> {tree_flow_str}
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Görsel akış düğümleri
        st.markdown(
            f"""
            <div class="flow-node target">
                <div>
                    <strong>🎯 Hedef Parça:</strong> {res.target_part_number}
                    <div style="font-size: 11px; color: #94a3b8;">Değişiklik Türü: {res.change_type} | Kurtarılabilir: {'Evet' if res.is_reworkable else 'Hayır'}</div>
                </div>
                <span style="font-size: 12px; color: #f43f5e; font-weight: bold;">KAYNAK</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if res.where_used_chain:
            table_rows: list[dict[str, object]] = []
            for item in res.where_used_chain:
                level = item.get("assembly_level", 1)
                p_num = str(item.get("parent_part_number", "-"))
                p_name = str(item.get("parent_part_name", "-"))

                table_rows.append(
                    {
                        "Seviye": f"L{level}",
                        "Üst Montaj Kodu": p_num,
                        "Üst Montaj Tanımı": p_name,
                    }
                )

                st.markdown(
                    f"""
                    <div class="flow-node">
                        <div>
                            <strong>⬆️ Montaj Seviyesi {level}:</strong> {p_num}
                            <div style="font-size: 11px; color: #94a3b8;">{p_name}</div>
                        </div>
                        <span style="font-size: 12px; color: #38bdf8; font-weight: bold;">ÜST MONTAJ</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with st.expander("📋 Where-Used Hiyerarşi Tablosunu Göster", expanded=False):
                st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
        else:
            st.info("Bu parça ana montaj seviyesindedir veya üst sistemi yoktur.")

    st.markdown("---")

    # 3. Yönetici Özeti Alanı (OpenAI GPT-4o Çıktısı)
    st.markdown("### 📝 Yönetici Özeti & Teknik Karar Raporu")
    with st.container(border=True):
        st.markdown("#### 🤖 OpenAI GPT-4o Kıdemli İmalat Mühendisi Ajan Değerlendirmesi")
        st.markdown(res.executive_summary)

    st.markdown("---")

    # 4. Aksiyon Butonu: ECODossierGenerator ile tek tıkla HTML Rapor İndir
    st.markdown("### 📑 Resmi Değişiklik Bildirimi (ECN Dossier)")
    dossier_gen = ECODossierGenerator()
    html_dossier = dossier_gen.generate_html(
        summary=summary,
        rework=summary.rework_analysis,
        where_used=summary.where_used_parents,
        eco_description=user_eco_text,
    )

    download_filename = f"ECO_IMPACT_REPORT_{summary.eco_id}.html"

    st.download_button(
        label="📥 IATF 16949 / PPAP Resmi ECO Raporunu İndir (.html)",
        data=html_dossier,
        file_name=download_filename,
        mime="text/html",
        use_container_width=True,
    )

else:
    # Henüz analiz yapılmadıysa başlangıç kılavuzu
    st.info(
        "👈 Sol menüden hazır bir senaryo seçin veya kendi ECO metninizi yazıp "
        "'🚀 Simülasyonu ve Ajanı Başlat' butonuna tıklayın."
    )

    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.markdown("#### 1. Serbest Metin Ayrıştırma")
        st.caption("Doğal dilde yazılan mühendislik değişiklikleri (tolerans, malzeme, geometri vb.) GPT-4o tarafından otomatik çözümlenir.")
    with col_info2:
        st.markdown("#### 2. Deterministik Hesaplama")
        st.caption("BOM ağaç gezintisi, SAP stok hurda hesapları ve talaşlı imalat kurtarma modelleri sıfır hata ile Python motorlarında hesaplanır.")
    with col_info3:
        st.markdown("#### 3. IATF 16949 ECN Dossier")
        st.caption("Üst yönetim için PPAP Seviye 3 uyumlu, ıslak imzaya ve ERP entegrasyonuna hazır resmi HTML etki dosyası üretilir.")
