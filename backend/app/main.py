import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import logging

from backend.database.connection import engine, Base
from backend.app.firebase import FIREBASE_INITIALIZED # Initialize Firebase Admin
from backend.routes.auth import router as auth_router
from backend.routes.face import router as face_router
from backend.routes.attendance import router as attendance_router
from backend.routes.fraud import router as fraud_router
from backend.routes.analytics import router as analytics_router
from backend.routes.notifications import router as notifications_router
from backend.routes.geofence import router as geofence_router
from backend.routes.review import router as review_router
from backend.routes.admin import router as admin_router
from fastapi.staticfiles import StaticFiles
import os

# Configure Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("main")

# Auto-clean project directories on startup
try:
    from clean_project import clean_project
    logger.info("Running automatic project cleanup...")
    clean_project()
except Exception as clean_err:
    logger.error(f"Error running automatic project cleanup: {clean_err}")

# Auto-create database tables on startup
logger.info("Initializing database and tables...")
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized successfully.")
    
    # Seed or update a default admin user 'chandru'
    from backend.database.models import User
    from backend.routes.auth import hash_password
    from backend.database.connection import SessionLocal
    
    db = SessionLocal()
    try:
        # Seed or update a default admin user 'chandru'
        admin_user = db.query(User).filter(User.username == "chandru").first()
        if not admin_user:
            logger.info("Seeding default admin user 'chandru'...")
            admin_user = User(
                username="chandru",
                email="chandru22ai@gmail.com",
                hashed_password=hash_password("admin_password_123!"),
                role="Admin"
            )
            db.add(admin_user)
            db.commit()
            logger.info("Default admin user 'chandru' seeded successfully.")
        else:
            logger.info("Updating default admin user 'chandru' password to ensure seamless auth...")
            admin_user.hashed_password = hash_password("admin_password_123!")  # type: ignore
            admin_user.role = "Admin"  # type: ignore
            db.commit()
            logger.info("Default admin user 'chandru' updated successfully.")

        # Seed or update a default faculty user 'faculty'
        faculty_user = db.query(User).filter(User.username == "faculty").first()
        if not faculty_user:
            logger.info("Seeding default faculty user 'faculty'...")
            faculty_user = User(
                username="faculty",
                email="faculty@college.edu",
                hashed_password=hash_password("faculty_password_123!"),
                role="Faculty"
            )
            db.add(faculty_user)
            db.commit()
            logger.info("Default faculty user 'faculty' seeded successfully.")
        else:
            logger.info("Updating default faculty user 'faculty' password to ensure seamless auth...")
            faculty_user.hashed_password = hash_password("faculty_password_123!")  # type: ignore
            faculty_user.role = "Faculty"  # type: ignore
            db.commit()
            logger.info("Default faculty user 'faculty' updated successfully.")
    except Exception as seed_err:
        logger.error(f"Error seeding default users: {seed_err}")
        db.rollback()
    finally:
        db.close()
        
except Exception as e:
    logger.error(f"Error during database initialization: {e}")

# Create FastAPI App
app = FastAPI(
    title="AI-Based Fraudulent Attendance Detection API",
    description="Backend API services supporting face verification, geolocation geofencing, device checks, and machine learning fraud analysis.",
    version="1.0.0"
)

# Warn if default secrets are used in production stage
from backend.app.config import JWT_SECRET, API_SIGNING_SECRET
if os.getenv("ENV") == "production" or os.getenv("STAGE") == "production" or os.getenv("FASTAPI_ENV") == "production":
    if JWT_SECRET == "ai_fraud_attendance_system_secret_key_2026":
        logger.warning("🚨 INSECURE CONFIGURATION: Using default JWT_SECRET in production! Override it using the JWT_SECRET environment variable.")
    if API_SIGNING_SECRET == "super_secret_payload_signing_key_2026":
        logger.warning("🚨 INSECURE CONFIGURATION: Using default API_SIGNING_SECRET in production! Override it using the API_SIGNING_SECRET environment variable.")

# CORS Middleware config
# Allow React frontend dev servers and production domains to interact with the API
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

cors_origins_env = os.getenv("CORS_ORIGINS")
if cors_origins_env:
    for o in cors_origins_env.split(","):
        stripped = o.strip()
        if stripped:
            origins.append(stripped)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import time
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"Path: {request.url.path} took: {process_time * 1000:.2f} ms")
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Register Routers
app.include_router(auth_router)
app.include_router(face_router)
app.include_router(attendance_router)
app.include_router(fraud_router)
app.include_router(analytics_router)
app.include_router(notifications_router)
app.include_router(geofence_router)
app.include_router(review_router)
app.include_router(admin_router)

# Mount static directory for check-in images
os.makedirs("backend/uploads", exist_ok=True)
app.mount("/backend/uploads", StaticFiles(directory="backend/uploads"), name="uploads")

@app.get("/")
def read_root(request: Request):
    # Check if request accepts HTML (typically browsers)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Based Attendance API</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 30, 49, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-green: #10b981;
            --accent-blue: #3b82f6;
            --accent-glow: rgba(16, 185, 129, 0.15);
        }
        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }
        body {
            font-family: 'Outfit', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            position: relative;
        }
        .glow-circle {
            position: absolute;
            width: 500px;
            height: 500px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.1) 0%, rgba(0,0,0,0) 70%);
            top: -200px;
            left: -200px;
            z-index: 0;
        }
        .glow-circle-right {
            position: absolute;
            width: 600px;
            height: 600px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(16, 185, 129, 0.08) 0%, rgba(0,0,0,0) 70%);
            bottom: -250px;
            right: -250px;
            z-index: 0;
        }
        .container {
            position: relative;
            z-index: 10;
            width: 100%;
            max-width: 540px;
            padding: 24px;
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 24px;
            padding: 40px;
            backdrop-filter: blur(16px);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
            text-align: center;
        }
        .logo-container {
            margin-bottom: 24px;
            display: inline-flex;
            position: relative;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: var(--accent-green);
            padding: 8px 16px;
            border-radius: 100px;
            font-weight: 600;
            font-size: 0.875rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            box-shadow: 0 0 20px var(--accent-glow);
            animation: pulse-border 2s infinite;
        }
        .status-dot {
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
            animation: blink 1.5s infinite;
        }
        h1 {
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.25;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #fff 0%, #a5b4fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .description {
            color: var(--text-secondary);
            font-size: 1rem;
            line-height: 1.6;
            margin-bottom: 32px;
        }
        .links-group {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }
        .btn {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            padding: 14px 24px;
            border-radius: 12px;
            font-weight: 600;
            font-size: 0.95rem;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
        }
        .btn-primary {
            background: linear-gradient(135deg, var(--accent-blue) 0%, #2563eb 100%);
            color: white;
            border: none;
            box-shadow: 0 4px 14px rgba(59, 130, 246, 0.3);
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
        }
        .btn-secondary {
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
            border: 1px solid var(--border-color);
        }
        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.08);
            border-color: rgba(255, 255, 255, 0.15);
            transform: translateY(-2px);
        }
        .footer {
            margin-top: 24px;
            font-size: 0.75rem;
            color: rgba(255, 255, 255, 0.3);
            letter-spacing: 0.05em;
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        @keyframes pulse-border {
            0%, 100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.2); }
            50% { box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }
        }
    </style>
</head>
<body>
    <div class="glow-circle"></div>
    <div class="glow-circle-right"></div>
    <div class="container">
        <div class="card">
            <div class="logo-container">
                <div class="status-badge">
                    <span class="status-dot"></span>
                    API Online
                </div>
            </div>
            <h1>AI Attendance System</h1>
            <p class="description">The backend API services are running successfully. Choose where you want to go next:</p>
            <div class="links-group">
                <a href="http://localhost:5173" class="btn btn-primary">
                    Open Frontend Web App Portal
                </a>
                <a href="/docs" class="btn btn-secondary">
                    View Swagger API Documentation
                </a>
            </div>
        </div>
        <div style="text-align: center;">
            <p class="footer">PORTAL PORT: 5173 &bull; API PORT: 8000</p>
        </div>
    </div>
</body>
</html>"""
        return HTMLResponse(content=html_content)
    
    return {
        "status": "online",
        "service": "AI-Based Fraudulent Attendance Detection API",
        "documentation": "/docs"
    }

@app.get("/api")
@app.get("/api/")
def read_api_root():
    return {
        "status": "online",
        "service": "AI-Based Fraudulent Attendance Detection API",
        "documentation": "/docs"
    }

@app.get("/api/config/campus")
def get_campus_config():
    """Return campus geofence configuration for the frontend."""
    from backend.app.config import CAMPUS_LATITUDE, CAMPUS_LONGITUDE, GEOFENCE_RADIUS_METERS, CAMPUS_NAME
    return {
        "name": CAMPUS_NAME,
        "latitude": CAMPUS_LATITUDE,
        "longitude": CAMPUS_LONGITUDE,
        "radius_meters": GEOFENCE_RADIUS_METERS
    }

if __name__ == "__main__":
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
