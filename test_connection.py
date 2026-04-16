"""Test diretto della connessione MongoDB senza Streamlit"""
from utils.db import _try_mongo, mongo_available, _mongo_checked, _mongo_db

print("=== Test Connessione MongoDB ===")
print(f"Prima del tentativo:")
print(f"  _mongo_checked = {_mongo_checked}")
print(f"  _mongo_db = {_mongo_db}")
print()

db = _try_mongo()
print(f"Dopo _try_mongo():")
print(f"  _mongo_checked = {_mongo_checked}")
print(f"  _mongo_db = {db}")
print(f"  mongo_available() = {mongo_available()}")
print()

if db is None:
    print("ERRORE: MongoDB non connesso")
    print("Verifica che mongod sia in esecuzione.")
else:
    print("MongoDB connesso!")
    print(f"  Database: {db.name}")
    print(f"  Collezioni: {db.list_collection_names()}")
