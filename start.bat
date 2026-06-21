@echo off
echo ========================================================
echo   Starting BEL Secure Checksheet Processing Portal
echo ========================================================
echo.

:: Start FastAPI Backend Server
echo [1/2] Launching backend server on port 8000...
start "BEL Backend Server" cmd /k "cd backend && venv\Scripts\activate.bat && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

:: Start React (Vite) Frontend Server
echo [2/2] Launching frontend development server on port 5173...
start "BEL Frontend Server" cmd /k "cd frontend && npm run dev"

echo.
echo ========================================================
echo Both servers have been launched in separate terminal windows.
echo Frontend URL: http://127.0.0.1:5173
echo Backend API : http://127.0.0.1:8000
echo ========================================================
pause
