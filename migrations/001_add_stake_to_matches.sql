-- Add stake column to matches table
ALTER TABLE matches ADD COLUMN IF NOT EXISTS stake INTEGER NOT NULL DEFAULT 10;

-- Update existing matches to have a default stake
UPDATE matches SET stake = 10 WHERE stake IS NULL;