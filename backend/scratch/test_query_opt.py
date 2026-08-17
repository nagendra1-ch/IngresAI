import time
from sqlalchemy import func
from app.database import SessionLocal
from app.models import Geography, GroundwaterObservation, RainfallRecord, GWRAAssessment

def main():
    db = SessionLocal()
    
    # Method 1: Existing memory-based
    start = time.time()
    # 1. Get latest observation year per district
    obs_max_years = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(GroundwaterObservation.observation_year).label("max_year")
    ).join(Geography).group_by(Geography.normalized_state_name, Geography.normalized_district_name).all()
    obs_max_years_map = {(r[0], r[1]): r[2] for r in obs_max_years}
    
    # 2. Get latest observations
    latest_obs_query = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        GroundwaterObservation.depth_to_water_level_m_bgl,
        GroundwaterObservation.observation_year
    ).join(Geography).all()
    
    from collections import defaultdict
    obs_by_district = defaultdict(list)
    for state_norm, dist_norm, depth, year in latest_obs_query:
        if depth is not None:
            if obs_max_years_map.get((state_norm, dist_norm)) == year:
                obs_by_district[(state_norm, dist_norm)].append(depth)
                
    depth_averages_orig = {}
    for key, depths in obs_by_district.items():
        depth_averages_orig[key] = round(sum(depths) / len(depths), 2)
    end1 = time.time()
    print(f"Original method took {end1 - start:.4f}s. Result size: {len(depth_averages_orig)}")
    
    # Method 2: Revised Database-based optimization
    start = time.time()
    obs_max_years_sub = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(GroundwaterObservation.observation_year).label("max_year")
    ).join(
        GroundwaterObservation, Geography.id == GroundwaterObservation.geography_id
    ).group_by(
        Geography.normalized_state_name, Geography.normalized_district_name
    ).subquery()
    
    avg_depths_res = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.avg(GroundwaterObservation.depth_to_water_level_m_bgl).label("avg_depth")
    ).join(
        GroundwaterObservation, Geography.id == GroundwaterObservation.geography_id
    ).join(
        obs_max_years_sub,
        (Geography.normalized_state_name == obs_max_years_sub.c.normalized_state_name) &
        (Geography.normalized_district_name == obs_max_years_sub.c.normalized_district_name) &
        (GroundwaterObservation.observation_year == obs_max_years_sub.c.max_year)
    ).filter(
        GroundwaterObservation.depth_to_water_level_m_bgl.isnot(None)
    ).group_by(
        Geography.normalized_state_name,
        Geography.normalized_district_name
    ).all()
    
    depth_averages_opt = {(r[0], r[1]): round(r[2], 2) for r in avg_depths_res}
    end2 = time.time()
    print(f"Optimized method took {end2 - start:.4f}s. Result size: {len(depth_averages_opt)}")
    
    # Check discrepancy
    diff = 0
    for k, v in depth_averages_orig.items():
        if depth_averages_opt.get(k) != v:
            diff += 1
            if diff < 10:
                print(f"Mismatch for {k}: orig={v}, opt={depth_averages_opt.get(k)}")
    print(f"Total mismatches: {diff}")
    
    db.close()

if __name__ == "__main__":
    main()
