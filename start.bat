@echo off

REM [1] Deterministically verify and activate the virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [FATAL] Virtual environment not found at 'venv'.
    echo Please initialize it first via: python -m venv venv
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

REM [2] Install dependencies within the isolated context
echo Installing dependencies...
pip install -r requirements.txt

REM [3] Launch the application
echo Starting Paymenter
echo The browser will open automatically once the server is ready.
python -m src.app.main

pause