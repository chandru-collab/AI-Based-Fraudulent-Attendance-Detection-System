import subprocess
import os
import sys
import time
import threading

def main():
    print("Starting backend...")
    python_exe = os.path.join(".venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable

    # Set up environment variables including PYTHONPATH
    env = dict(os.environ)
    env["PYTHONPATH"] = os.getcwd()

    # Start backend
    backend_proc = subprocess.Popen(
        [python_exe, "-u", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print("Starting frontend...")
    # Start frontend
    frontend_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd="frontend",
        shell=True,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    print("Services started!")
    print("- Backend & API Docs: http://localhost:8000/docs")
    print("- Frontend Portal:   http://localhost:5173")

    def log_output(proc, prefix):
        try:
            for line in proc.stdout:
                print(f"[{prefix}] {line.strip()}")
        except Exception as e:
            print(f"[{prefix}] Error reading stdout: {e}")

    t1 = threading.Thread(target=log_output, args=(backend_proc, "Backend"), daemon=True)
    t2 = threading.Thread(target=log_output, args=(frontend_proc, "Frontend"), daemon=True)
    t1.start()
    t2.start()

    try:
        while True:
            time.sleep(1)
            # If backend died, print error and exit
            if backend_proc.poll() is not None:
                print(f"Backend process terminated with exit code {backend_proc.returncode}.")
                break
            # If frontend died, print error and exit
            if frontend_proc.poll() is not None:
                print(f"Frontend process terminated with exit code {frontend_proc.returncode}.")
                break
    except KeyboardInterrupt:
        print("Stopping services...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()

if __name__ == "__main__":
    main()
