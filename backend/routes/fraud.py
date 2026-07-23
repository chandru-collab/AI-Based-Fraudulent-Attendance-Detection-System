from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from pydantic import BaseModel
import datetime
from backend.database.connection import get_db
from backend.database.models import User, FraudLog, AttendanceRecord, RiskScore
from backend.app.auth import get_current_user, require_role
from backend.fraud_detection.ml_engine import fraud_engine

router = APIRouter(prefix="/api/fraud", tags=["Fraud Analytics"])

# Pydantic schema for response
class FraudLogResponse(BaseModel):
    id: int
    user_id: int
    username: str
    attendance_id: Optional[int]
    rule_triggered: str
    severity: str
    details: Optional[str]
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

class FraudSummary(BaseModel):
    total_alerts: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

@router.get("/logs", response_model=List[FraudLogResponse])
def get_fraud_logs(
    severity: Optional[str] = None,
    username: Optional[str] = None,
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db)
):
    """Retrieve list of fraudulent logs. Restricted to Admin/Faculty."""
    query = db.query(
        FraudLog.id,
        FraudLog.user_id,
        User.username,
        FraudLog.attendance_id,
        FraudLog.rule_triggered,
        FraudLog.severity,
        FraudLog.details,
        FraudLog.timestamp
    ).join(User, User.id == FraudLog.user_id)

    if severity:
        query = query.filter(FraudLog.severity == severity)
    if username:
        query = query.filter(User.username.like(f"%{username}%"))

    # Return list ordered by newest
    results = query.order_by(FraudLog.timestamp.desc()).all()
    
    # Format results to match Pydantic schema
    formatted_logs = []
    for row in results:
        formatted_logs.append({
            "id": row.id,
            "user_id": row.user_id,
            "username": row.username,
            "attendance_id": row.attendance_id,
            "rule_triggered": row.rule_triggered,
            "severity": row.severity,
            "details": row.details,
            "timestamp": row.timestamp
        })
        
    return formatted_logs

@router.get("/summary", response_model=FraudSummary)
def get_fraud_summary(
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db)
):
    """Get aggregate count of fraud logs grouped by severity."""
    total = db.query(FraudLog).count()
    critical = db.query(FraudLog).filter(FraudLog.severity == "Critical").count()
    high = db.query(FraudLog).filter(FraudLog.severity == "High").count()
    medium = db.query(FraudLog).filter(FraudLog.severity == "Medium").count()
    low = db.query(FraudLog).filter(FraudLog.severity == "Low").count()

    return {
        "total_alerts": total,
        "critical_count": critical,
        "high_count": high,
        "medium_count": medium,
        "low_count": low
    }

@router.post("/logs/{log_id}/resolve", status_code=status.HTTP_200_OK)
def resolve_fraud_log(
    log_id: int,
    current_user: User = Depends(require_role(["Admin", "Super Admin"])),
    db: Session = Depends(get_db)
):
    """Delete or resolve an alert by log ID. Restricted to Admins."""
    log = db.query(FraudLog).filter(FraudLog.id == log_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Fraud log not found")
        
    db.delete(log)
    db.commit()
    return {"message": f"Alert {log_id} resolved successfully."}

@router.get("/analyze/{attendance_id}")
def analyze_attendance_fraud(
    attendance_id: int,
    current_user: User = Depends(require_role(["Admin", "Faculty", "Super Admin"])),
    db: Session = Depends(get_db)
):
    """AI Explainability API to analyze and decode fraud risks for a specific check-in."""
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == attendance_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found")
        
    explanation = fraud_engine.explain_anomaly(record.details, record.fraud_risk_score)
    return explanation
