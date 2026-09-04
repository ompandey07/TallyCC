@echo off
title TallyCC Server Runner
echo ========================================================
echo        Starting TallyCC FastAPI Server
echo ========================================================
echo.

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [NOTE] Running with global Python environment...
)

echo.
echo Server is starting on 0.0.0.0 (Port 8000)...
echo.
echo Access URLs:
echo   - Local PC:   http://localhost:8000
echo   - Network PC: http://^<Your-PC-IP^>:8000
echo.
echo ========================================================
echo.

python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

pause
