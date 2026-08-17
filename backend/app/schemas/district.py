from pydantic import BaseModel
from typing import Optional, List

class GroundwaterDataOut(BaseModel):
    id: int
    district_id: int
    depth_to_water_level_m_bgl: Optional[float] = None
    rainfall_mm: Optional[float] = None
    rainfall_period: Optional[str] = None
    gwra_year: Optional[int] = None
    annual_groundwater_recharge_ham: Optional[float] = None
    annual_extractable_groundwater_resource_ham: Optional[float] = None
    annual_groundwater_extraction_ham: Optional[float] = None
    stage_of_groundwater_extraction_percent: Optional[float] = None
    assessment_category: Optional[str] = None
    assessment_category_breakdown: Optional[str] = None
    summary_year: int
    year: int
    data_source_groundwater: Optional[str] = None
    data_source_rainfall: Optional[str] = None
    data_source_gwra: Optional[str] = None

    # Backward compatibility mappings
    groundwater_level: Optional[float] = None
    rainfall: Optional[float] = None
    recharge: Optional[float] = None
    extraction: Optional[float] = None
    availability: Optional[float] = None

    class Config:
        from_attributes = True

class DistrictOut(BaseModel):
    id: int
    district_name: str
    state_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True

class DistrictDetail(BaseModel):
    id: int
    district_name: str
    state_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    groundwater_data: List[GroundwaterDataOut] = []

    class Config:
        from_attributes = True

class DistrictComparison(BaseModel):
    district1: DistrictDetail
    district2: DistrictDetail
    explanation: str

    class Config:
        from_attributes = True

class ComparisonMetrics(BaseModel):
    depth_difference_m: Optional[float] = None
    rainfall_difference_mm: Optional[float] = None
    recharge_difference_ham: Optional[float] = None
    extractable_resource_difference_ham: Optional[float] = None
    extraction_difference_ham: Optional[float] = None
    stage_difference_percentage_points: Optional[float] = None

class ComparisonDistrictDetail(BaseModel):
    district_id: int
    district_name: str
    state_name: str
    depth_to_water_level_m_bgl: Optional[float] = None
    rainfall_mm: Optional[float] = None
    rainfall_period: Optional[str] = None
    gwra_year: Optional[int] = None
    annual_groundwater_recharge_ham: Optional[float] = None
    annual_extractable_groundwater_resource_ham: Optional[float] = None
    annual_groundwater_extraction_ham: Optional[float] = None
    stage_of_groundwater_extraction_percent: Optional[float] = None
    assessment_category: Optional[str] = None
    assessment_category_breakdown: Optional[str] = None
    sources: List[str] = []
    data_source_groundwater: Optional[str] = None
    data_source_rainfall: Optional[str] = None
    data_source_gwra: Optional[str] = None

    class Config:
        from_attributes = True

class DistrictComparisonOut(BaseModel):
    district_1: ComparisonDistrictDetail
    district_2: ComparisonDistrictDetail
    comparison: ComparisonMetrics
    explanation: str
