@echo off
setlocal
set "ENGINE=%~dp0.agents\skills\impeccable\scripts\impeccable.cmd"

if "%~1"=="" (
    call "%ENGINE%" help
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="audit" (
    echo [IMPECCABLE] Auditing frontend/src for design anti-patterns...
    call "%ENGINE%" detect frontend/src %2 %3 %4 %5
    if %ERRORLEVEL% equ 0 (
        echo [OK] 0 anti-patterns found. Frontend design is clean.
    )
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="detect" (
    call "%ENGINE%" detect %2 %3 %4 %5
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="doctor" (
    call "%ENGINE%" doctor %2 %3 %4 %5
    exit /b %ERRORLEVEL%
)

if /I "%~1"=="context" (
    call "%ENGINE%" context %2 %3 %4 %5
    exit /b %ERRORLEVEL%
)

call "%ENGINE%" %*
exit /b %ERRORLEVEL%
