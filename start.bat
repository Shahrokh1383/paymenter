@echo off
setlocal enabledelayedexpansion

REM Force working directory to the folder containing this script
cd /d "%~dp0"

REM [1] Create virtual environment if missing (check for python.exe in either location)
set "VENV_PYTHON="
if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"
if exist "venv\bin\python.exe" set "VENV_PYTHON=venv\bin\python.exe"

if "%VENV_PYTHON%"=="" (
    echo [INFO] Virtual environment not found. Creating it now...
    python -m venv venv
    if errorlevel 1 (
        echo [FATAL] Failed to create virtual environment. Ensure Python is installed and in PATH.
        pause
        exit /b 1
    )
    echo [INFO] Virtual environment created successfully.

    REM After creation, detect the python executable again
    if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"
    if exist "venv\bin\python.exe" set "VENV_PYTHON=venv\bin\python.exe"
)

if "%VENV_PYTHON%"=="" (
    echo [FATAL] Could not locate python.exe inside the virtual environment.
    pause
    exit /b 1
)

echo [INFO] Using virtual environment Python: "%VENV_PYTHON%"

REM [2] Install dependencies inside the venv
echo Installing dependencies in virtual environment...
"%VENV_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [WARNING] Dependency installation encountered an issue. Check requirements.txt.
)

REM [3] Launch the application using the venv's Python
echo Starting Paymenter...
echo The browser will open automatically once the server is ready.
"%VENV_PYTHON%" -m src.app.main

pause