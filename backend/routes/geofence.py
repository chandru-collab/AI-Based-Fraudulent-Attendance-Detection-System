from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
import datetime

from backend.database.connection import get_db
from backend.database.models import GeofenceArea, User
from backend.app.auth import get_current_user, require_role

router = APIRouter(prefix="/api/geofence", tags=["Geofence Management"])

# Schemas
class GeofenceCreate(BaseModel):
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    is_active: bool = True

class GeofenceResponse(BaseModel):
    id: int
    name: str
    latitude: float
    longitude: float
    radius_meters: float
    is_active: bool
    created_at: datetime.datetime

    class Config:
        from_attributes = True

@router.get("/", response_model=List[GeofenceResponse])
def get_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin"]))
):
    """Get all geofences. Admin only."""
    return db.query(GeofenceArea).all()

@router.post("/", response_model=GeofenceResponse)
def create_geofence(
    geofence: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin"]))
):
    """Create a new geofence. Admin only."""
    new_geo = GeofenceArea(**geofence.dict())
    db.add(new_geo)
    db.commit()
    db.refresh(new_geo)
    return new_geo

@router.put("/{geofence_id}", response_model=GeofenceResponse)
def update_geofence(
    geofence_id: int,
    geofence_update: GeofenceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin"]))
):
    """Update an existing geofence."""
    geo = db.query(GeofenceArea).filter(GeofenceArea.id == geofence_id).first()
    if not geo:
        raise HTTPException(status_code=404, detail="Geofence not found")
    
    for key, value in geofence_update.dict().items():
        setattr(geo, key, value)
        
    db.commit()
    db.refresh(geo)
    return geo

@router.delete("/{geofence_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_geofence(
    geofence_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["Admin", "Super Admin"]))
):
    """Delete a geofence."""
    geo = db.query(GeofenceArea).filter(GeofenceArea.id == geofence_id).first()
    if not geo:
        raise HTTPException(status_code=404, detail="Geofence not found")
        
    db.delete(geo)
    db.commit()
    return None
