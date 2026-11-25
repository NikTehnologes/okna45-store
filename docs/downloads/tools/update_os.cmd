@echo off
cd /d "%~dp0\.."
python -B tools\update_os.py
if errorlevel 1 pause
