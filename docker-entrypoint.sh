#!/bin/bash
set -e

# Run database migrations
flask db upgrade

# Initialize Telegram bot
python -c "from src.scripts.init_telegram_bot import init_telegram_bot; init_telegram_bot()"

# Start the Flask application
exec python -m flask run --host=0.0.0.0