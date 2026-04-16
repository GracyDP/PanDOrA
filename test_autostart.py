"""Test diagnostico per capire dove fallisce l'auto-avvio di mongod"""
import sys
sys.path.insert(0, '.')

from utils.db import _find_mongod, _ensure_mongod_running

print("=== TEST AUTO-AVVIO MONGODB ===\n")

print("1) Ricerca mongod.exe...")
mongod_path = _find_mongod()
if mongod_path:
    print(f"   ✓ Trovato: {mongod_path}")
else:
    print("   ✗ Non trovato nel PATH né in C:\\Program Files\\MongoDB\\Server")
    print("   Installa MongoDB da: https://www.mongodb.com/try/download/community")
    sys.exit(1)

print("\n2) Verifica/avvio mongod...")
result = _ensure_mongod_running()
print(f"   Risultato: {result}")

if result:
    print("\n✓ MongoDB avviato e pronto!")
    from pymongo import MongoClient
    client = MongoClient("mongodb://localhost:27017/", serverSelectionTimeoutMS=3000)
    info = client.server_info()
    print(f"   Versione: {info['version']}")
else:
    print("\n✗ Impossibile avviare MongoDB")
    print("\nProva manualmente:")
    print(f"   {mongod_path} --dbpath=C:\\data\\db")
