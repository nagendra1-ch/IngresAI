import sqlite3

db_path = r"c:\Users\chnag\OneDrive\Attachments\Desktop\ingres1\ingres_ai.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Query Guntur district
cursor.execute("SELECT id, canonical_district_name, state_name FROM districts WHERE canonical_district_name LIKE '%Guntur%'")
guntur_dists = cursor.fetchall()
print("Guntur districts in DB:", guntur_dists)

for dist_id, name, state in guntur_dists:
    cursor.execute("""
        SELECT summary_year, annual_groundwater_recharge_ham, annual_extractable_groundwater_resource_ham, 
               annual_groundwater_extraction_ham, stage_of_groundwater_extraction_percent, assessment_category
        FROM groundwater_district_summary 
        WHERE district_id = ?
    """, (dist_id,))
    summaries = cursor.fetchall()
    print(f"Summary for {name} ({state}):", summaries)

# Query Ananthapuramu district
cursor.execute("SELECT id, canonical_district_name, state_name FROM districts WHERE canonical_district_name LIKE '%Ananthapuramu%'")
ananth_dists = cursor.fetchall()
print("Ananthapuramu districts in DB:", ananth_dists)

for dist_id, name, state in ananth_dists:
    cursor.execute("""
        SELECT summary_year, annual_groundwater_recharge_ham, annual_extractable_groundwater_resource_ham, 
               annual_groundwater_extraction_ham, stage_of_groundwater_extraction_percent, assessment_category
        FROM groundwater_district_summary 
        WHERE district_id = ?
    """, (dist_id,))
    summaries = cursor.fetchall()
    print(f"Summary for {name} ({state}):", summaries)

conn.close()
