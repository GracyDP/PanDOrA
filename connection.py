"""
connection.py — COMPATIBILITÀ
==============================
"""

from utils.db import _try_mongo


def initialize_database():
    """Non necessaria: l'inizializzazione avviene automaticamente in utils/db.py."""
    _try_mongo()  # forza connessione + init se non già fatto
    print("[connection.py] Inizializzazione delegata a utils/db.py.")


def get_db():
    """Restituisce l'oggetto database MongoDB (o None)."""
    return _try_mongo()
