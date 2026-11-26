@echo off
rem One-time install of J.A.R.V.I.S. dependencies
cd /d "%~dp0"
python -m pip install -r requirements-v2.txt
if not exist .env copy .env.example .env
echo.
echo Done. Start Jarvis with jarvis.bat
pause
