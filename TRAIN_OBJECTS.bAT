@echo off
REM ===========================================================================
REM  AEGIS - Tier 2 object detector: capture, label, train, export.
REM  Needs PyTorch + Ultralytics. GROUND SIDE ONLY - the runtime does not.
REM  Full walkthrough: docs\OBJECT_DETECTION.md
REM ===========================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo .venv not found. Run INSTALL.bat first.
    pause
    exit /b 1
)

set PYTHONPATH=%~dp0src

.venv\Scripts\python.exe -c "import ultralytics" 2>nul
if errorlevel 1 (
    echo.
    echo Ultralytics is not installed. Installing training extras now...
    echo This pulls in PyTorch and is a ~2.5 GB download.
    echo.
    .venv\Scripts\python.exe -m pip install ultralytics
    if errorlevel 1 (
        echo Install failed. Check your connection and try again.
        pause
        exit /b 1
    )
)

if "%~1"=="" (
    echo.
    echo  AEGIS object detector - run these in order:
    echo.
    echo    PowerShell: .\TRAIN_OBJECTS.bat grab --source 1 --count 300 --preview
    echo    PowerShell: .\TRAIN_OBJECTS.bat autolabel
    echo        ^(then REVIEW the labels - see docs\OBJECT_DETECTION.md^)
    echo    PowerShell: .\TRAIN_OBJECTS.bat split
    echo    PowerShell: .\TRAIN_OBJECTS.bat train --epochs 80 --device auto
    echo    PowerShell: .\TRAIN_OBJECTS.bat export
    echo    PowerShell: .\TRAIN_OBJECTS.bat check
    echo.
    pause
    exit /b 0
)

.venv\Scripts\python.exe -m aegis.tools.train_objects %*
pause
