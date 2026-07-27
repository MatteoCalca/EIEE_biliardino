-- Foosball ELO tracker — Postgres schema (for Supabase).
--
-- You do NOT strictly need to run this by hand: the app calls
-- metadata.create_all() on first connection and will create these tables for
-- you. It's provided so you can review / create the schema in the Supabase SQL
-- editor if you prefer. Ratings are intentionally NOT stored — they are
-- recomputed from this match log on every load.

CREATE TABLE IF NOT EXISTS players (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(80) NOT NULL UNIQUE,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS matches (
    id                   SERIAL PRIMARY KEY,
    played_at            TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc'),
    team_a_attacker_id   INTEGER NOT NULL REFERENCES players(id),
    team_a_defender_id   INTEGER NOT NULL REFERENCES players(id),
    team_b_attacker_id   INTEGER NOT NULL REFERENCES players(id),
    team_b_defender_id   INTEGER NOT NULL REFERENCES players(id),
    score_a              INTEGER NOT NULL,
    score_b              INTEGER NOT NULL,
    overtime             BOOLEAN NOT NULL DEFAULT FALSE,
    voided               BOOLEAN NOT NULL DEFAULT FALSE,
    created_at           TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'utc')
);

-- Replay reads matches in this order.
CREATE INDEX IF NOT EXISTS idx_matches_played_at ON matches (played_at, id);
