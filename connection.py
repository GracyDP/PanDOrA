import pandas as pd
from pymongo import MongoClient

# Connessione a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["mioDatabase"]

# Legge i CSV
df_paesi = pd.read_csv("csv/key-countries-pivoted.csv")
df_serie = pd.read_csv("csv/time-series-19-covid-combined.csv")

# Converte in dizionari
paesi_dict = df_paesi.to_dict("records")
serie_dict = df_serie.to_dict("records")

# Inserisce nelle collezioni
db.paesi.insert_many(paesi_dict)
db.serie.insert_many(serie_dict)

print("Import completato :)")