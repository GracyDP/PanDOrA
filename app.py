"""
PanDOrA — COVID-19 Data Explorer
================================
Homepage ridisegnata con layout a card, KPI stilizzati,
trend interattivo e design coerente con il reference UI.
"""

from PIL import Image
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

try:
    import folium
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

# ── SVG icon helper (Heroicons outline) ──────────────────────────────────────
def _svg(name: str, color: str = "#7a9ac8", size: int = 16) -> str:
    """Restituisce un'icona SVG Heroicons inline come stringa HTML."""
    _paths = {
        "virus":      '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M2 12h3M19 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/>',
        "heart-off":  '<path d="M8.56 2.9A7 7 0 0 1 19 9v.5M4.27 4.27 3 5.55l7.5 7.5L12 14.45l7 7M16.95 16.95A7 7 0 0 1 5 9v-.5"/>',
        "heart":      '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>',
        "globe":      '<circle cx="12" cy="12" r="10"/><path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
        "trophy":     '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6M18 9h1.5a2.5 2.5 0 0 0 0-5H18M4 22h16M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22M18 2H6v7a6 6 0 0 0 12 0V2z"/>',
        "chart-bar":  '<path d="M18 20V10M12 20V4M6 20v-6"/>',
        "database":   '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
        "calendar":   '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
        "skull":      '<path d="M12 2a9 9 0 0 1 9 9c0 3.18-1.65 5.97-4.13 7.59L16 22H8l-.87-3.41A9 9 0 0 1 3 11a9 9 0 0 1 9-9z"/><path d="M9 17v2M15 17v2M10 12a1 1 0 1 0 2 0 1 1 0 0 0-2 0M14 12a1 1 0 1 0 2 0 1 1 0 0 0-2 0"/>',
        "map":        '<polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/><line x1="8" y1="2" x2="8" y2="18"/><line x1="16" y1="6" x2="16" y2="22"/>',
        "warning":    '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
        "activity":   '<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>',
        "trending-up":'<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
        "download":   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    }
    inner = _paths.get(name, '<circle cx="12" cy="12" r="3"/>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" ' 
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" '
        f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" '
        f'style="display:inline-block;vertical-align:middle;margin-right:4px;">' 
        f'{inner}</svg>'
    )


logo = Image.open("logoBD.png")

# ── Configurazione pagina ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="PanDOrA — COVID-19",
    page_icon=logo,
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS globale ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Nasconde nav automatica Streamlit */
[data-testid="stSidebarNav"] { display: none; }

/* Font */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Sfondo pagina */
.stApp {
    background: #0d1b2a;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #0a1628 !important;
    border-right: 1px solid rgba(255,255,255,0.06);
}
[data-testid="stSidebar"] * {
    color: #c8d8f0 !important;
}
[data-testid="stSidebar"] a {
    border-radius: 8px;
    transition: background 0.2s;
}
[data-testid="stSidebar"] a:hover {
    background: rgba(59,130,246,0.15) !important;
}

/* Titolo hero */
.hero-title {
    font-size: 2.8rem;
    font-weight: 700;
    color: #f0f6ff;
    letter-spacing: -0.5px;
    line-height: 1.1;
    margin: 0 0 6px 0;
}
.hero-sub {
    font-size: 1rem;
    color: #6b8cba;
    font-weight: 400;
    margin: 0 0 28px 0;
}

/* Badge data */
.date-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.25);
    color: #7eb3f5;
    font-size: 0.78rem;
    font-family: 'DM Mono', monospace;
    padding: 4px 12px;
    border-radius: 20px;
    margin-bottom: 28px;
}

/* KPI cards */
.kpi-card {
    background: linear-gradient(135deg, #112240 0%, #0d1b2e 100%);
    border: 1px solid rgba(59,130,246,0.18);
    border-radius: 14px;
    padding: 22px 24px 18px 24px;
    position: relative;
    overflow: hidden;
    transition: border-color 0.25s, transform 0.2s;
}
.kpi-card:hover {
    border-color: rgba(59,130,246,0.45);
    transform: translateY(-2px);
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    border-radius: 14px 14px 0 0;
}
.kpi-card.blue::before  { background: linear-gradient(90deg, #3b82f6, #60a5fa); }
.kpi-card.red::before   { background: linear-gradient(90deg, #ef4444, #f87171); }
.kpi-card.green::before { background: linear-gradient(90deg, #10b981, #34d399); }
.kpi-card.amber::before { background: linear-gradient(90deg, #f59e0b, #fbbf24); }

.kpi-icon {
    font-size: 1.5rem;
    margin-bottom: 10px;
    display: block;
}
.kpi-label {
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #5a7aaa;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 700;
    color: #e8f1ff;
    font-family: 'DM Mono', monospace;
    letter-spacing: -1px;
    line-height: 1;
}
.kpi-value.red   { color: #f87171; }
.kpi-value.green { color: #34d399; }
.kpi-value.amber { color: #fbbf24; }

/* Sezione card generica */
.section-card {
    background: #112240;
    border: 1px solid rgba(59,130,246,0.14);
    border-radius: 14px;
    padding: 24px;
    margin-bottom: 20px;
}
.section-title {
    font-size: 1rem;
    font-weight: 600;
    color: #c8d8f0;
    margin: 0 0 16px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}
.section-title span {
    font-size: 1.1rem;
}

/* Avviso disclaimer */
.disclaimer {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.3);
    border-radius: 10px;
    padding: 12px 16px;
    color: #fbbf24;
    font-size: 0.82rem;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    margin-top: 8px;
}

/* Pulsanti nav */
.nav-btn {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: linear-gradient(135deg, #1e3a5f, #1a3354);
    border: 1px solid rgba(59,130,246,0.3);
    color: #7eb3f5 !important;
    padding: 10px 20px;
    border-radius: 10px;
    font-size: 0.88rem;
    font-weight: 500;
    text-decoration: none;
    transition: all 0.2s;
    margin: 4px;
}
.nav-btn:hover {
    background: linear-gradient(135deg, #2a4e7a, #244470);
    border-color: rgba(59,130,246,0.6);
    color: #bdd6ff !important;
    transform: translateY(-1px);
}

/* Dataframe custom */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Metriche Streamlit override */
[data-testid="stMetric"] {
    background: transparent !important;
}

/* Filtro trend pill */
.trend-filter {
    background: rgba(59,130,246,0.12);
    border: 1px solid rgba(59,130,246,0.25);
    color: #7eb3f5;
    font-size: 0.8rem;
    padding: 5px 14px;
    border-radius: 20px;
    display: inline-block;
    cursor: pointer;
    margin: 2px;
    font-family: 'DM Sans', sans-serif;
}

/* Nasconde label vuote */
.stSelectbox label, .stMultiSelect label {
    color: #5a7aaa !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #0d1b2a; }
::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

from utils.navbar import render_top_navbar
render_top_navbar("Home")

# ── Import dati ────────────────────────────────────────────────────────────────
from utils.db import mongo_available, retry_mongo
from utils.queries import get_snapshot, get_date_range, get_countries, count_records, aggregate_timeseries

# Shell iniziale statica: titolo e placeholder mostrati subito
st.markdown('<p class="hero-title">Pannello Dati COVID-19</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Consultazione e gestione centralizzata dei dati pandemici globali: '
    'casi, decessi, guarigioni e paesi monitorati.</p>',
    unsafe_allow_html=True
)
date_badge_slot = st.empty()
date_badge_slot.markdown(
    f'<div class="date-badge">{_svg("calendar","#7eb3f5",14)} Ultimo aggiornamento: caricamento...</div>',
    unsafe_allow_html=True,
)

snap = get_snapshot()
tutti_paesi = get_countries()
min_date, max_date = get_date_range()
total_rows = count_records()

total_confirmed = int(snap["Confirmed"].sum())
total_deaths = int(snap["Deaths"].sum())
total_recovered = int(snap["Recovered"].sum()) if "Recovered" in snap.columns else 0
n_countries = snap["Country/Region"].nunique()
global_cfr = round(total_deaths / total_confirmed * 100, 2) if total_confirmed else 0

# Aggiorna badge data appena i dati sono disponibili
date_badge_slot.markdown(
    f'<div class="date-badge">{_svg("calendar","#7eb3f5",14)} Ultimo aggiornamento: {max_date}</div>',
    unsafe_allow_html=True
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image(logo, width=150)

    st.markdown("""
    <div style="text-align:center;margin-top:-8px;margin-bottom:16px;">
        <div style="font-size:1.3rem;font-weight:700;color:#e8f1ff;">PanDOrA</div>
        <div style="font-size:0.72rem;color:#4a6a99;letter-spacing:0.5px;">
            Pandemic Data Observatory & Analysis
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown("""
    <div style="font-size:0.68rem;font-weight:600;text-transform:uppercase;
                letter-spacing:1.5px;color:#3a5a8a;margin-bottom:10px;">
        Navigazione
    </div>
    """, unsafe_allow_html=True)

    st.page_link("app.py",                  label="Home")
    st.page_link("pages/Dashboard.py",      label="Dashboard")
    st.page_link("pages/Insert.py",         label="Inserimento")
    st.page_link("pages/CRUD.py",           label="Gestione Dati")
    st.page_link("pages/Stampa_Dati.py",    label="Stampa & Export")

    st.divider()

    if mongo_available():
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<span style="width:8px;height:8px;border-radius:50%;background:#10b981;display:inline-block;"></span>'
            '<span style="font-size:0.78rem;color:#34d399;">MongoDB connesso</span>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:8px;">'
            '<span style="width:8px;height:8px;border-radius:50%;background:#ef4444;display:inline-block;"></span>'
            '<span style="font-size:0.78rem;color:#f87171;">Modalità CSV</span>'
            '</div>',
            unsafe_allow_html=True
        )
        if st.button("↺  Riconnetti MongoDB", key="sidebar_retry_mongo", use_container_width=True):
            with st.spinner("Connessione in corso..."):
                if retry_mongo():
                    st.rerun()
                else:
                    st.error("Connessione fallita.")

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="font-size:0.68rem;color:#2a4a6a;text-align:center;">'
        f'Dataset: {min_date} → {max_date}'
        f'</div>',
        unsafe_allow_html=True
    )

# __________________________________________________________________________-
# MAIN CONTENT

# ── KPI Cards ─────────────────────────────────────────────────────────────────
k1, k2, k3, k4 = st.columns(4)

with k1:
    st.markdown(f"""
    <div class="kpi-card blue">
        <span class="kpi-icon">{_svg("virus","#3b82f6",28)}</span>
        <div class="kpi-label">Casi Totali</div>
        <div class="kpi-value">{total_confirmed:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with k2:
    st.markdown(f"""
    <div class="kpi-card red">
        <span class="kpi-icon">{_svg("heart-off","#ef4444",28)}</span>
        <div class="kpi-label">Decessi Totali</div>
        <div class="kpi-value red">{total_deaths:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with k3:
    st.markdown(f"""
    <div class="kpi-card green">
        <span class="kpi-icon">{_svg("heart","#10b981",28)}</span>
        <div class="kpi-label">Guariti Totali</div>
        <div class="kpi-value green">{total_recovered:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)

with k4:
    st.markdown(f"""
    <div class="kpi-card amber">
        <span class="kpi-icon">{_svg("globe","#f59e0b",28)}</span>
        <div class="kpi-label">Paesi Monitorati</div>
        <div class="kpi-value amber">{n_countries}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)

# ── Layout principale: tabella sinistra + info destra ─────────────────────────
col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown(f'<div class="section-title">{_svg("trophy","#f59e0b",17)} Top 10 Paesi per Casi Confermati</div>', unsafe_allow_html=True)

    top10 = snap.nlargest(10, "Confirmed")[["Country/Region", "Confirmed", "Deaths", "CFR"]]
    top10 = top10.reset_index(drop=True)
    top10.index = top10.index + 1
    top10.columns = ["Paese", "Confermati", "Decessi", "CFR (%)"]

    st.dataframe(
        top10,
        use_container_width=True,
        height=360,
        column_config={
            "Confermati": st.column_config.NumberColumn(format="%d"),
            "Decessi":    st.column_config.NumberColumn(format="%d"),
            "CFR (%)":    st.column_config.NumberColumn(format="%.2f%%"),
        }
    )

with col_right:
    st.markdown("""
    <div class="section-title"><span> </span> Info Dataset</div>
    """, unsafe_allow_html=True)

    # Card info singole
    infos = [
        (_svg("database","#f59e0b",14), "Documenti totali",  f"{total_rows:,}"),
        (_svg("calendar","#3b82f6",14), "Data inizio",       str(min_date)),
        (_svg("calendar","#3b82f6",14), "Data fine",         str(max_date)),
        (_svg("globe","#10b981",14), "Paesi unici",       str(n_countries)),
        (_svg("skull","#ef4444",14), "CFR Globale",       f"{global_cfr}%"),
    ]
    for icon, label, value in infos:
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;
                    padding:10px 14px;margin-bottom:6px;
                    background:rgba(255,255,255,0.03);
                    border:1px solid rgba(59,130,246,0.1);
                    border-radius:8px;">
            <span style="color:#5a7aaa;font-size:0.82rem;">{icon} {label}</span>
            <span style="color:#c8d8f0;font-size:0.88rem;font-weight:600;
                         font-family:'DM Mono',monospace;">{value}</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Barre CFR top 5
    st.markdown(f'<div class="section-title" style="margin-top:8px;">{_svg("activity","#ef4444",17)} CFR — Top 5 Paesi</div>', unsafe_allow_html=True)

    top5_cfr = snap[snap["Confirmed"] >= 10000].nlargest(5, "CFR")[["Country/Region", "CFR"]]
    fig_bar = go.Figure(go.Bar(
        x=top5_cfr["CFR"],
        y=top5_cfr["Country/Region"],
        orientation="h",
        marker=dict(
            color=top5_cfr["CFR"],
            colorscale=[[0, "#1e3a5f"], [0.5, "#3b82f6"], [1, "#ef4444"]],
            showscale=False,
        ),
        text=[f"{v:.1f}%" for v in top5_cfr["CFR"]],
        textposition="outside",
        textfont=dict(color="#c8d8f0", size=11),
    ))
    fig_bar.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=30, t=0, b=0),
        height=155,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(tickfont=dict(color="#7a9ac8", size=11)),
    )
    st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SEZIONE TREND — con filtri PRIMA del grafico, poi disclaimer
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f'<div class="section-title" style="font-size:1.05rem;margin-bottom:20px;"> Andamento Globale nel Tempo</div>', unsafe_allow_html=True)

# Filtri trend — riga compatta sopra il grafico
tf1, tf2, tf3 = st.columns([2, 2, 1])

with tf1:
    paesi_default = [p for p in ["Italy", "US", "France", "Germany", "United Kingdom"] if p in tutti_paesi]
    trend_paesi = st.multiselect(
        "Paesi",
        tutti_paesi,
        default=paesi_default[:3],
        key="home_trend_paesi",
        label_visibility="visible",
    )

with tf2:
    trend_metrica = st.selectbox(
        "Metrica",
        ["Confirmed", "Deaths", "Recovered"],
        key="home_trend_metrica",
        label_visibility="visible",
    )

with tf3:
    trend_log = st.toggle("Scala log", value=False, key="home_trend_log")

# Periodi rapidi
periodo_opts = {"Tutto": None, "Ultimi 90gg": 90, "Ultimi 60gg": 60, "Ultimi 30gg": 30}
periodo_sel = st.radio(
    "Periodo",
    list(periodo_opts.keys()),
    horizontal=True,
    index=0,
    key="home_trend_periodo",
    label_visibility="collapsed",
)

# Grafico trend
if trend_paesi:
    trend_plot_slot = st.empty()
    trend_plot_slot.markdown(
        """
        <div style="height:320px;display:flex;align-items:center;justify-content:center;
                    border:1px solid rgba(59,130,246,0.18);border-radius:12px;
                    background:rgba(17,34,64,0.35);color:#7a9ac8;font-size:0.9rem;">
            Preparazione grafico trend...
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.spinner("Caricamento trend in corso..."):
        df_trend = aggregate_timeseries(trend_paesi, min_date, max_date)

    # Filtra per periodo
    giorni = periodo_opts[periodo_sel]
    if giorni and not df_trend.empty:
        cutoff = df_trend["Date"].max() - pd.Timedelta(days=giorni)
        df_trend = df_trend[df_trend["Date"] >= cutoff]

    if not df_trend.empty:
        # Palette hex → rgba per fillcolor (Plotly non accetta hex a 8 cifre)
        PALETTE_HEX = ["#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
                       "#06b6d4", "#ec4899", "#84cc16"]

        def hex_to_rgba(hex_color: str, alpha: float = 0.07) -> str:
            h = hex_color.lstrip("#")
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return f"rgba({r},{g},{b},{alpha})"

        fig = go.Figure()
        for i, paese in enumerate(trend_paesi):
            dp = df_trend[df_trend["Country/Region"] == paese].sort_values("Date")
            if dp.empty:
                continue
            colore     = PALETTE_HEX[i % len(PALETTE_HEX)]
            fill_color = hex_to_rgba(colore, 0.07)
            fig.add_trace(go.Scatter(
                x=dp["Date"],
                y=dp[trend_metrica] if trend_metrica in dp.columns else dp["Confirmed"],
                name=paese,
                mode="lines",
                line=dict(color=colore, width=2.5),
                fill="tozeroy",
                fillcolor=fill_color,
                hovertemplate=f"<b>{paese}</b><br>%{{x|%d %b %Y}}<br>{trend_metrica}: %{{y:,.0f}}<extra></extra>",
            ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#7a9ac8"),
            margin=dict(l=10, r=10, t=10, b=10),
            height=320,
            hovermode="x unified",
            legend=dict(
                orientation="h",
                y=1.08,
                x=0,
                font=dict(size=11, color="#c8d8f0"),
                bgcolor="rgba(0,0,0,0)",
            ),
            xaxis=dict(
                showgrid=True,
                gridcolor="rgba(59,130,246,0.08)",
                tickfont=dict(size=10),
                zeroline=False,
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor="rgba(59,130,246,0.08)",
                tickfont=dict(size=10),
                zeroline=False,
                type="log" if trend_log else "linear",
                tickformat=",d",
            ),
        )
        trend_plot_slot.empty()
        with trend_plot_slot.container():
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        # Trend Casi Giornalieri (diminuendo) — per il primo paese selezionato
        if len(trend_paesi) >= 1:
            st.markdown(f'<div class="section-title" style="margin-top:4px;font-size:0.9rem;">Trend {trend_metrica} Giornaliero (7gg media mobile) — {trend_paesi[0]}</div>', unsafe_allow_html=True)

            daily_plot_slot = st.empty()
            daily_plot_slot.markdown(
                """
                <div style="height:260px;display:flex;align-items:center;justify-content:center;
                            border:1px solid rgba(59,130,246,0.18);border-radius:12px;
                            background:rgba(17,34,64,0.35);color:#7a9ac8;font-size:0.88rem;">
                    Preparazione grafico giornaliero...
                </div>
                """,
                unsafe_allow_html=True,
            )

            dp0 = df_trend[df_trend["Country/Region"] == trend_paesi[0]].sort_values("Date").copy()
            col_m = trend_metrica if trend_metrica in dp0.columns else "Confirmed"
            dp0["Nuovi"] = dp0[col_m].diff().clip(lower=0)
            dp0["MA7"]   = dp0["Nuovi"].rolling(7, center=True, min_periods=1).mean()

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=dp0["Date"], y=dp0["Nuovi"],
                name="Giornaliero",
                marker_color="rgba(59,130,246,0.2)",
                marker_line_width=0,
            ))
            fig2.add_trace(go.Scatter(
                x=dp0["Date"], y=dp0["MA7"],
                name="Media 7gg",
                line=dict(color="#3b82f6", width=2.5),
            ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans", color="#7a9ac8"),
                margin=dict(l=10, r=10, t=10, b=10),
                height=260,
                hovermode="x unified",
                legend=dict(orientation="h", y=1.08, bgcolor="rgba(0,0,0,0)",
                            font=dict(size=11, color="#c8d8f0")),
                xaxis=dict(showgrid=True, gridcolor="rgba(59,130,246,0.08)",
                           tickfont=dict(size=10), zeroline=False),
                yaxis=dict(showgrid=True, gridcolor="rgba(59,130,246,0.08)",
                           tickfont=dict(size=10), zeroline=False, tickformat=",d"),
                bargap=0.1,
            )
            daily_plot_slot.empty()
            with daily_plot_slot.container():
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    else:
        trend_plot_slot.empty()
        st.info("Nessun dato disponibile per i filtri selezionati.")
else:
    st.markdown("""
    <div style="padding:32px;text-align:center;color:#4a6a99;font-size:0.9rem;">
        Seleziona almeno un paese dal filtro per visualizzare il trend.
    </div>
    """, unsafe_allow_html=True)

# ── Disclaimer — DOPO il grafico ──────────────────────────────────────────────
st.markdown("""
<div class="disclaimer">
    <span>I dati mostrati sono parametri illustrativi e non rappresentano valori reali.
    Per dati ufficiali consultare le fonti WHO, ECDC o i bollettini nazionali.</span>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SEZIONE MAPPA INTERATTIVA — folium integrata in homepage
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div style='height:32px'></div>", unsafe_allow_html=True)
st.markdown("""
<div class="section-title" style="font-size:1.05rem;margin-bottom:20px;">Mappa Geografica</div>
""", unsafe_allow_html=True)

from utils.db import COUNTRY_COORDS, POPULATION
from utils.queries import aggregate_map_snapshot

# ── Filtri mappa in riga compatta ─────────────────────────────────────────────
mf1, mf2, mf3, mf4, mf5 = st.columns([2, 1, 1, 1, 1])

with mf1:
    map_metrica = st.selectbox(
        "Metrica",
        ["Confirmed", "Deaths", "Recovered", "CFR (%)"],
        key="map_metrica",
    )
with mf2:
    map_data = st.date_input(
        "Snapshot",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
        key="map_data",
    )
with mf3:
    map_min_casi = st.number_input(
        "Casi minimi",
        min_value=0, value=0, step=1000,
        key="map_min_casi",
    )
with mf4:
    map_scala = st.radio(
        "Scala cerchi",
        ["Lineare", "Log"],
        index=1,
        key="map_scala",
        horizontal=True,
    )
with mf5:
    map_tile = st.selectbox(
        "Stile",
        ["CartoDB Dark Matter", "CartoDB Positron", "OpenStreetMap"],
        key="map_tile",
    )

# Filtro paesi opzionale (collassato per non ingombrare)
with st.expander("Filtra per paesi specifici (opzionale)", expanded=False):
    map_paesi_sel = st.multiselect(
        "Seleziona paesi (vuoto = tutti)",
        tutti_paesi,
        default=[],
        key="map_paesi",
    )

# ── Caricamento dati mappa ────────────────────────────────────────────────────
map_slot = st.empty()
map_slot.markdown(
    """
    <div style="height:560px;display:flex;align-items:center;justify-content:center;
                border:1px solid rgba(59,130,246,0.18);border-radius:12px;
                background:rgba(17,34,64,0.35);color:#7a9ac8;font-size:0.92rem;">
        Preparazione mappa interattiva...
    </div>
    """,
    unsafe_allow_html=True,
)

with st.spinner("Caricamento snapshot mappa in corso..."):
    df_map = aggregate_map_snapshot(
        data_snapshot=map_data,
        min_confirmed=map_min_casi,
        paesi=map_paesi_sel if map_paesi_sel else None,
    )

if df_map.empty:
    map_slot.empty()
    st.warning("Nessun dato corrisponde ai filtri selezionati per la mappa.")
else:
    # Coordinate e popolazione
    df_map["lat"] = df_map["Country/Region"].map(
        lambda x: COUNTRY_COORDS.get(x, (None, None))[0]
    )
    df_map["lon"] = df_map["Country/Region"].map(
        lambda x: COUNTRY_COORDS.get(x, (None, None))[1]
    )
    df_map = df_map.dropna(subset=["lat", "lon"])

    df_map["Popolazione (M)"] = df_map["Country/Region"].map(
        lambda x: POPULATION.get(x, None)
    )
    df_map["Casi per 100k"] = np.where(
        df_map["Popolazione (M)"].notna(),
        (df_map["Confirmed"] / (df_map["Popolazione (M)"] * 1e6) * 1e5).round(1),
        None,
    )

    # Raggio cerchi
    col_metrica = map_metrica
    if col_metrica in df_map.columns:
        vals = df_map[col_metrica].fillna(0).astype(float)
        if map_scala == "Log":
            vals = np.log1p(vals)
        vmax = vals.max() if vals.max() > 0 else 1
        df_map["radius_m"] = (vals / vmax * 500_000).clip(lower=30_000)
    else:
        df_map["radius_m"] = 100_000

    # Colore cerchi: verde → giallo → rosso
    df_map["color_val"] = df_map[col_metrica].fillna(0).astype(float)
    cv_max = df_map["color_val"].max() if df_map["color_val"].max() > 0 else 1
    df_map["norm"] = (df_map["color_val"] / cv_max).clip(0, 1)

    def _circle_color(n: float) -> str:
        if n < 0.5:
            t = n * 2
            r = int(34  + t * (234 - 34))
            g = int(197 + t * (179 - 197))
            b = int(94  + t * (8   - 94))
        else:
            t = (n - 0.5) * 2
            r = int(234 + t * (239 - 234))
            g = int(179 - t * (179 - 68))
            b = int(8   + t * (68  - 8))
        return f"#{r:02x}{g:02x}{b:02x}"

    df_map["circle_color"] = df_map["norm"].apply(_circle_color)

    st.markdown(
        f'<div style="font-size:0.8rem;color:#5a7aaa;margin-bottom:12px;">'
        f'<b style="color:#c8d8f0">{len(df_map)}</b> paesi visualizzati — '
        f'Snapshot al <b style="color:#c8d8f0">{map_data}</b> — '
        f'Metrica: <b style="color:#c8d8f0">{map_metrica}</b>'
        f'</div>',
        unsafe_allow_html=True,
    )

    if HAS_FOLIUM:
        tiles_map = {
            "OpenStreetMap":      "OpenStreetMap",
            "CartoDB Positron":   "CartoDB positron",
            "CartoDB Dark Matter":"CartoDB dark_matter",
        }

        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            tiles=tiles_map[map_tile],
            control_scale=True,
            prefer_canvas=True,
        )

        for _, row in df_map.iterrows():
            confirmed  = int(row["Confirmed"])  if pd.notna(row["Confirmed"])  else 0
            deaths     = int(row["Deaths"])     if pd.notna(row["Deaths"])     else 0
            recovered  = int(row["Recovered"]) if pd.notna(row.get("Recovered")) else 0
            cfr        = float(row.get("CFR (%)", 0) or 0)
            casi_100k  = row.get("Casi per 100k")
            casi_100k  = "N/D" if (casi_100k is None or (isinstance(casi_100k, float) and np.isnan(casi_100k))) else f"{casi_100k:,.1f}"

            popup_html = f"""
            <div style="font-family:'DM Sans',sans-serif;font-size:13px;
                        min-width:190px;color:#1a1a2e;">
                <b style="font-size:14px;color:#1e3a5f;">
                    {row['Country/Region']}
                </b>
                <hr style="margin:6px 0;border-color:#e2e8f0;">
                <table style="width:100%;border-collapse:collapse;">
                    <tr><td style="color:#64748b;padding:2px 0;">Confermati</td>
                        <td style="text-align:right;font-weight:600;">{confirmed:,}</td></tr>
                    <tr><td style="color:#64748b;padding:2px 0;">Decessi</td>
                        <td style="text-align:right;font-weight:600;color:#ef4444;">{deaths:,}</td></tr>
                    <tr><td style="color:#64748b;padding:2px 0;">Guariti</td>
                        <td style="text-align:right;font-weight:600;color:#10b981;">{recovered:,}</td></tr>
                    <tr><td style="color:#64748b;padding:2px 0;">CFR</td>
                        <td style="text-align:right;font-weight:600;color:#f59e0b;">{cfr:.2f}%</td></tr>
                    <tr><td style="color:#64748b;padding:2px 0;">/100k ab.</td>
                        <td style="text-align:right;">{casi_100k}</td></tr>
                </table>
            </div>
            """

            folium.Circle(
                location=[row["lat"], row["lon"]],
                radius=row["radius_m"],
                color=row["circle_color"],
                fill=True,
                fill_color=row["circle_color"],
                fill_opacity=0.35,
                weight=1.5,
                popup=folium.Popup(popup_html, max_width=240),
                tooltip=f"<b>{row['Country/Region']}</b>: {confirmed:,} casi",
            ).add_to(m)

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=5,
                color=row["circle_color"],
                fill=True,
                fill_color=row["circle_color"],
                fill_opacity=0.95,
                weight=1,
            ).add_to(m)

        # Legenda dark coerente col tema
        legend_html = f"""
        <div style="position:fixed;bottom:28px;left:28px;z-index:1000;
                    background:rgba(17,34,64,0.95);padding:14px 18px;
                    border-radius:10px;font-size:12px;
                    font-family:'DM Sans',sans-serif;
                    box-shadow:0 4px 20px rgba(0,0,0,0.5);
                    border:1px solid rgba(59,130,246,0.25);color:#c8d8f0;">
            <div style="font-weight:700;margin-bottom:8px;color:#e8f1ff;">
                {map_metrica}
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
                <span style="width:12px;height:12px;border-radius:50%;
                             background:#22c55e;display:inline-block;"></span> Basso
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">
                <span style="width:12px;height:12px;border-radius:50%;
                             background:#eab308;display:inline-block;"></span> Medio
            </div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <span style="width:12px;height:12px;border-radius:50%;
                             background:#ef4444;display:inline-block;"></span> Alto
            </div>
            <div style="color:#4a6a99;font-size:10px;border-top:1px solid rgba(59,130,246,0.15);
                        padding-top:6px;">
                Raggio {'logaritmico' if map_scala == 'Log' else 'lineare'}
            </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        map_slot.empty()
        with map_slot.container():
            st_folium(m, use_container_width=True, height=560, returned_objects=[])

    else:
        map_slot.empty()
        st.warning(
            "Folium non installato. Esegui: `pip install folium streamlit-folium`"
        )
        with map_slot.container():
            st.map(
                df_map[["lat", "lon"]].rename(columns={"lat": "latitude", "lon": "longitude"}),
                use_container_width=True,
            )

    # ── Tabella sotto la mappa ────────────────────────────────────────────────
    with st.expander("Dati tabellari", expanded=False):
        show_cols = ["Country/Region", "Confirmed", "Deaths", "Recovered", "CFR (%)"]
        if "Casi per 100k" in df_map.columns:
            show_cols.append("Casi per 100k")
        df_show = (
            df_map[show_cols]
            .sort_values("Confirmed", ascending=False)
            .reset_index(drop=True)
        )
        df_show.index += 1
        st.dataframe(df_show, use_container_width=True, height=380)
        csv_map = df_show.to_csv(index=False).encode("utf-8")
        st.download_button(
            "↓ Scarica CSV",
            csv_map,
            f"pandora_mappa_{map_data}.csv",
            "text/csv",
        )
