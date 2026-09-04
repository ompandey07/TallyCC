@echo off
title TallyCC Package Installer
echo ========================================================
echo        TallyCC Dependencies Installer
echo ========================================================
echo.

if not exist "venv" (
    echo [1/2] Creating virtual environment in .\venv...
    python -m venv venv
) else (
    echo [1/2] Found existing virtual environment in .\venv
)

echo.
echo [2/2] Installing required Python packages...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn requests

echo.
echo ========================================================
echo   SUCCESS! All required packages have been installed.
echo   You can now double-click 'RunServer.bat' to start!
echo ========================================================
pause
