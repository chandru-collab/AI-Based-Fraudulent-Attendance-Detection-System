import os
from pathlib import Path
from dotenv import load_dotenv

# Load env variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./attendance.db")

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET", "ai_fraud_attendance_system_secret_key_2026")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440")) # 24 hours
API_SIGNING_SECRET = os.getenv("API_SIGNING_SECRET", "super_secret_payload_signing_key_2026")

# Geofence configuration — College Campus GPS
# Override via .env: CAMPUS_LATITUDE, CAMPUS_LONGITUDE, GEOFENCE_RADIUS_METERS, CAMPUS_NAME
CAMPUS_NAME = os.getenv("CAMPUS_NAME", "College Campus")
CAMPUS_LATITUDE = float(os.getenv("CAMPUS_LATITUDE", "12.8231"))   # Default: SRM IST Kattankulathur
CAMPUS_LONGITUDE = float(os.getenv("CAMPUS_LONGITUDE", "80.0444"))
GEOFENCE_RADIUS_METERS = float(os.getenv("GEOFENCE_RADIUS_METERS", "300.0"))

# Models directory
MODELS_DIR = os.path.join(BASE_DIR, "ml_models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Face recognition models
YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
SFACE_PATH = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")
FRAUD_MODEL_PATH = os.path.join(MODELS_DIR, "fraud_detector.pkl")
