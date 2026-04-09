@echo off
cd /d "%~dp0"

echo Starting Local KB UI...
echo.

start "Local KB Backend" cmd /k "py -m uvicorn frontend.api:app --reload --port 8000"

timeout /t 3 /nobreak >nul

cd frontend
start "Local KB Frontend" cmd /k "npm run dev"
cd ..

timeout /t 5 /nobreak >nul

start http://localhost:3000

echo Local KB is starting up...
echo Open http://localhost:3000 in your browser if it doesn't open automatically.
pause
