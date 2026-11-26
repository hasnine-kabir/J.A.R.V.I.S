@echo off
rem Double-click to start J.A.R.V.I.S.
cd /d "%~dp0"
python -m jarvis %*
if errorlevel 1 pause
