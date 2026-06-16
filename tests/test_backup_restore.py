import pytest
import os
import json
import streamlit as st
from pathlib import Path
from src.bolao.storage import (
    export_all_state,
    import_all_state,
    save_registered_participants,
    load_registered_participants,
    save_archived_participants,
    load_archived_participants,
    load_config
)

def test_backup_and_restore(tmp_path, monkeypatch):
    # Setup temporary directory for state files so we don't mess with real data during tests
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "submissions").mkdir(parents=True, exist_ok=True)

    # Patch storage constants/paths to use temp directory
    import src.bolao.storage as storage
    monkeypatch.setattr(storage, "_seed_initial_state", lambda: None)
    monkeypatch.setattr(storage, "STATE_DIR", state_dir)
    monkeypatch.setattr(storage, "CONFIG_PATH", state_dir / "config.json")
    monkeypatch.setattr(storage, "OFFICIAL_PATH", state_dir / "official_result.json")
    monkeypatch.setattr(storage, "EVENTS_PATH", state_dir / "events.json")
    monkeypatch.setattr(storage, "MATCHES_PATH", state_dir / "matches_2026.json")
    monkeypatch.setattr(storage, "LIVE_PREDICTIONS_PATH", state_dir / "live_predictions.json")
    monkeypatch.setattr(storage, "MIGRATIONS_PATH", state_dir / "migrations.json")
    monkeypatch.setattr(storage, "REGISTERED_PARTICIPANTS_PATH", state_dir / "registered_participants.json")
    monkeypatch.setattr(storage, "ARCHIVED_PARTICIPANTS_PATH", state_dir / "archived_participants.json")
    monkeypatch.setattr(storage, "SUBMISSIONS_DIR", state_dir / "submissions")

    # Clear cache to ensure cached values do not interfere
    st.cache_data.clear()

    # Set up some dummy data
    participants = ["Alice", "Bob", "Charlie"]
    archived = [{"name": "Old User", "participant_key": "old-user"}]
    
    save_registered_participants(participants)
    save_archived_participants(archived)

    # Clear cache after write
    st.cache_data.clear()

    # Export state
    exported = export_all_state()

    assert "registered_participants" in exported
    assert "archived_participants" in exported
    assert exported["registered_participants"] == participants
    assert exported["archived_participants"] == archived

    # Reset lists
    save_registered_participants([])
    save_archived_participants([])

    # Clear cache after reset
    st.cache_data.clear()

    assert load_registered_participants(include_archived=True) == []
    assert load_archived_participants() == []

    # Import state
    import_all_state(exported)

    # Clear cache after import
    st.cache_data.clear()

    # Verify restoration
    assert load_registered_participants(include_archived=True) == participants
    assert load_archived_participants() == archived
