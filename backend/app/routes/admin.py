from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import User, QueryHistory, ResultAccess, Geography
from app.routes.auth import get_admin_user
from app.schemas.admin import AdminSummary, AdminQueryLog, DistrictAccessStat, AdminUserLog
from app.services.excel_service import ExcelService

router = APIRouter(prefix="/api/admin", tags=["Admin Panel"])

@router.get("/statistics", response_model=AdminSummary)
def get_admin_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Computes overall summary metrics for the Admin Dashboard. Requires ADMIN.
    """
    total_users = db.query(User).count()
    total_queries = db.query(QueryHistory).count()
    
    dist_accessed_query = db.query(func.count(func.distinct(ResultAccess.district_id))).scalar()
    districts_accessed = dist_accessed_query if dist_accessed_query else 0
    
    # Identify the most viewed district
    most_viewed = db.query(
        ResultAccess.district_id,
        func.count(ResultAccess.id).label("cnt")
    ).group_by(ResultAccess.district_id).order_by(func.count(ResultAccess.id).desc()).first()
    
    most_viewed_district = "None"
    most_viewed_district_views = 0
    if most_viewed:
        dist = db.query(Geography).filter_by(id=most_viewed[0]).first()
        if dist:
            most_viewed_district = dist.district_name
            most_viewed_district_views = most_viewed[1]
            
    avg_queries = total_queries / total_users if total_users > 0 else 0.0
    
    return {
        "total_users": total_users,
        "total_queries": total_queries,
        "districts_accessed": districts_accessed,
        "most_viewed_district": most_viewed_district,
        "most_viewed_district_views": most_viewed_district_views,
        "avg_queries_per_user": avg_queries
    }

@router.get("/users", response_model=List[AdminUserLog])
def get_admin_users(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Exposes user management stats (registration date, activity count). Requires ADMIN.
    """
    users = db.query(User).order_by(User.created_at.desc()).all()
    out = []
    for u in users:
        queries_count = db.query(QueryHistory).filter_by(user_id=u.id).count()
        out.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "created_at": u.created_at,
            "queries_count": queries_count
        })
    return out

@router.get("/queries", response_model=List[AdminQueryLog])
def get_admin_queries(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Lists query records. Requires ADMIN.
    """
    queries = db.query(QueryHistory).order_by(QueryHistory.created_at.desc()).all()
    out = []
    for q in queries:
        username = q.user.name if q.user else "Unknown"
        email = q.user.email if q.user else "Unknown"
        dist_name = q.district.district_name if q.district else "N/A"
        out.append({
            "id": q.id,
            "username": username,
            "email": email,
            "query": q.query,
            "response": q.response,
            "district_name": dist_name,
            "created_at": q.created_at
        })
    return out

@router.get("/access-statistics", response_model=List[DistrictAccessStat])
def get_admin_access_statistics(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Calculates view logs (total views vs unique user views) per district. Requires ADMIN.
    """
    stats = db.query(
        ResultAccess.district_id,
        func.count(ResultAccess.id).label("total_views"),
        func.count(func.distinct(ResultAccess.user_id)).label("unique_users"),
        func.max(ResultAccess.accessed_at).label("last_accessed")
    ).group_by(ResultAccess.district_id).all()
    
    out = []
    for s in stats:
        dist = db.query(Geography).filter_by(id=s.district_id).first()
        if dist:
            out.append({
                "district_name": dist.district_name,
                "state_name": dist.state_name,
                "total_views": s.total_views,
                "unique_users": s.unique_users,
                "last_accessed": s.last_accessed
            })
    out.sort(key=lambda x: x["total_views"], reverse=True)
    return out

@router.get("/export-excel")
def get_admin_export_excel(db: Session = Depends(get_db), current_user: User = Depends(get_admin_user)):
    """
    Generates a multi-sheet Excel spreadsheet and streams it to the admin browser. Requires ADMIN.
    """
    users = db.query(User).all()
    queries = db.query(QueryHistory).all()
    
    # Retrieve access stats
    access_stats = get_admin_access_statistics(db, current_user)
    
    # Retrieve summaries
    summary_stats = get_admin_statistics(db, current_user)
    
    # Compile
    excel_buffer = ExcelService.generate_admin_report(users, queries, access_stats, summary_stats)
    
    headers = {
        'Content-Disposition': 'attachment; filename="ingres_ai_admin_report.xlsx"'
    }
    
    return StreamingResponse(
        excel_buffer,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
