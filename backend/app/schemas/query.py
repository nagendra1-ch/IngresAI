from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.schemas.district import DistrictOut

class QueryCreate(BaseModel):
    query: str

class QueryOut(BaseModel):
    id: int
    user_id: int
    query: str
    response: str
    district_id: Optional[int] = None
    created_at: datetime
    district: Optional[DistrictOut] = None

    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None

class LocationSchema(BaseModel):
    country: str = "India"
    state: Optional[str] = None
    district: Optional[str] = None
    mandal: Optional[str] = None
    village: Optional[str] = None

class AssessmentSchema(BaseModel):
    year: Optional[int] = None
    category: Optional[str] = None

class GroundwaterSchema(BaseModel):
    depth_to_water_level_m_bgl: Optional[float] = None
    groundwater_level_indicator_percent: Optional[float] = None
    observation_date: Optional[str] = None
    observation_period: Optional[str] = None

class RainfallSchema(BaseModel):
    value_mm: Optional[float] = None
    year: Optional[int] = None
    period: Optional[str] = None
    source: Optional[str] = None

class ResourcesSchema(BaseModel):
    annual_recharge_ham: Optional[float] = None
    annual_extractable_resource_ham: Optional[float] = None
    annual_extraction_ham: Optional[float] = None
    stage_of_extraction_percent: Optional[float] = None
    net_groundwater_availability_ham: Optional[float] = None

class ConversationContextSchema(BaseModel):
    location_resolved: bool = False
    intent_resolved: bool = False

class ChatResponse(BaseModel):
    query: str
    response: str
    conversation_id: Optional[str] = None
    
    location: Optional[LocationSchema] = None
    assessment: Optional[AssessmentSchema] = None
    groundwater: Optional[GroundwaterSchema] = None
    rainfall: Optional[RainfallSchema] = None
    resources: Optional[ResourcesSchema] = None
    sources: Optional[List[str]] = []
    data_quality: Optional[Dict[str, Any]] = {}
    conversation_context: Optional[ConversationContextSchema] = None

    # Flattened legacy fields for backward compatibility
    district_id: Optional[int] = None
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    depth_to_water_level_m_bgl: Optional[float] = None
    rainfall_mm: Optional[float] = None
    assessment_category: Optional[str] = None
    groundwater_level: Optional[float] = None
    rainfall: Optional[float] = None

    class Config:
        from_attributes = True
