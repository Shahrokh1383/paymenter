@echo off

REM [1] Activate the virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [FATAL] Virtual environment not found at 'venv'.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM [2] Set the FLASK_APP environment variable
set FLASK_APP=src/app/flask_app.py:create_app

REM [3] Run the background worker
echo Starting Paymenter Webhook Worker...
echo Do not close this window while the worker is running.
flask webhook-worker

pause