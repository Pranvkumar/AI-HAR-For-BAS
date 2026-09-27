@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title AEGIS - Web Mission Operations Console

echo ============================================================
echo   AEGIS  //  Web Mission Operations Console and Backend
echo   SIH 2026 Problem Statement 26174
echo ============================================================
echo.

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"

set "PYTHONPATH=%CD%;%CD%\src;%CD%\backend"

REM Start Backend in separate window
echo [1/2] Starting Telemetry Backend on http://127.0.0.1:8000 ...
start "AEGIS-Backend" "%PY_CMD%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

REM Ensure frontend dependencies
if not exist "frontend\node_modules\" (
    echo [SETUP] Installing frontend node dependencies...
    cd /d "%~dp0frontend"
    call npm install
    cd /d "%~dp0"
)

REM Wait 2 seconds for backend to initialize
timeout /t 2 /nobreak >nul

REM Start Frontend in separate window
echo [2/2] Starting Operations Dashboard on http://localhost:5173 ...
start "AEGIS-Dashboard" "%~dp0START_FRONTEND.bat"

REM Open default browser
timeout /t 3 /nobreak >nul
start http://localhost:5173

echo.
echo ============================================================
echo   AEGIS Web Console launched successfully!
echo   - Frontend: http://localhost:5173
echo   - Backend:  http://127.0.0.1:8000
echo   - API Docs: http://127.0.0.1:8000/docs
echo ============================================================
echo.
echo Press any key to stop all services...
pause >nul

taskkill /FI "WINDOWTITLE eq AEGIS-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AEGIS-Dashboard*" /T /F >nul 2>&1
echo Services stopped.
