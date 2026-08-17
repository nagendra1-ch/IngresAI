import sqlite3
import os

db_path = "ingres_ai.db"
print("Current Working Directory:", os.getcwd())
print("Database path exists:", os.path.exists(db_path))

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print("Tables in database:", tables)

if ("geographies",) in tables:
    cur.execute("SELECT id, district_name, state_name FROM geographies WHERE normalized_mandal_name IS NULL AND normalized_village_name IS NULL AND district_name IN ('Kurnool', 'Dr. B.R. Ambedkar Konaseema')")
    geos = cur.fetchall()
    print("Geographies found:")
    for g in geos:
        print(g)
        cur.execute("SELECT assessment_year, annual_groundwater_recharge_ham, stage_of_groundwater_extraction_percent FROM gwra_assessments WHERE geography_id = ?", (g[0],))
        print("GWRA:", cur.fetchall())
        
conn.close()
