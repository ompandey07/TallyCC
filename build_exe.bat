@echo off
title TallyCC Standalone Desktop Software Builder (.exe)
echo ========================================================
echo        TallyCC Desktop Software Compiler (.exe)
echo ========================================================
echo.

if exist "build" (
    echo [0/4] Purging old build directory...
    rd /s /q build
)
if exist "dist" (
    echo [0/4] Purging old dist directory...
    rd /s /q dist
)

echo.
if exist "venv\Scripts\activate.bat" (
    echo [1/4] Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo [1/4] Creating virtual environment in .\venv...
    python -m venv venv
    call venv\Scripts\activate.bat
)

echo.
echo [2/4] Installing required build dependencies...
python -m pip install --upgrade pip
python -m pip install fastapi uvicorn requests pyinstaller customtkinter darkdetect pystray pillow

echo.
echo [3/4] Building standalone single TallyCC.exe executable...
python build_exe.py

echo.
if exist "dist\TallyCC.exe" (
    echo ========================================================
    echo   SUCCESS! TallyCC.exe compiled cleanly!
    echo   File location: dist\TallyCC.exe
    echo.
    echo   Double-click dist\TallyCC.exe anytime to launch!
    echo   - Closes to System Tray to keep API active in background
    echo   - Zero command prompt window
    echo ========================================================
) else (
    echo [ERROR] Build failed. Please check output messages above.
)
echo.
pause
