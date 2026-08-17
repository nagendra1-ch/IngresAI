from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class AdminSummary(BaseModel):
    total_users: int
    total_queries: int
    districts_accessed: int
    most_viewed_district: Optional[str] = "None"
    most_viewed_district_views: int = 0
    avg_queries_per_user: float

class AdminQueryLog(BaseModel):
    id: int
    username: str
    email: str
    query: str
    response: str
    district_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DistrictAccessStat(BaseModel):
    district_name: str
    state_name: str
    total_views: int
    unique_users: int
    last_accessed: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminUserLog(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime
    queries_count: int

    class Config:
        from_attributes = True
