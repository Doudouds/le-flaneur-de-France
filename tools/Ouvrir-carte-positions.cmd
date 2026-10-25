@echo off
cd /d "%~dp0.."
python -B "%~dp0review_coordinates.py" --open
if errorlevel 1 pause
