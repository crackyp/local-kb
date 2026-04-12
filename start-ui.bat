@echo off
cd /d "%~dp0"

:: Configurable ports — override by setting these before running.
:: Defaults chosen to avoid colliding with common dev services (8000/3000).
if not defined KB_API_PORT set KB_API_PORT=8765
if not defined KB_FRONTEND_PORT set KB_FRONTEND_PORT=3737

echo Running preflight checks...
py preflight.py
if errorlevel 1 (
    echo.
    echo Preflight failed. Fix the [FAIL] items above before launching — for
    echo port conflicts, set KB_API_PORT / KB_FRONTEND_PORT to a free port.
    pause
    exit /b 1
)
echo.
echo Starting Local KB UI...
echo   Backend:  http://127.0.0.1:%KB_API_PORT%
echo   Frontend: http://localhost:%KB_FRONTEND_PORT%
echo.

set NEXT_PUBLIC_API_BASE=http://127.0.0.1:%KB_API_PORT%

start "Local KB Backend" cmd /k "py -m uvicorn frontend.api:app --reload --port %KB_API_PORT%"

timeout /t 3 /nobreak >nul

cd frontend
start "Local KB Frontend" cmd /k "npm run dev -- --port %KB_FRONTEND_PORT%"
cd ..

timeout /t 5 /nobreak >nul

start http://localhost:%KB_FRONTEND_PORT%

echo Local KB is running.
echo Open http://localhost:%KB_FRONTEND_PORT% in your browser if it didn't open automatically.
pause
