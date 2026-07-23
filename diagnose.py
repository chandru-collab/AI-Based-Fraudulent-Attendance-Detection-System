import os
import sys
import socket
import importlib
import traceback

def check_port(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True # Port is free
        except socket.error:
            return False # Port is occupied

def main():
    print("=== DIAGNOSTICS ===")
    
    # 1. Check Python executable and path
    print(f"Python Executable: {sys.executable}")
    print(f"Current Working Directory: {os.getcwd()}")
    
    # 2. Check virtual env paths
    venv_python = os.path.join(".venv", "Scripts", "python.exe")
    print(f".venv Python Exists: {os.path.exists(venv_python)}")
    
    # 3. Check if ports are occupied
    port_8000_free = check_port(8000)
    port_5173_free = check_port(5173)
    print(f"Port 8000 (Backend) free: {port_8000_free}")
    print(f"Port 5173 (Frontend) free: {port_5173_free}")
    
    # 4. Attempt imports
    modules_to_test = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "firebase_admin",
        "cryptography",
        "jwt",
        "cv2",
        "sklearn",
        "backend.database.connection",
        "backend.app.firebase",
        "backend.app.main"
    ]
    
    print("\n--- Testing Module Imports ---")
    for mod in modules_to_test:
        try:
            importlib.import_module(mod)
            print(f"[OK] {mod}")
        except Exception as e:
            print(f"[FAIL] {mod}: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    main()
