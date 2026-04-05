@echo off
title Local KB UI
cd /d "%~dp0"

:: Find Python
where py >nul 2>&1 && (
    py -m pip install -q -r requirements.txt
    start "" py -m streamlit run app.py
    goto :eof
)

where python >nul 2>&1 && (
    python -m pip install -q -r requirements.txt
    start "" python -m streamlit run app.py
    goto :eof
)

echo Python not found. Install Python 3.10+ and try again.
pause
