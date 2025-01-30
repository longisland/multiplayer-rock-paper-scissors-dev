#!/bin/bash

# Exit on error
set -e

echo "Installing test requirements..."
pip install -r tests/requirements.txt

echo "Running unit tests..."
pytest tests/test_game.py -v --cov=app --cov-report=term-missing

echo "Running integration tests..."
python -m unittest tests/test_game.py -v