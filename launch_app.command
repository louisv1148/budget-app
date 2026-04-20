#!/bin/bash

# Budget App Launcher
# Double-click this file to start the Streamlit budget application

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the app directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists, if not create one
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Launch the Streamlit app
echo "Starting Budget App..."
echo "The app will open in your default web browser"
echo "To stop the app, close this terminal window or press Ctrl+C"

# Run the main app from the src directory
streamlit run src/main_app.py

# Keep terminal open if there's an error
read -p "Press Enter to close..."