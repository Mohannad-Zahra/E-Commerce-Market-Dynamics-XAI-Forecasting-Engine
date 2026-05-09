@echo off
SETLOCAL EnableDelayedExpansion

echo ===================================================================
echo   E-Commerce Market Dynamics & XAI Forecasting Engine Runner
echo ===================================================================

echo.
echo [1/4] Skipping Backend Requirements Installation...
REM python -m pip install -r backend/requirements.txt
REM if %ERRORLEVEL% NEQ 0 (
REM     echo.
REM     echo [ERROR] Failed to install backend requirements. 
REM     echo Please make sure you have Python and Pip installed and added to your PATH.
REM     pause
REM     exit /b %ERRORLEVEL%
REM )

echo.
echo [2/4] Skipping Frontend Requirements Installation...
REM cd FrontEnd\app
REM call npm install --silent
REM if %ERRORLEVEL% NEQ 0 (
REM     echo [ERROR] Failed to install frontend requirements.
REM     pause
REM     exit /b %ERRORLEVEL%
REM )
REM cd ..\..

echo.
echo [3/4] Starting FastAPI Backend...
start "Backend - FastAPI" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo.
echo [4/4] Starting React Frontend...
start "Frontend - Vite" cmd /k "cd FrontEnd\app && npm run dev"

echo.
echo Waiting for services to initialize (5s)...
timeout /t 5 /nobreak > nul

echo.
echo [SUCCESS] Opening the website in your default browser...
start http://localhost:5173

echo.
echo ===================================================================
echo   SYSTEM RUNNING
echo   - Backend: http://localhost:8000
echo   - Frontend: http://localhost:5173
echo   Keep the separate command windows open to maintain the servers.
echo ===================================================================
echo.
pause
