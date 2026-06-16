-- ============================================================
-- Migration 001: Initial Schema - Bolão da Cabine do Glória
-- Execute this in the Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- 1. bolao_config: key-value store for app configuration
CREATE TABLE IF NOT EXISTS bolao_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. bolao_submissions: classic mode predictions
CREATE TABLE IF NOT EXISTS bolao_submissions (
    id TEXT PRIMARY KEY,
    participant TEXT NOT NULL,
    groups JSONB NOT NULL,
    best_thirds JSONB,
    knockout JSONB,
    champion TEXT,
    submission_id TEXT NOT NULL,
    submitted_at TEXT,
    status TEXT DEFAULT 'confirmado',
    meta JSONB,
    mode TEXT,
    schema_version TEXT,
    active BOOLEAN DEFAULT TRUE,
    archived_reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_submissions_participant ON bolao_submissions (participant);
CREATE INDEX IF NOT EXISTS idx_submissions_active ON bolao_submissions (active);

-- 3. bolao_official: official results
CREATE TABLE IF NOT EXISTS bolao_official (
    id TEXT PRIMARY KEY DEFAULT 'official',
    participant TEXT NOT NULL,
    groups JSONB NOT NULL,
    best_thirds JSONB,
    knockout JSONB,
    champion TEXT,
    submission_id TEXT,
    submitted_at TEXT,
    status TEXT DEFAULT 'aprovado',
    meta JSONB,
    mode TEXT,
    schema_version TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. bolao_live_predictions: match-by-match predictions
CREATE TABLE IF NOT EXISTS bolao_live_predictions (
    id TEXT PRIMARY KEY,
    participant_name TEXT NOT NULL,
    participant_key TEXT NOT NULL,
    match_id TEXT NOT NULL,
    predicted_home_goals INT NOT NULL,
    predicted_away_goals INT NOT NULL,
    submitted_at TEXT,
    updated_at TEXT,
    confirmation_code TEXT,
    locked_at TEXT,
    is_locked BOOLEAN DEFAULT FALSE,
    is_late BOOLEAN DEFAULT FALSE,
    points INT,
    scoring_breakdown JSONB DEFAULT '[]'::jsonb,
    schema_version TEXT DEFAULT 'live-v1',
    active BOOLEAN DEFAULT TRUE,
    archived_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_live_preds_participant ON bolao_live_predictions (participant_key);
CREATE INDEX IF NOT EXISTS idx_live_preds_match ON bolao_live_predictions (match_id);
CREATE INDEX IF NOT EXISTS idx_live_preds_active ON bolao_live_predictions (active);

-- 5. bolao_matches: match schedule and results
CREATE TABLE IF NOT EXISTS bolao_matches (
    match_id TEXT PRIMARY KEY,
    phase TEXT NOT NULL,
    "group" TEXT,
    round_label TEXT,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    starts_at_timezone TEXT DEFAULT 'America/Sao_Paulo',
    lock_at TEXT,
    status TEXT DEFAULT 'scheduled',
    official_home_goals INT,
    official_away_goals INT,
    winner TEXT,
    source TEXT DEFAULT 'manual',
    sort_order INT DEFAULT 0,
    bets_manual_closed BOOLEAN
);
CREATE INDEX IF NOT EXISTS idx_matches_status ON bolao_matches (status);
CREATE INDEX IF NOT EXISTS idx_matches_starts ON bolao_matches (starts_at);

-- 6. bolao_events: activity and audit log
CREATE TABLE IF NOT EXISTS bolao_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    metadata JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON bolao_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_visibility ON bolao_events (visibility);
