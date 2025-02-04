BEGIN;

-- Create a temporary table with the new schema
CREATE TABLE users_new (
    id character varying(36) NOT NULL DEFAULT nextval('user_id_seq'::regclass),
    username character varying(80) NOT NULL,
    telegram_id bigint,
    telegram_username character varying(80),
    telegram_first_name character varying(80),
    telegram_last_name character varying(80),
    telegram_auth_date timestamp without time zone,
    coins integer DEFAULT 100,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    total_games integer DEFAULT 0,
    wins integer DEFAULT 0,
    losses integer DEFAULT 0,
    draws integer DEFAULT 0,
    total_coins_won integer DEFAULT 0,
    total_coins_lost integer DEFAULT 0,
    CONSTRAINT users_new_pkey PRIMARY KEY (id),
    CONSTRAINT users_telegram_id_key UNIQUE (telegram_id),
    CONSTRAINT users_username_key UNIQUE (username)
);

-- Copy data from the old table
INSERT INTO users_new (
    id, username, telegram_id, telegram_username, telegram_first_name, telegram_last_name,
    coins, created_at, last_seen, total_games, wins, losses, draws, total_coins_won, total_coins_lost
)
SELECT 
    id, username, telegram_id::bigint, telegram_username, telegram_first_name, telegram_last_name,
    coins, created_at, last_seen, total_games, wins, losses, draws, total_coins_won, total_coins_lost
FROM users;

-- Drop the old table and rename the new one
DROP TABLE users CASCADE;
ALTER TABLE users_new RENAME TO users;

-- Recreate foreign keys
ALTER TABLE game_history
    ADD CONSTRAINT game_history_player1_id_fkey FOREIGN KEY (player1_id) REFERENCES users(id),
    ADD CONSTRAINT game_history_player2_id_fkey FOREIGN KEY (player2_id) REFERENCES users(id),
    ADD CONSTRAINT game_history_winner_id_fkey FOREIGN KEY (winner_id) REFERENCES users(id);

-- Create indexes
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_username ON users(username);

COMMIT;