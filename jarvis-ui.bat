@echo off
rem Double-click to open the J.A.R.V.I.S. web UI in your browser.
cd /d "%~dp0"
python -m jarvis --web %*
if errorlevel 1 pause
