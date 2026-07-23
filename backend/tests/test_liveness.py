import pytest
import numpy as np
from backend.face_recognition.face_engine import FaceEngine

@pytest.fixture
def face_engine():
    return FaceEngine()

def test_check_liveness_invalid_inputs(face_engine):
    # Null / empty inputs should return False
    is_live, score = face_engine.check_liveness(None, None)
    assert not is_live
    assert score == 0.0

def test_check_liveness_low_variance_spoof(face_engine):
    # 1. Create a completely flat image (uniform values) which has 0 Laplacian variance (spoof/blur check)
    flat_img = np.zeros((100, 100, 3), dtype=np.uint8)
    face_info = np.array([0, 0, 100, 100])
    
    is_live, score = face_engine.check_liveness(flat_img, face_info)
    assert not is_live
    assert score < 0.70

def test_check_liveness_high_variance_live(face_engine):
    # 2. Create a high-contrast noise image which has high Laplacian variance
    # Setting random seed for reproducibility
    np.random.seed(42)
    noise_img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    face_info = np.array([0, 0, 100, 100])
    
    is_live, score = face_engine.check_liveness(noise_img, face_info)
    assert is_live
    assert score > 0.70

def test_check_liveness_invalid_eye_geometry(face_engine):
    # 3. Create high contrast image but with weird landmarks (eye ratio out of bounds)
    np.random.seed(42)
    noise_img = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    
    # face_info format: [x, y, w, h, left_eye_x, left_eye_y, right_eye_x, right_eye_y, ...]
    # Eye distance = 5px, width = 100px -> ratio = 0.05 (too small, less than 0.18)
    bad_face_info = np.array([0, 0, 100, 100, 45, 50, 50, 50, 0, 0, 0, 0, 0, 0, 0], dtype=np.float32)
    
    is_live, score = face_engine.check_liveness(noise_img, bad_face_info)
    # Texture check might pass but geometry check should fail liveness
    assert not is_live

def test_explain_anomaly():
    from backend.fraud_detection.ml_engine import fraud_engine
    import json
    
    details = {
        "rules_triggered": ["Liveness Spoofing", "Location Mismatch"],
        "distance_meters": 350.0,
        "face_match_score": 0.95,
        "face_liveness_score": 0.20,
        "risk_category": "Critical"
    }
    
    explanation = fraud_engine.explain_anomaly(json.dumps(details), 85.0)
    assert "Liveness Check" in explanation["feature_importance"]
    assert "Geofence Coordinates" in explanation["feature_importance"]
    assert len(explanation["risk_factors"]) == 2
    assert "Critical" in explanation["summary"]
