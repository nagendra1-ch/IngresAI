from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import uuid
import re
import asyncio

from app.database import get_db
from app.models import Geography, GeographyAlias, GWRAAssessment, GroundwaterObservation, RainfallRecord, QueryHistory, ResultAccess, User, Conversation, ConversationMessage
from app.routes.auth import get_current_user
from app.schemas.query import ChatRequest, ChatResponse, QueryOut, LocationSchema, AssessmentSchema, GroundwaterSchema, RainfallSchema, ResourcesSchema, ConversationContextSchema
from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherService
from app.services.knowledge_base import resolve_domain_knowledge
from app.services.prediction_service import WaterLevelPredictionService
from app.services.web_search_service import WebSearchService
from app.routes.districts import resolve_district_response

from app.config import settings
from app.utils.temporal import normalize_period_with_year, validate_and_normalize_metadata
from collections import defaultdict

def save_query_history(db: Session, user_id: int, query: str, response: str, geography_id: Optional[int] = None):
    try:
        qh = QueryHistory(
            user_id=user_id,
            query=query,
            response=response,
            geography_id=geography_id
        )
        db.add(qh)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[INGRES-AI] Failed to log query history: {e}")

# ---------------------------------------------------------------------------
# Weather intent constants & helpers
# ---------------------------------------------------------------------------
WEATHER_KEYWORDS = {
    # Core weather terms
    "weather", "temperature", "humidity", "forecast", "raining",
    "wind", "windspeed", "wind speed", "sunny", "cloudy",
    "storm", "thunderstorm", "drizzle", "heatwave", "haze",
    "feels like", "apparent temperature", "current weather",
    "today's weather", "tomorrow's weather", "weather condition",
    "weather forecast", "3-day", "3 day",
    # Additional specific weather terms (no generic words to avoid false positives)
    "fog", "foggy", "mist", "misty", "overcast", "uv index",
    "dew point", "air quality", "aqi", "smog", "hail", "snow",
    "weather api", "live weather", "real-time weather",
    "heat index", "wind chill", "atmospheric pressure",
    "visibility", "sky condition", "weather update",
}
# Rainfall / precipitation keywords that belong to the OFFICIAL dataset
RAINFALL_ONLY_KEYWORDS = {"rainfall", "rain", "precipitation"}

_weather_service_singleton: Optional[WeatherService] = None

def _get_weather_service() -> WeatherService:
    global _weather_service_singleton
    if _weather_service_singleton is None:
        _weather_service_singleton = WeatherService()
    return _weather_service_singleton


def detect_weather_intent(query_lower: str) -> tuple[bool, bool]:
    """Return (has_weather_intent, has_rainfall_only_intent).

    has_weather_intent   – True when query wants live Open-Meteo weather
    has_rainfall_only    – True when query only asks about official rainfall data
    """
    tokens = set(re.findall(r'[a-z0-9]+', query_lower))
    full = query_lower  # also check phrases

    weather_hit = any(kw in full for kw in WEATHER_KEYWORDS) or bool(tokens & WEATHER_KEYWORDS)
    # Treat temporal/live precipitation requests as a weather query
    weather_timeframes = ["current", "live", "now", "today", "tomorrow", "yesterday"]
    is_current_precip = any(x in full for x in weather_timeframes) and any(kw in full for kw in RAINFALL_ONLY_KEYWORDS)
    # Plain "rainfall" / "rain" without weather qualifiers = official rainfall only
    rainfall_hit = any(kw in full for kw in RAINFALL_ONLY_KEYWORDS) and not is_current_precip

    has_weather = weather_hit or is_current_precip
    has_rainfall_only = rainfall_hit and not has_weather
    return has_weather, has_rainfall_only


def fetch_weather_sync(district_name: str) -> Optional[dict]:
    """Synchronous wrapper: call WeatherService from inside a sync FastAPI handler."""
    svc = _get_weather_service()
    try:
        loop = asyncio.new_event_loop()
        result = loop.run_until_complete(svc.get_weather_by_district_name(district_name))
        loop.close()
        return result
    except Exception:
        return None


def format_weather_response(weather: dict, district_name: str) -> str:
    """Format Open-Meteo payload into a clean markdown response."""
    cur = weather.get("current", {})
    forecast = weather.get("forecast", [])
    location = weather.get("location", district_name)

    temp = cur.get("temperature")
    feels = cur.get("feels_like")
    humidity = cur.get("humidity")
    precip = cur.get("precipitation")
    wind = cur.get("wind_speed")
    desc = cur.get("description", "—")

    temp_str    = f"{temp:.1f} °C"   if temp    is not None else "—"
    feels_str   = f"{feels:.1f} °C"  if feels   is not None else "—"
    humidity_str= f"{humidity} %"    if humidity is not None else "—"
    precip_str  = f"{precip} mm"     if precip  is not None else "—"
    wind_str    = f"{wind:.1f} km/h" if wind    is not None else "—"

    lines = [
        f"### Current Weather — {location}",
        "",
        "| Parameter | Value |",
        "|---|---:|",
        f"| Temperature | {temp_str} |",
        f"| Feels Like | {feels_str} |",
        f"| Humidity | {humidity_str} |",
        f"| Precipitation | {precip_str} |",
        f"| Wind Speed | {wind_str} |",
        f"| Condition | {desc} |",
        "",
    ]

    if forecast:
        lines += [
            "### 3-Day Forecast",
            "",
            "| Date | Max °C | Min °C | Precipitation | Probability | Condition |",
            "|---|---:|---:|---:|---:|---|",
        ]
        for day in forecast:
            date  = day.get("date", "—")
            tmax  = f"{day['temp_max']:.1f}"  if day.get("temp_max")  is not None else "—"
            tmin  = f"{day['temp_min']:.1f}"  if day.get("temp_min")  is not None else "—"
            dp    = f"{day['precipitation_sum']} mm" if day.get("precipitation_sum") is not None else "—"
            prob  = f"{day['precipitation_probability']}%" if day.get("precipitation_probability") is not None else "—"
            cond  = day.get("description", "—")
            lines.append(f"| {date} | {tmax} | {tmin} | {dp} | {prob} | {cond} |")
        lines.append("")

    lines.append("**Weather Source:** Open-Meteo (openmeteo.com) — live data")
    return "\n".join(lines)

router = APIRouter(prefix="/api/ai", tags=["AI Assistant"])

def get_state_count_by_assessment_category(db: Session, category: str, assessment_year: int, include_uts: bool = False):
    cat_lower = category.lower().strip()
    if "semi-critical" in cat_lower or "semi critical" in cat_lower:
        target_cat = "Semi-Critical"
    elif "over-exploited" in cat_lower or "over exploited" in cat_lower:
        target_cat = "Over-Exploited"
    elif "critical" in cat_lower:
        target_cat = "Critical"
    elif "safe" in cat_lower:
        target_cat = "Safe"
    elif "saline" in cat_lower:
        target_cat = "Saline"
    else:
        target_cat = "Critical"
        
    union_territories = {
        "andaman and nicobar islands", "chandigarh", "dadra and nagar haveli and daman and diu",
        "delhi", "jammu and kashmir", "ladakh", "lakshadweep", "puducherry"
    }
    
    # Query distinct states containing the target category
    records = db.query(Geography.state_name, func.count(GWRAAssessment.id).label("cnt")).join(
        GWRAAssessment, GWRAAssessment.geography_id == Geography.id
    ).filter(
        GWRAAssessment.district_assessment_category == target_cat,
        GWRAAssessment.assessment_year == assessment_year
    ).group_by(Geography.state_name).all()
    
    filtered = []
    for state_name, count in records:
        is_ut = state_name.lower().strip() in union_territories
        if not include_uts and is_ut:
            continue
        filtered.append({
            "state_name": state_name,
            "unit_count": count
        })
        
    return {
        "category": target_cat,
        "assessment_year": assessment_year,
        "state_count": len(filtered),
        "states": sorted(filtered, key=lambda x: x["unit_count"], reverse=True)
    }

def get_district_count_by_assessment_category(db: Session, category: str, assessment_year: int):
    cat_lower = category.lower().strip()
    if "semi-critical" in cat_lower or "semi critical" in cat_lower:
        target_cat = "Semi-Critical"
    elif "over-exploited" in cat_lower or "over exploited" in cat_lower:
        target_cat = "Over-Exploited"
    elif "critical" in cat_lower:
        target_cat = "Critical"
    elif "safe" in cat_lower:
        target_cat = "Safe"
    elif "saline" in cat_lower:
        target_cat = "Saline"
    else:
        target_cat = "Critical"
        
    records = db.query(Geography.state_name, Geography.district_name).join(
        GWRAAssessment, GWRAAssessment.geography_id == Geography.id
    ).filter(
        GWRAAssessment.district_assessment_category == target_cat,
        GWRAAssessment.assessment_year == assessment_year
    ).distinct().all()
    
    # Group by state
    state_groups = defaultdict(int)
    for state, dist in records:
        state_groups[state] += 1
        
    sorted_states = sorted([{"state_name": k, "unit_count": v} for k, v in state_groups.items()], key=lambda x: x["unit_count"], reverse=True)
    
    return {
        "category": target_cat,
        "assessment_year": assessment_year,
        "district_count": len(records),
        "states": sorted_states
    }

def get_unit_count_by_assessment_category(db: Session, category: str, assessment_year: int):
    cat_lower = category.lower().strip()
    if "semi-critical" in cat_lower or "semi critical" in cat_lower:
        target_cat = "Semi-Critical"
    elif "over-exploited" in cat_lower or "over exploited" in cat_lower:
        target_cat = "Over-Exploited"
    elif "critical" in cat_lower:
        target_cat = "Critical"
    elif "safe" in cat_lower:
        target_cat = "Safe"
    elif "saline" in cat_lower:
        target_cat = "Saline"
    else:
        target_cat = "Critical"
        
    records = db.query(Geography.state_name, func.count(GWRAAssessment.id).label("cnt")).join(
        GWRAAssessment, GWRAAssessment.geography_id == Geography.id
    ).filter(
        GWRAAssessment.district_assessment_category == target_cat,
        GWRAAssessment.assessment_year == assessment_year
    ).group_by(Geography.state_name).all()
    
    total = sum(r[1] for r in records)
    states = [{"state_name": r[0], "unit_count": r[1]} for r in records]
    
    return {
        "category": target_cat,
        "assessment_year": assessment_year,
        "unit_count": total,
        "states": sorted(states, key=lambda x: x["unit_count"], reverse=True)
    }

def format_category_aggregation_response(agg_result: dict, geo_level: str, include_uts: bool = False) -> str:
    cat = agg_result["category"]
    y = agg_result["assessment_year"]
    states_list = agg_result["states"]
    
    if geo_level == "STATE":
        count = agg_result["state_count"]
        label = "States and Union Territories" if include_uts else "States"
        header = f"### {cat} Groundwater Assessment\n\n"
        header += f"**Assessment Year:** {y}\n\n"
        header += f"**{label} with at least one {cat} assessment unit:** {count}\n\n"
        
        table = f"| {label.split(' and ')[0] if ' and ' in label else label} | {cat} Assessment Units |\n"
        table += f"|---|---:|\n"
        for s in states_list:
            table += f"| {s['state_name']} | {s['unit_count']} |\n"
            
        explanation = (
            f"\n**Source:** GWRA {y} / CGWB\n\n"
            f"Explanation:\n"
            f"This counts unique Indian {label.lower()} that contain at least one assessment unit classified as {cat}. "
            f"It does not mean that the entire state is classified as {cat}."
        )
        return header + table + explanation
        
    elif geo_level == "DISTRICT":
        count = agg_result["district_count"]
        header = f"### {cat} Groundwater Assessment\n\n"
        header += f"**Assessment Year:** {y}\n\n"
        header += f"**Districts classified as {cat}:** {count}\n\n"
        
        table = f"| State | Number of {cat} Districts |\n"
        table += f"|---|---:|\n"
        for s in states_list:
            table += f"| {s['state_name']} | {s['unit_count']} |\n"
            
        explanation = (
            f"\n**Source:** GWRA {y} / CGWB\n\n"
            f"Explanation:\n"
            f"This counts the total number of unique districts classified as {cat} across India."
        )
        return header + table + explanation
        
    else: # UNIT level
        count = agg_result["unit_count"]
        header = f"### {cat} Groundwater Assessment\n\n"
        header += f"**Assessment Year:** {y}\n\n"
        header += f"**Assessment Units classified as {cat}:** {count}\n\n"
        
        table = f"| State | Number of {cat} Assessment Units |\n"
        table += f"|---|---:|\n"
        for s in states_list:
            table += f"| {s['state_name']} | {s['unit_count']} |\n"
            
        explanation = (
            f"\n**Source:** GWRA {y} / CGWB\n\n"
            f"Explanation:\n"
            f"This counts the total number of assessment units (districts/blocks) classified as {cat} across India."
        )
        return header + table + explanation

def get_districts_list_by_assessment_category(db: Session, category: str, assessment_year: int):
    cat_lower = category.lower().strip()
    if "semi-critical" in cat_lower or "semi critical" in cat_lower:
        target_cat = "Semi-Critical"
    elif "over-exploited" in cat_lower or "over exploited" in cat_lower:
        target_cat = "Over-Exploited"
    elif "critical" in cat_lower:
        target_cat = "Critical"
    elif "safe" in cat_lower:
        target_cat = "Safe"
    elif "saline" in cat_lower:
        target_cat = "Saline"
    else:
        target_cat = "Critical"
        
    records = db.query(Geography.state_name, Geography.district_name, func.count(GWRAAssessment.id).label("units_cnt")).join(
        GWRAAssessment, GWRAAssessment.geography_id == Geography.id
    ).filter(
        GWRAAssessment.district_assessment_category == target_cat,
        GWRAAssessment.assessment_year == assessment_year
    ).group_by(Geography.state_name, Geography.district_name).all()
    
    unique_districts_count = len(records)
    sorted_records = sorted(records, key=lambda x: (x[0], x[1]))
    
    return {
        "category": target_cat,
        "assessment_year": assessment_year,
        "district_count": unique_districts_count,
        "districts": [{"state_name": r[0], "district_name": r[1], "unit_count": r[2]} for r in sorted_records]
    }

def format_districts_list_response(agg_result: dict, count_only: bool = False) -> str:
    cat = agg_result["category"]
    y = agg_result["assessment_year"]
    districts = agg_result["districts"]
    count = agg_result["district_count"]
    
    header = f"### {cat} Assessment Districts\n\n"
    header += f"**Assessment Year:** {y}\n"
    header += f"**Assessment Category:** {cat}\n\n"
    header += f"**Total districts containing at least one {cat} assessment unit:** {count}\n\n"
    header += f"**Districts classified as {cat}:** {count}\n\n"
    
    if count_only:
        header += f"**Source:** GWRA {y} / CGWB\n"
        return header
        
    table = f"| State | District | {cat} Assessment Units |\n"
    table += "|---|---|---:|\n"
    for d in districts:
        table += f"| {d['state_name']} | {d['district_name']} | {d['unit_count']} |\n"
        
    explanation = (
        f"\n**Source:** GWRA {y} / CGWB\n\n"
        f"Explanation:\n"
        f"These are districts containing at least one assessment unit classified as {cat}. "
        f"This does not mean the entire district is necessarily classified as {cat}."
    )
    return header + table + explanation

def get_state_with_most_category(db: Session, category: str, assessment_year: int):
    cat_lower = category.lower().strip()
    if "semi-critical" in cat_lower or "semi critical" in cat_lower:
        target_cat = "Semi-Critical"
    elif "over-exploited" in cat_lower or "over exploited" in cat_lower:
        target_cat = "Over-Exploited"
    elif "critical" in cat_lower:
        target_cat = "Critical"
    elif "safe" in cat_lower:
        target_cat = "Safe"
    elif "saline" in cat_lower:
        target_cat = "Saline"
    else:
        target_cat = "Critical"
        
    records = db.query(Geography.state_name, func.count(GWRAAssessment.id).label("cnt")).join(
        GWRAAssessment, GWRAAssessment.geography_id == Geography.id
    ).filter(
        GWRAAssessment.district_assessment_category == target_cat,
        GWRAAssessment.assessment_year == assessment_year
    ).group_by(Geography.state_name).all()
    
    if not records:
        return None
        
    sorted_records = sorted(records, key=lambda x: x[1], reverse=True)
    max_rec = sorted_records[0]
    
    return {
        "category": target_cat,
        "assessment_year": assessment_year,
        "state_name": max_rec[0],
        "count": max_rec[1]
    }

def format_rank_state_response(rank_result: dict) -> str:
    if not rank_result:
        return "No data found for this category and year."
    cat = rank_result["category"]
    y = rank_result["assessment_year"]
    state = rank_result["state_name"]
    count = rank_result["count"]
    
    header = f"### State with Most {cat} Assessment Units\n\n"
    header += f"**Assessment Year:** {y}\n"
    header += f"**Assessment Category:** {cat}\n\n"
    header += f"The state with the highest number of {cat} assessment units is **{state}** with **{count}** units.\n\n"
    header += f"**Source:** GWRA {y} / CGWB\n"
    return header

def clean_input_token(val):
    if not val:
        return ""
    cleaned = str(val).strip().lower()
    return re.sub(r'[^a-z0-9]', '', cleaned)

def resolve_query_geographies(db: Session, query_text: str):
    query_lower = query_text.lower().strip()
    
    # Find candidate states from query
    states_query = db.query(Geography.state_name).distinct().all()
    states = [s[0] for s in states_query]
    
    state_in_query = None
    for s in states:
        if s.lower() in query_lower:
            state_in_query = s
            break
            
    # Find matching district geographies
    all_districts = db.query(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).all()
    
    matched_map = {}  # geo_id -> (start_pos, geo)
    
    for g in all_districts:
        g_name_lower = g.district_name.lower().strip()
        pattern = r'\b' + re.escape(g_name_lower) + r'\b'
        match = re.search(pattern, query_lower)
        if match:
            start_pos = match.start()
            if g.id not in matched_map or start_pos < matched_map[g.id][0]:
                g.matched_sublocation = None
                matched_map[g.id] = (start_pos, g)
                
    # Always check aliases as well!
    aliases = db.query(GeographyAlias).join(Geography).filter(
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None
    ).all()
    for a in aliases:
        a_name_lower = a.alias_name.lower().strip()
        pattern = r'\b' + re.escape(a_name_lower) + r'\b'
        match = re.search(pattern, query_lower)
        if match:
            start_pos = match.start()
            geo = a.geography
            if geo.id not in matched_map or start_pos < matched_map[geo.id][0]:
                geo.matched_sublocation = None
                matched_map[geo.id] = (start_pos, geo)
                
    # Check Mandals and Villages in DB if no district match or if comparison needs 2
    is_comp_hint = any(x in query_lower for x in ["compare", "comparison", "vs", "versus", "difference", "between", "which is higher", "which is lower"])
    if not matched_map or (is_comp_hint and len(matched_map) < 2):
        ENGLISH_STOP_WORDS = {
            "what", "where", "when", "which", "who", "whom", "this", "that", "these", "those",
            "then", "than", "them", "they", "their", "there", "here", "with", "from", "about",
            "your", "have", "were", "will", "would", "could", "should", "some", "many", "more",
            "less", "most", "year", "years", "show", "find", "list", "name", "names", "district",
            "districts", "state", "states", "mandal", "mandals", "village", "villages", "water",
            "level", "levels", "rainfall", "rain", "recharge", "extraction", "stage", "status",
            "category", "value", "values", "data", "report", "reports", "history", "trend",
            "next", "last", "past", "future", "compare", "comparison", "versus", "difference", "between",
            "ground", "groundwater", "table", "depth", "give", "tell", "please", "help"
        }
        tokens = [w for w in re.findall(r'[a-z0-9]+', query_lower) if len(w) >= 4 and w not in ENGLISH_STOP_WORDS]
        
        for tok in tokens:
            m_matches = db.query(Geography).filter(
                (Geography.mandal_name.ilike(tok)) | 
                (Geography.village_name.ilike(tok))
            ).all()
            if m_matches:
                first_m = m_matches[0]
                parent_dist = db.query(Geography).filter(
                    Geography.district_name == first_m.district_name,
                    Geography.state_name == first_m.state_name,
                    Geography.normalized_mandal_name == None,
                    Geography.normalized_village_name == None
                ).first()
                if parent_dist:
                    start_pos = query_lower.find(tok)
                    parent_dist.matched_sublocation = first_m.mandal_name or first_m.village_name or tok.title()
                    matched_map[parent_dist.id] = (start_pos if start_pos != -1 else 0, parent_dist)
                    if not is_comp_hint:
                        break

    # Sort matched geographies by appearance order in query
    sorted_geos = [item[1] for item in sorted(matched_map.values(), key=lambda x: x[0])]
    
    # Filter using Authoritative Geography to prevent false ambiguities
    authoritative_map = {
        "guntur": "Andhra Pradesh",
        "kurnool": "Andhra Pradesh",
        "ysr kadapa": "Andhra Pradesh",
        "kadapa": "Andhra Pradesh",
        "ananthapuramu": "Andhra Pradesh",
        "anantapur": "Andhra Pradesh",
        "hapur": "Uttar Pradesh",
        "dr. b.r. ambedkar konaseema": "Andhra Pradesh",
        "konaseema": "Andhra Pradesh",
        "theni": "Tamil Nadu",
        "nilgiris": "Tamil Nadu"
    }
    
    filtered_geos = []
    for g in sorted_geos:
        g_name_lower = g.district_name.lower().strip()
        if g_name_lower in authoritative_map:
            if g.state_name.lower().strip() != authoritative_map[g_name_lower].lower().strip():
                continue
        is_false_alias = False
        for a in g.aliases:
            a_name_lower = a.alias_name.lower().strip()
            if a_name_lower in authoritative_map:
                if g.state_name.lower().strip() != authoritative_map[a_name_lower].lower().strip():
                    is_false_alias = True
                    break
        if is_false_alias:
            continue
        filtered_geos.append(g)
    matched_geos = filtered_geos
    
    if state_in_query:
        matched_geos = [g for g in matched_geos if g.state_name.lower() == state_in_query.lower()]
        
    # If single location was asked (not a comparison), keep only 1 match
    if not is_comp_hint and len(matched_geos) > 1:
        exact_matched = [g for g in matched_geos if re.search(r'\b' + re.escape(g.district_name.lower()) + r'\b', query_lower)]
        if exact_matched:
            matched_geos = exact_matched[:1]
        else:
            matched_geos = matched_geos[:1]
        
    return matched_geos, state_in_query

def generate_factual_response(details: dict) -> str:
    name = details["district_name"]
    state = details["state_name"]
    y = details["assessment"]["year"]
    category = details["assessment"]["category"] or "Unknown"
    
    depth = details["groundwater"]["depth_to_water_level_m_bgl"]
    indicator = details["groundwater"]["groundwater_level_indicator_percent"]
    indicator_str = f"{indicator:.2f}%" if indicator is not None else "Data insufficient"
    
    rainfall = details["rainfall"]["value_mm"]
    rain_year = details["rainfall"]["year"]
    rain_period = details["rainfall"]["period"]
    
    recharge = details["resources"]["annual_recharge_ham"]
    extractable = details["resources"]["annual_extractable_resource_ham"]
    extraction = details["resources"]["annual_extraction_ham"]
    stage = details["resources"]["stage_of_extraction_percent"]
    net_avail = details["resources"]["net_groundwater_availability_ham"]
    
    gwra_src = details["sources"]["gwra"] or "GWRA_2025.pdf"
    wl_src = details["sources"]["groundwater_level"] or "January 2026.xlsx.pdf"
    rain_src = details["sources"]["rainfall"] or "IMD Gridded Rainfall Dataset"
    
    obs_year = details.get("observation_year") or 2026
    obs_period = details.get("rainfall_period") or "January"
    
    # Rule 10 Validation & Normalization
    norm_obs_period = validate_and_normalize_metadata(wl_src, obs_period, obs_year)
    
    norm_rain_period = rain_period
    if not norm_rain_period:
        norm_rain_period = "Period: Not specified in source"
    elif str(rain_year) == "2026" and "annual" in str(norm_rain_period).lower():
        norm_rain_period = "Period: Not specified in source"
        
    if norm_rain_period != "Period: Not specified in source":
        norm_rain_period = normalize_period_with_year(norm_rain_period, rain_year)
    
    # Format numbers
    recharge_str = f"{recharge:,.2f} ham" if recharge is not None else "Data unavailable"
    extractable_str = f"{extractable:,.2f} ham" if extractable is not None else "Data unavailable"
    extraction_str = f"{extraction:,.2f} ham" if extraction is not None else "Data unavailable"
    net_avail_str = f"{net_avail:,.2f} ham" if net_avail is not None else "Data unavailable"
    depth_str = f"{depth:.2f} m bgl" if depth is not None else "Data unavailable"
    rainfall_str = f"{rainfall:,.1f} mm" if rainfall is not None else "Data unavailable"
    stage_str = f"{stage:.2f}%" if stage is not None else "Data unavailable"
    
    # Bold versions
    b_depth_str = f"**{depth_str}**" if depth is not None else "Data unavailable"
    b_indicator_str = f"**{indicator_str}**" if indicator is not None else "Data insufficient"
    b_recharge_str = f"**{recharge_str}**" if recharge is not None else "Data unavailable"
    b_extractable_str = f"**{extractable_str}**" if extractable is not None else "Data unavailable"
    b_extraction_str = f"**{extraction_str}**" if extraction is not None else "Data unavailable"
    b_stage_str = f"**{stage_str}**" if stage is not None else "Data unavailable"
    b_net_avail_str = f"**{net_avail_str}**" if net_avail is not None else "Data unavailable"
    b_category = f"**{category}**"
    
    return (
        f"### {name}, {state}\n\n"
        f"### Groundwater Information\n\n"
        f"| Parameter | Value | Period / Temporal Metadata |\n"
        f"|---|---:|---|\n"
        f"| **Depth to Water Level** | {b_depth_str} | Observation: **{norm_obs_period}** |\n"
        f"| **Groundwater Level Indicator** | {b_indicator_str} | Calculated indicator based on groundwater-depth observations |\n"
        f"| **Annual Groundwater Recharge** | {b_recharge_str} | GWRA Assessment Year: **{y}** |\n"
        f"| **Annual Extractable Groundwater Resource** | {b_extractable_str} | GWRA Assessment Year: **{y}** |\n"
        f"| **Annual Groundwater Extraction** | {b_extraction_str} | GWRA Assessment Year: **{y}** |\n"
        f"| **Stage of Groundwater Extraction** | {b_stage_str} | GWRA Assessment Year: **{y}** |\n"
        f"| **Net Groundwater Availability for Future Use** | {b_net_avail_str} | GWRA Assessment Year: **{y}** |\n"
        f"| **District Assessment Category** | {b_category} | GWRA Assessment Year: **{y}** |\n\n"
        f"### Annual Rainfall\n\n"
        f"**Rainfall: {rainfall_str}**\n\n"
        f"**Period:** {norm_rain_period}\n\n"
        f"> Do not label this value as **\"Annual {rain_year}\"** unless the source explicitly confirms that {rainfall_str} represents the complete calendar year {rain_year}.\n\n"
        f"### Important Note\n\n"
        f"**Depth to Water Level ({depth_str})** and **Groundwater Level Indicator ({indicator_str})** are different metrics.\n\n"
        f"* **{depth_str}** = observed depth to groundwater below ground level.\n"
        f"* **{indicator_str}** = application-calculated normalized indicator based on groundwater-depth observations.\n"
        f"* **{stage_str}** = official Stage of Groundwater Extraction from the GWRA {y} assessment.\n\n"
        f"The Groundwater Level Indicator must **not** be presented as the official groundwater level or as the Stage of Groundwater Extraction.\n\n"
        f"### Sources\n\n"
        f"* GWRA: {gwra_src} — Assessment Year: {y}\n"
        f"* Groundwater Level: {wl_src} — Observation: {norm_obs_period}\n"
        f"* Rainfall: {rain_src} — {norm_rain_period}\n"
        f"* Dataset: IN-GRES Groundwater Dataset\n"
    )

def format_prediction_response(pred: dict) -> str:
    """Formats hydro-statistical predictive model output into rich Markdown."""
    d_name = pred["district_name"]
    s_name = pred["state_name"]
    b = pred["baseline"]
    series = pred["projected_series"]
    scenarios = pred["all_scenarios_comparison"]
    insights = pred["insights"]
    meta = pred["methodology"]

    rows = []
    for p in series:
        rows.append(
            f"| **{p['year']}** | **{p['depth_to_water_level_m_bgl']:.2f} m bgl** | {p['confidence_lower_m_bgl']:.2f} – {p['confidence_upper_m_bgl']:.2f} m | {p['stage_of_extraction_percent']:.1f}% | {p['category']} | {p['risk_level']} |"
        )
    table_str = "\n".join(rows)

    scen_items = []
    for k, s in scenarios.items():
        chg_sign = "+" if s["depth_change_m"] >= 0 else ""
        scen_items.append(
            f"* **{s['icon']} {s['name']}**: Projected Depth **{s['final_year_depth_m_bgl']:.2f} m bgl** (Change: {chg_sign}{s['depth_change_m']:.2f} m) · Status: **{s['final_year_category']}**"
        )
    scenarios_str = "\n".join(scen_items)

    insights_str = "\n".join([f"* **{i['title']}**: {i['content']}" for i in insights])

    return (
        f"## 🔮 Future Groundwater Level Prediction — {d_name} ({s_name})\n\n"
        f"### 📍 Current Baseline ({b['year']})\n"
        f"* **Depth to Water Level**: **{b['depth_to_water_level_m_bgl']:.2f} m bgl**\n"
        f"* **Stage of Extraction**: **{b['stage_of_extraction_percent']:.1f}%** (Category: **{b['category']}**)\n"
        f"* **Historical Trend Rate**: **{b['annual_trend_rate_m_per_year']:+.2f} m/year** (Evaluated across {b['historical_data_points_count']} historical observation years)\n\n"
        f"### 📈 Multi-Year Model Projections (Baseline Normal Scenario)\n\n"
        f"| Year | Projected Depth | 80% Confidence Interval | Stage of Extraction | Projected Category | Risk Level |\n"
        f"|:---:|:---:|:---:|:---:|:---:|:---:|\n"
        f"{table_str}\n\n"
        f"### 🌦️ Multi-Scenario Impact Analysis\n"
        f"{scenarios_str}\n\n"
        f"### 💡 Key Findings & Advisory\n"
        f"{insights_str}\n\n"
        f"---\n"
        f"**Model Type:** {meta['label']} · {meta['data_source']}\n\n"
        f"*{meta['disclaimer']}*"
    )


def is_greeting_or_help_query(query: str) -> bool:
    """Detects general greetings and pleasantries (pure greetings only)."""
    q = query.lower().strip()
    q_clean = re.sub(r'[^\w\s]', '', q).strip()
    
    # Matches variations: hi, hii, hiii, hey, heyy, hello, namaste, vanakkam, hola, etc.
    greeting_pattern = r'^(h+i+|h+e+y+|hello+|namaste|vanakkam|hola|greetings|good\s+(morning|afternoon|evening|day)|sup|yo)(\s+.*)?$'
    if re.match(greeting_pattern, q_clean):
        return True
        
    pure_greetings = {
        "hi", "hey", "hello", "namaste", "vanakkam", "greetings",
        "good morning", "good afternoon", "good evening", "how are you", "how r u"
    }
    if q_clean in pure_greetings:
        return True
        
    return False

def is_unrelated_query(query: str) -> bool:
    # Domain knowledge questions (What is INGRES, GEC, categories, formulas, guide) are fully in-scope
    if resolve_domain_knowledge(query) is not None:
        return False

    # Greetings or introductory commands are fully in-scope
    if is_greeting_or_help_query(query):
        return False

    query_lower = query.lower().strip()

    # Weather queries are in-scope
    has_weather, _ = detect_weather_intent(query_lower)
    if has_weather:
        return False
        
    # Domain keywords to confirm standard groundwater queries
    groundwater_keywords = {
        "groundwater", "water", "rainfall", "rain", "recharge", "extraction", "stage", "gwra",
        "aquifer", "borewell", "wells", "well", "cgwb", "infiltration", "conservation", "irrigation",
        "crop", "crops", "depth", "level", "drought", "depletion", "monsoon", "precipitation",
        "safe", "critical", "over-exploited", "semi-critical", "saline", "district", "districts",
        "mandal", "mandals", "village", "villages", "state", "states", "compare", "conservation",
        "harvesting", "pit", "pits", "dam", "dams", "tank", "tanks", "pond", "ponds", "trench", "trenches",
        "watershed", "drip", "sprinkler", "ambedkar", "konaseema", "ysr", "kadapa", "guntur", "ananthapuramu",
        "kurnool", "theni", "nilgiris", "ingres", "in-gres", "gec", "ham", "mbgl", "m bgl", "indicator", "methodology"
    }
    
    words = re.findall(r'[a-z0-9]+', query_lower)
    if any(w in groundwater_keywords for w in words):
        return False
        
    return True


# ---------------------------------------------------------------------------
# National Ranking Handler
# ---------------------------------------------------------------------------
_RANKING_METRIC_MAP = {
    # Depth to water level: "highest level" = shallowest = ASC; "lowest level" = deepest = DESC
    "depth_asc":  ("depth_to_water_level_m_bgl",  "Depth to Water Level (m bgl)",  "Shallowest (Highest Groundwater Level)"),
    "depth_desc": ("depth_to_water_level_m_bgl",  "Depth to Water Level (m bgl)",  "Deepest (Lowest Groundwater Level)"),
    "recharge_desc":   ("annual_groundwater_recharge_ham",   "Annual Recharge (ham)",   "Highest Recharge"),
    "recharge_asc":    ("annual_groundwater_recharge_ham",   "Annual Recharge (ham)",   "Lowest Recharge"),
    "extraction_desc": ("annual_groundwater_extraction_ham", "Annual Extraction (ham)", "Highest Extraction"),
    "extraction_asc":  ("annual_groundwater_extraction_ham", "Annual Extraction (ham)", "Lowest Extraction"),
    "stage_desc":      ("stage_of_groundwater_extraction_percent", "Stage of Extraction (%)", "Highest Stage"),
    "stage_asc":       ("stage_of_groundwater_extraction_percent", "Stage of Extraction (%)", "Lowest Stage"),
    "rainfall_desc":   ("rainfall_mm",  "Annual Rainfall (mm)",  "Highest Rainfall"),
    "rainfall_asc":    ("rainfall_mm",  "Annual Rainfall (mm)",  "Lowest Rainfall"),
    "availability_desc": ("net_groundwater_availability_ham", "Net Availability (ham)", "Highest Net Availability"),
    "availability_asc":  ("net_groundwater_availability_ham", "Net Availability (ham)", "Lowest Net Availability"),
}

def resolve_national_ranking(db: Session, query_lower: str) -> Optional[str]:
    """
    Detect and resolve a national ranking query such as:
      'Which district has the highest groundwater level?'
      'Which district has the most recharge?'
      'Top districts with lowest extraction'
    Returns a formatted markdown string, or None if not a ranking query.
    """
    is_rank = any(x in query_lower for x in [
        "highest", "lowest", "most", "least", "top", "best", "worst",
        "maximum", "minimum", "which district has", "which districts have",
        "low", "high"
    ])
    if not is_rank:
        return None

    # Determine direction
    wants_high = any(x in query_lower for x in ["highest", "most", "maximum", "top", "best", "high"])
    wants_low  = any(x in query_lower for x in ["lowest", "least", "minimum", "worst", "low"])
    # Default to high if ambiguous
    direction = "desc" if wants_high or not wants_low else "asc"

    # Determine metric
    if any(x in query_lower for x in ["level", "depth", "water table", "water level"]):
        # For groundwater level: "highest level" = shallowest depth = ASC order
        metric_key = "depth_asc" if wants_high else "depth_desc"
    elif any(x in query_lower for x in ["recharge", "replenish"]):
        metric_key = f"recharge_{direction}"
    elif any(x in query_lower for x in ["stage"]):
        metric_key = f"stage_{direction}"
    elif any(x in query_lower for x in ["extraction", "draft", "withdraw"]):
        metric_key = f"extraction_{direction}"
    elif any(x in query_lower for x in ["rainfall", "rain", "precipitation"]):
        metric_key = f"rainfall_{direction}"
    elif any(x in query_lower for x in ["availability", "available", "surplus"]):
        metric_key = f"availability_{direction}"
    else:
        # Fallback: groundwater level
        metric_key = "depth_asc" if wants_high else "depth_desc"

    col_name, col_label, rank_label = _RANKING_METRIC_MAP[metric_key]
    order_dir = "asc" if metric_key.endswith("_asc") else "desc"

    # State filter?
    state_filter = None
    states_in_db = [s[0] for s in db.query(Geography.state_name).distinct().all()]
    for s in states_in_db:
        if s.lower() in query_lower:
            state_filter = s
            break

    # How many results?
    n_match = re.search(r'\btop\s*(\d+)\b', query_lower)
    n = int(n_match.group(1)) if n_match else 10
    n = min(n, 50)

    # Build query joining Geography → GroundwaterObservation for depth,
    # Geography for rainfall, or GWRAAssessment for volumetric metrics
    from app.models import GroundwaterObservation, GWRAAssessment, RainfallRecord
    from sqlalchemy import desc as sa_desc, asc as sa_asc

    results = []

    if col_name in ("depth_to_water_level_m_bgl",):
        q = (
            db.query(
                Geography.district_name,
                Geography.state_name,
                GroundwaterObservation.depth_to_water_level_m_bgl,
            )
            .join(GroundwaterObservation, GroundwaterObservation.geography_id == Geography.id)
            .filter(
                Geography.normalized_mandal_name == None,
                Geography.normalized_village_name == None,
                GroundwaterObservation.depth_to_water_level_m_bgl != None,
            )
        )
        if state_filter:
            q = q.filter(Geography.state_name == state_filter)
        if order_dir == "asc":
            q = q.order_by(sa_asc(GroundwaterObservation.depth_to_water_level_m_bgl))
        else:
            q = q.order_by(sa_desc(GroundwaterObservation.depth_to_water_level_m_bgl))
        rows = q.limit(n).all()
        results = [(r.district_name, r.state_name, r.depth_to_water_level_m_bgl) for r in rows]

    elif col_name == "rainfall_mm":
        from sqlalchemy import func
        q = (
            db.query(
                Geography.district_name,
                Geography.state_name,
                func.avg(RainfallRecord.rainfall_mm).label("avg_rainfall"),
            )
            .join(RainfallRecord, RainfallRecord.geography_id == Geography.id)
            .filter(
                Geography.district_name != None,
                RainfallRecord.rainfall_mm != None,
            )
            .group_by(
                Geography.normalized_district_name,
                Geography.normalized_state_name,
                Geography.district_name,
                Geography.state_name,
            )
        )
        if state_filter:
            q = q.filter(Geography.state_name == state_filter)
        if order_dir == "desc":
            q = q.order_by(sa_desc("avg_rainfall"))
        else:
            q = q.order_by(sa_asc("avg_rainfall"))
        rows = q.limit(n).all()
        results = [(r.district_name, r.state_name, r.avg_rainfall) for r in rows]

    else:
        # GWRAAssessment metrics
        col_attr = getattr(GWRAAssessment, col_name, None)
        if col_attr is None:
            return None
        q = (
            db.query(
                Geography.district_name,
                Geography.state_name,
                col_attr,
            )
            .join(GWRAAssessment, GWRAAssessment.geography_id == Geography.id)
            .filter(
                Geography.normalized_mandal_name == None,
                Geography.normalized_village_name == None,
                col_attr != None,
            )
        )
        if state_filter:
            q = q.filter(Geography.state_name == state_filter)
        if order_dir == "desc":
            q = q.order_by(sa_desc(col_attr))
        else:
            q = q.order_by(sa_asc(col_attr))
        rows = q.limit(n).all()
        results = [(r[0], r[1], r[2]) for r in rows]

    if not results:
        return None

    # Format response
    scope = f" in {state_filter}" if state_filter else " across India"
    header = (
        f"### Top {len(results)} Districts — {rank_label}{scope}\n\n"
        f"| # | District | State | {col_label} |\n"
        f"|---|---|---|---:|\n"
    )
    rows_str = ""
    for i, (dist, state, val) in enumerate(results, 1):
        if col_name == "depth_to_water_level_m_bgl":
            val_str = f"{val:.2f} m bgl"
        elif col_name in ("annual_groundwater_recharge_ham", "annual_groundwater_extraction_ham", "net_groundwater_availability_ham"):
            val_str = f"{val:,.2f} ham"
        elif col_name == "stage_of_groundwater_extraction_percent":
            val_str = f"{val:.2f}%"
        elif col_name == "rainfall_mm":
            val_str = f"{val:.1f} mm"
        else:
            val_str = str(val)
        rows_str += f"| {i} | {dist} | {state} | {val_str} |\n"

    note = ""
    if col_name == "depth_to_water_level_m_bgl" and wants_high:
        note = (
            "\n> **Note:** A lower depth value (m bgl) means groundwater is closer to the surface, "
            "i.e., a **higher** groundwater level. Districts at the top of this list have the "
            "shallowest water table — the highest groundwater level.\n"
        )

    return (
        header + rows_str
        + note
        + f"\n**Source:** IN-GRES Groundwater Dataset (CGWB / IMD)\n"
    )

# ---------------------------------------------------------------------------
# State-Level Statistics Handler
# ---------------------------------------------------------------------------
def resolve_state_statistics(db: Session, state_name: str) -> Optional[str]:
    """
    Returns aggregate groundwater statistics for all districts within a given state.
    Covers: assessment category breakdown, avg depth, total recharge, extraction,
    net availability, avg rainfall, and a per-district summary table.
    """
    from app.models import GroundwaterObservation, GWRAAssessment, RainfallRecord
    from sqlalchemy import func, desc as sa_desc

    state_row = db.query(Geography.state_name).filter(
        func.upper(Geography.state_name) == state_name.upper().strip()
    ).first()
    canonical_state = state_row[0] if state_row else None
    if not canonical_state:
        return None

    # ── 1. GWRA Aggregates ────────────────────────────────────────────────
    gwra_rows = (
        db.query(
            Geography.district_name,
            GWRAAssessment.district_assessment_category,
            GWRAAssessment.assessment_year,
            GWRAAssessment.annual_groundwater_recharge_ham,
            GWRAAssessment.annual_extractable_groundwater_resource_ham,
            GWRAAssessment.annual_groundwater_extraction_ham,
            GWRAAssessment.net_groundwater_availability_ham,
            GWRAAssessment.stage_of_groundwater_extraction_percent,
        )
        .join(GWRAAssessment, GWRAAssessment.geography_id == Geography.id)
        .filter(
            Geography.state_name == canonical_state,
            Geography.normalized_mandal_name == None,
            Geography.normalized_village_name == None,
        )
        .order_by(sa_desc(GWRAAssessment.assessment_year), Geography.district_name)
        .all()
    )

    if not gwra_rows:
        return None

    # Use most recent assessment year
    latest_year = gwra_rows[0][2]
    gwra_rows = [r for r in gwra_rows if r[2] == latest_year]

    # ── 2. Depth to Water Level (avg per district) ───────────────────────
    depth_rows = (
        db.query(
            Geography.district_name,
            func.avg(GroundwaterObservation.depth_to_water_level_m_bgl).label("avg_depth"),
        )
        .join(GroundwaterObservation, GroundwaterObservation.geography_id == Geography.id)
        .filter(
            Geography.state_name == canonical_state,
            GroundwaterObservation.depth_to_water_level_m_bgl != None,
        )
        .group_by(Geography.district_name)
        .all()
    )
    depth_map = {r.district_name: r.avg_depth for r in depth_rows}

    # ── 3. Rainfall (avg per district) ───────────────────────────────────
    rain_rows = (
        db.query(
            Geography.district_name,
            func.avg(RainfallRecord.rainfall_mm).label("avg_rain"),
        )
        .join(RainfallRecord, RainfallRecord.geography_id == Geography.id)
        .filter(
            Geography.state_name == canonical_state,
            RainfallRecord.rainfall_mm != None,
        )
        .group_by(Geography.district_name)
        .all()
    )
    rain_map = {r.district_name: r.avg_rain for r in rain_rows}

    # ── 4. Build per-district rows ────────────────────────────────────────
    category_counts: dict = {}
    total_recharge = 0.0
    total_extraction = 0.0
    total_net = 0.0
    total_extractable = 0.0
    valid_recharge = valid_extraction = valid_net = valid_extractable = 0
    district_rows = []

    for row in gwra_rows:
        dist_name = row[0]
        cat = row[1] or "Unknown"
        recharge = row[3]
        extractable = row[4]
        extraction = row[5]
        net = row[6]
        stage = row[7]
        depth = depth_map.get(dist_name)
        rainfall = rain_map.get(dist_name)

        category_counts[cat] = category_counts.get(cat, 0) + 1

        if recharge is not None:
            total_recharge += recharge
            valid_recharge += 1
        if extraction is not None:
            total_extraction += extraction
            valid_extraction += 1
        if net is not None:
            total_net += net
            valid_net += 1
        if extractable is not None:
            total_extractable += extractable
            valid_extractable += 1

        district_rows.append({
            "district": dist_name,
            "category": cat,
            "depth": depth,
            "rainfall": rainfall,
            "recharge": recharge,
            "extraction": extraction,
            "stage": stage,
            "net": net,
        })

    n_districts = len(district_rows)

    # ── 5. Format Response ────────────────────────────────────────────────
    # Category breakdown
    cat_order = ["Safe", "Semi-Critical", "Critical", "Over-Exploited", "Saline", "Unknown"]
    cat_lines = ""
    for c in cat_order:
        cnt = category_counts.get(c, 0)
        if cnt:
            bar = "█" * cnt
            cat_lines += f"| {c} | {cnt} | {bar} |\n"

    # Aggregate summary
    recharge_str = f"{total_recharge:,.2f} ham" if valid_recharge else "N/A"
    extraction_str = f"{total_extraction:,.2f} ham" if valid_extraction else "N/A"
    net_str = f"{total_net:,.2f} ham" if valid_net else "N/A"
    extractable_str = f"{total_extractable:,.2f} ham" if valid_extractable else "N/A"
    overall_stage = f"{(total_extraction/total_extractable*100):.1f}%" if (valid_extraction and valid_extractable and total_extractable > 0) else "N/A"

    # Per-district table (sorted by category severity then district name)
    severity = {"Over-Exploited": 0, "Critical": 1, "Semi-Critical": 2, "Saline": 3, "Safe": 4, "Unknown": 5}
    district_rows_sorted = sorted(district_rows, key=lambda r: (severity.get(r["category"], 5), r["district"]))

    table_rows = ""
    for d in district_rows_sorted:
        depth_s = f"{d['depth']:.2f} m" if d["depth"] is not None else "—"
        rain_s = f"{d['rainfall']:.0f} mm" if d["rainfall"] is not None else "—"
        recharge_s = f"{d['recharge']:,.0f}" if d["recharge"] is not None else "—"
        stage_s = f"{d['stage']:.1f}%" if d["stage"] is not None else "—"
        table_rows += f"| {d['district']} | {d['category']} | {depth_s} | {rain_s} | {recharge_s} | {stage_s} |\n"

    return (
        f"## Groundwater Statistics — {canonical_state}\n\n"
        f"**GWRA Assessment Year: {latest_year}** | **Total Districts: {n_districts}**\n\n"
        f"---\n\n"
        f"### Assessment Category Distribution\n\n"
        f"| Category | Districts | Distribution |\n"
        f"|---|---:|---|\n"
        f"{cat_lines}\n"
        f"### State-Level Aggregate Totals\n\n"
        f"| Metric | Total / Value |\n"
        f"|---|---:|\n"
        f"| Annual Groundwater Recharge | {recharge_str} |\n"
        f"| Annual Extractable Resource | {extractable_str} |\n"
        f"| Annual Groundwater Extraction | {extraction_str} |\n"
        f"| Net Groundwater Availability | {net_str} |\n"
        f"| Overall Stage of Extraction | {overall_stage} |\n\n"
        f"### District-wise Summary\n\n"
        f"| District | Category | Avg Depth | Avg Rainfall | Annual Recharge (ham) | Stage (%) |\n"
        f"|---|---|---:|---:|---:|---:|\n"
        f"{table_rows}\n"
        f"**Source:** GWRA {latest_year} / CGWB · Groundwater Observations · IMD Rainfall Dataset · IN-GRES\n"
    )


@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query_text = request.query
    query_lower = query_text.lower().strip()
    
    # 1. Fetch or initialize conversation context
    conv_id = request.conversation_id or str(uuid.uuid4())
    conv = db.query(Conversation).filter_by(conversation_id=conv_id, user_id=current_user.id).first()
    if not conv:
        conv = Conversation(conversation_id=conv_id, user_id=current_user.id)
        db.add(conv)
        db.commit()
        
    # Log user message
    user_msg = ConversationMessage(conversation_id=conv_id, sender="user", text=query_text)
    db.add(user_msg)
    db.commit()
    
    # Conversation state flags
    is_clarifying = conv.pending_intent is not None and conv.pending_location is not None
    is_followup = conv.current_intent is not None or conv.last_user_question is not None

    # 4. Resolve location candidates first
    matched_geos, state_in_query = resolve_query_geographies(db, query_text)

    # 0. Check for conceptual domain knowledge or FAQ questions (only if no specific location was requested)
    domain_match = resolve_domain_knowledge(query_text) if not matched_geos and not state_in_query else None
    if domain_match and not is_clarifying:
        response_text = domain_match["response"]
        sources = domain_match.get("sources", ["Central Ground Water Board (CGWB)", "IN-GRES"])
        
        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()
        save_query_history(db, current_user.id, query_text, response_text, None)
        return {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": None,
            "assessment": None,
            "groundwater": None,
            "rainfall": None,
            "resources": None,
            "sources": sources,
            "conversation_context": {
                "location_resolved": False,
                "intent_resolved": True
            }
        }

    # 1. Check for pure greetings (hi, hello, namaste, etc.)
    if is_greeting_or_help_query(query_text) and not is_clarifying and not is_followup:
        response_text = (
            "Hello! 👋 I am the **IN-GRES AI Assistant** for India's Ground Water Resource Estimation System.\n\n"
            "I can help you explore official groundwater datasets, assessments, and weather:\n\n"
            "• **Groundwater Levels & Trends** — *'What is the water level in Kadapa?'*\n"
            "• **GWRA Assessment Categories** — Safe, Semi-Critical, Critical, or Over-Exploited\n"
            "• **Rainfall & Recharge Data** — Annual rainfall and assessed recharge metrics\n"
            "• **Extraction & Availability** — Stage of extraction and net water availability\n"
            "• **Conservation Strategies** — Practical recommendations for recharge and conservation\n"
            "• **Live Weather Forecasts** — Current temperature and conditions for any district\n\n"
            "How can I assist you today? Feel free to ask a question or name any district or state!"
        )
        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()
        save_query_history(db, current_user.id, query_text, response_text, None)
        return {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": None,
            "assessment": None,
            "groundwater": None,
            "rainfall": None,
            "resources": None,
            "sources": ["IN-GRES Assistant Guide"],
            "conversation_context": {
                "location_resolved": False,
                "intent_resolved": True
            }
        }

    # 2. Check for unrelated query / external questions -> Search Google!
    if is_unrelated_query(query_text) and not is_clarifying and not is_followup:
        response_text, search_sources = WebSearchService.answer_with_web_search(query_text)
        
        # Log assistant message
        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()
        
        save_query_history(db, current_user.id, query_text, response_text, None)
        return {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": None,
            "assessment": None,
            "groundwater": None,
            "rainfall": None,
            "resources": None,
            "sources": search_sources,
            "conversation_context": {
                "location_resolved": False,
                "intent_resolved": True
            }
        }
    
    # 2. Detect Year changes in user query
    year_match = re.search(r'\b(202\d)\b', query_text)
    if year_match:
        conv.current_year = int(year_match.group(1))
        db.commit()
        
    # 3. Detect intent keywords
    detected_intent = None
    
    is_previous_agg = conv.current_intent in [
        "STATE_ASSESSMENT_CATEGORY_COUNT",
        "DISTRICT_ASSESSMENT_CATEGORY_COUNT",
        "UNIT_ASSESSMENT_CATEGORY_COUNT",
        "RANK_STATE_MOST_CATEGORY"
    ]
    
    # Check for state/district/unit category counts
    is_state_query = "state" in query_lower or "states" in query_lower
    is_district_query = "district" in query_lower or "districts" in query_lower
    is_unit_query = "unit" in query_lower or "units" in query_lower
    
    is_names_query = any(x in query_lower for x in ["name", "names", "list", "which", "show", "tell me"])
    is_how_many = any(x in query_lower for x in ["how many", "count", "number of"])
    is_most_query = any(x in query_lower for x in ["most", "highest", "maximum", "max"])
    
    # Check for category match in query
    detected_cat = None
    if "semi-critical" in query_lower or "semi critical" in query_lower:
        detected_cat = "Semi-Critical"
    elif "over-exploited" in query_lower or "over exploited" in query_lower:
        detected_cat = "Over-Exploited"
    elif "critical" in query_lower:
        detected_cat = "Critical"
    elif "safe" in query_lower:
        detected_cat = "Safe"
    elif "saline" in query_lower:
        detected_cat = "Saline"
        
    if detected_cat:
        conv.current_metric = detected_cat
        db.commit()
        
    if (is_state_query or is_district_query or is_unit_query) and detected_cat:
        if is_state_query:
            detected_intent = "STATE_ASSESSMENT_CATEGORY_COUNT"
        elif is_district_query:
            detected_intent = "DISTRICT_ASSESSMENT_CATEGORY_COUNT"
        else:
            detected_intent = "UNIT_ASSESSMENT_CATEGORY_COUNT"
    elif detected_cat and is_previous_agg:
        # Carry over previous geography level/intent, but update category
        detected_intent = conv.current_intent
    elif is_previous_agg:
        # Context carryovers for queries without explicit categories
        if is_most_query:
            detected_intent = "RANK_STATE_MOST_CATEGORY"
        elif is_names_query and "district" in query_lower:
            detected_intent = "DISTRICT_ASSESSMENT_CATEGORY_COUNT"
        elif is_names_query and "state" in query_lower:
            detected_intent = "STATE_ASSESSMENT_CATEGORY_COUNT"
        elif is_how_many:
            detected_intent = conv.current_intent
        elif is_state_query:
            detected_intent = "STATE_ASSESSMENT_CATEGORY_COUNT"
        elif is_district_query:
            detected_intent = "DISTRICT_ASSESSMENT_CATEGORY_COUNT"
        elif is_unit_query:
            detected_intent = "UNIT_ASSESSMENT_CATEGORY_COUNT"
    else:
        is_rec_query = any(x in query_lower for x in ["improve", "increase", "conserve", "save", "depletion", "suggestion", "suggestions", "recommend", "recommendation", "recommendations", "prevent", "practice", "practices", "method", "methods", "tip", "tips", "manage", "management", "how to", "how can", "what should", "what can"])
        is_trend_query = any(x in query_lower for x in ["trend", "trends", "decline", "declined", "declining", "over the years", "over time", "change", "changes", "history", "historical", "chronological", "years", "2020", "2021", "2022", "2023", "2024", "2025", "2026"])

        # --- Weather intent detection (takes priority over plain rainfall check) ---
        _has_weather, _has_rainfall_only = detect_weather_intent(query_lower)
        # National ranking: 'which district has highest/lowest X?' — check FIRST before all metric intents
        _is_rank_signal = any(x in query_lower for x in [
            "highest", "lowest", "most", "least", "which district has", "which districts have",
            "maximum", "minimum", "top districts", "bottom districts", "top", "bottom", "low", "high"
        ])
        _has_rank_metric = any(x in query_lower for x in [
            "level", "depth", "recharge", "extraction", "stage", "rainfall", "rain", "availability", "available"
        ])
        if _is_rank_signal and _has_rank_metric and not _has_weather:
            detected_intent = "NATIONAL_RANKING"
        elif _has_weather:
            detected_intent = "WEATHER"
        elif is_rec_query:
            detected_intent = "RECOMMENDATION"
        elif is_trend_query:
            detected_intent = "TREND"
        elif any(x in query_lower for x in ["level", "depth", "water table"]):
            detected_intent = "GROUNDWATER_LEVEL"
        elif _has_rainfall_only or any(x in query_lower for x in ["rainfall", "rain"]):
            detected_intent = "RAINFALL"
        elif any(x in query_lower for x in ["recharge", "replenish"]):
            detected_intent = "RECHARGE"
        elif any(x in query_lower for x in ["extraction", "draft", "withdraw"]) and not any(x in query_lower for x in ["stage", "percent", "percentage", "rate"]):
            detected_intent = "EXTRACTION"
        elif any(x in query_lower for x in ["stage", "extraction rate", "rate of extraction", "extraction percent", "extraction percentage", "percentage", "percent"]):
            if any(x in query_lower for x in ["level", "depth", "water table", "indicator"]):
                detected_intent = "GROUNDWATER_LEVEL"
            else:
                detected_intent = "STAGE_OF_EXTRACTION"
        elif any(x in query_lower for x in ["category", "status", "safe", "critical", "over-exploited"]) and not is_state_query:
            detected_intent = "ASSESSMENT_CATEGORY"
        elif any(x in query_lower for x in ["availability", "available", "surplus"]):
            detected_intent = "NET_GROUNDWATER_AVAILABILITY"
        elif any(x in query_lower for x in ["statistics", "stats", "overview", "summary", "profile", "groundwater data", "show", "all districts", "districts in"]):
            detected_intent = "STATE_STATS"

    is_compare_requested = any(x in query_lower for x in ["compare", "comparison", "vs", "versus", "difference", "which is higher", "which is lower", "which has higher", "which has lower", "which is better", "which is deeper", "which is shallower", "between"])
    if is_compare_requested:
        detected_intent = "COMPARISON"
        
    # 4. Resolve location candidates
    matched_geos, state_in_query = resolve_query_geographies(db, query_text)

    if len(matched_geos) >= 2 and is_compare_requested:
        detected_intent = "COMPARISON"
    elif len(matched_geos) >= 2 and not is_compare_requested:
        matched_geos = matched_geos[:1]
        
    # Update active intent if detected
    if detected_intent:
        if detected_intent != "RANK_STATE_MOST_CATEGORY":
            conv.current_intent = detected_intent
            db.commit()
    
    # 5. Clarification Loop Resolution
    # If there is a pending clarification
    if conv.pending_intent and conv.pending_location:
        # Check if user clarified the state in this query (supporting full state names or common abbreviations)
        state_abbreviations = {
            "ap": "Andhra Pradesh",
            "hp": "Himachal Pradesh",
            "up": "Uttar Pradesh",
            "mp": "Madhya Pradesh",
            "tn": "Tamil Nadu",
            "ka": "Karnataka"
        }
        clarified_state = None
        for abbr, full_state in state_abbreviations.items():
            if f" {abbr} " in f" {query_lower} " or query_lower == abbr:
                clarified_state = full_state
                break
                
        if not clarified_state:
            states_query = db.query(Geography.state_name).distinct().all()
            for s in [st[0] for st in states_query]:
                if s.lower() in query_lower:
                    clarified_state = s
                    break
                    
        if clarified_state:
            # Resolve the pending location strictly for that state
            norm_pending = conv.pending_location.upper().strip()
            geo = db.query(Geography).filter(
                Geography.normalized_mandal_name == None,
                Geography.normalized_village_name == None,
                Geography.normalized_state_name == clarified_state.upper().strip(),
                (Geography.district_name.ilike(norm_pending) | Geography.id.in_(
                    db.query(GeographyAlias.geography_id).filter(GeographyAlias.normalized_alias_name == norm_pending)
                ))
            ).first()
            
            if geo:
                # Clarified successfully! Set context geography
                conv.current_district_name = geo.district_name
                conv.current_state_name = geo.state_name
                conv.current_geography_id = geo.id
                conv.current_intent = conv.pending_intent
                # Clear pending clarification
                conv.pending_intent = None
                conv.pending_location = None
                db.commit()
                # Re-assign matched_geos for immediate execution
                matched_geos = [geo]
                
    # 6. Apply location context switches or context carryover
    if len(matched_geos) >= 1:
        # Context Switch detected: user named location
        unique_names = list({g.district_name.lower() for g in matched_geos})
        if len(unique_names) == 1 and len(matched_geos) > 1:
            # Ambiguous Duplicate name collision detected! (UP vs HP Hamirpur)
            # Ask for state clarification and pause execution
            conv.pending_intent = conv.current_intent or "GROUNDWATER_LEVEL"
            conv.pending_location = matched_geos[0].district_name
            db.commit()
            
            response_text = f"I found multiple locations for '{matched_geos[0].district_name}'. Please specify which state you mean:\n"
            for g in matched_geos:
                response_text += f"- {g.district_name}, {g.state_name}\n"
                
            save_query_history(db, current_user.id, query_text, response_text, None)
            return {
                "query": query_text,
                "response": response_text,
                "conversation_id": conv_id,
                "conversation_context": {
                    "location_resolved": False,
                    "intent_resolved": True
                }
            }
        else:
            # Unique location resolved! Save to context
            geo = matched_geos[0]
            conv.current_district_name = geo.district_name
            conv.current_state_name = geo.state_name
            conv.current_geography_id = geo.id
            db.commit()
    else:
        # No location named in query - Context Carryover!
        # Only carry over if NO state was explicitly named in the query
        if not state_in_query and conv.current_geography_id:
            geo = db.query(Geography).filter_by(id=conv.current_geography_id).first()
            if geo:
                matched_geos = [geo]
                
    # 7. Execute resolution and response generation
    response_text = ""
    location_schema = None
    assessment_schema = None
    groundwater_schema = None
    rainfall_schema = None
    resources_schema = None
    sources = []
    
    # Check if this is an aggregation count query
    active_intent = detected_intent or conv.current_intent
    is_agg_query = active_intent in [
        "STATE_ASSESSMENT_CATEGORY_COUNT",
        "DISTRICT_ASSESSMENT_CATEGORY_COUNT",
        "UNIT_ASSESSMENT_CATEGORY_COUNT",
        "RANK_STATE_MOST_CATEGORY"
    ]
    
    if is_agg_query:
        target_cat = conv.current_metric or "Critical"
        target_year = conv.current_year or 2025
        include_uts = any(x in query_lower for x in ["union territory", "ut", "union territories"])
        
        if active_intent == "STATE_ASSESSMENT_CATEGORY_COUNT":
            agg = get_state_count_by_assessment_category(db, target_cat, target_year, include_uts)
            response_text = format_category_aggregation_response(agg, "STATE", include_uts)
        elif active_intent == "DISTRICT_ASSESSMENT_CATEGORY_COUNT":
            agg = get_districts_list_by_assessment_category(db, target_cat, target_year)
            is_pure_count = is_how_many and not is_names_query
            response_text = format_districts_list_response(agg, count_only=is_pure_count)
        elif active_intent == "RANK_STATE_MOST_CATEGORY":
            rank = get_state_with_most_category(db, target_cat, target_year)
            response_text = format_rank_state_response(rank)
        else: # UNIT
            agg = get_unit_count_by_assessment_category(db, target_cat, target_year)
            response_text = format_category_aggregation_response(agg, "UNIT")
            
        # Log assistant message
        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()
        
        save_query_history(db, current_user.id, query_text, response_text, None)
        return {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": None,
            "assessment": {
                "year": target_year,
                "category": target_cat
            },
            "groundwater": None,
            "rainfall": None,
            "resources": None,
            "sources": [],
            "conversation_context": {
                "location_resolved": False,
                "intent_resolved": True
            }
        }

    # -----------------------------------------------------------------------
    # NATIONAL RANKING PATH: 'which district has the highest/lowest X?'
    # -----------------------------------------------------------------------
    active_intent_pre = detected_intent or conv.current_intent
    if active_intent_pre == "NATIONAL_RANKING":
        ranking_response = resolve_national_ranking(db, query_lower)
        if ranking_response:
            asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=ranking_response)
            db.add(asst_msg)
            db.commit()
            save_query_history(db, current_user.id, query_text, ranking_response, None)
            return {
                "query": query_text,
                "response": ranking_response,
                "conversation_id": conv_id,
                "location": None,
                "assessment": None,
                "groundwater": None,
                "rainfall": None,
                "resources": None,
                "sources": ["IN-GRES Groundwater Dataset"],
                "conversation_context": {
                    "location_resolved": False,
                    "intent_resolved": True
                }
            }

    # -----------------------------------------------------------------------
    # FUTURE WATER LEVEL PREDICTION INTENT
    # -----------------------------------------------------------------------
    is_water_level_prediction = any(x in query_lower for x in [
        "predict future", "future water level", "future water levels", "predict water level",
        "predict groundwater", "forecast water level", "forecast groundwater", "projected water level",
        "future water table", "predict water table", "water level prediction", "predict levels",
        "predicting future water", "predict future levels", "predict the future", "predicting water level",
        "water level in 2027", "water level in 2028", "water level in 2029", "water level in 2030", "water level in 2031",
        "groundwater level in 2027", "groundwater level in 2028", "groundwater level in 2029", "groundwater level in 2030", "groundwater level in 2031",
        "future levels", "future level"
    ]) or (
        any(x in query_lower for x in ["predict", "prediction", "predicting", "forecast", "projection"])
        and any(x in query_lower for x in ["water level", "groundwater", "water table", "depth", "water"])
        and "recharge" not in query_lower
    )

    if is_water_level_prediction:
        target_geo = None
        if len(matched_geos) >= 1:
            target_geo = matched_geos[0]
        elif conv.current_geography_id:
            target_geo = db.query(Geography).get(conv.current_geography_id)

        if target_geo:
            # Determine scenario if requested
            scenario_key = "normal"
            if any(x in query_lower for x in ["drought", "deficit", "dry", "less rain", "low rain"]):
                scenario_key = "drought"
            elif any(x in query_lower for x in ["surplus", "excess", "heavy rain", "good rain", "high rain"]):
                scenario_key = "surplus"
            elif any(x in query_lower for x in ["conserve", "conservation", "harvesting", "recharge structure", "efficiency"]):
                scenario_key = "conservation"

            # Determine horizon
            years_ahead = 5
            for yr in [2027, 2028, 2029, 2030, 2031]:
                if str(yr) in query_lower:
                    years_ahead = max(1, min(10, yr - 2026))
                    break

            pred_result = WaterLevelPredictionService.predict_district(
                db=db,
                district_name=target_geo.district_name,
                years_ahead=years_ahead,
                scenario_key=scenario_key
            )

            if pred_result:
                response_text = format_prediction_response(pred_result)
                asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
                db.add(asst_msg)
                db.commit()
                save_query_history(db, current_user.id, query_text, response_text, target_geo.id)

                return {
                    "query": query_text,
                    "response": response_text,
                    "conversation_id": conv_id,
                    "location": {
                        "country": target_geo.country_name,
                        "state": target_geo.state_name,
                        "district": target_geo.district_name
                    },
                    "assessment": {
                        "year": pred_result["baseline"]["year"],
                        "category": pred_result["baseline"]["category"]
                    },
                    "groundwater": {
                        "depth_to_water_level_m_bgl": pred_result["baseline"]["depth_to_water_level_m_bgl"],
                        "groundwater_level_indicator_percent": None
                    },
                    "rainfall": None,
                    "resources": {
                        "stage_of_extraction_percent": pred_result["baseline"]["stage_of_extraction_percent"],
                        "annual_recharge_ham": None,
                        "annual_extractable_resource_ham": None,
                        "annual_extraction_ham": None,
                        "net_groundwater_availability_ham": None
                    },
                    "sources": [pred_result["methodology"]["label"], pred_result["methodology"]["data_source"]],
                    "conversation_context": {
                        "location_resolved": True,
                        "intent_resolved": True
                    }
                }
        else:
            prompt_resp = (
                "🔮 **Future Groundwater Level Prediction**\n\n"
                "I can generate hydro-statistical multi-year water level projections, confidence intervals, and scenario forecasts for any district in India.\n\n"
                "Please specify a district name (e.g., *'Predict future water level in Kadapa'* or *'Forecast water level in Ananthapuramu for next 3 years'*)."
            )
            asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=prompt_resp)
            db.add(asst_msg)
            db.commit()
            save_query_history(db, current_user.id, query_text, prompt_resp, None)
            return {
                "query": query_text,
                "response": prompt_resp,
                "conversation_id": conv_id,
                "location": None,
                "assessment": None,
                "groundwater": None,
                "rainfall": None,
                "resources": None,
                "sources": ["IN-GRES Predictive Modeling Engine"],
                "conversation_context": {
                    "location_resolved": False,
                    "intent_resolved": True
                }
            }

    is_future_recharge = "recharge" in query_lower and any(x in query_lower for x in ["future", "predict", "forecast", "next", "2027", "2028", "2029"])
    if is_future_recharge:

        recharge_str = "Data unavailable"
        loc_name = ""
        district_name_str = None
        state_name_str = None
        district_id_val = None
        
        location_schema = None
        assessment_schema = None
        groundwater_schema = None
        rainfall_schema = None
        resources_schema = None
        sources = []
        
        if len(matched_geos) >= 1:
            geo = matched_geos[0]
            details = resolve_district_response(db, geo)
            recharge_val = details["resources"]["annual_recharge_ham"]
            if recharge_val is not None:
                recharge_str = f"{recharge_val:,.2f}"
            loc_name = f" for {geo.district_name}"
            district_name_str = geo.district_name
            state_name_str = geo.state_name
            district_id_val = geo.id
            
            location_schema = LocationSchema(
                country=details["location"]["country"],
                state=details["location"]["state"],
                district=details["location"]["district"]
            )
            assessment_schema = AssessmentSchema(
                year=details["assessment"]["year"],
                category=details["assessment"]["category"]
            )
            groundwater_schema = GroundwaterSchema(
                depth_to_water_level_m_bgl=details["groundwater"]["depth_to_water_level_m_bgl"],
                groundwater_level_indicator_percent=details["groundwater"]["groundwater_level_indicator_percent"],
                observation_date=str(details["observation_year"]) if details.get("observation_year") is not None else None,
                observation_period=details["rainfall_period"]
            )
            rainfall_schema = RainfallSchema(
                value_mm=details["rainfall"]["value_mm"],
                year=details["rainfall"]["year"],
                period=details["rainfall"]["period"],
                source=details["sources"]["rainfall"]
            )
            resources_schema = ResourcesSchema(
                annual_recharge_ham=details["resources"]["annual_recharge_ham"],
                annual_extractable_resource_ham=details["resources"]["annual_extractable_resource_ham"],
                annual_extraction_ham=details["resources"]["annual_extraction_ham"],
                stage_of_extraction_percent=details["resources"]["stage_of_extraction_percent"],
                net_groundwater_availability_ham=details["resources"]["net_groundwater_availability_ham"]
            )
            sources = [details["sources"]["gwra"], details["sources"]["groundwater_level"], details["sources"]["rainfall"]]
            
        future_text = f"### Future Recharge\nFuture groundwater recharge cannot be reliably predicted from the current GWRA dataset alone. The available {recharge_str} ham is the assessed annual recharge value{loc_name}, not a two-year forecast."
        
        # Check adequacy
        adequacy_text = ""
        is_adequacy_requested = any(x in query_lower for x in ["low", "adequate", "adequacy", "sufficient", "scarcity"])
        if is_adequacy_requested and len(matched_geos) >= 1:
            geo = matched_geos[0]
            details = resolve_district_response(db, geo)
            stage = details["resources"]["stage_of_extraction_percent"]
            cat = details["assessment"]["category"] or "Unknown"
            adequacy_text = f"### Recharge Adequacy Evaluation\nThe current groundwater assessment category for **{geo.district_name}** is **{cat}** (Stage of Extraction: {f'{stage:.2f}%' if stage is not None else 'Data unavailable'}). Recharge is currently classified under the '{cat}' resource category."

        # Check suggestions / improve
        improve_text = ""
        is_improve_requested = any(x in query_lower for x in ["improve", "increase", "conserve", "save", "prevent", "recharge how", "how to improve", "how can i improve", "how can we improve"])
        if is_improve_requested:
            if len(matched_geos) >= 1:
                geo = matched_geos[0]
                details = resolve_district_response(db, geo)
                
                depth_val = details['groundwater']['depth_to_water_level_m_bgl']
                depth_str = f"{depth_val:.2f} m bgl" if depth_val is not None else "Data unavailable"
                
                stage_val = details['resources']['stage_of_extraction_percent']
                stage_str = f"{stage_val:.2f}%" if stage_val is not None else "Data unavailable"
                
                improve_text = (
                    f"### Current Situation\n"
                    f"For **{geo.district_name}** ({geo.state_name}):\n"
                    f"- **Depth to Water Level**: {depth_str}\n"
                    f"- **Stage of Extraction**: {stage_str}\n\n"
                    f"### Possible Causes\n"
                    f"Possible factors affecting the water table in {geo.district_name} include:\n"
                    f"- Extraction activities for domestic, agricultural, or industrial uses.\n"
                    f"- Rainfall variability affecting natural recharge rates.\n\n"
                    f"### Recommended Actions\n"
                    f"Here are practical actions suitable for {geo.district_name} to improve recharge:\n"
                    f"1. **Rainwater Harvesting**: Construct check dams, recharge pits, and percolation tanks.\n"
                    f"2. **Rooftop Rainwater Harvesting**: Capture rooftop water runoff to feed recharge wells.\n"
                    f"3. **Agricultural Efficiency**: Encourage drip and sprinkler irrigation.\n\n"
                    f"### Monitoring\n"
                    f"It is recommended to monitor depth to water level (m bgl) and extraction trends over time. Please note that these are AI-generated general recommendations based on the local condition metrics."
                )
            else:
                improve_text = (
                    "### General Recommendations to Improve Recharge\n"
                    "Here are practical measures to conserve and recharge groundwater:\n"
                    "1. **Rainwater Harvesting**: Build check dams and percolation tanks to collect runoff.\n"
                    "2. **Rooftop Rainwater Harvesting**: Capture rooftop runoff to direct into recharge wells/pits.\n"
                    "3. **Recharge Pits & Wells**: Direct clean, untreated rainwater into fields/pits.\n"
                    "4. **Restoration of Tanks**: Desilt and maintain village tanks and ponds.\n"
                    "5. **Watershed Management**: Plant trees and build contour trenches.\n"
                    "6. **Efficient Irrigation**: Transition to drip and sprinkler systems.\n\n"
                    "*Note: These recommendations are general. Feasibility depends on local geology, soil, and terrain.*"
                )
                
        response_text = future_text
        if adequacy_text:
            response_text += "\n\n" + adequacy_text
        if improve_text:
            response_text += "\n\n" + improve_text
            
        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()
        
        save_query_history(db, current_user.id, query_text, response_text, district_id_val)
        return {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": location_schema,
            "assessment": assessment_schema,
            "groundwater": groundwater_schema,
            "rainfall": rainfall_schema,
            "resources": resources_schema,
            "sources": sources,
            "conversation_context": {
                "location_resolved": len(matched_geos) >= 1,
                "intent_resolved": True
            },
            "district_id": district_id_val,
            "district_name": district_name_str,
            "state_name": state_name_str,
            "depth_to_water_level_m_bgl": groundwater_schema.depth_to_water_level_m_bgl if groundwater_schema else None,
            "rainfall_mm": rainfall_schema.value_mm if rainfall_schema else None,
            "assessment_category": assessment_schema.category if assessment_schema else None
        }

    # Re-evaluate weather intent from active intent (may have been carried from context)
    active_intent = detected_intent or conv.current_intent
    _has_weather_active, _ = detect_weather_intent(query_lower)
    is_weather_query = active_intent == "WEATHER" or _has_weather_active
    # A combined query wants both groundwater AND weather
    is_combined_query = is_weather_query and any(x in query_lower for x in [
        "groundwater", "water level", "depth", "recharge", "extraction", "stage",
        "status", "assessment", "category"
    ])
    # Pure weather = weather intent with no groundwater keywords
    is_pure_weather = is_weather_query and not is_combined_query

    # -----------------------------------------------------------------------
    # WEATHER PATH: call Open-Meteo for any weather intent
    # -----------------------------------------------------------------------
    weather_response_part = ""
    if is_weather_query and len(matched_geos) >= 1:
        geo_for_weather = matched_geos[0]
        print(f"[INGRES-AI] Weather intent detected. Fetching weather for '{geo_for_weather.district_name}'.")
        weather_data = fetch_weather_sync(geo_for_weather.district_name)
        if weather_data:
            weather_response_part = format_weather_response(weather_data, geo_for_weather.district_name)
            print(f"[INGRES-AI] Weather fetch SUCCESS for '{geo_for_weather.district_name}'.")
        else:
            weather_response_part = (
                f"### Current Weather — {geo_for_weather.district_name}\n\n"
                "Live weather information is temporarily unavailable. "
                "Please try again in a moment.\n\n"
                "**Weather Source:** Open-Meteo"
            )
            print(f"[INGRES-AI] Weather fetch FAILED for '{geo_for_weather.district_name}'.")
    elif is_weather_query and not matched_geos:
        weather_response_part = (
            "I could not resolve a specific Indian district from your query. "
            "Please mention a district or city name (e.g. 'Guntur', 'YSR Kadapa') to get live weather."
        )

    # -----------------------------------------------------------------------
    # PURE WEATHER — return only weather, no groundwater data
    # -----------------------------------------------------------------------
    if is_pure_weather:
        response_text = weather_response_part

        asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
        db.add(asst_msg)
        db.commit()

        save_query_history(db, current_user.id, query_text, response_text, matched_geos[0].id if matched_geos else None)
        payload = {
            "query": query_text,
            "response": response_text,
            "conversation_id": conv_id,
            "location": LocationSchema(
                country="India",
                state=matched_geos[0].state_name if matched_geos else None,
                district=matched_geos[0].district_name if matched_geos else None,
            ) if matched_geos else None,
            "assessment": None,
            "groundwater": None,
            "rainfall": None,
            "resources": None,
            "sources": ["Open-Meteo"],
            "conversation_context": {
                "location_resolved": bool(matched_geos),
                "intent_resolved": True,
            },
        }
        if matched_geos:
            payload["district_id"]   = matched_geos[0].id
            payload["district_name"] = matched_geos[0].district_name
            payload["state_name"]    = matched_geos[0].state_name
        return payload

    # -----------------------------------------------------------------------
    # GROUNDWATER / COMBINED PATH
    # -----------------------------------------------------------------------
    # If we have a resolved geography context
    if len(matched_geos) >= 1 and not is_compare_requested:
        geo = matched_geos[0]
        details = resolve_district_response(db, geo)
        
        subloc = getattr(geo, "matched_sublocation", None)
        loc_display = f"{subloc} ({details['district_name']}, {details['state_name']})" if subloc else details["district_name"]

        # Populate response schemas
        location_schema = LocationSchema(
            country=details["location"]["country"],
            state=details["location"]["state"],
            district=f"{details['location']['district']} ({subloc})" if subloc else details["location"]["district"]
        )
        assessment_schema = AssessmentSchema(
            year=details["assessment"]["year"],
            category=details["assessment"]["category"]
        )
        groundwater_schema = GroundwaterSchema(
            depth_to_water_level_m_bgl=details["groundwater"]["depth_to_water_level_m_bgl"],
            groundwater_level_indicator_percent=details["groundwater"]["groundwater_level_indicator_percent"],
            observation_date=str(details["observation_year"]) if details.get("observation_year") is not None else None,
            observation_period=details["rainfall_period"]
        )
        rainfall_schema = RainfallSchema(
            value_mm=details["rainfall"]["value_mm"],
            year=details["rainfall"]["year"],
            period=details["rainfall"]["period"],
            source=details["sources"]["rainfall"]
        )
        resources_schema = ResourcesSchema(
            annual_recharge_ham=details["resources"]["annual_recharge_ham"],
            annual_extractable_resource_ham=details["resources"]["annual_extractable_resource_ham"],
            annual_extraction_ham=details["resources"]["annual_extraction_ham"],
            stage_of_extraction_percent=details["resources"]["stage_of_extraction_percent"],
            net_groundwater_availability_ham=details["resources"]["net_groundwater_availability_ham"]
        )
        sources = [details["sources"]["gwra"], details["sources"]["groundwater_level"], details["sources"]["rainfall"]]
        
        # Determine if simple query for Gemini Bypass
        is_simple = conv.current_intent in [
            "GROUNDWATER_LEVEL", "RAINFALL", "RECHARGE", "EXTRACTION",
            "STAGE_OF_EXTRACTION", "ASSESSMENT_CATEGORY", "NET_GROUNDWATER_AVAILABILITY"
        ]
        
        is_concise_requested = not any(re.search(rf"\b{x}\b", query_lower) for x in ["full", "detail", "details", "table", "all", "report", "summary"])
        
        # Recommendations and trend queries should not bypass to factual metrics table
        if conv.current_intent in ["RECOMMENDATION", "TREND"]:
            verified_data = {"district": details}
            response_text = GeminiService.generate_chat_response(query_text, verified_data)
        elif is_simple and is_concise_requested:
            # Concise response for simple queries
            name = loc_display
            if conv.current_intent == "GROUNDWATER_LEVEL":
                indicator = details["groundwater"]["groundwater_level_indicator_percent"]
                depth = details["groundwater"]["depth_to_water_level_m_bgl"]
                if any(x in query_lower for x in ["percent", "percentage", "indicator"]):
                    if indicator is not None:
                        response_text = f"The groundwater level indicator in {name} is {indicator:.2f}%."
                    elif depth is not None:
                        response_text = f"The depth to water level in {name} is {depth:.2f} m bgl."
                    else:
                        response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                        sources = s_list
                elif any(x in query_lower for x in ["depth", "m bgl", "mbgl"]):
                    if depth is not None:
                        response_text = f"The depth to water level in {name} is {depth:.2f} m bgl."
                    elif indicator is not None:
                        response_text = f"The groundwater level indicator in {name} is {indicator:.2f}%."
                    else:
                        response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                        sources = s_list
                elif indicator is not None and depth is not None:
                    response_text = f"The groundwater level in {name} is {indicator:.2f}% (Depth to water level: {depth:.2f} m bgl)."
                elif indicator is not None:
                    response_text = f"The groundwater level in {name} is {indicator:.2f}%."
                elif depth is not None:
                    response_text = f"The depth to water level in {name} is {depth:.2f} m bgl."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "RAINFALL":
                rainfall = details["rainfall"]["value_mm"]
                if rainfall is not None:
                    response_text = f"The rainfall in {name} is {rainfall:.1f} mm."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "RECHARGE":
                recharge = details["resources"]["annual_recharge_ham"]
                if recharge is not None:
                    response_text = f"The annual groundwater recharge in {name} is {recharge:,.2f} ham."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "EXTRACTION":
                extraction = details["resources"]["annual_extraction_ham"]
                if extraction is not None:
                    response_text = f"The annual groundwater extraction in {name} is {extraction:,.2f} ham."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "STAGE_OF_EXTRACTION":
                stage = details["resources"]["stage_of_extraction_percent"]
                cat = details["assessment"]["category"]
                cat_suffix = f" (Assessment Category: {cat})" if cat else ""
                if stage is not None:
                    response_text = f"The stage of groundwater extraction in {name} is {stage:.2f}%{cat_suffix}."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "ASSESSMENT_CATEGORY":
                cat = details["assessment"]["category"]
                if cat:
                    response_text = f"The assessment category for {name} is {cat}."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
            elif conv.current_intent == "NET_GROUNDWATER_AVAILABILITY":
                net_avail = details["resources"]["net_groundwater_availability_ham"]
                if net_avail is not None:
                    response_text = f"The net groundwater availability for future use in {name} is {net_avail:,.2f} ham."
                else:
                    response_text, s_list = WebSearchService.answer_with_web_search(query_text)
                    sources = s_list
        elif is_simple or not settings.GEMINI_API_KEY:
            # Gemini Bypass: Return database results directly!
            response_text = generate_factual_response(details)
        else:
            # Enhance with Gemini (for reasoning/general chats)
            verified_data = {"district": details}
            response_text = GeminiService.generate_chat_response(query_text, verified_data)

        # COMBINED QUERY: append weather section after groundwater section
        if is_combined_query and weather_response_part:
            response_text = (
                response_text
                + "\n\n---\n\n"
                + weather_response_part
            )
            sources.append("Open-Meteo")
            
    # Comparison case
    elif len(matched_geos) >= 2:
        geo1 = matched_geos[0]
        geo2 = matched_geos[1]
        
        detail1 = resolve_district_response(db, geo1)
        detail2 = resolve_district_response(db, geo2)
        
        from app.utils.calculations import absolute_difference
        verified_data = {
            "comparison": {
                "district_1": detail1,
                "district_2": detail2,
                "metrics_difference": {
                    "depth_difference_m": absolute_difference(detail1["depth_to_water_level_m_bgl"], detail2["depth_to_water_level_m_bgl"]),
                    "rainfall_difference_mm": absolute_difference(detail1["rainfall_mm"], detail2["rainfall_mm"]),
                    "recharge_difference_ham": absolute_difference(detail1["resources"]["annual_recharge_ham"], detail2["resources"]["annual_recharge_ham"]),
                    "extraction_difference_ham": absolute_difference(detail1["resources"]["annual_extraction_ham"], detail2["resources"]["annual_extraction_ham"])
                }
            }
        }
        response_text = GeminiService.generate_chat_response(query_text, verified_data)

        # Append weather for comparison if requested
        if is_weather_query and weather_response_part:
            response_text += "\n\n---\n\n" + weather_response_part
            
    elif len(matched_geos) == 1 and is_compare_requested:
        d_name = matched_geos[0].district_name
        response_text = f"To compare groundwater data for **{d_name}**, please specify a second district (e.g. *'Compare {d_name} and Kurnool'* or *'Compare {d_name} and Guntur'*)."
        
    else:
        # General query or unresolved location — check for state-level statistics first
        active_intent_for_state = detected_intent or conv.current_intent
        _state_in_query = None
        _states_db = [s[0] for s in db.query(Geography.state_name).distinct().all()]
        for _s in _states_db:
            if _s.lower() in query_lower:
                _state_in_query = _s
                break

        if _state_in_query and active_intent_for_state in [
            "STATE_STATS", "GROUNDWATER_LEVEL", "GROUNDWATER_RESOURCE",
            "RAINFALL", "RECHARGE", "EXTRACTION", "STAGE_OF_EXTRACTION",
            "NET_GROUNDWATER_AVAILABILITY", "DISTRICT_STATUS", "GENERAL_GROUNDWATER",
            None
        ]:
            state_stats_response = resolve_state_statistics(db, _state_in_query)
            if state_stats_response:
                response_text = state_stats_response
            else:
                if is_weather_query and weather_response_part:
                    response_text = weather_response_part
                else:
                    verified_data = {"general_query": True}
                    response_text = GeminiService.generate_chat_response(query_text, verified_data)
        elif is_weather_query and weather_response_part:
            response_text = weather_response_part
        elif conv.current_intent == "RECOMMENDATION" or any(x in query_lower for x in ["suggestion", "suggestions", "tip", "tips", "recommend", "recommendation", "how to improve", "how to conserve", "how to save", "practices"]):
            verified_data = {"general_query": True}
            response_text = GeminiService.generate_chat_response(query_text, verified_data)
            sources = ["Central Ground Water Board (CGWB)", "IN-GRES"]
        else:
            response_text, s_list = WebSearchService.answer_with_web_search(query_text)
            sources = s_list
        
    # Log assistant message
    asst_msg = ConversationMessage(conversation_id=conv_id, sender="assistant", text=response_text)
    db.add(asst_msg)
    db.commit()
    
    save_query_history(db, current_user.id, query_text, response_text, matched_geos[0].id if len(matched_geos) >= 1 else None)
    
    # Build final response payload
    res_payload = {
        "query": query_text,
        "response": response_text,
        "conversation_id": conv_id,
        "location": location_schema,
        "assessment": assessment_schema,
        "groundwater": groundwater_schema,
        "rainfall": rainfall_schema,
        "resources": resources_schema,
        "sources": sources,
        "conversation_context": {
            "location_resolved": len(matched_geos) >= 1,
            "intent_resolved": conv.current_intent is not None
        }
    }
    
    # Flattened legacy fields for backward compatibility
    if len(matched_geos) >= 1:
        geo = matched_geos[0]
        res_payload["district_id"] = geo.id
        res_payload["district_name"] = geo.district_name
        res_payload["state_name"] = geo.state_name
        if location_schema:
            res_payload["depth_to_water_level_m_bgl"] = groundwater_schema.depth_to_water_level_m_bgl
            res_payload["rainfall_mm"] = rainfall_schema.value_mm
            res_payload["assessment_category"] = assessment_schema.category
            res_payload["groundwater_level"] = groundwater_schema.depth_to_water_level_m_bgl
            res_payload["rainfall"] = rainfall_schema.value_mm
            
    return res_payload

@router.get("/history", response_model=List[QueryOut])
def get_user_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    history = db.query(QueryHistory).filter_by(user_id=current_user.id).order_by(QueryHistory.created_at.desc()).all()
    return history

@router.get("/history/{id}", response_model=QueryOut)
def get_history_detail(id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    log = db.query(QueryHistory).filter_by(id=id, user_id=current_user.id).first()
    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Query history item not found."
        )
    return log