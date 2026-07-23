from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
import datetime
from pydantic import BaseModel

from backend.database.connection import get_db
from backend.database.models import User, AttendanceRecord, Notification
from backend.app.auth import get_current_user, require_role
from backend.fraud_detection.ml_engine import fraud_engine

router = APIRouter(prefix="/api/attendance", tags=["Attendance Quarantine & Review"])

class ReviewActionRequest(BaseModel):
    action: str  # "Approve" or "Reject"
    reason: Optional[str] = None

@router.get("/pending")
def get_pending_reviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin", "Faculty"]))
):
    """Get all attendance records currently in the Quarantine/Pending Review queue."""
    records = db.query(
        AttendanceRecord, User.username
    ).join(User, User.id == AttendanceRecord.user_id).filter(
        AttendanceRecord.status == "Pending Review"
    ).order_by(AttendanceRecord.timestamp.desc()).all()
    
    results = []
    for record, username in records:
        # Generate Explainable AI summary
        xai_summary = fraud_engine.explain_anomaly(record.details, record.fraud_risk_score)
        
        # Parse details to get image_path
        import json
        details_obj = {}
        if record.details:
            try:
                details_obj = json.loads(record.details)
            except:
                pass
                
        results.append({
            "id": record.id,
            "username": username,
            "timestamp": record.timestamp,
            "face_verified": record.face_verified,
            "fraud_risk_score": record.fraud_risk_score,
            "image_url": f"/{details_obj.get('image_path', '').replace('\\', '/')}" if details_obj.get('image_path') else None,
            "xai_explanation": xai_summary
        })
        
    return results

@router.post("/{record_id}/review")
def submit_review(
    record_id: int,
    review_req: ReviewActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin", "Faculty"]))
):
    """Manually approve or reject a quarantined attendance record."""
    record = db.query(AttendanceRecord).filter(AttendanceRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attendance record not found.")
        
    if record.status != "Pending Review":
        raise HTTPException(status_code=400, detail=f"Record is already processed (Status: {record.status}).")
        
    if review_req.action == "Approve":
        record.status = "Present"
        msg = f"Your attendance for {record.timestamp.strftime('%d %b %Y')} has been Manually Approved."
    elif review_req.action == "Reject":
        record.status = "Absent"
        msg = f"Your attendance for {record.timestamp.strftime('%d %b %Y')} was Rejected after manual review. Reason: {review_req.reason or 'Policy Violation'}."
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'Approve' or 'Reject'.")
        
    # Notify user
    notify = Notification(
        user_id=record.user_id,
        message=msg,
        type="info" if review_req.action == "Approve" else "alert",
        timestamp=datetime.datetime.utcnow()
    )
    db.add(notify)
    db.commit()
    
    return {"message": f"Record {record.id} updated to {record.status}."}
