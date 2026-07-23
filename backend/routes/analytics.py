from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case
import datetime
from typing import List, Dict, Any
from backend.database.connection import get_db
from backend.database.models import User, AttendanceRecord, DeviceLog, LocationLog, FraudLog, RiskScore
from backend.app.auth import get_current_user, require_role

router = APIRouter(prefix="/api/analytics", tags=["Dashboard Analytics"])

@router.get("/admin")
def get_admin_analytics(
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db)
):
    """Aggregates all real-time stats and timeline data for the Admin Dashboard."""
    # 1. KPI cards
    total_students = db.query(User).filter(User.role == "Student").count()
    total_records = db.query(AttendanceRecord).count()
    flagged_records = db.query(AttendanceRecord).filter(AttendanceRecord.status == "Pending Review").count()
    critical_risk_count = db.query(RiskScore).filter(RiskScore.category == "Critical").count()

    attendance_rate = 0.0
    if total_records > 0:
        present_count = db.query(AttendanceRecord).filter(AttendanceRecord.status == "Present").count()
        attendance_rate = (present_count / total_records) * 100.0

    # 2. Risk Categories Breakdown
    risk_breakdown = {
        "Low": db.query(RiskScore).filter(RiskScore.category == "Low").count(),
        "Medium": db.query(RiskScore).filter(RiskScore.category == "Medium").count(),
        "High": db.query(RiskScore).filter(RiskScore.category == "High").count(),
        "Critical": db.query(RiskScore).filter(RiskScore.category == "Critical").count()
    }

    # 3. Timeline Chart Data (last 7 days of attendance counts)
    now = datetime.datetime.utcnow()
    seven_days_ago = now - datetime.timedelta(days=7)
    
    # Query presenting counts grouped by date
    timeline_query = db.query(
        func.date(AttendanceRecord.timestamp).label("date"),
        func.sum(case((AttendanceRecord.status == "Present", 1), else_=0)).label("present"),
        func.sum(case((AttendanceRecord.status == "Pending Review", 1), else_=0)).label("flagged")
    ).filter(AttendanceRecord.timestamp >= seven_days_ago)\
     .group_by(func.date(AttendanceRecord.timestamp))\
     .order_by("date").all()

    timeline_data = []
    for day in timeline_query:
        timeline_data.append({
            "date": str(day.date),
            "present": int(day.present or 0),
            "flagged": int(day.flagged or 0)
        })

    # 4. Device Analytics OS Breakdown
    device_query = db.query(
        DeviceLog.os,
        func.count(DeviceLog.id).label("count")
    ).group_by(DeviceLog.os).all()
    
    device_data = {row.os or "Unknown": row.count for row in device_query}

    # 5. Live Ticker (Recent check-in list, showing username, status, face validation, and timestamp)
    recent_checks = db.query(
        AttendanceRecord.id,
        User.username,
        AttendanceRecord.timestamp,
        AttendanceRecord.status,
        AttendanceRecord.face_verified,
        AttendanceRecord.location_verified,
        AttendanceRecord.device_verified,
        AttendanceRecord.fraud_risk_score
    ).join(User, User.id == AttendanceRecord.user_id)\
     .order_by(AttendanceRecord.timestamp.desc())\
     .limit(10).all()

    ticker_data = []
    for r in recent_checks:
        ticker_data.append({
            "id": r.id,
            "username": r.username,
            "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "status": r.status,
            "face_verified": r.face_verified,
            "location_verified": r.location_verified,
            "device_verified": r.device_verified,
            "fraud_risk_score": r.fraud_risk_score
        })

    # 6. Heatmap Coordinate Data
    locations_query = db.query(
        LocationLog.latitude,
        LocationLog.longitude,
        LocationLog.verified_in_geofence,
        User.username
    ).join(User, User.id == LocationLog.user_id)\
     .order_by(LocationLog.timestamp.desc())\
     .limit(100).all()

    location_data = []
    for loc in locations_query:
        location_data.append({
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "verified": loc.verified_in_geofence,
            "username": loc.username
        })

    return {
        "stats": {
            "total_students": total_students,
            "total_records": total_records,
            "flagged_records": flagged_records,
            "critical_risk_count": critical_risk_count,
            "attendance_rate": round(attendance_rate, 1)
        },
        "risk_breakdown": risk_breakdown,
        "timeline": timeline_data,
        "device_breakdown": device_data,
        "recent_check_ins": ticker_data,
        "locations": location_data
    }

@router.get("/student")
def get_student_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Aggregates dashboard stats and individual charts for the Student Portal."""
    total_records = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == current_user.id).count()
    present_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.user_id == current_user.id,
        AttendanceRecord.status == "Present"
    ).count()
    flagged_records = db.query(AttendanceRecord).filter(
        AttendanceRecord.user_id == current_user.id,
        AttendanceRecord.status == "Pending Review"
    ).count()
    
    attendance_rate = 0.0
    if total_records > 0:
        attendance_rate = (present_records / total_records) * 100.0

    # Risk score trend
    recent_scores = db.query(RiskScore).filter(RiskScore.user_id == current_user.id)\
                      .order_by(RiskScore.timestamp.desc())\
                      .limit(7).all()
                      
    scores_trend = []
    for s in reversed(recent_scores):  # Chronological order
        scores_trend.append({
            "timestamp": s.timestamp.strftime("%m/%d %H:%M"),
            "score": s.score
        })

    return {
        "stats": {
            "total_records": total_records,
            "present_records": present_records,
            "flagged_records": flagged_records,
            "attendance_rate": round(attendance_rate, 1)
        },
        "scores_trend": scores_trend
    }
