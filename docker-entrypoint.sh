#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until PGPASSWORD=rps_password psql -h postgres -U rps_user -d rps_db -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# Initialize database
python -c "
from src.app import app, db
with app.app_context():
    db.create_all()
"

# Update database schema
python -m src.scripts.update_schema

# Initialize Telegram bot
python -c "from src.scripts.init_telegram_bot import init_telegram_bot; init_telegram_bot()"

# Start the Flask application
exec python -m flask run --host=0.0.0.0