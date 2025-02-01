\c rps_game;

CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(16) UNIQUE NOT NULL,
    coins INTEGER DEFAULT 100,
    current_match_id VARCHAR(8),
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    total_coins_won INTEGER DEFAULT 0,
    total_coins_lost INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS matches (
    id VARCHAR(8) PRIMARY KEY,
    creator_id VARCHAR(16) REFERENCES players(session_id),
    joiner_id VARCHAR(16) REFERENCES players(session_id),
    stake INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'waiting',
    creator_move VARCHAR(10),
    joiner_move VARCHAR(10),
    creator_ready BOOLEAN DEFAULT TRUE,
    joiner_ready BOOLEAN DEFAULT FALSE,
    winner VARCHAR(16),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    finished_at TIMESTAMP
);