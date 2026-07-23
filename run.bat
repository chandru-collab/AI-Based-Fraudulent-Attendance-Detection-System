@echo off
start /b cmd /c ".venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"
start /b cmd /c "cd frontend && npm run dev"
echo Services started successfully!
echo - Backend ^& API Docs: http://localhost:8000/docs
echo - Frontend Portal:   http://localhost:5173
