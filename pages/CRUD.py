"""
Pagina 4 — CRUD Completo + JOIN
========================================
Tutte le operazioni CRUD usano query MongoDB native:
  READ   -> find() con $eq, $regex, $gte, $lte + skip/limit server-side
  CREATE -> insert_one()
  UPDATE -> find_records_for_edit() + update_one() con $set
  DELETE -> find_records_for_edit() + delete_one() / delete_many()
  JOIN   -> $lookup per unire collection serie e paesi
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime

st.set_page_config(page_title="Operazioni CRUD", layout="wide", initial_sidebar_state="collapsed")

from utils.styles import apply_dark_theme
apply_dark_theme()
from utils.navbar import render_top_navbar

render_top_navbar("Gestione Dati")
st.markdown('<p class="pandora-title" style="font-size:2rem;">CRUD — Gestione Dati</p>', unsafe_allow_html=True)
st.markdown('<p class="pandora-sub">Crea, Leggi, Aggiorna, Elimina record COVID-19</p>', unsafe_allow_html=True)

from utils.db import insert_record, update_record, delete_record, mongo_available, _try_mongo, load_timeseries, load_pivoted, retry_mongo
from utils.queries import get_countries, count_records, query_records, find_records_for_edit

mongo_ok = mongo_available()
paesi    = get_countries()

if not mongo_ok:
    col_warn, col_btn = st.columns([5, 1])
    with col_warn:
        st.warning(
            "**MongoDB non connesso** — Le operazioni di scrittura (Create/Update/Delete) "
            "non sono disponibili. La lettura funziona tramite i file CSV."
        )
    with col_btn:
        if st.button("Riconnetti", key="crud_retry_mongo"):
            with st.spinner("Connessione a MongoDB in corso..."):
                if retry_mongo():
                    st.success("MongoDB connesso!")
                    st.rerun()
                else:
                    st.error("Connessione fallita. Assicurati che MongoDB sia in esecuzione.")

# ── TAB ──────────────────────────────────────────────────────────────────────
tab_r, tab_c, tab_u, tab_d, tab_j = st.tabs([
    " READ ",
    " CREATE ",
    " UPDATE ",
    " DELETE ",
    " JOIN ",
])

#______________________________________________________________________________
# READ  — find() con filtri MongoDB + paginazione skip/limit server-side

with tab_r:
    st.subheader("READ")

    r1, r2, r3, r4 = st.columns(4)
    with r1:
        r_paese = st.selectbox("Paese", ["Tutti"] + paesi, key="r_paese")
    with r2:
        r_min_date = st.date_input("Data inizio", value=date(2020, 1, 22), key="r_min")
    with r3:
        r_max_date = st.date_input("Data fine", value=date(2021, 5, 29), key="r_max")
    with r4:
        r_min_cases = st.number_input("Casi minimi (>=)", min_value=0, value=0, step=100, key="r_cases")

    rc1, rc2, rc3 = st.columns([2, 1, 1])
    with rc1:
        r_provincia = st.text_input("Provincia/Stato (regex)", "", key="r_prov",
                                    help="Supporta regex. Es: ^New")
    with rc2:
        r_sort_opt = st.selectbox(
            "Ordina per",
            ["Date (desc)", "Date (asc)", "Confirmed (desc)", "Deaths (desc)", "Country/Region (asc)"],
            key="r_sort",
        )
    with rc3:
        r_limit = st.selectbox("Record per pagina", [25, 50, 100, 200, 500], key="r_limit")

    sort_map = {
        "Date (desc)":          ("Date",           False),
        "Date (asc)":           ("Date",           True),
        "Confirmed (desc)":     ("Confirmed",      False),
        "Deaths (desc)":        ("Deaths",         False),
        "Country/Region (asc)": ("Country/Region", True),
    }
    sort_field, sort_asc = sort_map[r_sort_opt]

    # count_documents() — conta senza trasferire dati
    total = count_records(
        paese=r_paese,
        provincia=r_provincia,
        date_from=r_min_date,
        date_to=r_max_date,
        min_confirmed=r_min_cases,
    )

    st.markdown(
        f"**{total:,} record trovati** "
        f"<span style='color:#8a9abf;font-size:0.8rem;'>"
        f"(paese={r_paese!r}, date=[{r_min_date} → {r_max_date}], confirmed>={r_min_cases})"
        f"</span>",
        unsafe_allow_html=True,
    )

    if total > 0:
        n_pages = max(1, (total - 1) // r_limit + 1)
        page = st.number_input("Pagina", min_value=1, max_value=n_pages, value=1, key="r_page")
        skip = (page - 1) * r_limit

        # find() con skip/limit — trasferisce solo i record della pagina
        df_page = query_records(
            paese=r_paese,
            provincia=r_provincia,
            date_from=r_min_date,
            date_to=r_max_date,
            min_confirmed=r_min_cases,
            sort_field=sort_field,
            sort_asc=sort_asc,
            skip=skip,
            limit=r_limit,
        )
        df_page = df_page.reset_index(drop=True)
        df_page.index = df_page.index + skip + 1

        st.dataframe(df_page, use_container_width=True, height=480)
        st.caption(
            f"Pagina {page} di {n_pages} — "
            f"Record {skip+1}–{min(skip+r_limit, total):,} di {total:,}"
        )

        #if st.button("Esporta tutti i risultati (CSV)"):
            #df_all = query_records(
                #paese=r_paese, provincia=r_provincia,
                #date_from=r_min_date, date_to=r_max_date,
                #min_confirmed=r_min_cases,
                #sort_field=sort_field, sort_asc=sort_asc,
                #skip=0, limit=total,
            #)
            #csv_data = df_all.to_csv(index=False).encode("utf-8")
            #st.download_button("Scarica CSV", csv_data, "pandora_export.csv", "text/csv")
    #else:
        #st.info("Nessun record corrisponde ai filtri.")'''

# CREATE
#______________________________________________________________________________
with tab_c:
    st.subheader("CREATE")

    if not mongo_ok:
        st.error("MongoDB non disponibile. Impossibile creare record.")
    else:
        with st.form("crud_create", clear_on_submit=True):
            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                c_data = st.date_input("Data", value=date.today(), key="c_data",
                                       min_value=date(2019, 12, 1), max_value=date.today())
                c_paese = st.selectbox("Paese *", [""] + paesi, key="c_paese")
            with cc2:
                c_prov = st.text_input("Provincia", key="c_prov")
                c_conf = st.number_input("Confermati", min_value=0, value=0, key="c_conf")
            with cc3:
                c_deaths = st.number_input("Decessi", min_value=0, value=0, key="c_deaths")
                c_rec = st.number_input("Guariti", min_value=0, value=0, key="c_rec")

            c_submit = st.form_submit_button("Crea", use_container_width=True)

        if c_submit:
            if not c_paese:
                st.error("Il paese è obbligatorio.")
            elif c_deaths > c_conf:
                st.error("Decessi > Confermati non è valido.")
            else:
                rec = {
                    "Date": datetime.combine(c_data, datetime.min.time()),
                    "Country/Region": c_paese,
                    "Province/State": c_prov if c_prov else None,
                    "Confirmed": c_conf,
                    "Deaths": c_deaths,
                    "Recovered": c_rec,
                }
                if insert_record(rec):
                    st.success("Record creato con successo!")
                else:
                    st.error("Errore nella creazione.")


# UPDATE  — find() per il preview + update_one() con $set
#______________________________________________________________________________
with tab_u:
    st.subheader("UPDATE")
    #st.caption("Cerca con `find()` → seleziona il record → modifica con `update_one({ filtro }, { $set: {...} })`")

    if not mongo_ok:
        st.error("MongoDB non disponibile. Impossibile modificare record.")
    else:
        st.markdown("**1. Cerca il record da modificare:**")
        uc1, uc2, uc3 = st.columns(3)
        with uc1:
            u_paese = st.selectbox("Paese", paesi, key="u_paese")
        with uc2:
            u_data = st.date_input("Data esatta", value=date(2021, 5, 29), key="u_data")
        with uc3:
            u_prov = st.text_input("Provincia (vuoto = tutte)", key="u_prov")

        if st.button("Cerca record", key="u_search"):
            st.session_state["u_search_done"] = True

        if st.session_state.get("u_search_done", False):
            # find() MongoDB per anteprima
            found = find_records_for_edit(u_paese, u_data, u_prov if u_prov else None)

            if found.empty:
                st.info("Nessun record trovato. Modifica i criteri e riprova.")
            else:
                st.success(f"Trovati **{len(found)}** record:")
                st.dataframe(found, use_container_width=True)

                # Se ci sono più record, permetti di selezionarne uno
                if len(found) > 1:
                    st.markdown("**2. Seleziona il record da modificare:**")
                    options = []
                    for i, row in found.iterrows():
                        prov_label = row.get("Province/State", "") or "nazionale"
                        conf_label = int(row["Confirmed"]) if pd.notna(row["Confirmed"]) else 0
                        options.append(f"#{i} — {prov_label} — Confermati: {conf_label:,}")
                    sel_idx = st.selectbox("Record", range(len(options)),
                                          format_func=lambda x: options[x], key="u_sel_idx")
                    row = found.iloc[sel_idx]
                else:
                    row = found.iloc[0]

                # Valori attuali
                cur_conf = int(row["Confirmed"]) if pd.notna(row.get("Confirmed")) else 0
                cur_deaths = int(row["Deaths"]) if pd.notna(row.get("Deaths")) else 0
                cur_rec = int(row["Recovered"]) if pd.notna(row.get("Recovered")) else 0
                cur_prov = row.get("Province/State", "") or ""

                st.markdown("**3. Inserisci i nuovi valori (`$set`):**")
                with st.form("crud_update"):
                    eu1, eu2, eu3 = st.columns(3)
                    with eu1:
                        new_conf = st.number_input("Confermati", min_value=0,
                                                    value=cur_conf, key="u_conf")
                    with eu2:
                        new_deaths = st.number_input("Decessi", min_value=0,
                                                      value=cur_deaths, key="u_deaths")
                    with eu3:
                        new_rec = st.number_input("Guariti", min_value=0,
                                                    value=cur_rec, key="u_rec")
                    u_submit = st.form_submit_button("Aggiorna con $set", use_container_width=True)

                if u_submit:
                    if new_deaths > new_conf:
                        st.error("Decessi > Confermati non è valido.")
                    else:
                        filtro = {
                            "Country/Region": u_paese,
                            "Date": datetime.combine(u_data, datetime.min.time()),
                        }
                        # Se c'è una provincia specifica, aggiungiamo al filtro
                        if cur_prov:
                            filtro["Province/State"] = cur_prov
                        aggiornamento = {
                            "Confirmed": new_conf,
                            "Deaths": new_deaths,
                            "Recovered": new_rec,
                        }
                        if update_record(filtro, aggiornamento):
                            st.success(
                                f"Record aggiornato con `update_one()` + `$set` ✔\n\n"
                                f"Filtro: `{filtro}`\n\n"
                                f"$set: `{aggiornamento}`"
                            )
                            st.session_state["u_search_done"] = False
                            st.rerun()
                        else:
                            st.error("Nessun documento modificato — controlla i criteri.")

# DELETE  — find() per il preview + delete_one() / delete_many()
#______________________________________________________________________________
    st.subheader("DELETE")
    st.caption("Cerca con `find()` → elimina con `delete_one()` o `delete_many()`.")

    if not mongo_ok:
        st.error("MongoDB non disponibile. Impossibile eliminare record.")
    else:
        st.warning(" L'eliminazione è **permanente**. Procedi con cautela.")

        dc1, dc2, dc3 = st.columns(3)
        with dc1:
            d_paese = st.selectbox("Paese", paesi, key="d_paese")
        with dc2:
            d_data = st.date_input("Data esatta", value=date(2021, 5, 29), key="d_data")
        with dc3:
            d_prov = st.text_input("Provincia (vuoto = nazionale)", key="d_prov")

        d_many = st.checkbox(
            "Usa `delete_many()` — elimina tutti i record corrispondenti",
            key="d_many",
        )

        # find() per anteprima dei documenti da eliminare
        found_d = find_records_for_edit(d_paese, d_data, d_prov if d_prov else None)

        if found_d.empty:
            st.info("Nessun record trovato.")
        else:
            st.dataframe(found_d, use_container_width=True)
            n_found = len(found_d)
            st.markdown(
                f"Verranno eliminati **{n_found}** documento/i con "
                f"`{'delete_many' if d_many else 'delete_one'}()`."
            )

            conferma = st.checkbox(
                f"Confermo di voler eliminare {n_found} record/s", key="d_confirm"
            )

            if st.button("Elimina", type="primary", disabled=not conferma):
                filtro = {
                    "Country/Region": d_paese,
                    "Date":           datetime.combine(d_data, datetime.min.time()),
                    "Province/State": d_prov if d_prov else None,
                }
                eliminati = delete_record(filtro, delete_many=d_many)
                if eliminati > 0:
                    st.success(f"Eliminati **{eliminati}** documento/i ✔")
                    st.rerun()
                else:
                    st.error("Nessun documento eliminato.")


# JOIN  — $lookup per unire le collection serie e paesi
#______________________________________________________________________________
with tab_j:
    st.subheader("JOIN")
    st.caption(
        "Unisce la collection **serie** (dati dettagliati per paese/data) "
        "con la collection **paesi** (dati pivotati 8 paesi chiave) "
        "tramite `$lookup` (MongoDB) o `pd.merge()` (fallback pandas)."
    )

    st.markdown("""
    | Collection | Contenuto | Struttura |
    |---|---|---|
    | `serie` | Dati giornalieri per **tutti** i paesi | Date, Country/Region, Province/State, Confirmed, Deaths, Recovered |
    | `paesi` | Dati pivotati per **8 paesi chiave** | Date, China, US, United\_Kingdom, Italy, France, Germany, Spain, Iran |

    """)

    # Mappa nomi serie -> colonna pivotata
    SERIE_TO_PIVOT = {
        "China": "China", "US": "US", "United Kingdom": "United_Kingdom",
        "Italy": "Italy", "France": "France", "Germany": "Germany",
        "Spain": "Spain", "Iran": "Iran",
    }

    jc1, jc2, jc3 = st.columns(3)
    with jc1:
        j_paese = st.selectbox(
            "Paese", list(SERIE_TO_PIVOT.keys()),
            index=list(SERIE_TO_PIVOT.keys()).index("Italy"), key="j_paese",
        )
    with jc2:
        j_date_from = st.date_input("Da", value=date(2020, 3, 1), key="j_from")
    with jc3:
        j_date_to = st.date_input("A", value=date(2020, 4, 30), key="j_to")

    pivot_col = SERIE_TO_PIVOT[j_paese]

    if st.button("Esegui JOIN", key="j_run", type="primary"):
        import plotly.graph_objects as go

        df_join = pd.DataFrame()
        method_used = ""

        # ── Tentativo 1: $lookup nativo MongoDB ──────────────────────────────
        if mongo_ok:
            try:
                db = _try_mongo()
                if db is not None:
                    dt_from = datetime.combine(j_date_from, datetime.min.time())
                    dt_to = datetime.combine(j_date_to, datetime.max.time())

                    pipeline = [
                        {"$match": {
                            "Country/Region": j_paese,
                            "Date": {"$gte": dt_from, "$lte": dt_to},
                        }},
                        {"$group": {
                            "_id": "$Date",
                            "Confirmed_serie": {"$sum": "$Confirmed"},
                            "Deaths_serie": {"$sum": "$Deaths"},
                            "Recovered_serie": {"$sum": "$Recovered"},
                        }},
                        {"$lookup": {
                            "from": "paesi",
                            "localField": "_id",
                            "foreignField": "Date",
                            "as": "pivot",
                        }},
                        {"$unwind": {"path": "$pivot", "preserveNullAndEmptyArrays": True}},
                        {"$project": {
                            "_id": 0,
                            "Date": "$_id",
                            "Confirmed_serie": 1,
                            "Deaths_serie": 1,
                            "Recovered_serie": 1,
                            "Confirmed_paesi": f"$pivot.{pivot_col}",
                        }},
                        {"$sort": {"Date": 1}},
                    ]
                    results = list(db.serie.aggregate(pipeline))
                    if results:
                        df_join = pd.DataFrame(results)
                        df_join["Date"] = pd.to_datetime(df_join["Date"])
                        method_used = "`$lookup` nativo MongoDB"

                        # Verifica che la join abbia effettivamente prodotto dati paesi
                        if "Confirmed_paesi" not in df_join.columns or df_join["Confirmed_paesi"].isna().all():
                            df_join = pd.DataFrame()  # forza fallback
            except Exception:
                pass

        # ── Tentativo 2: fallback pandas merge (funziona sempre) ─────────────
        if df_join.empty:
            df_serie_full = load_timeseries()
            df_piv = load_pivoted()

            # Aggrega serie per Country+Date
            df_s = df_serie_full[df_serie_full["Country/Region"] == j_paese].copy()
            df_s = (
                df_s.groupby("Date", as_index=False)
                .agg(Confirmed_serie=("Confirmed", "sum"),
                     Deaths_serie=("Deaths", "sum"),
                     Recovered_serie=("Recovered", "sum"))
                .sort_values("Date")
            )

            # Filtra per range date
            dt_from_pd = pd.Timestamp(j_date_from)
            dt_to_pd = pd.Timestamp(j_date_to)
            df_s = df_s[(df_s["Date"] >= dt_from_pd) & (df_s["Date"] <= dt_to_pd)]

            # Estrai colonna dal pivotato
            df_p = df_piv[["Date", pivot_col]].rename(columns={pivot_col: "Confirmed_paesi"})

            # INNER JOIN su Date
            df_join = pd.merge(df_s, df_p, on="Date", how="inner")
            method_used = "`pd.merge(on='Date', how='inner')` — fallback pandas"

        # ── Risultati ─────────────────────────────────────────────────────────
        if df_join.empty:
            st.warning("Nessun risultato. Verifica che entrambe le sorgenti contengano dati per il periodo selezionato.")
        else:
            df_join = df_join.sort_values("Date").reset_index(drop=True)
            df_join["Differenza"] = df_join["Confirmed_serie"] - df_join["Confirmed_paesi"]

            st.success(
                f"**{len(df_join)}** record trovati — metodo: {method_used}"
            )

            # ── Pipeline $lookup di riferimento ──────────────────────────────
            with st.expander("🔧 Pipeline MongoDB `$lookup`"):
                st.code(f"""db.serie.aggregate([
    {{ "$match": {{ "Country/Region": "{j_paese}",
                   "Date": {{ "$gte": ISODate("{j_date_from}"),
                              "$lte": ISODate("{j_date_to}") }} }} }},
    {{ "$group": {{ "_id": "$Date",
                   "Confirmed_serie": {{ "$sum": "$Confirmed" }},
                   "Deaths_serie":    {{ "$sum": "$Deaths" }},
                   "Recovered_serie": {{ "$sum": "$Recovered" }} }} }},
    {{ "$lookup": {{ "from":         "paesi",
                    "localField":   "_id",
                    "foreignField": "Date",
                    "as":           "pivot" }} }},
    {{ "$unwind": {{ "path": "$pivot",
                    "preserveNullAndEmptyArrays": true }} }},
    {{ "$project": {{ "_id": 0, "Date": "$_id",
                     "Confirmed_serie": 1, "Deaths_serie": 1,
                     "Recovered_serie": 1,
                     "Confirmed_paesi": "$pivot.{pivot_col}" }} }},
    {{ "$sort": {{ "Date": 1 }} }}
])""", language="javascript")

            # ── Tabella ──────────────────────────────────────────────────────
            df_show = df_join.copy()
            df_show.columns = [c.replace("_", " ").title() if c != "Date" else c for c in df_show.columns]
            st.dataframe(df_show, use_container_width=True, height=400)
