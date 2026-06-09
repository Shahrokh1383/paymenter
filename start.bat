@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo Starting Payment Gateway Simulator...
start http://127.0.0.1:5000
python app.py
pause