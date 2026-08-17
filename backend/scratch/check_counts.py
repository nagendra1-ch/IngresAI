import time
from app.database import SessionLocal
from app.models import Geography, GWRAAssessment, GroundwaterObservation, RainfallRecord

def main():
    db = SessionLocal()
    print("Geography count:", db.query(Geography).count())
    print("GWRAAssessment count:", db.query(GWRAAssessment).count())
    print("GroundwaterObservation count:", db.query(GroundwaterObservation).count())
    print("RainfallRecord count:", db.query(RainfallRecord).count())
    
    start = time.time()
    from app.routes.dashboard import get_all_resolved_records
    records = get_all_resolved_records(db)
    end = time.time()
    print(f"get_all_resolved_records returned {len(records)} records in {end - start:.4f} seconds")
    db.close()

if __name__ == "__main__":
    main()
