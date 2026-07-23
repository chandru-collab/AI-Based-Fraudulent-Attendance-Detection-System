import firebase_admin
from firebase_admin import credentials, auth
import os
import json

def reset_users():
    # Initialize firebase-admin
    cred_path = os.getenv("FIREBASE_CREDENTIALS_JSON_PATH")
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    
    try:
        if cred_json:
            cred = credentials.Certificate(json.loads(cred_json))
            firebase_admin.initialize_app(cred)
        elif cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            firebase_admin.initialize_app()
        print("Firebase Admin SDK successfully initialized.")
    except Exception as e:
        print(f"Could not initialize Firebase Admin SDK: {e}")
        print("Please ensure your Google Application Default Credentials or FIREBASE_CREDENTIALS_JSON_PATH in .env are configured.")
        return

    print("Fetching users from Firebase Authentication...")
    try:
        # List all users
        page = auth.list_users()
        users_to_delete = []
        while page:
            for user in page.users:
                users_to_delete.append(user.uid)
            page = page.get_next_page()
            
        if not users_to_delete:
            print("No users found in Firebase Authentication. Nothing to delete!")
            return
            
        print(f"Found {len(users_to_delete)} users. Deleting...")
        
        # Batch delete users in chunks of 1000 (Firebase API limit)
        for i in range(0, len(users_to_delete), 1000):
            chunk = users_to_delete[i:i+1000]
            result = auth.delete_users(chunk)
            print(f"Deleted batch: {len(chunk)} users. Successes: {result.success_count}, Failures: {result.failure_count}")
            for err in result.errors:
                print(f"Error deleting user {err.index}: {err.reason}")
                
        print("\nSuccessfully reset Firebase Authentication database!")
    except Exception as e:
        print(f"Error during Firebase reset: {e}")

if __name__ == "__main__":
    # Load dotenv if exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    reset_users()
