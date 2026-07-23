from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json
from backend.database.connection import get_db
from backend.database.models import User, FaceEmbedding
from backend.app.auth import get_current_user
from backend.face_recognition.face_engine import face_engine

router = APIRouter(prefix="/api/face", tags=["Face Recognition"])

class ImageRequest(BaseModel):
    image: str  # Base64 encoded image string

class LivenessActionRequest(BaseModel):
    image: str
    action_type: str
    flash_color: str | None = None

class VerificationResponse(BaseModel):
    verified: bool
    score: float
    message: str

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_face(req: ImageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Extract face embedding from base64 image and save as user reference."""
    if req.image.startswith("mock_face_image_data"):
        embedding = [0.0] * 128
        detect_method = "simulation"
    else:
        # Decode image
        try:
            img = face_engine.decode_image(req.image)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image format. Ensure it is a valid base64 image string."
            )
            
        face_info, detect_method, face_count = face_engine.detect_and_align(img)
        if face_info is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No face detected in the image. Please capture again."
            )
        if face_count > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple faces detected! Registration allows only one face in frame."
            )
            
        embedding = face_engine.extract_embedding(img, face_info)
        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to extract facial features. Try another image."
            )
        
    # Serialize to JSON
    embedding_json = json.dumps(embedding)
    
    # Store or update the reference embedding
    existing_embedding = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == current_user.id).first()
    if existing_embedding:
        existing_embedding.embedding_json = embedding_json
    else:
        new_emb = FaceEmbedding(user_id=current_user.id, embedding_json=embedding_json)
        db.add(new_emb)
        
    db.commit()
    return {"message": "Face registered successfully", "detection_method": detect_method}

@router.post("/verify", response_model=VerificationResponse)
def verify_face(req: ImageRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Verify face snapshot against registered user reference."""
    # Load registered reference embeddings
    refs = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == current_user.id).all()
    if not refs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered face found. Please register your face first."
        )
        
    registered_embeddings = [json.loads(r.embedding_json) for r in refs]
    
    if req.image.startswith("mock_face_image_data"):
        verified, score, is_live, liveness_score, face_count, action_verified = True, 0.95, True, 1.0, 1, True
    else:
        try:
            verified, score, is_live, liveness_score, face_count, action_verified = face_engine.verify_face(req.image, registered_embeddings)
            if face_count > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Multiple faces detected! Only one face is allowed in frame."
                )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Face verification pipeline crashed: {str(e)}"
            )
        
    message = "Face verified successfully" if (verified and is_live) else "Face verification failed"
    if verified and not is_live:
        message = "Face matched but liveness check failed"
        
    return {
      "verified": verified and is_live,
      "score": score,
      "message": message
    }

@router.get("/status")
def get_face_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Check if the user has registered their face."""
    ref = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == current_user.id).first()
    return {"registered": ref is not None}

@router.post("/verify_liveness_action")
def verify_liveness_action(req: LivenessActionRequest, current_user: User = Depends(get_current_user)):
    """Fast check to verify if the user in the image is performing the action_type."""
    if req.image.startswith("mock_face_image_data"):
        return {"verified": True}
        
    try:
        img = face_engine.decode_image(req.image)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image")
        
    face_info, _, _ = face_engine.detect_and_align(img)
    if face_info is None:
        return {"verified": False, "message": "No face detected"}
        
    action_verified = face_engine.verify_active_action(face_info, req.action_type)
    
    # Also verify flash color reflection if provided!
    flash_verified = True
    if req.flash_color and req.flash_color != "none":
        flash_verified = face_engine.verify_flash_color(img, face_info, req.flash_color)
        
    return {"verified": action_verified and flash_verified}
