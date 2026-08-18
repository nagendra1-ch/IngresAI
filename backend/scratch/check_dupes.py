import sqlite3

db = sqlite3.connect(r'c:\Users\chnag\OneDrive\Attachments\Desktop\ingres1\ingres_ai.db')
c = db.cursor()

# Check Ananthapuramu duplicates
c.execute("SELECT id, district_name, state_name FROM geographies WHERE district_name = 'Ananthapuramu' AND normalized_mandal_name IS NULL")
rows = c.fetchall()
print("Ananthapuramu district entries:")
for row in rows:
    print(f"  id={row[0]} state={row[2]}")

# Check Aurangabad duplicates
c.execute("SELECT id, district_name, state_name FROM geographies WHERE district_name = 'Aurangabad' AND normalized_mandal_name IS NULL")
rows = c.fetchall()
print("Aurangabad district entries:")
for row in rows:
    print(f"  id={row[0]} state={row[2]}")

# Count district vs total geographies
c.execute("SELECT COUNT(*) FROM geographies WHERE normalized_mandal_name IS NULL AND normalized_village_name IS NULL")
district_count = c.fetchone()[0]
print(f"District-level geographies: {district_count}")

c.execute("SELECT COUNT(*) FROM geographies")
total_count = c.fetchone()[0]
print(f"Total geographies: {total_count}")

# Check if the weather route prefix is correct
# The prefix in weather.py is '/weather' but in main.py it's included without /api prefix
print("\nNote: weather router prefix = /weather (not /api/weather)")
print("Forecast.jsx calls /api/weather/forecast/{district} — this will 404!")

db.close()
