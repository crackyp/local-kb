@echo off
setlocal
cd /d "%~dp0"

:: Configurable ports - override by setting these before running.
:: Defaults chosen to avoid colliding with common dev services (8000/3000).
if not defined KB_API_PORT set KB_API_PORT=8765
if not defined KB_FRONTEND_PORT set KB_FRONTEND_PORT=3737

:: Remote access - bind the backend to all interfaces (0.0.0.0) so other
:: computers on the LAN can reach it. Set KB_LOCAL_ONLY=1 to restrict to localhost.
if not defined KB_LOCAL_ONLY set KB_LOCAL_ONLY=0

:: Detect the primary LAN IP so remote browsers get a reachable API base.
for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_lan_ip.ps1"`) do set KB_LAN_IP=%%i
if not defined KB_LAN_IP set KB_LAN_IP=127.0.0.1

if "%KB_LOCAL_ONLY%"=="1" (
    set KB_HOST=127.0.0.1
    set KB_API_BASE=http://127.0.0.1:%KB_API_PORT%
    echo Remote access disabled, KB_LOCAL_ONLY=1 - localhost only.
) else (
    set KB_HOST=0.0.0.0
    set KB_API_BASE=http://%KB_LAN_IP%:%KB_API_PORT%
    echo Remote access enabled - reachable on the LAN via %KB_LAN_IP%.
)

echo Running preflight checks...
py preflight.py
if errorlevel 1 (
    echo.
    echo Preflight failed. Fix the [FAIL] items above before launching.
    echo - For port conflicts, set KB_API_PORT / KB_FRONTEND_PORT.
    echo - For the chat backend, run python start-llm.py or start llama-swap.
    pause
    exit /b 1
)
echo.
echo Starting Local KB UI...
echo   Backend:  http://%KB_HOST%:%KB_API_PORT%
echo   Frontend: http://localhost:%KB_FRONTEND_PORT%
echo.
echo Expecting these to already be running:
echo   - local chat server   on 127.0.0.1:8080
echo   - Ollama     (embeds) on 127.0.0.1:11434
echo.

set NEXT_PUBLIC_API_BASE=%KB_API_BASE%

:: If a Local KB backend is already running (a previous launch that was left
:: behind), reuse it instead of starting a second one on the same port.
set API_ALREADY_UP=0
for /f "tokens=*" %%c in ('curl -s -m 3 -o nul -w "%%{http_code}" "http://127.0.0.1:%KB_API_PORT%/api/status" 2^>nul') do set API_ALREADY_UP=%%c
if "%API_ALREADY_UP%"=="200" (
    echo Backend already running on http://127.0.0.1:%KB_API_PORT% - reusing it.
) else (
    start "Local KB Backend" cmd /k "py -m uvicorn backend.app:app --reload --host %KB_HOST% --port %KB_API_PORT%"
)

cd frontend
start "Local KB Frontend" cmd /k "npm run dev -- --port %KB_FRONTEND_PORT%"
cd ..

:: Wait until the backend actually responds before opening the browser.
:: Without this, the page loads while the API is still starting (or dead)
:: and every fetch throws "Failed to fetch".
set API_URL=http://127.0.0.1:%KB_API_PORT%/api/status
set READY=0
for /l %%i in (1,1,30) do (
  curl -s -o nul -w "%%{http_code}" "%API_URL%" 2>nul | findstr /r "^[0-9][0-9][0-9]$" >nul
  if not errorlevel 1 (
    set READY=1
    goto :backend_ready
  )
  timeout /t 1 /nobreak >nul
)
:backend_ready
if "%READY%"=="1" (
  echo Backend is up on http://127.0.0.1:%KB_API_PORT% - opening UI.
  start http://localhost:%KB_FRONTEND_PORT%
) else (
  echo.
  echo [WARN] Backend did not become ready within 30s.
  echo        The "Local KB Backend" window may have crashed or port %KB_API_PORT% is in use.
  echo        Open http://localhost:%KB_FRONTEND_PORT% manually once it is running.
  echo        (You will see "Failed to fetch" errors until the backend is up.)
  start http://localhost:%KB_FRONTEND_PORT%
)

echo Local KB is running.
echo Open http://localhost:%KB_FRONTEND_PORT% in your browser if it didn't open automatically.
echo Close the Backend / Frontend windows to stop.
pause
