@echo off
rem Double-click to start J.A.R.V.I.S. in hands-free voice mode
cd /d "%~dp0"
python -m jarvis --handsfree %*
if errorlevel 1 pause
