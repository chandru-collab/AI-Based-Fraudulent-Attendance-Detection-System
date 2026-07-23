from backend.database.connection import SessionLocal
from backend.database.models import User

def promote_user():
    db = SessionLocal()
    try:
        target = input("Enter the username or email of the user to promote to Admin: ").strip()
        if not target:
            print("No user specified. Exiting.")
            return
            
        # Query user by username or email
        user = db.query(User).filter((User.username == target) | (User.email == target)).first()
        
        if not user:
            print(f"User '{target}' was not found in the database. Please register/log in once first.")
            return
            
        print(f"Found user: {user.username} | Current Role: {user.role}")
        
        if user.role == 'Admin':
            print(f"User '{user.username}' is already an Admin!")
        else:
            user.role = 'Admin'
            db.commit()
            print(f"Successfully promoted user '{user.username}' to Admin role in the database!")
    except Exception as e:
        print(f"Error promoting user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    promote_user()
