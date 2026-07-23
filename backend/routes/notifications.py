from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import datetime
from backend.database.connection import get_db
from backend.database.models import User, Notification
from backend.app.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notification Center"])

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    message: str
    is_read: bool
    type: str
    timestamp: datetime.datetime

    class Config:
        from_attributes = True

@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    unread_only: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve notifications list for the logged-in user."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    return query.order_by(Notification.timestamp.desc()).all()

@router.post("/{notification_id}/read", status_code=status.HTTP_200_OK)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read."""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
        
    notification.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all unread notifications for current user as read."""
    unread_notifications = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).all()
    
    for n in unread_notifications:
        n.is_read = True
        
    db.commit()
    return {"message": f"Marked {len(unread_notifications)} notifications as read"}
