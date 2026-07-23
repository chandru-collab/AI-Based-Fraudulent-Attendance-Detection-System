import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.database.connection import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="Student", nullable=False)  # Admin, Faculty, Student, Super Admin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    face_embeddings = relationship("FaceEmbedding", back_populates="user", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="user", cascade="all, delete-orphan")
    fraud_logs = relationship("FraudLog", back_populates="user", cascade="all, delete-orphan")
    device_logs = relationship("DeviceLog", back_populates="user", cascade="all, delete-orphan")
    location_logs = relationship("LocationLog", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    risk_scores = relationship("RiskScore", back_populates="user", cascade="all, delete-orphan")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    status = Column(String(20), default="Present", nullable=False)  # Present, Absent, Flagged
    face_verified = Column(Boolean, default=False)
    location_verified = Column(Boolean, default=False)
    device_verified = Column(Boolean, default=False)
    fraud_risk_score = Column(Float, default=0.0)
    details = Column(Text, nullable=True)  # JSON or plain text details

    # Relationships
    user = relationship("User", back_populates="attendance_records")
    fraud_logs = relationship("FraudLog", back_populates="attendance", cascade="all, delete-orphan")

class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    embedding_json = Column(Text, nullable=False)  # Serialized list of floats
    registered_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="face_embeddings")

class FraudLog(Base):
    __tablename__ = "fraud_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance_records.id", ondelete="SET NULL"), nullable=True, index=True)
    rule_triggered = Column(String(100), nullable=False)  # Location Mismatch, Device Change, Facial Mismatch, Anomaly
    severity = Column(String(20), default="Low", nullable=False)  # Low, Medium, High, Critical
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="fraud_logs")
    attendance = relationship("AttendanceRecord", back_populates="fraud_logs")

class DeviceLog(Base):
    __tablename__ = "device_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    fingerprint = Column(String(100), nullable=False, index=True)  # Browser fingerprint hash
    browser = Column(String(50), nullable=True)
    os = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)
    is_virtual_camera = Column(Boolean, default=False, nullable=True)
    is_devtools_open = Column(Boolean, default=False, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="device_logs")

class GeofenceArea(Base):
    __tablename__ = "geofence_areas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    radius_meters = Column(Float, default=100.0, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class LocationLog(Base):
    __tablename__ = "location_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    verified_in_geofence = Column(Boolean, default=False)
    geofence_id = Column(Integer, ForeignKey("geofence_areas.id", ondelete="SET NULL"), nullable=True)
    distance_from_center = Column(Float, default=0.0)  # distance in meters
    ip_address = Column(String(45), nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="location_logs")
    geofence = relationship("GeofenceArea")

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    type = Column(String(20), default="info")  # info, warning, alert
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="notifications")

class RiskScore(Base):
    __tablename__ = "risk_scores"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    score = Column(Float, default=0.0)
    category = Column(String(20), default="Low")  # Low, Medium, High, Critical
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="risk_scores")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=True)
    faculty = Column(String(100), nullable=True)

