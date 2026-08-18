from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.services.weather_service import WeatherService
from app.dependencies import get_weather_service
from app.database import get_db
from app.models import Geography, GWRAAssessment, RainfallRecord
from sqlalchemy import func

router = APIRouter(prefix="/api/weather", tags=["weather"])

@router.get("/coords", summary="Get weather by latitude and longitude")
async def get_weather_by_coords(
    lat: float,
    lon: float,
    weather_service: WeatherService = Depends(get_weather_service),
):
    """Return current weather and a 3‑day forecast for the supplied coordinates.

    The service uses the Open‑Meteo API with caching (TTL 10 min). If the external
    service cannot be reached an HTTP 503 is raised.
    """
    data = await weather_service.get_weather_by_coordinates(lat, lon)
    if data is None:
        raise HTTPException(status_code=503, detail="Weather service unavailable")
    return data

@router.get("/district/{district_name}", summary="Get weather for a district by name")
async def get_weather_by_district(
    district_name: str,
    weather_service: WeatherService = Depends(get_weather_service),
):
    """Resolve the district's coordinates (fallback to Open‑Meteo geocoding) and
    return its weather data.
    """
    data = await weather_service.get_weather_by_district_name(district_name)
    if data is None:
        raise HTTPException(status_code=404, detail="District not found or no weather data")
    return data


@router.get("/forecast/{district_name}", summary="Extended 7-day forecast with groundwater impact")
async def get_extended_forecast(
    district_name: str,
    weather_service: WeatherService = Depends(get_weather_service),
    db: Session = Depends(get_db),
):
    """Return 7-day forecast, 48h hourly precipitation, and a groundwater impact
    indicator that combines live weather data with historical GWRA assessments.
    """
    # 1. Fetch extended weather forecast
    forecast_data = await weather_service.get_extended_forecast_by_district_name(district_name)
    if forecast_data is None:
        raise HTTPException(status_code=404, detail="District not found or forecast unavailable")

    # 2. Look up historical data from the database
    dist_upper = district_name.upper().strip()
    geo = db.query(Geography).filter(
        Geography.normalized_district_name == dist_upper,
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None,
    ).first()

    groundwater_impact = None
    if geo:
        # Get GWRA assessment
        gwra = db.query(GWRAAssessment).filter_by(geography_id=geo.id).first()

        # Get historical average rainfall
        rain_avg = db.query(
            func.avg(RainfallRecord.rainfall_mm)
        ).filter(RainfallRecord.geography_id == geo.id).scalar()

        historical_avg_rain = round(float(rain_avg), 1) if rain_avg else None
        forecast_total = forecast_data.get("forecast_total_rain_mm", 0)

        # Compute impact indicator
        extraction_rate = None
        category = None
        recharge_ham = None
        if gwra:
            extraction_rate = gwra.stage_of_groundwater_extraction_percent
            category = gwra.district_assessment_category
            recharge_ham = gwra.annual_groundwater_recharge_ham

            if extraction_rate is None and gwra.annual_groundwater_extraction_ham and gwra.annual_extractable_groundwater_resource_ham:
                extraction_rate = round(
                    (gwra.annual_groundwater_extraction_ham / gwra.annual_extractable_groundwater_resource_ham) * 100, 2
                )

        # Determine recharge potential based on forecast rainfall
        rain_vs_avg = None
        recharge_potential = "Unknown"
        if historical_avg_rain and historical_avg_rain > 0:
            rain_vs_avg = round((forecast_total / historical_avg_rain) * 100, 1)
            if rain_vs_avg > 15:
                recharge_potential = "High"
            elif rain_vs_avg > 5:
                recharge_potential = "Moderate"
            elif rain_vs_avg > 1:
                recharge_potential = "Low"
            else:
                recharge_potential = "Minimal"

        # Determine risk level
        risk_level = category or "Safe"

        # Generate narrative
        narrative_parts = []
        if forecast_total > 0:
            narrative_parts.append(
                f"With {forecast_total:.1f} mm of rainfall expected over the next 7 days"
            )
            if rain_vs_avg is not None:
                narrative_parts.append(f" (~{rain_vs_avg}% of the annual average)")
            narrative_parts.append(
                f", {recharge_potential.lower()} groundwater recharge potential is indicated."
            )
        else:
            narrative_parts.append(
                "No significant rainfall is expected in the coming 7 days, suggesting minimal recharge potential."
            )

        if extraction_rate is not None:
            narrative_parts.append(
                f" The current stage of groundwater extraction is {extraction_rate:.1f}%"
            )
            if extraction_rate > 100:
                narrative_parts.append(", which is over-exploited and requires urgent attention.")
            elif extraction_rate > 70:
                narrative_parts.append(", indicating high extraction pressure.")
            elif extraction_rate > 40:
                narrative_parts.append(", which is within manageable limits.")
            else:
                narrative_parts.append(", indicating sustainable usage.")

        groundwater_impact = {
            "forecast_total_rain_mm": forecast_total,
            "historical_avg_rain_mm": historical_avg_rain,
            "rain_vs_avg_percent": rain_vs_avg,
            "recharge_potential": recharge_potential,
            "extraction_rate_percent": round(extraction_rate, 2) if extraction_rate else None,
            "annual_recharge_ham": round(recharge_ham, 2) if recharge_ham else None,
            "risk_level": risk_level,
            "narrative": "".join(narrative_parts),
        }

    forecast_data["groundwater_impact"] = groundwater_impact
    forecast_data["source"] = "Open-Meteo + INGRES Historical Data"
    return forecast_data
