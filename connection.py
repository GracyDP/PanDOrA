"""
connection.py — COMPATIBILITÀ
==============================
Questo file NON è più necessario.
Tutta la logica di connessione e inizializzazione del database
è ora integrata in utils/db.py e viene eseguita automaticamente
all'avvio di app.py.

Le funzioni qui sotto sono mantenute come wrapper per non rompere
eventuali script che ancora le importano.
"""

from utils.db import _try_mongo


def initialize_database():
    """Non necessaria: l'inizializzazione avviene automaticamente in utils/db.py."""
    _try_mongo()  # forza connessione + init se non già fatto
    print("[connection.py] Inizializzazione delegata a utils/db.py.")


def get_db():
    """Restituisce l'oggetto database MongoDB (o None)."""
    return _try_mongo()