@echo off
TITLE GTA 6 AI Clip Factory Launcher
COLOR 0B

echo ======================================================================
echo           GTA 6 AI CLIP FACTORY - LOCAL DESKTOP LAUNCHER
echo ======================================================================
echo.

:: 1. Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not found in your system PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 2. Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not found in your system PATH.
    echo Please install Node.js 18+ from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Python and Node.js detected.
echo.

:: 3. Prepare storage directories
if not exist "backend\data\temp" mkdir "backend\data\temp"
if not exist "backend\data\storage\recordings" mkdir "backend\data\storage\recordings"
if not exist "backend\data\storage\clips" mkdir "backend\data\storage\clips"
if not exist "backend\data\storage\thumbnails" mkdir "backend\data\storage\thumbnails"
if not exist "backend\data\models" mkdir "backend\data\models"

:: 4. Frontend node_modules check
if not exist "frontend\node_modules" (
    echo [INFO] Installing frontend dependencies (first-time setup)...
    cd frontend
    call npm install
    cd ..
)

:: 5. Launch FastAPI Backend
echo [INFO] Starting FastAPI Backend on http://localhost:8000...
start "GTA 6 Clip Factory - Backend API" cmd /k "cd backend && set PYTHONPATH=. && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"

:: 6. Launch Next.js Frontend
echo [INFO] Starting Next.js Gaming UI on http://localhost:3000...
start "GTA 6 Clip Factory - Web Dashboard" cmd /k "cd frontend && npm run dev"

:: 7. Wait and Open Browser
echo.
echo Waiting 5 seconds for servers to initialize...
timeout /t 5 /nobreak >nul

echo [INFO] Opening GTA 6 AI Clip Factory Studio in your default browser...
start http://localhost:3000

echo.
echo ======================================================================
echo   GTA 6 AI CLIP FACTORY IS RUNNING!
echo   - Web Dashboard: http://localhost:3000
echo   - Interactive API Docs: http://localhost:8000/docs
echo   - Zero Cloud Publishing: Strictly local MP4 storage
echo.
echo   To shut down, simply close the Backend and Frontend console windows.
echo ======================================================================
echo.
pause
