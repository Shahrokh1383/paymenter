@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Starting Paymenter (Hexagonal Architecture)...
echo The browser will open automatically once the server is ready.
python -m src.app.main
pause