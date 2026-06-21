-- Migration to add api_match_id to bolao_matches for football-data.org sync
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS api_match_id INTEGER UNIQUE;
