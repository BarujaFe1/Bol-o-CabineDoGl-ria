"""
Script to run SQL migration directly on the Supabase PostgreSQL database.
Uses psycopg2 with the service_role JWT as password.
"""

import sys

JWT = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFvY2JxdmF2a2h4d2ZjdmpxaGNkIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTE5NDYxMywiZXhwIjoyMDk0NzcwNjEzfQ.3DlAw8mXLiuBIrgRjJJYNxJd_TmHeHPAzl2HjSa-qyU"

SQL = """
CREATE TABLE IF NOT EXISTS bolao_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

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

CREATE TABLE IF NOT EXISTS bolao_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_submissions_participant ON bolao_submissions (participant);
CREATE INDEX IF NOT EXISTS idx_submissions_active ON bolao_submissions (active);
CREATE INDEX IF NOT EXISTS idx_live_preds_participant ON bolao_live_predictions (participant_key);
CREATE INDEX IF NOT EXISTS idx_live_preds_match ON bolao_live_predictions (match_id);
CREATE INDEX IF NOT EXISTS idx_live_preds_active ON bolao_live_predictions (active);
CREATE INDEX IF NOT EXISTS idx_matches_status ON bolao_matches (status);
CREATE INDEX IF NOT EXISTS idx_matches_starts ON bolao_matches (starts_at);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON bolao_events (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_visibility ON bolao_events (visibility);
"""

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
    import psycopg2

try:
    DB_PASSWORD = "BarujaFe17.."
    conn = psycopg2.connect(
        host="db.qocbqvavkhxwfcvjqhcd.supabase.co",
        port=5432,
        dbname="postgres",
        user="postgres",
        password=DB_PASSWORD,
        connect_timeout=15,
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(SQL)
    cur.close()
    conn.close()
    print("ALL TABLES CREATED SUCCESSFULLY!")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
