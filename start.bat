@echo off
title Boreal
echo.
echo  ==========================================
echo   Boreal - Personal Finance Dashboard
echo  ==========================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo.
    echo  Download Python from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

:: Install dependencies if needed
if not exist ".installed" (
    echo  Installing dependencies (first time only)...
    pip install -r requirements.txt >nul 2>&1
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
    echo. > .installed
    echo  Done!
    echo.
)

echo  Starting Boreal...
echo  Open your browser to: http://localhost:5000
echo  Press Ctrl+C to stop.
echo.
start "" http://localhost:5000
python app.py
pause
