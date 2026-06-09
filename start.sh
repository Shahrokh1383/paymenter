#!/bin/bash
echo "Installing dependencies..."
pip install -r requirements.txt
echo "Starting Payment Gateway Simulator..."
echo "The browser will open automatically once the server is ready."
python app.py