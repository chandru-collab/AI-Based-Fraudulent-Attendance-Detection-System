import sqlite3
import os

def create_indexes(db_path):
    if not os.path.exists(db_path):
        print(f"Database {db_path} does not exist. Skipping.")
        return
    print(f"Applying indexes to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List of CREATE INDEX statements
    statements = [
        # AttendanceRecord indexes
        "CREATE INDEX IF NOT EXISTS idx_attendance_records_user_id ON attendance_records (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_attendance_records_timestamp ON attendance_records (timestamp);",
        
        # FaceEmbedding indexes
        "CREATE INDEX IF NOT EXISTS idx_face_embeddings_user_id ON face_embeddings (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_face_embeddings_registered_at ON face_embeddings (registered_at);",
        
        # FraudLog indexes
        "CREATE INDEX IF NOT EXISTS idx_fraud_logs_user_id ON fraud_logs (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_fraud_logs_attendance_id ON fraud_logs (attendance_id);",
        "CREATE INDEX IF NOT EXISTS idx_fraud_logs_timestamp ON fraud_logs (timestamp);",
        
        # DeviceLog indexes
        "CREATE INDEX IF NOT EXISTS idx_device_logs_user_id ON device_logs (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_device_logs_fingerprint ON device_logs (fingerprint);",
        "CREATE INDEX IF NOT EXISTS idx_device_logs_timestamp ON device_logs (timestamp);",
        
        # LocationLog indexes
        "CREATE INDEX IF NOT EXISTS idx_location_logs_user_id ON location_logs (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_location_logs_timestamp ON location_logs (timestamp);",
        
        # Notification indexes
        "CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications (timestamp);",
        
        # RiskScore indexes
        "CREATE INDEX IF NOT EXISTS idx_risk_scores_user_id ON risk_scores (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_risk_scores_timestamp ON risk_scores (timestamp);"
    ]
    
    for stmt in statements:
        cursor.execute(stmt)
        
    conn.commit()
    conn.close()
    print(f"Successfully applied all indexes to {db_path}.")

if __name__ == "__main__":
    create_indexes("attendance.db")
    create_indexes("test_attendance.db")
