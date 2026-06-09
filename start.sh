#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Starting Payment Gateway Simulator..."
# Try to open browser, ignore errors if display not available
xdg-open http://127.0.0.1:5000 2>/dev/null || echo "Please open your browser and navigate to http://127.0.0.1:5000"
python app.py