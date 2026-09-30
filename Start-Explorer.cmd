@echo off
python "%~dp0tools\explorer\server.py" --open-browser
if errorlevel 1 pause
