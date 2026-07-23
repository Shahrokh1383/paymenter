@echo off
setlocal enabledelayedexpansion

REM Force working directory to the folder containing this script
cd /d "%~dp0"

REM [1] Locate the venv Python executable (create venv if missing – just in case)
set "VENV_PYTHON="
if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"
if exist "venv\bin\python.exe"      set "VENV_PYTHON=venv\bin\python.exe"

if "%VENV_PYTHON%"=="" (
    echo [INFO] Virtual environment not found. Creating it now...
    python -m venv venv
    if errorlevel 1 (
        echo [FATAL] Failed to create virtual environment.
        pause
        exit /b 1
    )
    if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"
    if exist "venv\bin\python.exe"      set "VENV_PYTHON=venv\bin\python.exe"
)

if "%VENV_PYTHON%"=="" (
    echo [FATAL] Could not locate python.exe inside the virtual environment.
    pause
    exit /b 1
)

REM [2] Set Flask app environment variable
set FLASK_APP=src/app/flask_app.py:create_app

REM [3] Run the background worker using the venv's Python
echo Starting Paymenter Webhook Worker...
echo Do not close this window while the worker is running.
"%VENV_PYTHON%" -m flask webhook-worker

pause