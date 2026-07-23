import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from backend.app.main import app
from backend.database.connection import Base, get_db
from backend.database.models import User

# Setup isolated test database
TEST_DB_URL = "sqlite:///./test_attendance.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override the get_db dependency in the app
app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True, scope="module")
def setup_and_teardown_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    yield
    # Drop tables after tests finish
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_attendance.db"):
        try:
            os.remove("./test_attendance.db")
        except PermissionError:
            pass

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "online"

def test_register_user():
    response = client.post(
        "/api/auth/register",
        json={
            "username": "teststudent",
            "email": "teststudent@example.com",
            "password": "testpassword123",
            "role": "Student"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "teststudent"
    assert data["email"] == "teststudent@example.com"
    assert data["role"] == "Student"
    assert "id" in data

def test_register_duplicate_user():
    # Attempt duplicate register
    response = client.post(
        "/api/auth/register",
        json={
            "username": "teststudent",
            "email": "another@example.com",
            "password": "testpassword123",
            "role": "Student"
        }
    )
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]

def test_login_json():
    # Login successfully
    response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "testpassword123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "Student"
    assert data["username"] == "teststudent"

def test_login_incorrect_password():
    response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == 400
    assert "Incorrect username or password" in response.json()["detail"]

def test_get_profile_unauthorized():
    response = client.get("/api/auth/me")
    assert response.status_code == 401

def test_get_profile_authorized():
    # Login to get token
    login_response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "testpassword123"
        }
    )
    token = login_response.json()["access_token"]
    
    # Request profile
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "teststudent"
    assert data["role"] == "Student"


def test_mark_attendance_valid_signature():
    import hmac
    import hashlib
    import time
    from backend.app.config import API_SIGNING_SECRET
    from backend.database.models import FaceEmbedding
    import json
    
    # 1. Login to get token
    login_response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "testpassword123"
        }
    )
    token = login_response.json()["access_token"]
    
    # Get database session from dependency overrides
    db = next(override_get_db())
    user = db.query(User).filter(User.username == "teststudent").first()
    
    # Add face reference for user in the test database
    dummy_embedding = [0.1] * 128
    face_ref = FaceEmbedding(user_id=user.id, embedding_json=json.dumps(dummy_embedding))
    db.add(face_ref)
    db.commit()

    # Create valid signature
    timestamp = str(int(time.time()))
    lat, lon = 12.8231, 80.0444
    fingerprint = "test_fingerprint"
    virtual_cam_str = "0"
    devtools_str = "0"
    lat_str = f"{lat:.6f}"
    lon_str = f"{lon:.6f}"
    message = f"{lat_str}|{lon_str}|{fingerprint}|{timestamp}|{virtual_cam_str}|{devtools_str}"
    signature = hmac.new(
        API_SIGNING_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    response = client.post(
        "/api/attendance/mark",
        json={
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "latitude": lat,
            "longitude": lon,
            "device_fingerprint": fingerprint,
            "browser": "Chrome",
            "os": "Windows",
            "ip_address": "127.0.0.1",
            "signature": signature,
            "client_timestamp": timestamp
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200, response.json()
    data = response.json()
    assert data["face_verified"] is False
    assert data["status"] == "Pending Review"
    assert data["location_verified"] is True

def test_mark_attendance_invalid_signature():
    import time
    login_response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "testpassword123"
        }
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/attendance/mark",
        json={
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "latitude": 12.8231,
            "longitude": 80.0444,
            "device_fingerprint": "test_fingerprint",
            "browser": "Chrome",
            "os": "Windows",
            "ip_address": "127.0.0.1",
            "signature": "invalid_signature_here",
            "client_timestamp": str(int(time.time()))
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "signature mismatch" in response.json()["detail"].lower()

def test_mark_attendance_expired_timestamp():
    import hmac
    import hashlib
    import time
    from backend.app.config import API_SIGNING_SECRET

    login_response = client.post(
        "/api/auth/login/json",
        json={
            "username": "teststudent",
            "password": "testpassword123"
        }
    )
    token = login_response.json()["access_token"]

    # Use expired timestamp (10 minutes ago)
    timestamp = str(int(time.time()) - 600)
    lat, lon = 12.8231, 80.0444
    fingerprint = "test_fingerprint"
    virtual_cam_str = "0"
    devtools_str = "0"
    lat_str = f"{lat:.6f}"
    lon_str = f"{lon:.6f}"
    message = f"{lat_str}|{lon_str}|{fingerprint}|{timestamp}|{virtual_cam_str}|{devtools_str}"
    signature = hmac.new(
        API_SIGNING_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    response = client.post(
        "/api/attendance/mark",
        json={
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "latitude": lat,
            "longitude": lon,
            "device_fingerprint": fingerprint,
            "browser": "Chrome",
            "os": "Windows",
            "ip_address": "127.0.0.1",
            "signature": signature,
            "client_timestamp": timestamp
        },
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "timestamp has expired" in response.json()["detail"].lower()

def test_mark_attendance_device_sharing():
    import hmac
    import hashlib
    import time
    from backend.app.config import API_SIGNING_SECRET
    from backend.database.models import FaceEmbedding, User, DeviceLog
    import json
    
    # 1. Register dedicated users for this test to isolate execution completely
    for username, email in [("ds_student1", "ds1@example.com"), ("ds_student2", "ds2@example.com")]:
        reg_response = client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": "testpassword123",
                "role": "Student"
            }
        )
        assert reg_response.status_code in [201, 400]

    # Get database session from dependency overrides
    db = next(override_get_db())
    user1 = db.query(User).filter(User.username == "ds_student1").first()
    user2 = db.query(User).filter(User.username == "ds_student2").first()
    
    # Add face references
    for u in [user1, user2]:
        existing = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == u.id).first()
        if not existing:
            dummy_embedding = [0.1] * 128
            face_ref = FaceEmbedding(user_id=u.id, embedding_json=json.dumps(dummy_embedding))
            db.add(face_ref)
    db.commit()

    # 2. Login as user1
    login_res1 = client.post(
        "/api/auth/login/json",
        json={"username": "ds_student1", "password": "testpassword123"}
    )
    token1 = login_res1.json()["access_token"]

    # Mark attendance for user1 with shared fingerprint
    timestamp1 = str(int(time.time()))
    lat, lon = 12.8231, 80.0444
    shared_fingerprint = "shared_fingerprint_xyz"
    virtual_cam_str = "0"
    devtools_str = "0"
    lat_str = f"{lat:.6f}"
    lon_str = f"{lon:.6f}"
    message1 = f"{lat_str}|{lon_str}|{shared_fingerprint}|{timestamp1}|{virtual_cam_str}|{devtools_str}"
    sig1 = hmac.new(API_SIGNING_SECRET.encode('utf-8'), message1.encode('utf-8'), hashlib.sha256).hexdigest()

    res1 = client.post(
        "/api/attendance/mark",
        json={
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "latitude": lat,
            "longitude": lon,
            "device_fingerprint": shared_fingerprint,
            "browser": "Chrome",
            "os": "Windows",
            "ip_address": "127.0.0.1",
            "signature": sig1,
            "client_timestamp": timestamp1
        },
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert res1.status_code == 200, res1.json()

    # 3. Login as user2
    login_res2 = client.post(
        "/api/auth/login/json",
        json={"username": "ds_student2", "password": "testpassword123"}
    )
    token2 = login_res2.json()["access_token"]

    # Mark attendance for user2 with the SAME shared fingerprint
    timestamp2 = str(int(time.time()))
    lat_str = f"{lat:.6f}"
    lon_str = f"{lon:.6f}"
    message2 = f"{lat_str}|{lon_str}|{shared_fingerprint}|{timestamp2}|{virtual_cam_str}|{devtools_str}"
    sig2 = hmac.new(API_SIGNING_SECRET.encode('utf-8'), message2.encode('utf-8'), hashlib.sha256).hexdigest()

    res2 = client.post(
        "/api/attendance/mark",
        json={
            "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            "latitude": lat,
            "longitude": lon,
            "device_fingerprint": shared_fingerprint,
            "browser": "Chrome",
            "os": "Windows",
            "ip_address": "127.0.0.1",
            "signature": sig2,
            "client_timestamp": timestamp2
        },
        headers={"Authorization": f"Bearer {token2}"}
    )
    
    assert res2.status_code == 200, res2.json()
    data2 = res2.json()
    
    # Verification of sharing flag
    assert data2["fraud_risk_score"] >= 80.0
    assert data2["status"] == "Pending Review"
    
    # Check details to ensure rule triggered matches
    details = json.loads(data2["details"]) if isinstance(data2["details"], str) else data2["details"]
    assert "Device Sharing" in details["rules_triggered"]

def test_firebase_login_new_user():
    response = client.post(
        "/api/auth/firebase",
        json={
            "id_token": "mock_firebase_token_for_newstudent",
            "role": "Student",
            "username": "newstudent"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["role"] == "Student"
    assert data["username"] == "newstudent"

def test_firebase_login_existing_user():
    response = client.post(
        "/api/auth/firebase",
        json={
            "id_token": "mock_firebase_token_for_newstudent",
            "role": "Student"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["username"] == "newstudent"

def test_mark_attendance_device_sharing_retry_auto_verify():
    import hmac
    import hashlib
    import time
    from backend.app.config import API_SIGNING_SECRET
    from backend.database.models import FaceEmbedding, User, AttendanceRecord
    import json
    from backend.face_recognition.face_engine import face_engine

    # Override verify_face to simulate successful face and liveness check
    original_verify = face_engine.verify_face
    face_engine.verify_face = lambda *args, **kwargs: (True, 0.95, True, 1.0, 1, True)

    try:
        # 1. Register dedicated users for this test
        for username, email in [("retry_student1", "retry1@example.com"), ("retry_student2", "retry2@example.com")]:
            reg_response = client.post(
                "/api/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": "testpassword123",
                    "role": "Student"
                }
            )
            assert reg_response.status_code in [201, 400]

        # Get database session
        db = next(override_get_db())
        user1 = db.query(User).filter(User.username == "retry_student1").first()
        user2 = db.query(User).filter(User.username == "retry_student2").first()
        
        # Add face references
        for u in [user1, user2]:
            existing = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == u.id).first()
            if not existing:
                dummy_embedding = [0.1] * 128
                face_ref = FaceEmbedding(user_id=u.id, embedding_json=json.dumps(dummy_embedding))
                db.add(face_ref)
        db.commit()

        # 2. Login as user1
        login_res1 = client.post(
            "/api/auth/login/json",
            json={"username": "retry_student1", "password": "testpassword123"}
        )
        token1 = login_res1.json()["access_token"]

        # Mark attendance for user1
        timestamp1 = str(int(time.time()))
        lat, lon = 12.8231, 80.0444
        shared_fingerprint = "retry_shared_fingerprint"
        virtual_cam_str = "0"
        devtools_str = "0"
        lat_str = f"{lat:.6f}"
        lon_str = f"{lon:.6f}"
        message1 = f"{lat_str}|{lon_str}|{shared_fingerprint}|{timestamp1}|{virtual_cam_str}|{devtools_str}"
        sig1 = hmac.new(API_SIGNING_SECRET.encode('utf-8'), message1.encode('utf-8'), hashlib.sha256).hexdigest()

        res1 = client.post(
            "/api/attendance/mark",
            json={
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "latitude": lat,
                "longitude": lon,
                "device_fingerprint": shared_fingerprint,
                "browser": "Chrome",
                "os": "Windows",
                "ip_address": "127.0.0.1",
                "signature": sig1,
                "client_timestamp": timestamp1
            },
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert res1.status_code == 200, res1.json()
        assert res1.json()["status"] == "Present"

        # 3. Login as user2
        login_res2 = client.post(
            "/api/auth/login/json",
            json={"username": "retry_student2", "password": "testpassword123"}
        )
        token2 = login_res2.json()["access_token"]

        # Mark attendance for user2 (First attempt: triggers Device Sharing -> Pending Review)
        timestamp2 = str(int(time.time()))
        lat_str = f"{lat:.6f}"
        lon_str = f"{lon:.6f}"
        message2 = f"{lat_str}|{lon_str}|{shared_fingerprint}|{timestamp2}|{virtual_cam_str}|{devtools_str}"
        sig2 = hmac.new(API_SIGNING_SECRET.encode('utf-8'), message2.encode('utf-8'), hashlib.sha256).hexdigest()

        res2 = client.post(
            "/api/attendance/mark",
            json={
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "latitude": lat,
                "longitude": lon,
                "device_fingerprint": shared_fingerprint,
                "browser": "Chrome",
                "os": "Windows",
                "ip_address": "127.0.0.1",
                "signature": sig2,
                "client_timestamp": timestamp2
            },
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert res2.status_code == 200, res2.json()
        data2 = res2.json()
        assert data2["status"] == "Pending Review"
        assert data2["fraud_risk_score"] >= 80.0

        # 4. Retry check-in sequence for user2 (Second attempt within 15 minutes)
        timestamp3 = str(int(time.time()) + 1)  # Ensure distinct timestamp
        lat_str = f"{lat:.6f}"
        lon_str = f"{lon:.6f}"
        message3 = f"{lat_str}|{lon_str}|{shared_fingerprint}|{timestamp3}|{virtual_cam_str}|{devtools_str}"
        sig3 = hmac.new(API_SIGNING_SECRET.encode('utf-8'), message3.encode('utf-8'), hashlib.sha256).hexdigest()

        res3 = client.post(
            "/api/attendance/mark",
            json={
                "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
                "latitude": lat,
                "longitude": lon,
                "device_fingerprint": shared_fingerprint,
                "browser": "Chrome",
                "os": "Windows",
                "ip_address": "127.0.0.1",
                "signature": sig3,
                "client_timestamp": timestamp3
            },
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert res3.status_code == 200, res3.json()
        data3 = res3.json()
        
        # User should now be automatically verified as "Present" with a lower risk score
        assert data3["status"] == "Present"
        assert data3["fraud_risk_score"] < 80.0

        # Check database to ensure user2 only has 1 attendance record total (the record was updated, not duplicated)
        records = db.query(AttendanceRecord).filter(AttendanceRecord.user_id == user2.id).all()
        assert len(records) == 1
        assert records[0].status == "Present"
    finally:
        # Restore original verify_face function
        face_engine.verify_face = original_verify

