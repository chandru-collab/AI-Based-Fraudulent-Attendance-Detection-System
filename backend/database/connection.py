# pyrefly: ignore [missing-import]
import urllib.parse
# pyrefly: ignore [missing-import]
from sqlalchemy import create_engine, text
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import declarative_base, sessionmaker
# pyrefly: ignore [missing-import]
from backend.app.config import DATABASE_URL

# Handle SQLite concurrency parameters
engine = None
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine = create_engine(DATABASE_URL, connect_args=connect_args)
else:
    db_name = None
    # Auto-create MySQL database if it doesn't exist
    if DATABASE_URL.startswith("mysql"):
        try:
            parsed = urllib.parse.urlparse(DATABASE_URL)
            db_name = parsed.path.lstrip('/')
            if db_name:
                server_url = f"{parsed.scheme}://{parsed.netloc}/"
                temp_engine = create_engine(server_url, connect_args={"connect_timeout": 2})
                with temp_engine.connect() as conn:
                    # Execute raw SQL to create the database if not exists
                    conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{db_name}`"))
                temp_engine.dispose()
        except Exception as e:
            import sys
            print(f"Warning: Attempted to auto-create MySQL database '{db_name}' but failed: {e}", file=sys.stderr)

    # Try creating MySQL engine and testing connection
    mysql_failed = False
    try:
        engine = create_engine(
            DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_recycle=3600,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 2}
        )
        # Verify the connection works
        with engine.connect() as conn:
            pass
    except Exception as e:
        import sys
        print(f"Error: Connection to MySQL failed ({e}). Falling back to local SQLite.", file=sys.stderr)
        mysql_failed = True

    if mysql_failed:
        connect_args = {"check_same_thread": False}
        engine = create_engine("sqlite:///./attendance.db", connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
