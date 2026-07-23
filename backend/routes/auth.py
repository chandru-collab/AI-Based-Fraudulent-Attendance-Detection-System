from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, Field
from backend.database.connection import get_db
from backend.database.models import User
from backend.app.auth import hash_password, verify_password, create_access_token, get_current_user
from backend.app.firebase import verify_firebase_token

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Pydantic schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field("Student", description="Student, Admin, Faculty, Super Admin")

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str
    username: str

import logging
logger = logging.getLogger("auth")

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Return the real, current role of the authenticated user from the database."""
    return current_user

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(
        (User.username == user_in.username) | (User.email == user_in.email)
    ).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered"
        )
    
    # Hash password and create user
    hashed_pwd = hash_password(user_in.password)
    
    # Security: Force self-registrations to be "Student" by default.
    # Promoting to Admin must be done database-side or via an authorized admin user.
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_pwd,
        role="Student"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 password login (form-encoded)."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    
    # Create token
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }

@router.post("/login/json", response_model=Token)
def login_json(login_data: UserLogin, db: Session = Depends(get_db)):
    """JSON-encoded login fallback, convenient for standard Axios clients."""
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, str(user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect username or password"
        )
    
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve logged-in user profile details."""
    return current_user

class FirebaseLoginRequest(BaseModel):
    id_token: str
    role: str = "Student"
    username: str | None = None

@router.post("/firebase", response_model=Token)
def firebase_login(data: FirebaseLoginRequest, db: Session = Depends(get_db)):
    """Verifies Firebase ID token and registers/logs in the user."""
    logger.info("Received Firebase authentication request. Verifying token...")
    try:
        decoded = verify_firebase_token(data.id_token)
        logger.info("Firebase token verified successfully.")
    except Exception as e:
        logger.error(f"Firebase token verification failed with exception: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Firebase token verification failed: {str(e)}"
        )
        
    email = decoded.get("email")
    if not email:
        logger.warning("Firebase token verified but does not contain a valid email address.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Firebase token does not contain a valid email address"
        )
    
    # Try to find user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Auto-provision username from email if not explicitly provided during login
        base_username = data.username or email.split("@")[0]
        unique_username = base_username
        counter = 1
        while db.query(User).filter(User.username == unique_username).first():
            unique_username = f"{base_username}_{counter}"
            counter += 1
            
        # Register a new user automatically
        hashed_pwd = hash_password(f"firebase_sso_default_{unique_username}!")
        
        # Create user profile
        # Security: Force role to Student during auto-provisioning
        user = User(
            username=unique_username,
            email=email,
            hashed_password=hashed_pwd,
            role="Student"
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            logger.info(f"Auto-provisioned local user profile for {email} with username {unique_username}")
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error during Firebase registration: {str(e)}"
            )
            
    # Backend Role Verification: Check if user has the requested privileges
    if data.role in ["Admin", "Faculty", "Super Admin"] and user.role not in ["Admin", "Faculty", "Super Admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access Denied: Your account does not have administrator privileges."
        )
            
    access_token = create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "username": user.username
    }


