#!/bin/bash

# [1] Deterministically verify and activate the virtual environment
if [ ! -d "venv" ] || [ ! -f "venv/bin/activate" ]; then
    echo "[FATAL] Virtual environment not found at 'venv'."
    echo "Please initialize it first via: python3 -m venv venv"
    exit 1
fi

source venv/bin/activate

# [2] Install dependencies within the isolated context
echo "Installing dependencies..."
pip install -r requirements.txt

# [3] Launch the application
echo "Starting Paymenter"
echo "The browser will open automatically once the server is ready."
python -m src.app.main