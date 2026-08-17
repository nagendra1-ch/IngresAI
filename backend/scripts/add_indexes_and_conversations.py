import os
import sys
import sqlite3

# Add backend directory to system path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base
from app.models import User, Geography, GeographyAlias, GWRAAssessment, GroundwaterObservation, RainfallRecord, Conversation, ConversationMessage

def main():
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ingres_ai.db")
    print(f"Connecting to database at: {db_path}")
    
    # 1. Recreate/create Conversation tables using SQLAlchemy
    print("Creating tables via SQLAlchemy Base...")
    Base.metadata.create_all(bind=engine)
    
    # 2. Add performance optimization indexes
    print("Connecting raw sqlite3 to create indexes...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        # Create Geography composite lookup index
        print("Creating index: idx_geo_lookup...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_geo_lookup 
            ON geographies(normalized_state_name, normalized_district_name, normalized_mandal_name, normalized_village_name)
        """)
        
        # Create GWRA composite index
        print("Creating index: idx_gwra_geo_year...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_gwra_geo_year 
            ON gwra_assessments(geography_id, assessment_year)
        """)
        
        # Create Observation composite index
        print("Creating index: idx_obs_geo_year...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_obs_geo_year 
            ON groundwater_observations(geography_id, observation_year)
        """)
        
        # Create Rainfall composite index
        print("Creating index: idx_rain_geo_year...")
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_rain_geo_year 
            ON rainfall_records(geography_id, rainfall_year)
        """)
        
        conn.commit()
        print("Indexes created successfully!")
        
    except Exception as e:
        print("Error creating indexes:", e)
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
