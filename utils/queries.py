"""
Modulo Query MongoDB — PanDOrA
================================
Contiene tutte le operazioni di lettura/aggregazione sul database:
  - helper interni (_build_mongo_query, _sort_spec, _apply_pandas_filter)
  - find con filtri (count_records, query_records, get_one_record, find_records_for_edit)
  - aggregation pipeline (get_snapshot, aggregate_timeseries, aggregate_map_snapshot)
  - utilità (get_date_range, get_countries)

Ogni funzione tenta prima MongoDB, poi ricade sul CSV locale tramite
le funzioni bulk load di utils.db.
"""

import pandas as pd
from datetime import datetime, date as date_type

from utils.db import _try_mongo, load_timeseries


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS INTERNI
# ══════════════════════════════════════════════════════════════════════════════

def _build_mongo_query(
    paese: str = None,
    provincia: str = None,
    date_from=None,
    date_to=None,
    min_confirmed: int = 0,
) -> dict:
    """
    Costruisce un dizionario query MongoDB da usare con find() o count_documents().

    Operatori usati:
      $eq   — corrispondenza esatta (paese)
      $regex / $options — ricerca testo case-insensitive (provincia)
      $gte / $lte     — range di date e casi minimi
    """
    query = {}

    if paese and paese != "Tutti":
        query["Country/Region"] = {"$eq": paese}

    if provincia:
        query["Province/State"] = {"$regex": provincia, "$options": "i"}

    date_clause = {}
    if date_from:
        dt_from = datetime.combine(date_from, datetime.min.time()) \
                  if isinstance(date_from, date_type) else date_from
        date_clause["$gte"] = dt_from
    if date_to:
        dt_to = datetime.combine(date_to, datetime.max.time()) \
                if isinstance(date_to, date_type) else date_to
        date_clause["$lte"] = dt_to
    if date_clause:
        query["Date"] = date_clause

    if min_confirmed > 0:
        query["Confirmed"] = {"$gte": min_confirmed}

    return query


def _sort_spec(sort_field: str, ascending: bool) -> list:
    """Converte (campo, bool) nel formato sort di pymongo [(campo, direzione)]."""
    from pymongo import ASCENDING, DESCENDING
    return [(sort_field, ASCENDING if ascending else DESCENDING)]


def _apply_pandas_filter(
    df: pd.DataFrame,
    paese: str = None,
    provincia: str = None,
    date_from=None,
    date_to=None,
    min_confirmed: int = 0,
) -> pd.DataFrame:
    """Applica gli stessi filtri su un DataFrame pandas (CSV fallback)."""
    out = df.copy()
    if paese and paese != "Tutti":
        out = out[out["Country/Region"] == paese]
    if provincia:
        out = out[out["Province/State"].fillna("").str.contains(provincia, case=False)]
    if date_from:
        out = out[out["Date"].dt.date >= date_from]
    if date_to:
        out = out[out["Date"].dt.date <= date_to]
    if min_confirmed > 0:
        out = out[out["Confirmed"] >= min_confirmed]
    return out


# ══════════════════════════════════════════════════════════════════════════════
# QUERY CON FILTRI — usa find() MongoDB con operatori nativi
# ══════════════════════════════════════════════════════════════════════════════

def count_records(
    paese: str = None,
    provincia: str = None,
    date_from=None,
    date_to=None,
    min_confirmed: int = 0,
) -> int:
    """
    Conta i documenti corrispondenti ai filtri usando count_documents().
    Evita di trasferire dati solo per contare.
    """
    db = _try_mongo()
    if db is not None:
        try:
            query = _build_mongo_query(paese, provincia, date_from, date_to, min_confirmed)
            return db.serie.count_documents(query)
        except Exception:
            pass

    # Fallback pandas
    df = load_timeseries()
    return len(_apply_pandas_filter(df, paese, provincia, date_from, date_to, min_confirmed))


def query_records(
    paese: str = None,
    provincia: str = None,
    date_from=None,
    date_to=None,
    min_confirmed: int = 0,
    sort_field: str = "Date",
    sort_asc: bool = False,
    skip: int = 0,
    limit: int = 100,
) -> pd.DataFrame:
    """
    Esegue find() su MongoDB con:
      - filtri ($eq, $regex, $gte, $lte)
      - ordinamento nativo (.sort())
      - paginazione server-side (.skip().limit())

    Fallback su pandas per CSV.
    """
    db = _try_mongo()
    if db is not None:
        try:
            query = _build_mongo_query(paese, provincia, date_from, date_to, min_confirmed)
            cursor = (
                db.serie
                .find(query, {"_id": 0})
                .sort(_sort_spec(sort_field, sort_asc))
                .skip(skip)
                .limit(limit)
            )
            data = list(cursor)
            if data:
                df = pd.DataFrame(data)
                df["Date"] = pd.to_datetime(df["Date"])
                return df
        except Exception:
            pass

    # Fallback pandas (anche se MongoDB è connesso ma la query non trova dati)
    df = load_timeseries()
    df = _apply_pandas_filter(df, paese, provincia, date_from, date_to, min_confirmed)
    df = df.sort_values(sort_field, ascending=sort_asc)
    return df.iloc[skip: skip + limit].reset_index(drop=True)


def get_one_record(
    paese: str,
    data: date_type,
    provincia: str = None,
) -> dict | None:
    """
    Recupera un singolo documento con find_one().
    Usato da UPDATE e DELETE per mostrare il record prima di modificarlo.
    """
    db = _try_mongo()
    if db is not None:
        try:
            query = {"Country/Region": paese,
                     "Date": datetime.combine(data, datetime.min.time())}
            if provincia:
                query["Province/State"] = {"$regex": provincia, "$options": "i"}
            # Se non specificata, non filtriamo per provincia

            doc = db.serie.find_one(query, {"_id": 0})
            return doc
        except Exception:
            pass

    # Fallback pandas
    df = load_timeseries()
    mask = (df["Country/Region"] == paese) & (df["Date"].dt.date == data)
    if provincia:
        mask &= df["Province/State"].fillna("").str.contains(provincia, case=False)
    else:
        mask &= df["Province/State"].isna()
    found = df[mask]
    return found.iloc[0].to_dict() if len(found) == 1 else None


def find_records_for_edit(
    paese: str,
    data: date_type,
    provincia: str = None,
) -> pd.DataFrame:
    """
    Cerca tutti i documenti che corrispondono ai criteri di ricerca per UPDATE/DELETE.
    Usa find() con proiezione esplicita.
    """
    db = _try_mongo()
    if db is not None:
        try:
            query: dict = {
                "Country/Region": {"$eq": paese},
                "Date": {"$eq": datetime.combine(data, datetime.min.time())},
            }
            if provincia:
                query["Province/State"] = {"$regex": provincia, "$options": "i"}
            # Se non specificata, non filtriamo per provincia
            # così troviamo record con Province/State null, "", o assente

            data_list = list(db.serie.find(query, {"_id": 0}))
            if data_list:
                df = pd.DataFrame(data_list)
                df["Date"] = pd.to_datetime(df["Date"])
                return df
        except Exception:
            pass

    # Fallback pandas (anche se MongoDB è connesso ma non trova dati)
    df = load_timeseries()
    mask = (df["Country/Region"] == paese) & (df["Date"].dt.date == data)
    if provincia:
        mask &= df["Province/State"].fillna("").str.contains(provincia, case=False)
    else:
        mask &= df["Province/State"].isna()
    return df[mask].copy()


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATION PIPELINES
# ══════════════════════════════════════════════════════════════════════════════

def get_snapshot(df: pd.DataFrame = None) -> pd.DataFrame:
    """
    Snapshot KPI per paese usando aggregation pipeline MongoDB:

    $group  — aggrega prima per (Country/Region, Date) sommando le province
    $group  — seleziona poi l'ultima data disponibile per ogni paese
               (Recovered usa l'ultimo valore noto, via massimo storico)
      $match  — esclude paesi con 0 casi
      $addFields — calcola CFR
      $sort   — ordine decrescente per Confirmed

    Fallback pandas se MongoDB non disponibile (usa df passato o carica da CSV).
    """
    db = _try_mongo()
    if db is not None:
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": {
                            "Country": "$Country/Region",
                            "Date": "$Date",
                        },
                        "Confirmed": {"$sum": "$Confirmed"},
                        "Deaths": {"$sum": "$Deaths"},
                        "Recovered": {"$sum": "$Recovered"},
                    }
                },
                {"$sort": {"_id.Date": -1}},
                {
                    "$group": {
                        "_id": "$_id.Country",
                        "Confirmed": {"$first": "$Confirmed"},
                        "Deaths": {"$first": "$Deaths"},
                        "Recovered": {"$max": "$Recovered"},
                        "LastDate": {"$first": "$_id.Date"},
                    }
                },
                {
                    "$match": {"Confirmed": {"$gt": 0}}
                },
                {
                    "$addFields": {
                        "Country/Region": "$_id",
                        "CFR": {
                            "$round": [
                                {"$multiply": [
                                    {"$divide": ["$Deaths", "$Confirmed"]},
                                    100
                                ]},
                                2
                            ]
                        },
                    }
                },
                {
                    "$project": {"_id": 0, "Country/Region": 1,
                                 "Confirmed": 1, "Deaths": 1,
                                 "Recovered": 1, "CFR": 1, "LastDate": 1}
                },
                {"$sort": {"Confirmed": -1}},
            ]
            data = list(db.serie.aggregate(pipeline))
            if data:
                return pd.DataFrame(data)
        except Exception:
            pass

    # Fallback pandas
    if df is None:
        df = load_timeseries()
    last = df["Date"].max()
    snap_last = (
        df[df["Date"] == last]
        .groupby("Country/Region")[["Confirmed", "Deaths", "Recovered"]]
        .sum(min_count=1)
        .reset_index()
    )

    # Recovered nei dataset COVID spesso manca nelle date finali;
    # usiamo il massimo storico per paese come ultimo valore noto.
    rec_max = (
        df.groupby("Country/Region")["Recovered"]
        .max()
        .reset_index()
        .rename(columns={"Recovered": "Recovered_max"})
    )

    snap = snap_last.drop(columns=["Recovered"]).merge(
        rec_max,
        on="Country/Region",
        how="left",
    )
    snap = snap.rename(columns={"Recovered_max": "Recovered"})
    snap = snap[snap["Confirmed"] > 0].copy()
    snap["CFR"] = (snap["Deaths"] / snap["Confirmed"] * 100).round(2)
    return snap


def aggregate_timeseries(
    paesi: list,
    date_from=None,
    date_to=None,
) -> pd.DataFrame:
    """
    Aggregation pipeline per la Dashboard — raggruppa per (Date, Country/Region)
    con $match + $group + $sort.
    Usata al posto di filtrare in pandas.
    """
    db = _try_mongo()
    if db is not None:
        try:
            match_stage: dict = {}
            if paesi:
                match_stage["Country/Region"] = {"$in": paesi}
            date_clause: dict = {}
            if date_from:
                date_clause["$gte"] = datetime.combine(date_from, datetime.min.time()) \
                                       if isinstance(date_from, date_type) else date_from
            if date_to:
                date_clause["$lte"] = datetime.combine(date_to, datetime.max.time()) \
                                       if isinstance(date_to, date_type) else date_to
            if date_clause:
                match_stage["Date"] = date_clause

            pipeline = [
                {"$match": match_stage},
                {
                    "$group": {
                        "_id": {
                            "Date":    "$Date",
                            "Country": "$Country/Region",
                        },
                        "Confirmed":  {"$sum": "$Confirmed"},
                        "Deaths":     {"$sum": "$Deaths"},
                        "Recovered":  {"$sum": "$Recovered"},
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "Date":              "$_id.Date",
                        "Country/Region":    "$_id.Country",
                        "Confirmed":  1,
                        "Deaths":     1,
                        "Recovered":  1,
                    }
                },
                {"$sort": {"Date": 1, "Country/Region": 1}},
            ]

            data = list(db.serie.aggregate(pipeline))
            if data:
                df = pd.DataFrame(data)
                df["Date"] = pd.to_datetime(df["Date"])
                return df
        except Exception:
            pass

    # Fallback pandas (anche se MongoDB è connesso ma la pipeline non trova dati)
    df = load_timeseries()
    mask_p = df["Country/Region"].isin(paesi) if paesi else pd.Series(True, index=df.index)
    mask_d = pd.Series(True, index=df.index)
    if date_from:
        mask_d &= df["Date"].dt.date >= date_from
    if date_to:
        mask_d &= df["Date"].dt.date <= date_to
    df = df[mask_p & mask_d]
    return (
        df.groupby(["Date", "Country/Region"])[["Confirmed", "Deaths", "Recovered"]]
        .sum(min_count=1)
        .reset_index()
    )


def aggregate_map_snapshot(
    data_snapshot,
    min_confirmed: int = 0,
    paesi: list = None,
) -> pd.DataFrame:
    """
    Aggregation per la Mappa Interattiva:
    dati aggregati per paese in una data specifica con $match + $group.
    """
    db = _try_mongo()
    if db is not None:
        try:
            dt = datetime.combine(data_snapshot, datetime.min.time()) \
                 if isinstance(data_snapshot, date_type) else data_snapshot

            match_stage: dict = {
                "Date":      {"$eq": dt},
                "Confirmed": {"$gte": min_confirmed},
            }
            if paesi:
                match_stage["Country/Region"] = {"$in": paesi}

            pipeline = [
                {"$match": match_stage},
                {
                    "$group": {
                        "_id": "$Country/Region",
                        "Confirmed":  {"$sum": "$Confirmed"},
                        "Deaths":     {"$sum": "$Deaths"},
                        "Recovered":  {"$sum": "$Recovered"},
                    }
                },
                {
                    "$addFields": {
                        "Country/Region": "$_id",
                        "CFR (%)": {
                            "$round": [
                                {"$cond": [
                                    {"$gt": ["$Confirmed", 0]},
                                    {"$multiply": [{"$divide": ["$Deaths", "$Confirmed"]}, 100]},
                                    0
                                ]},
                                2
                            ]
                        },
                    }
                },
                {"$project": {"_id": 0, "Country/Region": 1,
                               "Confirmed": 1, "Deaths": 1,
                               "Recovered": 1, "CFR (%)": 1}},
                {"$sort": {"Confirmed": -1}},
            ]

            data = list(db.serie.aggregate(pipeline))
            if data:
                return pd.DataFrame(data)
        except Exception:
            pass

    # Fallback pandas (anche se MongoDB è connesso ma la pipeline non trova dati)
    import numpy as np
    df = load_timeseries()
    ts = pd.Timestamp(data_snapshot)
    df_day = df[df["Date"] == ts].copy()
    df_map = (
        df_day.groupby("Country/Region")[["Confirmed", "Deaths", "Recovered"]]
        .sum(min_count=1).reset_index()
    )
    df_map = df_map[df_map["Confirmed"] >= min_confirmed].copy()
    if paesi:
        df_map = df_map[df_map["Country/Region"].isin(paesi)]
    df_map["CFR (%)"] = np.where(
        df_map["Confirmed"] > 0,
        (df_map["Deaths"] / df_map["Confirmed"] * 100).round(2), 0)
    return df_map


def get_date_range() -> tuple:
    """
    Recupera la data minima e massima del dataset con una pipeline $group.
    Ritorna (min_date, max_date) come oggetti date.
    """
    db = _try_mongo()
    if db is not None:
        try:
            result = list(db.serie.aggregate([
                {"$group": {"_id": None,
                            "minDate": {"$min": "$Date"},
                            "maxDate": {"$max": "$Date"}}},
            ]))
            if result:
                r = result[0]
                return r["minDate"].date(), r["maxDate"].date()
        except Exception:
            pass
    # Fallback pandas
    df = load_timeseries()
    return df["Date"].min().date(), df["Date"].max().date()


# ══════════════════════════════════════════════════════════════════════════════
# DISTINCT — lista paesi
# ══════════════════════════════════════════════════════════════════════════════

def get_countries(df: pd.DataFrame = None) -> list:
    """
    Lista ordinata dei paesi unici.
    Usa distinct() su MongoDB; fallback su pandas.
    """
    db = _try_mongo()
    if db is not None:
        try:
            paesi = db.serie.distinct("Country/Region")
            return sorted([p for p in paesi if p])
        except Exception:
            pass

    if df is None:
        df = load_timeseries()
    return sorted(df["Country/Region"].dropna().unique().tolist())
