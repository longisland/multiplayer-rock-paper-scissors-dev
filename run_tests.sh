#!/bin/bash

# Install Chrome and ChromeDriver for Selenium tests
apt-get update
apt-get install -y chromium-browser chromium-chromedriver

# Install dependencies
pip install -r requirements.txt

# Run unit tests with coverage
pytest tests/test_match_mechanics.py tests/test_game_service.py -v --cov=src --cov-report=term-missing

# Start the application server in the background
cd src
python app.py > server.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
sleep 5

# Run UI automation tests
cd ..
python tests/test_ui_automation.py

# Kill the server
kill $SERVER_PID