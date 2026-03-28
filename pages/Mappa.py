"""
Pagina 1 — Mappa Interattiva COVID-19
Visualizza i dati su una mappa Leaflet (OpenStreetMap) con cerchi/buffer
proporzionali ai casi.  Fallback su st.map se folium non è installato.
"""

import streamlit as st
import pandas as pd
import numpy as np

# Prova ad importare folium; se non c'è, fallback su st.map
try:
    import folium
    from streamlit_folium import st_folium
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

st.set_page_config(page_title="Mappa Interattiva", page_icon="🗺️", layout="wide", initial_sidebar_state="collapsed")

from utils.styles import apply_dark_theme, apply_plotly_dark
#apply_dark_theme()
#apply_plotly_dark()
from utils.navbar import render_top_navbar

render_top_navbar("Mappa")
st.markdown('<p class="pandora-title" style="font-size:2rem;"> Mappa Interattiva</p>', unsafe_allow_html=True)
st.markdown('<p class="pandora-sub">Visualizzazione geospaziale dei dati pandemici — Leaflet / OpenStreetMap</p>', unsafe_allow_html=True)

# ── Caricamento dati ──────────────────────────────────────────────────────────
from utils.db import COUNTRY_COORDS, POPULATION
from utils.queries import aggregate_map_snapshot, get_countries, get_date_range

# Range di date tramite aggregazione MongoDB ($group min/max)
min_date, max_date = get_date_range()
# Lista paesi tramite distinct()
tutti_paesi = get_countries()

# ── Sidebar filtri ────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filtri Mappa")

    metrica = st.selectbox(
        "Metrica da visualizzare",
        ["Confirmed", "Deaths", "Recovered", "CFR (%)"],
        index=0,
    )

    data_sel = st.date_input(
        "Data snapshot",
        value=max_date,
        min_value=min_date,
        max_value=max_date,
    )

    min_casi = st.number_input("Casi minimi", min_value=0, value=0, step=100)

    paesi_sel = st.multiselect(
        "Filtra paesi (vuoto = tutti)",
        tutti_paesi,
        default=[],
    )

    st.divider()
    scala = st.radio("Scala cerchi", ["Lineare", "Logaritmica"], index=1)

    st.divider()
    tile_choice = st.selectbox(
        "Stile mappa",
        ["OpenStreetMap", "CartoDB Positron", "CartoDB Dark Matter"],
        index=0,
    )

# ── Dati mappa via aggregation pipeline MongoDB ($match + $group + $addFields) ──
df_map = aggregate_map_snapshot(
    data_snapshot=data_sel,
    min_confirmed=min_casi,
    paesi=paesi_sel if paesi_sel else None,
)

# ── Arricchimento con coordinate e popolazione ────────────────────────────────
if df_map.empty:
    st.warning("Nessun dato corrisponde ai filtri selezionati.")
    st.stop()

df_map["lat"] = df_map["Country/Region"].map(lambda x: COUNTRY_COORDS.get(x, (None, None))[0])
df_map["lon"] = df_map["Country/Region"].map(lambda x: COUNTRY_COORDS.get(x, (None, None))[1])
df_map = df_map.dropna(subset=["lat", "lon"])

# Aggiungi popolazione
df_map["Popolazione (M)"] = df_map["Country/Region"].map(
    lambda x: POPULATION.get(x, None)
)
df_map["Casi per 100k"] = np.where(
    df_map["Popolazione (M)"].notna(),
    (df_map["Confirmed"] / (df_map["Popolazione (M)"] * 1e6) * 1e5).round(1),
    None,
)

# ── Colonna metrica e raggio cerchi ───────────────────────────────────────────
col_metrica = metrica

if col_metrica in df_map.columns and len(df_map) > 0:
    vals = df_map[col_metrica].fillna(0).astype(float)
    if scala == "Logaritmica":
        vals = np.log1p(vals)
    vmax = vals.max() if vals.max() > 0 else 1
    # Raggio in metri: da 30 km a 500 km proporzionale alla metrica
    df_map["radius_m"] = (vals / vmax * 500_000).clip(lower=30_000)
else:
    df_map["radius_m"] = 100_000

# ── Colore cerchi: gradiente basato sulla metrica ─────────────────────────────
df_map["color_val"] = df_map[col_metrica].fillna(0).astype(float)
cv_max = df_map["color_val"].max() if df_map["color_val"].max() > 0 else 1
df_map["norm"] = (df_map["color_val"] / cv_max).clip(0, 1)


def _circle_color(norm_val: float) -> str:
    """Gradiente: verde #22c55e (basso) → giallo #eab308 (medio) → rosso #ef4444 (alto)."""
    if norm_val < 0.5:
        t = norm_val * 2
        r = int(34 + t * (234 - 34))
        g = int(197 + t * (179 - 197))
        b = int(94 + t * (8 - 94))
    else:
        t = (norm_val - 0.5) * 2
        r = int(234 + t * (239 - 234))
        g = int(179 - t * (179 - 68))
        b = int(8 + t * (68 - 8))
    return f"#{r:02x}{g:02x}{b:02x}"


df_map["circle_color"] = df_map["norm"].apply(_circle_color)

# ── Render mappa Leaflet con Folium (o fallback st.map) ───────────────────────
if len(df_map) == 0:
    st.warning("Nessun dato corrisponde ai filtri selezionati.")
else:
    st.markdown(f"**{len(df_map)} paesi** visualizzati — Snapshot al **{data_sel}** — Metrica: **{metrica}**")

    if HAS_FOLIUM:
        # ── Mappa Leaflet / OpenStreetMap via Folium ──────────────────────────
        tiles_map = {
            "OpenStreetMap": "OpenStreetMap",
            "CartoDB Positron": "CartoDB positron",
            "CartoDB Dark Matter": "CartoDB dark_matter",
        }

        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            tiles=tiles_map[tile_choice],
            control_scale=True,
            prefer_canvas=True,
        )

        # Cerchi buffer proporzionali alla metrica
        for _, row in df_map.iterrows():
            confirmed = int(row["Confirmed"]) if pd.notna(row["Confirmed"]) else 0
            deaths = int(row["Deaths"]) if pd.notna(row["Deaths"]) else 0
            recovered = int(row["Recovered"]) if pd.notna(row.get("Recovered")) else 0
            cfr = row.get("CFR (%)", 0) if pd.notna(row.get("CFR (%)")) else 0
            casi_100k = row.get("Casi per 100k", "N/D")
            if casi_100k is None or (isinstance(casi_100k, float) and np.isnan(casi_100k)):
                casi_100k = "N/D"

            popup_html = f"""
            <div style="font-family:Inter,sans-serif;font-size:13px;min-width:180px;">
                <b style="font-size:14px;">{row['Country/Region']}</b><hr style="margin:4px 0;">
                <b>Confermati:</b> {confirmed:,}<br>
                <b>Decessi:</b> {deaths:,}<br>
                <b>Guariti:</b> {recovered:,}<br>
                <b>CFR:</b> {cfr:.2f}%<br>
                <b>Casi/100k:</b> {casi_100k}
            </div>
            """

            folium.Circle(
                location=[row["lat"], row["lon"]],
                radius=row["radius_m"],
                color=row["circle_color"],
                fill=True,
                fill_color=row["circle_color"],
                fill_opacity=0.4,
                weight=1.5,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=f"{row['Country/Region']}: {confirmed:,} casi",
            ).add_to(m)

            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=5,
                color=row["circle_color"],
                fill=True,
                fill_color=row["circle_color"],
                fill_opacity=0.9,
                weight=1,
            ).add_to(m)

        # Legenda
        legend_html = f"""
        <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                    background:rgba(255,255,255,0.92);padding:12px 16px;
                    border-radius:8px;font-size:12px;font-family:Inter,sans-serif;
                    box-shadow:0 2px 8px rgba(0,0,0,0.2);border:1px solid #ccc;">
            <b>Legenda — {metrica}</b><br>
            <i style="background:#22c55e;width:14px;height:14px;display:inline-block;
               border-radius:50%;margin-right:4px;vertical-align:middle;"></i> Basso<br>
            <i style="background:#eab308;width:14px;height:14px;display:inline-block;
               border-radius:50%;margin-right:4px;vertical-align:middle;"></i> Medio<br>
            <i style="background:#ef4444;width:14px;height:14px;display:inline-block;
               border-radius:50%;margin-right:4px;vertical-align:middle;"></i> Alto<br>
            <span style="color:#888;font-size:11px;">Raggio proporzionale
            ({scala.lower()})</span>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        st_folium(m, use_container_width=True, height=620, returned_objects=[])

    else:
        # ── Fallback: st.map (se folium non installato) ──────────────────────
        st.info("📦 Installa `folium` e `streamlit-folium` per la mappa Leaflet completa. "
                "Usa: `pip install folium streamlit-folium`")
        st.map(
            df_map[["lat", "lon"]].rename(columns={"lat": "latitude", "lon": "longitude"}),
            size=df_map["radius_m"] / 50_000,
            use_container_width=True,
        )

    # ── Tabella sotto la mappa ────────────────────────────────────────────────
    st.divider()
    st.subheader("Dati filtrati")

    show_cols = ["Country/Region", "Confirmed", "Deaths", "Recovered", "CFR (%)"]
    if "Casi per 100k" in df_map.columns:
        show_cols.append("Casi per 100k")

    df_show = df_map[show_cols].sort_values("Confirmed", ascending=False).reset_index(drop=True)
    df_show.index = df_show.index + 1

    st.dataframe(df_show, use_container_width=True, height=400)

    # Download
    csv = df_show.to_csv(index=False).encode("utf-8")
    st.download_button("Scarica CSV filtrato", csv, "pandora_mappa_dati.csv", "text/csv")
