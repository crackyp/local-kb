@echo off
setlocal
cd /d "%~dp0"

:: Configurable ports — override by setting these before running.
:: Defaults chosen to avoid colliding with common dev services (8000/3000).
if not defined KB_API_PORT set KB_API_PORT=8765
if not defined KB_FRONTEND_PORT set KB_FRONTEND_PORT=3737

echo Running preflight checks...
py preflight.py
if errorlevel 1 (
    echo.
    echo Preflight failed. Fix the [FAIL] items above before launching.
    echo - For port conflicts, set KB_API_PORT / KB_FRONTEND_PORT.
    echo - For llama-server, install llama.cpp at H:\llama.cpp or set LLAMACPP_DIR,
    echo   or edit [llamacpp] server_exe in kb.toml.
    pause
    exit /b 1
)
echo.
echo Starting Local KB UI (llama.cpp backend)...
echo   Backend:  http://127.0.0.1:%KB_API_PORT%
echo   Frontend: http://localhost:%KB_FRONTEND_PORT%
echo.
echo Expecting llama-server already running (auto_spawn disabled):
echo   - chat    on 127.0.0.1:8080
echo   - embeds  on 127.0.0.1:8081
echo.

set NEXT_PUBLIC_API_BASE=http://127.0.0.1:%KB_API_PORT%

start "Local KB Backend" cmd /k "py -m uvicorn backend.app:app --reload --port %KB_API_PORT%"

timeout /t 3 /nobreak >nul

cd frontend
start "Local KB Frontend" cmd /k "npm run dev -- --port %KB_FRONTEND_PORT%"
cd ..

timeout /t 5 /nobreak >nul

start http://localhost:%KB_FRONTEND_PORT%

echo Local KB is running.
echo Open http://localhost:%KB_FRONTEND_PORT% in your browser if it didn't open automatically.
echo Close the Backend / Frontend windows to stop.
pause
