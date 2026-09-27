@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title AEGIS - Web Telemetry Backend

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"

set "PYTHONPATH=%CD%;%CD%\src;%CD%\backend"

echo ============================================================
echo   AEGIS  //  Web Telemetry and Inference API Backend
echo ============================================================
echo.
echo Starting FastAPI backend on http://127.0.0.1:8000 ...
echo API Docs available at http://127.0.0.1:8000/docs
echo.

"%PY_CMD%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo [ERROR] Backend exited unexpectedly.
    pause
    exit /b 1
)
