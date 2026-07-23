#!/bin/bash
set -e

# Force working directory to the folder containing this script
cd "$(dirname "$0")"

# [1] Detect or create virtual environment
VENV_PYTHON=""
if [ -f "venv/bin/python" ]; then
    VENV_PYTHON="venv/bin/python"
elif [ -f "venv/Scripts/python.exe" ]; then
    # fallback for Windows-style venv (rare in bash, but safe)
    VENV_PYTHON="venv/Scripts/python.exe"
fi

if [ -z "$VENV_PYTHON" ]; then
    echo "[INFO] Virtual environment not found. Creating it now..."
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "[FATAL] Failed to create virtual environment."
        exit 1
    fi
    echo "[INFO] Virtual environment created successfully."

    # Re‑detect after creation
    if [ -f "venv/bin/python" ]; then
        VENV_PYTHON="venv/bin/python"
    elif [ -f "venv/Scripts/python.exe" ]; then
        VENV_PYTHON="venv/Scripts/python.exe"
    else
        echo "[FATAL] Could not locate python inside venv."
        exit 1
    fi
fi

echo "[INFO] Using virtual environment Python: $VENV_PYTHON"

# [2] Install dependencies inside the venv
echo "Installing dependencies..."
"$VENV_PYTHON" -m pip install -r requirements.txt

# [3] Launch the application
echo "Starting Paymenter"
echo "The browser will open automatically once the server is ready."
"$VENV_PYTHON" -m src.app.main