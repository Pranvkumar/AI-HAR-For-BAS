@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title AEGIS - Web Console Installer

echo ============================================================
echo   AEGIS  //  Web Console Prerequisites Installer
echo ============================================================
echo.

set "PY_CMD=python"
if exist ".venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"

echo [1/2] Installing backend Python dependencies...
"%PY_CMD%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Python package installation returned an error.
)

echo.
echo [2/2] Installing frontend Node dependencies...
cd /d "%~dp0frontend"
where npm >nul 2>nul
if errorlevel 1 (
    echo [ERROR] npm was not found. Please install Node.js from https://nodejs.org/
    cd /d "%~dp0"
    pause
    exit /b 1
)
call npm install
cd /d "%~dp0"

echo.
echo ============================================================
echo   Web Console installation complete!
echo   Run START_WEB_DASHBOARD.bat to launch the console.
echo ============================================================
pause
