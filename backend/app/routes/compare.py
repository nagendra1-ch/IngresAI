from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Geography, User
from app.routes.auth import get_current_user
from app.services.gemini_service import GeminiService
from app.services.weather_service import WeatherService
from app.dependencies import get_weather_service
from app.utils.calculations import absolute_difference
from app.routes.districts import resolve_district_response
from app.schemas.district import DistrictComparisonOut

router = APIRouter(prefix="/api/compare", tags=["Comparison"])

@router.get("")
async def compare_districts(
    district1: int,
    district2: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    weather_service: WeatherService = Depends(get_weather_service),
):
    """
    Compare groundwater, rainfall, and weather metrics of two selected districts. Requires auth.
    """
    if district1 == district2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="District 1 and District 2 must be different entities."
        )

    d1 = db.query(Geography).filter(
        Geography.id == district1,
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None,
    ).first()
    d2 = db.query(Geography).filter(
        Geography.id == district2,
        Geography.normalized_mandal_name == None,
        Geography.normalized_village_name == None,
    ).first()

    if not d1 or not d2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or both of the selected districts could not be found in the geography database."
        )

    detail1 = resolve_district_response(db, d1)
    detail2 = resolve_district_response(db, d2)

    # Calculate backend differences
    depth_diff = absolute_difference(
        detail1["depth_to_water_level_m_bgl"],
        detail2["depth_to_water_level_m_bgl"]
    )
    rainfall_diff = absolute_difference(
        detail1["rainfall_mm"],
        detail2["rainfall_mm"]
    )
    recharge_diff = absolute_difference(
        detail1["resources"]["annual_recharge_ham"],
        detail2["resources"]["annual_recharge_ham"]
    )
    extractable_diff = absolute_difference(
        detail1["resources"]["annual_extractable_resource_ham"],
        detail2["resources"]["annual_extractable_resource_ham"]
    )
    extraction_diff = absolute_difference(
        detail1["resources"]["annual_extraction_ham"],
        detail2["resources"]["annual_extraction_ham"]
    )
    stage_diff = absolute_difference(
        detail1["resources"]["stage_of_extraction_percent"],
        detail2["resources"]["stage_of_extraction_percent"]
    )

    # Fetch weather for both districts (best-effort, non-blocking)
    weather_1 = None
    weather_2 = None
    try:
        import asyncio
        w1_task = weather_service.get_weather_by_district_name(detail1["district_name"])
        w2_task = weather_service.get_weather_by_district_name(detail2["district_name"])
        weather_1, weather_2 = await asyncio.gather(w1_task, w2_task, return_exceptions=True)
        if isinstance(weather_1, Exception):
            weather_1 = None
        if isinstance(weather_2, Exception):
            weather_2 = None
    except Exception:
        pass

    # Format verified data for Gemini Prompting
    verified_data = {
        "district_1": detail1,
        "district_2": detail2,
        "comparison": {
            "depth_difference_m": depth_diff,
            "rainfall_difference_mm": rainfall_diff,
            "recharge_difference_ham": recharge_diff,
            "extractable_resource_difference_ham": extractable_diff,
            "extraction_difference_ham": extraction_diff,
            "stage_difference_percentage_points": stage_diff
        }
    }

    # Generate comparative narrative
    explanation = GeminiService.generate_comparison_explanation(
        detail1["district_name"],
        detail2["district_name"],
        verified_data
    )

    return {
        "district_1": detail1,
        "district_2": detail2,
        "weather_1": weather_1,
        "weather_2": weather_2,
        "comparison": {
            "depth_difference_m": depth_diff,
            "rainfall_difference_mm": rainfall_diff,
            "recharge_difference_ham": recharge_diff,
            "extractable_resource_difference_ham": extractable_diff,
            "extraction_difference_ham": extraction_diff,
            "stage_difference_percentage_points": stage_diff
        },
        "explanation": explanation
    }

