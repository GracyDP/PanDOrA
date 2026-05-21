"""
Modulo di connessione dati — PanDOrA
 
Gestisce la connessione a MongoDB (singleton, auto-inizializzazione),
i dati statici (coordinate da JSON, popolazione),
il caricamento bulk dei CSV e le operazioni di scrittura (INSERT/UPDATE/DELETE).

All'import del modulo la connessione viene tentata automaticamente e,
se il DB è vuoto, i CSV vengono importati senza bisogno di lanciare script esterni.

Tutte le query di lettura e aggregazione si trovano in utils/queries.py.
Se MongoDB non è raggiungibile, ogni funzione ricade sul CSV locale.
"""

import json
import os
import pandas as pd
import streamlit as st
from datetime import datetime, date as date_type
from pathlib import Path


# ── Coordinate paesi (caricate da JSON) ───────────────────────────────────────
_COORDS_PATH = Path(__file__).parent / "country_coords.json"

def _load_coords() -> dict:
    """Carica coordinate da utils/country_coords.json → dict {nome: (lat, lon)}."""
    try:
        with open(_COORDS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return {k: tuple(v) for k, v in raw.items()}
    except FileNotFoundError:
        print(f"[WARN] File coordinate non trovato: {_COORDS_PATH}")
        return {}

COUNTRY_COORDS: dict = _load_coords()


# ── Popolazione 2020 (milioni) — World Bank ───────────────────────────────────
POPULATION = {
    "US": 331.0, "Italy": 60.4, "China": 1439.3, "Spain": 46.8,
    "Germany": 83.8, "Iran": 83.9, "France": 65.3,
    "United Kingdom": 67.9, "United_Kingdom": 67.9,
    "Brazil": 212.6, "India": 1380.0, "Russia": 145.9,
    "Mexico": 128.9, "Peru": 32.9, "South Africa": 59.3,
    "Colombia": 50.9, "Argentina": 45.2, "Turkey": 84.3,
    "Indonesia": 273.5, "Pakistan": 220.9, "Japan": 126.5,
    "Canada": 37.7, "Australia": 25.5, "South Korea": 51.8,
    "Egypt": 102.3, "Nigeria": 206.1, "Bangladesh": 164.7,
}


 
# CONNESSIONE MONGODB — singleton con auto-inizializzazione
 

_mongo_db = None          # cache: l'oggetto Database (o None se non raggiungibile)
_mongo_checked = False    # True dopo il primo tentativo di connessione


def _try_mongo():
    """
    Restituisce l'oggetto database MongoDB (singleton).
    
    Al primo tentativo:
      1. Prova la connessione a MongoDB su localhost:27017
      2. Se riesce, chiama _init_database() per creare indici e importare
         i CSV solo quando le collezioni sono vuote
      3. Caching del risultato: le chiamate successive non ripetono la connessione
    
    Se la connessione fallisce, si può riprovare con retry_mongo().
    
    IMPORTANTE: MongoDB deve essere già in esecuzione (avvia mongod o MongoDB Compass prima).
    """
    global _mongo_db, _mongo_checked

    if _mongo_checked:
        return _mongo_db          # già provato (può essere None se non disponibile)

    _mongo_checked = True
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
        client.server_info()       # forza handshake per verificare la connessione
        _mongo_db = client["mioDatabase"]
        _init_database(_mongo_db)  # crea indici e importa CSV se il DB è vuoto
        print("[PanDOrA] ✓ MongoDB connesso e pronto.")
    except Exception as e:
        _mongo_db = None
        print(f"[PanDOrA] ✗ MongoDB non raggiungibile: {e}")
        print("[PanDOrA]   Avvia mongod o MongoDB Compass, poi premi 'Riconnetti MongoDB'.")

    return _mongo_db


def _init_database(db):
    """
    Inizializza il database MongoDB in modo completamente idempotente:
      - Crea l'indice unico su (Date, Country/Region, Province/State)
      - Importa i CSV con upsert — mai insert_many cieco, mai duplicati
      - Sicuro da chiamare N volte: se i dati esistono già non fa nulla

    Province/State può essere null: MongoDB tratta null come valore normale
    nell'indice unico, quindi due documenti con Province/State=null ma stesso
    Date+Country sarebbero considerati DIVERSI. Per questo normalizziamo
    Province/State a stringa vuota "" prima dell'upsert, così l'indice funziona.
    """

    # ── 1. Indice unico — protezione definitiva contro i duplicati ────────────
    # drop_dups=False: se esistono già duplicati, create_index fallisce (non li
    # elimina silenziosamente). Il nome fisso rende l'operazione idempotente:
    # MongoDB non ricrea un indice con lo stesso nome se esiste già.
    existing_indexes = {idx["name"] for idx in db.serie.list_indexes()}
    if "unique_record_idx" not in existing_indexes:
        try:
            db.serie.create_index(
                [("Date", 1), ("Country/Region", 1), ("Province/State", 1)],
                unique=True,
                name="unique_record_idx",
            )
            print("[PanDOrA] Indice unico creato su (Date, Country/Region, Province/State).")
        except Exception as e:
            print(f"[PanDOrA] WARN creazione indice: {e}")
    else:
        print("[PanDOrA] Indice unico già presente — skip.")

    # ── 2. Indice su paesi.Date — ottimizza la JOIN $lookup ───────────────────
    existing_paesi_idx = {idx["name"] for idx in db.paesi.list_indexes()}
    if "paesi_date_idx" not in existing_paesi_idx:
        try:
            db.paesi.create_index([("Date", 1)], name="paesi_date_idx")
            print("[PanDOrA] Indice paesi.Date creato.")
        except Exception as e:
            print(f"[PanDOrA] WARN indice paesi: {e}")

    # ── Helper: normalizza Province/State a "" se null/NaN ───────────────────
    def _norm_prov(val) -> str:
        """Converte NaN/None/NaT in stringa vuota per l'indice unico."""
        if val is None:
            return ""
        try:
            import math
            if isinstance(val, float) and math.isnan(val):
                return ""
        except Exception:
            pass
        return str(val).strip()

    # ── 3. Import serie temporale — upsert idempotente ────────────────────────
    csv_serie = "csv/time-series-19-covid-combined.csv"
    if not os.path.exists(csv_serie):
        print(f"[PanDOrA] CSV {csv_serie} non trovato — import serie saltato.")
    else:
        n_existing = db.serie.count_documents({})
        if n_existing > 0:
            # Conta righe CSV per confronto rapido senza reimportare tutto
            import subprocess
            try:
                result = subprocess.run(
                    ["wc", "-l", csv_serie], capture_output=True, text=True
                )
                n_csv = int(result.stdout.strip().split()[0]) - 1  # -1 per header
            except Exception:
                n_csv = None

            if n_csv is not None and abs(n_existing - n_csv) < 10:
                # Differenza trascurabile: DB già allineato con il CSV
                print(f"[PanDOrA] Collection 'serie' già popolata "
                      f"({n_existing:,} doc, CSV ~{n_csv:,} righe) — import saltato.")
            else:
                # Differenza significativa: qualcuno ha modificato il CSV
                # Riesegui upsert solo sui record mancanti
                print(f"[PanDOrA] Differenza rilevata (DB={n_existing:,}, "
                      f"CSV~{n_csv}) — upsert differenziale in corso...")
                _upsert_serie(db, csv_serie, _norm_prov)
        else:
            # DB vuoto: import completo
            print("[PanDOrA] Collection 'serie' vuota — import CSV in corso...")
            _upsert_serie(db, csv_serie, _norm_prov)

    # ── 4. Import paesi pivotati — insert_many protetto da count ─────────────
    csv_paesi = "csv/key-countries-pivoted.csv"
    if not os.path.exists(csv_paesi):
        print(f"[PanDOrA] CSV {csv_paesi} non trovato — import paesi saltato.")
    else:
        if db.paesi.count_documents({}) == 0:
            df = pd.read_csv(csv_paesi, parse_dates=["Date"])
            db.paesi.insert_many(df.to_dict("records"))
            print(f"[PanDOrA] Importati {len(df):,} record nella collection 'paesi'.")
        else:
            print("[PanDOrA] Collection 'paesi' già popolata — import saltato.")


def _upsert_serie(db, csv_path: str, norm_prov_fn) -> None:
    """
    Importa il CSV della serie temporale con update_one + upsert=True.
    Usa ordered=False per continuare anche in caso di conflitti di indice.
    È sicuro da eseguire più volte: record già presenti vengono solo aggiornati
    (stesso risultato), record nuovi vengono inseriti.
    """
    df = pd.read_csv(csv_path, parse_dates=["Date"])

    # Normalizza Province/State: null → "" per coerenza con l'indice unico
    df["Province/State"] = df["Province/State"].apply(norm_prov_fn)

    # Costruisce lista di operazioni bulk upsert
    from pymongo import UpdateOne
    operations = []
    for rec in df.to_dict("records"):
        filt = {
            "Date":             rec["Date"],
            "Country/Region":   rec["Country/Region"],
            "Province/State":   rec["Province/State"],  # ora sempre stringa
        }
        operations.append(UpdateOne(filt, {"$set": rec}, upsert=True))

    if operations:
        # bulk_write è molto più veloce di N update_one sequenziali
        result = db.serie.bulk_write(operations, ordered=False)
        print(f"[PanDOrA] bulk_write completato: "
              f"{result.upserted_count} inseriti, "
              f"{result.modified_count} aggiornati, "
              f"{result.matched_count} già presenti.")



# CARICAMENTO BULK (usato per grafici che necessitano l'intera serie)


@st.cache_data(ttl=300)
def load_timeseries() -> pd.DataFrame:
    """
    Carica l'intera serie temporale (MongoDB oppure CSV).
    Usata SOLO per grafici che necessitano di tutti i dati.
    Per filtri e CRUD usa query_records() / count_records().
    """
    db = _try_mongo()
    if db is not None:
        try:
            data = list(db.serie.find({}, {"_id": 0}))
            if data:
                df = pd.DataFrame(data)
                df["Date"] = pd.to_datetime(df["Date"])
                return df
        except Exception:
            pass

    df = pd.read_csv("csv/time-series-19-covid-combined.csv", parse_dates=["Date"])
    return df


@st.cache_data(ttl=300)
def load_pivoted() -> pd.DataFrame:
    """Carica i dati pivotati 8 paesi (MongoDB oppure CSV)."""
    db = _try_mongo()
    if db is not None:
        try:
            data = list(db.paesi.find({}, {"_id": 0}))
            if data:
                df = pd.DataFrame(data)
                df["Date"] = pd.to_datetime(df["Date"])
                return df
        except Exception:
            pass

    df = pd.read_csv("csv/key-countries-pivoted.csv", parse_dates=["Date"])
    return df



# CRUD — CREATE / UPDATE / DELETE


def insert_record(record: dict) -> bool:
    """
    Inserisce/aggiorna un documento usando update_one con upsert=True.
    Province/State viene normalizzato a "" (stringa vuota) per coerenza
    con l'indice unico — evita duplicati con Province/State=null vs "".
    Invalida la cache dopo l'operazione.
    """
    db = _try_mongo()
    if db is None:
        return False
    try:
        # Normalizza Province/State: None/NaN → "" per coerenza con l'indice
        prov = record.get("Province/State") or ""
        record["Province/State"] = prov

        filter_query = {
            "Date":             record["Date"],
            "Country/Region":   record["Country/Region"],
            "Province/State":   prov,
        }

        result = db.serie.update_one(
            filter_query,
            {"$set": record},
            upsert=True
        )

        action = "INSERITO" if result.upserted_id else "AGGIORNATO"
        print(f"\n[DEBUG insert_record] {action}: "
              f"{record['Country/Region']} | {record['Date']} | "
              f"Confermati: {record['Confirmed']}\n")

        load_timeseries.clear()
        return True
    except Exception as e:
        print(f"Errore insert_record: {e}")
        return False


def update_record(filter_dict: dict, update_dict: dict) -> bool:
    """
    Aggiorna un documento con update_one() e $set.
    filter_dict — query MongoDB per identificare il documento
    update_dict — campi da aggiornare (vengono wrappati in {"$set": ...})
    """
    db = _try_mongo()
    if db is None:
        return False
    try:
        result = db.serie.update_one(filter_dict, {"$set": update_dict})
        load_timeseries.clear()
        return result.modified_count > 0
    except Exception:
        return False


def delete_record(filter_dict: dict, delete_many: bool = False) -> int:
    """
    Elimina documento/i con delete_one() o delete_many().
    Ritorna il numero di documenti eliminati.
    """
    db = _try_mongo()
    if db is None:
        return 0
    try:
        if delete_many:
            result = db.serie.delete_many(filter_dict)
        else:
            result = db.serie.delete_one(filter_dict)
        load_timeseries.clear()
        return result.deleted_count
    except Exception:
        return 0


def mongo_available() -> bool:
    """Controlla se MongoDB è raggiungibile."""
    return _try_mongo() is not None


def retry_mongo() -> bool:
    """
    Resetta il flag di connessione e riprova a connettersi a MongoDB.
    Utile quando mongod è stato avviato dopo il primo tentativo fallito.
    Ritorna True se la connessione è riuscita.
    """
    global _mongo_db, _mongo_checked
    _mongo_db = None
    _mongo_checked = False
    # Pulisce la cache Streamlit per ricaricare i dati
    try:
        load_timeseries.clear()
        load_pivoted.clear()
    except Exception:
        pass
    return _try_mongo() is not None