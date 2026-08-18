from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from collections import defaultdict
import time
from app.database import get_db
from app.models import Geography, GWRAAssessment, GroundwaterObservation, RainfallRecord, User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

_resolved_records_cache = None
_cache_timestamp = 0.0
_CACHE_TTL = 300.0  # 5 minutes

def get_all_resolved_records(db: Session):
    global _resolved_records_cache, _cache_timestamp
    now = time.time()
    if _resolved_records_cache is not None and (now - _cache_timestamp) < _CACHE_TTL:
        return _resolved_records_cache

    geos = db.query(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).all()
    
    # 1. Get latest observation year per district (fast)
    obs_max_years = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(GroundwaterObservation.observation_year).label("max_year")
    ).join(Geography).group_by(Geography.normalized_state_name, Geography.normalized_district_name).all()
    obs_max_years_map = {(r[0], r[1]): r[2] for r in obs_max_years}
    
    unique_obs_years = list(set(obs_max_years_map.values()))
    
    # 2. Get latest observations using year filter (fast)
    latest_obs_query = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        GroundwaterObservation.depth_to_water_level_m_bgl,
        GroundwaterObservation.observation_year
    ).join(Geography).filter(
        GroundwaterObservation.observation_year.in_(unique_obs_years)
    ).all()
    
    obs_by_district = defaultdict(list)
    for state_norm, dist_norm, depth, year in latest_obs_query:
        if depth is not None:
            if obs_max_years_map.get((state_norm, dist_norm)) == year:
                obs_by_district[(state_norm, dist_norm)].append(depth)
                
    depth_averages = {}
    for key, depths in obs_by_district.items():
        depth_averages[key] = round(sum(depths) / len(depths), 2)
        
    # 3. Get latest rainfall year per district
    rain_max_years = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(RainfallRecord.rainfall_year).label("max_year")
    ).join(Geography).group_by(Geography.normalized_state_name, Geography.normalized_district_name).all()
    rain_max_years_map = {(r[0], r[1]): r[2] for r in rain_max_years}
    
    unique_rain_years = list(set(rain_max_years_map.values()))
    
    # 4. Get latest rainfall records using year filter (fast)
    latest_rains_query = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        RainfallRecord.rainfall_mm,
        RainfallRecord.rainfall_year
    ).join(Geography).filter(
        RainfallRecord.rainfall_year.in_(unique_rain_years)
    ).all()
    
    rains_by_district = defaultdict(list)
    for state_norm, dist_norm, rain, year in latest_rains_query:
        if rain is not None:
            if rain_max_years_map.get((state_norm, dist_norm)) == year:
                rains_by_district[(state_norm, dist_norm)].append(rain)
                
    rain_averages = {}
    for key, rains in rains_by_district.items():
        rain_averages[key] = round(sum(rains) / len(rains), 1)
        
    # 5. Get GWRA Assessments
    latest_gwra_query = db.query(GWRAAssessment).all()
    gwra_by_geo = {g.geography_id: g for g in latest_gwra_query}
    
    resolved_records = []
    for geo in geos:
        key = (geo.normalized_state_name, geo.normalized_district_name)
        avg_depth = depth_averages.get(key)
        avg_rain = rain_averages.get(key)
        
        gwra = gwra_by_geo.get(geo.id)
        recharge = gwra.annual_groundwater_recharge_ham if gwra else None
        extraction = gwra.annual_groundwater_extraction_ham if gwra else None
        stage = gwra.stage_of_groundwater_extraction_percent if gwra else None
        category = gwra.district_assessment_category if gwra else None
        
        if stage is None and extraction is not None and gwra and gwra.annual_extractable_groundwater_resource_ham:
            stage = round((extraction / gwra.annual_extractable_groundwater_resource_ham) * 100.0, 2)
            
        resolved_records.append({
            "id": geo.id,
            "district_name": geo.district_name,
            "state_name": geo.state_name,
            "depth_to_water_level_m_bgl": avg_depth,
            "rainfall_mm": avg_rain,
            "annual_groundwater_recharge_ham": recharge,
            "annual_groundwater_extraction_ham": extraction,
            "stage_of_groundwater_extraction_percent": stage,
            "assessment_category": category or "Safe"
        })
        
    _resolved_records_cache = resolved_records
    _cache_timestamp = time.time()
    return resolved_records

@router.get("/summary")
def get_dashboard_summary(
    state_name: Optional[str] = None,
    district_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Computes total national or regional stats (averages of rainfall, recharge, extraction),
    highest/lowest ranking districts, and category counts. Supports optional state/district filters. Requires auth.
    """
    resolved_records = get_all_resolved_records(db)
    
    # Filter by state
    if state_name:
        state_upper = state_name.upper().strip()
        resolved_records = [r for r in resolved_records if r["state_name"].upper().strip() == state_upper]
        
    # Filter by district
    if district_name:
        dist_upper = district_name.upper().strip()
        resolved_records = [r for r in resolved_records if r["district_name"].upper().strip() == dist_upper]

    total_districts = len(resolved_records)
    total_states = len(set(r["state_name"] for r in resolved_records))
    
    gw_vals = [r["depth_to_water_level_m_bgl"] for r in resolved_records if r["depth_to_water_level_m_bgl"] is not None]
    avg_gw = sum(gw_vals) / len(gw_vals) if len(gw_vals) > 0 else 0.0
    
    rainfall_vals = [r["rainfall_mm"] for r in resolved_records if r["rainfall_mm"] is not None]
    avg_rainfall = sum(rainfall_vals) / len(rainfall_vals) if len(rainfall_vals) > 0 else 0.0
    
    recharge_vals = [r["annual_groundwater_recharge_ham"] for r in resolved_records if r["annual_groundwater_recharge_ham"] is not None]
    total_recharge = sum(recharge_vals)
    avg_recharge = total_recharge / len(recharge_vals) if len(recharge_vals) > 0 else 0.0
    
    extraction_vals = [r["annual_groundwater_extraction_ham"] for r in resolved_records if r["annual_groundwater_extraction_ham"] is not None]
    total_extraction = sum(extraction_vals)
    avg_extraction = total_extraction / len(extraction_vals) if len(extraction_vals) > 0 else 0.0
    
    stage_vals = [r["stage_of_groundwater_extraction_percent"] for r in resolved_records if r["stage_of_groundwater_extraction_percent"] is not None]
    avg_stage = sum(stage_vals) / len(stage_vals) if len(stage_vals) > 0 else 0.0
    
    # Rank districts
    ranked = sorted(
        [
            {
                "id": r["id"],
                "district_name": r["district_name"],
                "state_name": r["state_name"],
                "groundwater_level": r["depth_to_water_level_m_bgl"] if r["depth_to_water_level_m_bgl"] is not None else 0.0
            } for r in resolved_records
        ],
        key=lambda x: x["groundwater_level"],
        reverse=True
    )
    
    highest_gw = ranked[:5]
    lowest_gw = list(reversed(ranked))[:5]
    
    cat_counts = {}
    for r in resolved_records:
        cat = r["assessment_category"] or "Safe"
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        
    category_distribution = [{"category": k, "count": v} for k, v in cat_counts.items()]
    
    return {
        "total_districts": total_districts,
        "total_states": total_states,
        "avg_groundwater_level": round(avg_gw, 2),
        "avg_stage_of_extraction": round(avg_stage, 2),
        "avg_rainfall": round(avg_rainfall, 2),
        "total_recharge": round(total_recharge, 2),
        "avg_recharge": round(avg_recharge, 2),
        "total_extraction": round(total_extraction, 2),
        "avg_extraction": round(avg_extraction, 2),
        "highest_districts": highest_gw,
        "lowest_districts": lowest_gw,
        "category_distribution": category_distribution
    }

@router.get("/state-statistics")
def get_state_statistics(
    state_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Computes averages of groundwater stats grouped by State. 
    If a state_name is provided, it groups by District inside that state instead. Requires auth.
    """
    resolved_records = get_all_resolved_records(db)
    
    if state_name:
        state_upper = state_name.upper().strip()
        filtered = [r for r in resolved_records if r["state_name"].upper().strip() == state_upper]
        
        result = []
        for r in sorted(filtered, key=lambda x: x["district_name"]):
            result.append({
                "state_name": r["district_name"],  # map to state_name so charts can render seamlessly
                "district_name": r["district_name"],
                "avg_groundwater_level": r["depth_to_water_level_m_bgl"] or 0.0,
                "avg_rainfall": r["rainfall_mm"] or 0.0,
                "avg_recharge": r["annual_groundwater_recharge_ham"] or 0.0,
                "avg_extraction": r["annual_groundwater_extraction_ham"] or 0.0
            })
        return result

    by_state = defaultdict(list)
    for r in resolved_records:
        by_state[r["state_name"]].append({
            "gw": r["depth_to_water_level_m_bgl"],
            "rainfall": r["rainfall_mm"],
            "recharge": r["annual_groundwater_recharge_ham"],
            "extraction": r["annual_groundwater_extraction_ham"]
        })
        
    result = []
    for s_name, items in sorted(by_state.items()):
        gw_vals = [i["gw"] for i in items if i["gw"] is not None]
        rain_vals = [i["rainfall"] for i in items if i["rainfall"] is not None]
        recharge_vals = [i["recharge"] for i in items if i["recharge"] is not None]
        extraction_vals = [i["extraction"] for i in items if i["extraction"] is not None]
        
        result.append({
            "state_name": s_name,
            "avg_groundwater_level": round(sum(gw_vals) / len(gw_vals), 2) if gw_vals else 0.0,
            "avg_rainfall": round(sum(rain_vals) / len(rain_vals), 2) if rain_vals else 0.0,
            "avg_recharge": round(sum(recharge_vals) / len(recharge_vals), 2) if recharge_vals else 0.0,
            "avg_extraction": round(sum(extraction_vals) / len(extraction_vals), 2) if extraction_vals else 0.0
        })
    return result

@router.get("/district-statistics")
def get_district_statistics(
    state_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Lists the latest statistics for all districts, optionally filtered by state. Requires auth.
    """
    resolved = get_all_resolved_records(db)
    if state_name:
        state_upper = state_name.upper().strip()
        resolved = [r for r in resolved if r["state_name"].upper().strip() == state_upper]
        
    return [
        {
            "id": r["id"],
            "district_name": r["district_name"],
            "state_name": r["state_name"],
            "groundwater_level": r["depth_to_water_level_m_bgl"],
            "rainfall": r["rainfall_mm"],
            "assessment_category": r["assessment_category"]
        } for r in resolved
    ]

@router.get("/rainfall")
def get_rainfall_statistics(
    state_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Aggregates state/district level rainfall for visual charts. Requires auth.
    """
    return get_state_statistics(state_name, db, current_user)

@router.get("/groundwater")
def get_groundwater_distribution(
    state_name: Optional[str] = None,
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    """
    Exposes Safe vs Critical category distributions. Requires auth.
    """
    summary = get_dashboard_summary(state_name, None, db, current_user)
    return summary["category_distribution"]
