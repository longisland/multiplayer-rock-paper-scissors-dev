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
from sqlalchemy import text

with app.app_context():
    # Add Telegram columns if they don't exist
    with db.engine.connect() as conn:
        # Check if telegram_id column exists
        result = conn.execute(text(\"\"\"
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='telegram_id'
        \"\"\"))
        if not result.fetchone():
            conn.execute(text(\"\"\"
                ALTER TABLE users 
                ADD COLUMN telegram_id BIGINT UNIQUE,
                ADD COLUMN telegram_username VARCHAR(80),
                ADD COLUMN telegram_first_name VARCHAR(80),
                ADD COLUMN telegram_last_name VARCHAR(80),
                ADD COLUMN telegram_auth_date TIMESTAMP
            \"\"\"))
            conn.commit()
    
    # Create any new tables
    db.create_all()
"

# Initialize Telegram bot
python -c "from src.scripts.init_telegram_bot import init_telegram_bot; init_telegram_bot()"

# Start the Flask application
exec python -m flask run --host=0.0.0.0