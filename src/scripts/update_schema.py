from src.app import app, db
from sqlalchemy import text

def update_schema():
    with app.app_context():
        with db.engine.connect() as conn:
            # Start transaction
            trans = conn.begin()
            try:
                # Drop existing constraints and indexes
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_new_telegram_id_key;
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_new_telegram_id_key1;
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_new_username_key;
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_new_username_key1;
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_key;
                        ALTER TABLE users DROP CONSTRAINT IF EXISTS users_username_key;
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END $$;
                """))

                # Add or modify columns
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        -- Add telegram_id column if it doesn't exist
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='users' AND column_name='telegram_id') THEN
                            ALTER TABLE users ADD COLUMN telegram_id BIGINT;
                        ELSE
                            ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT USING telegram_id::bigint;
                        END IF;

                        -- Add telegram_username column if it doesn't exist
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='users' AND column_name='telegram_username') THEN
                            ALTER TABLE users ADD COLUMN telegram_username VARCHAR(80);
                        END IF;

                        -- Add telegram_first_name column if it doesn't exist
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='users' AND column_name='telegram_first_name') THEN
                            ALTER TABLE users ADD COLUMN telegram_first_name VARCHAR(80);
                        END IF;

                        -- Add telegram_last_name column if it doesn't exist
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='users' AND column_name='telegram_last_name') THEN
                            ALTER TABLE users ADD COLUMN telegram_last_name VARCHAR(80);
                        END IF;

                        -- Add telegram_auth_date column if it doesn't exist
                        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                     WHERE table_name='users' AND column_name='telegram_auth_date') THEN
                            ALTER TABLE users ADD COLUMN telegram_auth_date TIMESTAMP;
                        END IF;
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END $$;
                """))

                # Add new constraints and indexes
                conn.execute(text("""
                    DO $$ 
                    BEGIN
                        -- Add unique constraint for telegram_id
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_telegram_id_key') THEN
                            ALTER TABLE users ADD CONSTRAINT users_telegram_id_key UNIQUE (telegram_id);
                        END IF;

                        -- Add unique constraint for username
                        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_username_key') THEN
                            ALTER TABLE users ADD CONSTRAINT users_username_key UNIQUE (username);
                        END IF;

                        -- Add index for telegram_id
                        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_telegram_id') THEN
                            CREATE INDEX idx_users_telegram_id ON users(telegram_id);
                        END IF;

                        -- Add index for username
                        IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_users_username') THEN
                            CREATE INDEX idx_users_username ON users(username);
                        END IF;
                    EXCEPTION WHEN OTHERS THEN NULL;
                    END $$;
                """))

                # Commit transaction
                trans.commit()
                print("Schema updated successfully")
            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"Error updating schema: {e}")
                raise

if __name__ == '__main__':
    update_schema()