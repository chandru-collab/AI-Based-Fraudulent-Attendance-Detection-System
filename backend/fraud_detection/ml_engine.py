import os
import math
import pickle
import datetime
import logging
from typing import cast
from sqlalchemy.orm import Session
from backend.app.config import CAMPUS_LATITUDE, CAMPUS_LONGITUDE, GEOFENCE_RADIUS_METERS, FRAUD_MODEL_PATH
from backend.database.models import User, AttendanceRecord, DeviceLog, LocationLog, FraudLog, RiskScore

logger = logging.getLogger("fraud_engine")

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points in meters."""
    R = 6371000.0  # Radius of earth in meters
    
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    
    return R * c

class FraudEngine:
    def __init__(self):
        self.model = None
        self.load_model()
        
    def load_model(self):
        """Load trained Isolation Forest model from disk."""
        if os.path.exists(FRAUD_MODEL_PATH):
            try:
                import joblib
                self.model = joblib.load(FRAUD_MODEL_PATH)
                logger.info("Machine learning fraud detection model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading Isolation Forest model: {e}")
                self.model = None
        else:
            logger.warning(f"ML fraud model file not found at {FRAUD_MODEL_PATH}. Using heuristic engine.")
            self.model = None

    def evaluate_fraud(
        self, 
        db: Session, 
        user_id: int, 
        lat: float, 
        lon: float, 
        device_fingerprint: str,
        browser: str,
        os_name: str,
        ip_address: str,
        face_verified: bool,
        face_score: float,
        face_live: bool = True,
        liveness_score: float = 1.0,
        is_virtual_camera: bool = False,
        is_devtools_open: bool = False
    ) -> tuple[float, str, list[dict]]:
        """Evaluate checks and return (overall_risk_score, risk_category, list_of_rules_triggered)."""
        rules_triggered = []
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        hour_of_day = now.hour + now.minute / 60.0
        
        # 1. Location / Geofence Check
        distance = haversine_distance(lat, lon, CAMPUS_LATITUDE, CAMPUS_LONGITUDE)
        outside_geofence = distance > GEOFENCE_RADIUS_METERS
        if outside_geofence:
            rules_triggered.append({
                "rule": "Location Mismatch",
                "severity": "Medium",
                "details": f"Check-in outside campus boundary. Distance: {distance:.1f}m (limit: {GEOFENCE_RADIUS_METERS}m)."
            })
            
        # 2. Device Fingerprint Check
        # Query previous devices
        known_devices = db.query(DeviceLog).filter(DeviceLog.user_id == user_id).all()
        device_mismatch = False
        if known_devices:
            known_fingerprints = {d.fingerprint for d in known_devices}
            if device_fingerprint not in known_fingerprints:
                device_mismatch = True
                rules_triggered.append({
                    "rule": "Device Change",
                    "severity": "Medium",
                    "details": f"Unrecognized device fingerprint: {device_fingerprint[:8]}..."
                })
        else:
            # First device log for this user, register it silently
            pass

        # 3. Impossible Travel Check
        # Check time and distance from the last attendance record of the user
        last_record = db.query(AttendanceRecord).filter(
            AttendanceRecord.user_id == user_id
        ).order_by(AttendanceRecord.timestamp.desc()).first()
        
        impossible_travel = False
        if last_record:
            # Find matching location log for that attendance
            # For simplicity, fetch the last LocationLog of this user
            last_location = db.query(LocationLog).filter(
                LocationLog.user_id == user_id
            ).order_by(LocationLog.timestamp.desc()).first()
            
            if last_location:
                time_diff_hours = (now - last_location.timestamp).total_seconds() / 3600.0
                if 0.0027 < time_diff_hours < 4.0:  # Check windows between 10 seconds and 4 hours
                    travel_distance = haversine_distance(lat, lon, cast(float, last_location.latitude), cast(float, last_location.longitude))
                    speed_kmh = (travel_distance / 1000.0) / time_diff_hours
                    # Threshold speed: 120 km/h (unlikely driving speed) and at least 1 km distance to filter GPS jitter
                    if speed_kmh > 120.0 and travel_distance > 1000.0:
                        impossible_travel = True
                        rules_triggered.append({
                            "rule": "Impossible Travel",
                            "severity": "High",
                            "details": f"Subsequent check-in from {travel_distance/1000.0:.1f}km away in {time_diff_hours*60:.0f} mins (Speed: {speed_kmh:.1f} km/h)."
                        })

        # 4. Face Match Score Check
        face_mismatch = not face_verified
        face_mismatch_score = 1.0 - face_score  # Mismatch distance representation
        if face_mismatch:
            rules_triggered.append({
                "rule": "Facial Mismatch",
                "severity": "Critical",
                "details": f"Face verification match score {face_score:.2f} is below verification threshold."
            })

        # 5. Face Liveness Check (Anti-spoofing)
        if not face_live:
            rules_triggered.append({
                "rule": "Liveness Spoofing",
                "severity": "Critical",
                "details": f"Face liveness check failed. Liveness confidence score: {liveness_score:.2f}."
            })

        # 6. Odd Hours Check
        odd_hours = hour_of_day < 6.0 or hour_of_day > 22.0  # Before 6 AM or after 10 PM
        if odd_hours:
            rules_triggered.append({
                "rule": "Suspicious Timing",
                "severity": "Low",
                "details": f"Check-in at an unusual hour: {now.strftime('%I:%M %p')}."
            })

        # 7. Virtual Camera Check
        if is_virtual_camera:
            rules_triggered.append({
                "rule": "Virtual Camera",
                "severity": "Critical",
                "details": "Client webcam appears to be a virtual or software-emulated camera feed."
            })

        # 8. Console Tampering Check
        if is_devtools_open:
            rules_triggered.append({
                "rule": "Console Tampering",
                "severity": "High",
                "details": "Browser developer tools/console were active during verification."
            })

        # 9. Co-located Device Sharing / Peer Proxy Detection
        device_sharing = False
        twelve_hours_ago = now - datetime.timedelta(hours=12)
        other_device_logs = db.query(DeviceLog, User).join(User, User.id == DeviceLog.user_id).filter(
            DeviceLog.fingerprint == device_fingerprint,
            DeviceLog.user_id != user_id,
            DeviceLog.timestamp >= twelve_hours_ago
        ).all()
        
        if other_device_logs:
            # Check if this is a retry attempt (user has a pending review in the last 15 minutes)
            # If they are retrying and face_verified is True, we don't flag device sharing to allow auto-verification
            fifteen_minutes_ago = now - datetime.timedelta(minutes=15)
            recent_pending = db.query(AttendanceRecord).filter(
                AttendanceRecord.user_id == user_id,
                AttendanceRecord.status == "Pending Review",
                AttendanceRecord.timestamp >= fifteen_minutes_ago
            ).first()
            
            if recent_pending and face_verified:
                logger.info(f"User {user_id} is retrying check-in. Device sharing flag bypassed.")
            else:
                device_sharing = True
                sharing_usernames = list({u.username for _, u in other_device_logs})
                rules_triggered.append({
                    "rule": "Device Sharing",
                    "severity": "High",
                    "details": f"Device fingerprint shared with other student account(s) within 12 hours: {', '.join(sharing_usernames)}."
                })

        # Compute Risk Score using ML or Heuristics
        # Features order: [hour, distance, device_mismatch, face_mismatch_score, ip_mismatch, impossible_travel]
        # (IP mismatch is True if IP is different from last recorded IP)
        last_device = db.query(DeviceLog).filter(DeviceLog.user_id == user_id).order_by(DeviceLog.timestamp.desc()).first()
        ip_mismatch = 1 if (last_device and last_device.ip_address != ip_address) else 0
        
        feature_vector = [
            hour_of_day,
            distance,
            1 if device_mismatch else 0,
            face_mismatch_score,
            ip_mismatch,
            1 if impossible_travel else 0
        ]
        
        risk_score = 0.0
        
        if self.model:
            try:
                # Isolation Forest outputs -1 for anomaly, 1 for normal
                decision_value = float(self.model.decision_function([feature_vector])[0])
                risk_score = min(100.0, max(0.0, (0.5 - decision_value) * 100.0))
            except Exception as e:
                logger.error(f"Error during ML evaluation: {e}. Falling back to heuristic.")
                risk_score = self.compute_heuristic_score(outside_geofence, device_mismatch, impossible_travel, face_mismatch, face_score, odd_hours, not face_live, is_virtual_camera, is_devtools_open, device_sharing)
        else:
            risk_score = self.compute_heuristic_score(outside_geofence, device_mismatch, impossible_travel, face_mismatch, face_score, odd_hours, not face_live, is_virtual_camera, is_devtools_open, device_sharing)

        # Direct overrides for high-severity tampering
        if not face_live:
            risk_score = max(risk_score, 85.0)
        if is_virtual_camera:
            risk_score = max(risk_score, 95.0)
        if is_devtools_open:
            risk_score = max(risk_score, 75.0)
        if device_sharing:
            risk_score = max(risk_score, 80.0)

        # Categorize
        if risk_score >= 80.0:
            category = "Critical"
        elif risk_score >= 60.0:
            category = "High"
        elif risk_score >= 30.0:
            category = "Medium"
        else:
            category = "Low"
            
        return risk_score, category, rules_triggered

    def compute_heuristic_score(
        self, 
        outside_geofence: bool, 
        device_mismatch: bool, 
        impossible_travel: bool, 
        face_mismatch: bool, 
        face_score: float,
        odd_hours: bool,
        liveness_failed: bool = False,
        virtual_camera_detected: bool = False,
        devtools_open: bool = False,
        device_sharing: bool = False
    ) -> float:
        """Compute score (0-100) based on weighted heuristics."""
        score = 0.0
        
        if liveness_failed:
            score += 65.0  # Heavy penalty for face spoofing
            
        if face_mismatch:
            score += 50.0  # Heavily penalize face mismatch
        else:
            # Add minor penalty if face score was borderline
            if face_score < 0.75:
                score += (0.75 - face_score) * 40.0
                
        if outside_geofence:
            score += 25.0
            
        if impossible_travel:
            score += 35.0
            
        if device_mismatch:
            score += 15.0
            
        if odd_hours:
            score += 5.0

        if virtual_camera_detected:
            score += 80.0

        if devtools_open:
            score += 40.0

        if device_sharing:
            score += 45.0
            
        return min(100.0, score)

    def explain_anomaly(self, details_json: str, risk_score: float) -> dict:
        """AI-based explainability framework (XAI) for fraud detection records.
        Decodes the feature triggers and provides a structured natural-language rationale
        along with feature importances.
        """
        import json
        explanation = {
            "summary": "This attendance log shows no signs of anomaly.",
            "risk_factors": [],
            "feature_importance": {}
        }
        
        if not details_json:
            return explanation
            
        try:
            details = json.loads(details_json)
        except Exception:
            return explanation
            
        rules = details.get("rules_triggered", [])
        dist = details.get("distance_meters", 0.0)
        face_score = details.get("face_match_score", 1.0)
        liveness_score = details.get("face_liveness_score", 1.0)
        
        # Calculate feature contributions
        importances = {}
        factors = []
        
        if any("Liveness" in r for r in rules) or liveness_score < 0.47:
            importances["Liveness Check"] = 0.40
            factors.append("A spoofing/presentation attack was suspected on the camera feed due to texture flatness/blur detection.")
        if any("Facial" in r for r in rules) or face_score < 0.68:
            importances["Biometric ID Check"] = 0.35
            factors.append("Facial geometry matching confidence was below the verified student profile threshold.")
        if any("Impossible" in r for r in rules):
            importances["Impossible Speed Check"] = 0.25
            factors.append("Subsequent login attempt speed indicates impossible transit travel limits from the last session.")
        if any("Location" in r for r in rules) or dist > 150.0:
            importances["Geofence Coordinates"] = 0.20
            factors.append(f"Device coordinates were located outside the campus geofence range by {dist:.1f} meters.")
        if any(r == "Device Change" for r in rules):
            importances["Device Fingerprint"] = 0.10
            factors.append("Check-in was requested from an unrecognized client hardware fingerprint.")
        if any("Device Sharing" in r for r in rules):
            importances["Device Sharing Check"] = 0.35
            factors.append("This device fingerprint has been shared with other student account(s) in a short timeframe.")
        if any("Virtual Camera" in r for r in rules):
            importances["Virtual Camera Check"] = 0.50
            factors.append("A virtual camera emulation software (like OBS/ManyCam) was detected on the device.")
        if any("Console Tampering" in r for r in rules):
            importances["DevTools Detection"] = 0.30
            factors.append("Browser developer tools/console were active during verification.")
            
        # Normalize contributions
        total = sum(importances.values())
        if total > 0:
            importances = {k: float(v / total) for k, v in importances.items()}
            
        explanation["feature_importance"] = importances
        explanation["risk_factors"] = factors
        
        # Synthesize summary
        if factors:
            explanation["summary"] = f"Flagged with {details.get('risk_category', 'High')} Risk ({risk_score:.0f}%) due to: " + " ".join(factors)
        else:
            explanation["summary"] = f"Authorized session with a normal risk index of {risk_score:.1f}%."
            
        return explanation

# Instantiate singleton
fraud_engine = FraudEngine()
