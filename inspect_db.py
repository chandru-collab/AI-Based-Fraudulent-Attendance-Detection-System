from backend.database.connection import SessionLocal
from backend.database.models import User, AttendanceRecord, DeviceLog
from sqlalchemy import and_
import datetime
from sqlalchemy.orm import aliased

def main():
    db = SessionLocal()
    try:
        print("--- USERS ---")
        users = db.query(User).all()
        for u in users:
            print(f"ID: {u.id} | Username: {u.username} | Email: {u.email} | Role: {u.role}")

        print("\n--- RECENT ATTENDANCE RECORDS ---")
        records = db.query(AttendanceRecord).order_by(AttendanceRecord.timestamp.desc()).limit(5).all()
        for r in records:
            print(f"ID: {r.id} | UserID: {r.user_id} | Time: {r.timestamp} | Status: {r.status} | Face: {r.face_verified} | Loc: {r.location_verified} | Dev: {r.device_verified} | Risk: {r.fraud_risk_score:.2f}% | Details: {r.details}")

        print("\n--- RECENT DEVICE LOGS ---")
        device_logs = db.query(DeviceLog).order_by(DeviceLog.timestamp.desc()).limit(10).all()
        for d in device_logs:
            print(f"ID: {d.id} | UserID: {d.user_id} | Fingerprint: {d.fingerprint} | Browser: {d.browser} | OS: {d.os} | IP: {d.ip_address} | Time: {d.timestamp}")

        print("\n--- SHARED DEVICE FINGERPRINTS IN LAST 12 HOURS ---")
        twelve_hours_ago = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=12)
        
        d1 = aliased(DeviceLog)
        d2 = aliased(DeviceLog)
        u1 = aliased(User)
        u2 = aliased(User)
        
        shared = db.query(
            d1.fingerprint,
            d1.user_id.label('user1_id'),
            u1.username.label('user1_name'),
            d2.user_id.label('user2_id'),
            u2.username.label('user2_name'),
            d1.timestamp
        ).join(
            d2, and_(d1.fingerprint == d2.fingerprint, d1.user_id != d2.user_id)
        ).join(
            u1, d1.user_id == u1.id
        ).join(
            u2, d2.user_id == u2.id
        ).filter(
            d1.timestamp >= twelve_hours_ago
        ).all()

        for s in shared:
            print(f"Fingerprint: {s.fingerprint} | User 1: {s.user1_name} (ID: {s.user1_id}) | User 2: {s.user2_name} (ID: {s.user2_id}) | Time: {s.timestamp}")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
