@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"
title AEGIS - Mission Console

if not exist ".venv\Scripts\python.exe" (
    echo [AEGIS] First launch - running the installer...
    call INSTALL.bat
    if errorlevel 1 exit /b 1
)

set "PYTHONPATH=%CD%\src"
echo [AEGIS] Launching mission console...
".venv\Scripts\python.exe" -m aegis.gui.app %*
if errorlevel 1 goto :failed
exit /b 0

:failed
echo.
echo [AEGIS] The console exited with an error.
echo         Run DIAGNOSTICS.bat for a full environment report.
echo.
pause
exit /b 1
