"""
Pagina 3 — Inserimento Dati
Form per aggiungere nuovi record al database COVID-19.
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="Inserimento Dati", page_icon="➕", layout="wide", initial_sidebar_state="collapsed")

from utils.styles import apply_dark_theme
apply_dark_theme()
from utils.navbar import render_top_navbar

render_top_navbar("Inserimento")
st.markdown('<p class="pandora-title" style="font-size:2rem;">Inserimento Dati</p>', unsafe_allow_html=True)
st.markdown('<p class="pandora-sub">Aggiungi nuovi record al database COVID-19</p>', unsafe_allow_html=True)

from utils.db import insert_record, mongo_available
from utils.queries import get_countries

# distinct() su MongoDB per lista paesi
paesi = get_countries()

# ── Stato MongoDB ─────────────────────────────────────────────────────────────
if not mongo_available():
    st.warning(
        "**MongoDB non è connesso.** L'inserimento dati richiede MongoDB attivo.\n\n"
        "Assicurati che MongoDB sia in esecuzione su `localhost:27017` e che il database "
        "`mioDatabase` esista (vedi `connection.py` per l'import iniziale)."
    )

st.divider()

# ── Form di inserimento ──────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Nuovo Record")

    with st.form("insert_form", clear_on_submit=True):
        fc1, fc2 = st.columns(2)

        with fc1:
            data_ins = st.date_input(
                "Data *",
                value=date.today(),
                min_value=date(2019, 12, 1),
                max_value=date.today(),
            )

            paese = st.selectbox(
                "Paese/Regione *",
                options=[""] + paesi,
                index=0,
                help="Seleziona il paese. Campo obbligatorio.",
            )

            provincia = st.text_input(
                "Provincia/Stato",
                value="",
                help="Lascia vuoto per dati a livello nazionale.",
            )

        with fc2:
            confirmed = st.number_input(
                "Casi Confermati *",
                min_value=0,
                value=0,
                step=1,
                help="Numero cumulativo di casi confermati. Deve essere ≥ 0.",
            )

            deaths = st.number_input(
                "Decessi *",
                min_value=0,
                value=0,
                step=1,
                help="Numero cumulativo di decessi. Deve essere ≤ Confermati.",
            )

            recovered = st.number_input(
                "Guariti",
                min_value=0,
                value=0,
                step=1,
                help="Numero cumulativo di guariti. 0 se non disponibile.",
            )

        st.divider()
        submitted = st.form_submit_button("Inserisci Record", use_container_width=True)

    # Validazione e inserimento
    if submitted:
        errors = []
        if not paese:
            errors.append("Il campo **Paese** è obbligatorio.")
        if deaths > confirmed:
            errors.append("I **Decessi** non possono superare i **Casi Confermati**.")
        if recovered > confirmed:
            errors.append("I **Guariti** non possono superare i **Casi Confermati**.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            record = {
                "Date": datetime.combine(data_ins, datetime.min.time()),
                "Country/Region": paese,
                "Province/State": provincia if provincia else None,
                "Confirmed": confirmed,
                "Deaths": deaths,
                "Recovered": recovered,
            }

            if not mongo_available():
                st.error("MongoDB non disponibile. Impossibile inserire il record.")
            else:
                if insert_record(record):
                    st.success(
                        f"Record inserito con successo!\n\n"
                        f"**{paese}** — {data_ins} — "
                        f"Confermati: {confirmed:,} | Decessi: {deaths:,} | Guariti: {recovered:,}"
                    )
                    st.balloons()
                else:
                    st.error("Errore durante l'inserimento. Controlla la connessione a MongoDB.")

with col2:
    st.subheader("Regole di Validazione")
    st.markdown("""
    | Regola | Dettaglio |
    |--------|----------|
    | Data | Tra 01/12/2019 e oggi |
    | Paese | Obbligatorio |
    | Provincia | Opzionale (vuoto = nazionale) |
    | Confermati | ≥ 0, obbligatorio |
    | Decessi | ≥ 0, ≤ Confermati |
    | Guariti | ≥ 0, ≤ Confermati |
    """)

    st.divider()
    st.subheader("Ultimi record inseriti")
    # query_records con sort Date desc, limit 10
    from utils.queries import query_records
    ultimi = query_records(sort_field="Date", sort_asc=False, limit=10)
    if not ultimi.empty:
        ultimi = ultimi[["Date", "Country/Region", "Province/State", "Confirmed", "Deaths"]].reset_index(drop=True)
        ultimi.index = ultimi.index + 1
        st.dataframe(ultimi, use_container_width=True)

# ── Inserimento multiplo da CSV ──────────────────────────────────────────────
st.divider()
st.subheader("Inserimento Multiplo da File CSV")
st.markdown(
    "Carica un file CSV con le colonne: `Date`, `Country/Region`, "
    "`Province/State`, `Confirmed`, `Deaths`, `Recovered`"
)

uploaded = st.file_uploader("Carica CSV", type=["csv"])
if uploaded is not None:
    try:
        df_up = pd.read_csv(uploaded, parse_dates=["Date"])
        st.dataframe(df_up.head(20), use_container_width=True)
        st.info(f"{len(df_up)} record trovati nel file.")

        required_cols = {"Date", "Country/Region", "Confirmed", "Deaths"}
        if not required_cols.issubset(set(df_up.columns)):
            st.error(f"Colonne mancanti: {required_cols - set(df_up.columns)}")
        elif st.button("Inserisci tutti i record"):
            if not mongo_available():
                st.error("MongoDB non disponibile.")
            else:
                from utils.db import _try_mongo, load_timeseries
                db = _try_mongo()
                records = df_up.to_dict("records")
                db.serie.insert_many(records)
                load_timeseries.clear()
                st.success(f"{len(records)} record inseriti con successo!")
                st.balloons()
    except Exception as e:
        st.error(f"❌ Errore nella lettura del file: {e}")
