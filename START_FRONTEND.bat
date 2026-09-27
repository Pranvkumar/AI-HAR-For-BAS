@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0frontend"
title AEGIS - Operations Console Frontend

echo ============================================================
echo   AEGIS  //  Web Operations Console Frontend
echo ============================================================
echo.

if not exist "node_modules\" (
    echo [SETUP] Installing frontend node dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed. Make sure Node.js is installed.
        pause
        exit /b 1
    )
)

echo Starting Vite dev server...
echo Frontend will be accessible at http://localhost:5173
echo.

call npm run dev
if errorlevel 1 (
    echo.
    echo [ERROR] Frontend exited unexpectedly.
    pause
    exit /b 1
)
