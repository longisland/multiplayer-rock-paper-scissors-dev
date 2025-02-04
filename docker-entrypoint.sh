#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
until PGPASSWORD=rps_password psql -h postgres -U rps_user -d rps_db -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

# Initialize migrations if needed
if [ ! -d "migrations" ]; then
  flask db init
fi

# Run database migrations
flask db migrate -m "Add Telegram fields"
flask db upgrade

# Initialize Telegram bot
python -c "from src.scripts.init_telegram_bot import init_telegram_bot; init_telegram_bot()"

# Start the Flask application
exec python -m flask run --host=0.0.0.0