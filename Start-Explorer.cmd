@echo off
setlocal
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0tools\explorer\launcher.py" %*
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 "%~dp0tools\explorer\launcher.py" %*
    ) else (
        python "%~dp0tools\explorer\launcher.py" %*
    )
)
if errorlevel 1 pause
