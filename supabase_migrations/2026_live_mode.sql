-- Migration for Copa 2026 Live Mode (Jogo a Jogo)

-- 1. Create table bolao_matches
CREATE TABLE IF NOT EXISTS bolao_matches (
    match_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL,
    "group" TEXT NOT NULL,
    round_label TEXT NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    starts_at_timezone TEXT DEFAULT 'America/Sao_Paulo',
    lock_at TEXT,
    status TEXT DEFAULT 'scheduled',
    official_home_goals INTEGER,
    official_away_goals INTEGER,
    winner TEXT,
    source TEXT DEFAULT 'manual',
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index on starts_at and status
CREATE INDEX IF NOT EXISTS idx_bolao_matches_starts_at ON bolao_matches(starts_at);
CREATE INDEX IF NOT EXISTS idx_bolao_matches_status ON bolao_matches(status);

-- 2. Create table bolao_live_predictions
CREATE TABLE IF NOT EXISTS bolao_live_predictions (
    id TEXT PRIMARY KEY, -- participant_key + '_' + match_id
    participant_name TEXT NOT NULL,
    participant_key TEXT NOT NULL,
    match_id TEXT NOT NULL,
    predicted_home_goals INTEGER NOT NULL,
    predicted_away_goals INTEGER NOT NULL,
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmation_code TEXT,
    locked_at TEXT,
    is_locked BOOLEAN DEFAULT FALSE,
    is_late BOOLEAN DEFAULT FALSE,
    points INTEGER,
    scoring_breakdown JSONB,
    schema_version TEXT DEFAULT 'live-v1',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_participant_match UNIQUE (participant_key, match_id)
);

-- Indexes for search/aggregation performance
CREATE INDEX IF NOT EXISTS idx_live_preds_participant_key ON bolao_live_predictions(participant_key);
CREATE INDEX IF NOT EXISTS idx_live_preds_match_id ON bolao_live_predictions(match_id);
CREATE INDEX IF NOT EXISTS idx_live_preds_submitted_at ON bolao_live_predictions(submitted_at);

-- 3. Create table bolao_events
CREATE TABLE IF NOT EXISTS bolao_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bolao_events_timestamp ON bolao_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_bolao_events_visibility ON bolao_events(visibility);
