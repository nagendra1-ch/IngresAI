from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.database import get_db
from app.models import Geography, GeographyAlias, GWRAAssessment, GroundwaterObservation, RainfallRecord, ResultAccess, User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/districts", tags=["Districts"])

def get_district_depth_and_indicator(db: Session, geo: Geography):
    # Find the latest observation year for observations associated with this state/district
    max_year = db.query(func.max(GroundwaterObservation.observation_year)).join(Geography).filter(
        Geography.normalized_state_name == geo.normalized_state_name,
        Geography.normalized_district_name == geo.normalized_district_name
    ).scalar()
    if not max_year:
        return None, None, 0, "No observations", None, None
        
    obs_list = db.query(GroundwaterObservation).join(Geography).filter(
        Geography.normalized_state_name == geo.normalized_state_name,
        Geography.normalized_district_name == geo.normalized_district_name,
        GroundwaterObservation.observation_year == max_year
    ).all()
    
    depths = [o.depth_to_water_level_m_bgl for o in obs_list if o.depth_to_water_level_m_bgl is not None]
    avg_depth = round(sum(depths) / len(depths), 2) if depths else None
    
    # Calculate indicator % from historical observations in this district
    hist_obs = db.query(GroundwaterObservation).join(Geography).filter(
        Geography.normalized_state_name == geo.normalized_state_name,
        Geography.normalized_district_name == geo.normalized_district_name
    ).all()
    hist_depths = [o.depth_to_water_level_m_bgl for o in hist_obs if o.depth_to_water_level_m_bgl is not None]
    
    indicator_val = None
    if len(hist_depths) >= 2 and avg_depth is not None:
        min_d = min(hist_depths)
        max_d = max(hist_depths)
        if max_d > min_d:
            val = ((max_d - avg_depth) / (max_d - min_d)) * 100.0
            indicator_val = round(max(0.0, min(100.0, val)), 2)
            
    src = obs_list[0].source if obs_list else None
    period = obs_list[0].observation_date if obs_list else None
    
    return avg_depth, indicator_val, len(depths), period, src, max_year

def get_district_rainfall(db: Session, geo: Geography):
    max_year = db.query(func.max(RainfallRecord.rainfall_year)).join(Geography).filter(
        Geography.normalized_state_name == geo.normalized_state_name,
        Geography.normalized_district_name == geo.normalized_district_name
    ).scalar()
    if not max_year:
        return None, None, None, None
        
    rains = db.query(RainfallRecord).join(Geography).filter(
        Geography.normalized_state_name == geo.normalized_state_name,
        Geography.normalized_district_name == geo.normalized_district_name,
        RainfallRecord.rainfall_year == max_year
    ).all()
    
    vals = [r.rainfall_mm for r in rains if r.rainfall_mm is not None]
    avg_rain = round(sum(vals) / len(vals), 1) if vals else None
    src = rains[0].rainfall_source if rains else None
    period = rains[0].rainfall_period if rains else None
    
    return avg_rain, max_year, period, src

def resolve_district_response(db: Session, geo: Geography):
    gwra = db.query(GWRAAssessment).filter_by(geography_id=geo.id).order_by(GWRAAssessment.assessment_year.desc()).first()
    
    avg_depth, indicator, depth_count, depth_period, depth_src, depth_year = get_district_depth_and_indicator(db, geo)
    avg_rain, rain_year, rain_period, rain_src = get_district_rainfall(db, geo)
    
    # Check for official government rainfall fallback registry overrides for 2026/survey years
    from app.utils.official_fallbacks import get_official_rainfall_fallback
    fb = get_official_rainfall_fallback(geo.state_name, geo.district_name, depth_year or 2026)
    if fb:
        avg_rain = fb["value"]
        rain_year = depth_year or 2026
        rain_period = fb["period"]
        rain_src = fb["source"]
        
    recharge = gwra.annual_groundwater_recharge_ham if gwra else None
    extractable = gwra.annual_extractable_groundwater_resource_ham if gwra else None
    extraction = gwra.annual_groundwater_extraction_ham if gwra else None
    stage = gwra.stage_of_groundwater_extraction_percent if gwra else None
    net_avail = gwra.net_groundwater_availability_ham if gwra else None
    category = gwra.district_assessment_category if gwra else None
    gwra_year = gwra.assessment_year if gwra else 2025
    gwra_src = gwra.source_document if gwra else None
    
    if stage is None and extraction is not None and extractable is not None and extractable > 0:
        stage = round((extraction / extractable) * 100.0, 2)
        
    # Get historical chronological list
    years_query = db.query(GWRAAssessment.assessment_year).filter_by(geography_id=geo.id).all()
    years = [y[0] for y in years_query]
    if not years:
        years = [gwra_year]
        
    historical_data = []
    for y in sorted(list(set(years)), reverse=True):
        gwra_y = db.query(GWRAAssessment).filter_by(geography_id=geo.id, assessment_year=y).first()
        obs_list_y = db.query(GroundwaterObservation).join(Geography).filter(
            Geography.normalized_state_name == geo.normalized_state_name,
            Geography.normalized_district_name == geo.normalized_district_name,
            GroundwaterObservation.observation_year == y
        ).all()
        depths_y = [o.depth_to_water_level_m_bgl for o in obs_list_y if o.depth_to_water_level_m_bgl is not None]
        avg_depth_y = round(sum(depths_y) / len(depths_y), 2) if depths_y else None
        
        rains_y = db.query(RainfallRecord).join(Geography).filter(
            Geography.normalized_state_name == geo.normalized_state_name,
            Geography.normalized_district_name == geo.normalized_district_name,
            RainfallRecord.rainfall_year == y
        ).all()
        vals_y = [r.rainfall_mm for r in rains_y if r.rainfall_mm is not None]
        avg_rain_y = round(sum(vals_y) / len(vals_y), 1) if vals_y else None
        
        recharge_y = gwra_y.annual_groundwater_recharge_ham if gwra_y else None
        extractable_y = gwra_y.annual_extractable_groundwater_resource_ham if gwra_y else None
        extraction_y = gwra_y.annual_groundwater_extraction_ham if gwra_y else None
        stage_y = gwra_y.stage_of_groundwater_extraction_percent if gwra_y else None
        net_avail_y = gwra_y.net_groundwater_availability_ham if gwra_y else None
        category_y = gwra_y.district_assessment_category if gwra_y else None
        
        # Calculate dynamic stage for historical records
        if stage_y is None and extraction_y is not None and extractable_y is not None and extractable_y > 0:
            stage_y = round((extraction_y / extractable_y) * 100.0, 2)
            
        historical_data.append({
            "year": y,
            "observation_year": y,
            "depth_to_water_level_m_bgl": avg_depth_y,
            "rainfall_mm": avg_rain_y,
            "annual_groundwater_recharge_ham": recharge_y,
            "annual_extractable_groundwater_resource_ham": extractable_y,
            "annual_groundwater_extraction_ham": extraction_y,
            "stage_of_groundwater_extraction_percent": stage_y,
            "net_groundwater_availability_ham": net_avail_y,
            "assessment_category": category_y,
            "data_source_groundwater": obs_list_y[0].source if obs_list_y else None,
            "data_source_rainfall": rains_y[0].rainfall_source if rains_y else None,
            "data_source_gwra": gwra_y.source_document if gwra_y else None
        })

    res = {
        "id": geo.id,
        "district_name": geo.district_name,
        "state_name": geo.state_name,
        "latitude": geo.latitude,
        "longitude": geo.longitude,
        
        "location": {
            "country": geo.country_name,
            "state": geo.state_name,
            "district": geo.district_name
        },
        "assessment": {
            "year": gwra_year,
            "category": category
        },
        "groundwater": {
            "depth_to_water_level_m_bgl": avg_depth,
            "groundwater_level_indicator_percent": indicator
        },
        "resources": {
            "annual_recharge_ham": recharge,
            "annual_extractable_resource_ham": extractable,
            "annual_extraction_ham": extraction,
            "stage_of_extraction_percent": stage,
            "net_groundwater_availability_ham": net_avail
        },
        "rainfall": {
            "value_mm": avg_rain,
            "year": rain_year,
            "period": rain_period
        },
        "sources": {
            "gwra": gwra_src,
            "groundwater_level": depth_src,
            "rainfall": rain_src
        },
        
        # Flattened legacy fields for backward compatibility
        "depth_to_water_level_m_bgl": avg_depth,
        "rainfall_mm": avg_rain,
        "rainfall_period": rain_period,
        "stage_of_groundwater_extraction_percent": stage,
        "assessment_category": category,
        "observation_year": depth_year or gwra_year,
        "data_source_groundwater": depth_src,
        "data_source_rainfall": rain_src,
        "data_source_gwra": gwra_src,
        
        "annual_groundwater_recharge_ham": recharge,
        "annual_groundwater_extraction_ham": extraction,
        "annual_extractable_groundwater_resource_ham": extractable,
        "net_groundwater_availability_ham": net_avail,
        
        "groundwater_data": historical_data
    }
    
    return res

@router.get("")
def get_districts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Fetch basic list of all districts for selectors and dropdown menus. Requires auth.
    """
    geos = db.query(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).order_by(Geography.state_name, Geography.district_name).all()
    return [
        {
            "id": g.id,
            "district_name": g.district_name,
            "state_name": g.state_name,
            "latitude": g.latitude,
            "longitude": g.longitude
        } for g in geos
    ]

@router.get("/search")
def search_districts(
    query: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Filter districts by name matching or state matching.
    Returns lightweight card data (no per-district history loops). Requires auth.
    """
    q = db.query(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    )
    if query:
        q = q.filter(Geography.district_name.ilike(f"%{query}%"))
    if state:
        q = q.filter(Geography.state_name.ilike(state))

    results = q.order_by(Geography.district_name).limit(100).all()

    if not results:
        return []

    # ---- Batch fetch latest groundwater depth per district ----
    from sqlalchemy import text
    state_dist_pairs = list({(g.normalized_state_name, g.normalized_district_name) for g in results})

    # Max obs year per district (single query)
    obs_max_rows = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(GroundwaterObservation.observation_year).label("max_year")
    ).join(GroundwaterObservation).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).group_by(
        Geography.normalized_state_name,
        Geography.normalized_district_name
    ).all()
    obs_max_map = {(r[0], r[1]): r[2] for r in obs_max_rows}

    unique_obs_years = list(set(obs_max_map.values()))
    obs_rows = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        GroundwaterObservation.depth_to_water_level_m_bgl,
        GroundwaterObservation.observation_year
    ).join(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None,
        GroundwaterObservation.observation_year.in_(unique_obs_years)
    ).all() if unique_obs_years else []

    from collections import defaultdict
    obs_depths: dict = defaultdict(list)
    for sn, dn, depth, yr in obs_rows:
        if depth is not None and obs_max_map.get((sn, dn)) == yr:
            obs_depths[(sn, dn)].append(depth)
    depth_avg = {k: round(sum(v) / len(v), 2) for k, v in obs_depths.items()}

    # ---- Batch fetch latest rainfall per district ----
    rain_max_rows = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        func.max(RainfallRecord.rainfall_year).label("max_year")
    ).join(RainfallRecord).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).group_by(
        Geography.normalized_state_name,
        Geography.normalized_district_name
    ).all()
    rain_max_map = {(r[0], r[1]): r[2] for r in rain_max_rows}

    unique_rain_years = list(set(rain_max_map.values()))
    rain_rows = db.query(
        Geography.normalized_state_name,
        Geography.normalized_district_name,
        RainfallRecord.rainfall_mm,
        RainfallRecord.rainfall_year
    ).join(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None,
        RainfallRecord.rainfall_year.in_(unique_rain_years)
    ).all() if unique_rain_years else []

    rain_vals: dict = defaultdict(list)
    for sn, dn, rain, yr in rain_rows:
        if rain is not None and rain_max_map.get((sn, dn)) == yr:
            rain_vals[(sn, dn)].append(rain)
    rain_avg = {k: round(sum(v) / len(v), 1) for k, v in rain_vals.items()}

    # ---- Batch fetch GWRA assessments ----
    geo_ids = [g.id for g in results]
    gwra_rows = db.query(GWRAAssessment).filter(GWRAAssessment.geography_id.in_(geo_ids)).all()
    gwra_map = {g.geography_id: g for g in gwra_rows}

    # ---- Assemble lightweight response ----
    output = []
    for geo in results:
        key = (geo.normalized_state_name, geo.normalized_district_name)
        gwra = gwra_map.get(geo.id)
        avg_depth = depth_avg.get(key)
        avg_rain = rain_avg.get(key)
        stage = gwra.stage_of_groundwater_extraction_percent if gwra else None
        if stage is None and gwra and gwra.annual_groundwater_extraction_ham and gwra.annual_extractable_groundwater_resource_ham:
            stage = round((gwra.annual_groundwater_extraction_ham / gwra.annual_extractable_groundwater_resource_ham) * 100.0, 2)

        output.append({
            "id": geo.id,
            "district_name": geo.district_name,
            "state_name": geo.state_name,
            "latitude": geo.latitude,
            "longitude": geo.longitude,
            "depth_to_water_level_m_bgl": avg_depth,
            "rainfall_mm": avg_rain,
            "stage_of_groundwater_extraction_percent": stage,
            "assessment_category": (gwra.district_assessment_category if gwra else None) or "Safe",
            "annual_groundwater_recharge_ham": gwra.annual_groundwater_recharge_ham if gwra else None,
            "annual_groundwater_extraction_ham": gwra.annual_groundwater_extraction_ham if gwra else None,
        })

    return output

@router.get("/{id}")
def get_district_by_id(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieve single district detail. Logs a ResultAccess action. Requires auth.
    """
    geo = db.query(Geography).filter_by(id=id).first()
    if not geo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="I couldn't find this district in the available groundwater dataset."
        )
    
    # Track result access count
    access_log = ResultAccess(
        user_id=current_user.id,
        geography_id=geo.id,
        access_type="detail"
    )
    db.add(access_log)
    db.commit()
    
    return resolve_district_response(db, geo)

@router.get("/{id}/statistics")
def get_district_statistics(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Retrieves chronological groundwater level data for line charts. Requires auth.
    """
    geo = db.query(Geography).filter_by(id=id).first()
    if not geo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="District not found in database."
        )
        
    # Log access
    access_log = ResultAccess(
        user_id=current_user.id,
        geography_id=geo.id,
        access_type="statistics"
    )
    db.add(access_log)
    db.commit()
    
    details = resolve_district_response(db, geo)
    # The client expects stats in ascending order
    stats = sorted(details["groundwater_data"], key=lambda x: x["year"])
    
    # Rename fields to match Recharts expected parameters in details page
    return [
        {
            "year": item["year"],
            "groundwater_level": item["depth_to_water_level_m_bgl"],
            "depth_to_water_level_m_bgl": item["depth_to_water_level_m_bgl"],
            "rainfall": item["rainfall_mm"],
            "rainfall_mm": item["rainfall_mm"],
            "recharge": item["annual_groundwater_recharge_ham"],
            "annual_groundwater_recharge_ham": item["annual_groundwater_recharge_ham"],
            "extraction": item["annual_groundwater_extraction_ham"],
            "annual_groundwater_extraction_ham": item["annual_groundwater_extraction_ham"],
            "availability": item["annual_extractable_groundwater_resource_ham"],
            "annual_extractable_groundwater_resource_ham": item["annual_extractable_groundwater_resource_ham"],
            "stage_of_groundwater_extraction_percent": item["stage_of_groundwater_extraction_percent"]
        } for item in stats
    ]
