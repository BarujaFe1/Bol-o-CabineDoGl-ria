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


def _patch_state_dir(monkeypatch, state_dir):
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
    monkeypatch.setattr(storage, "ARTILHEIRO_DIA_PATH", state_dir / "artilheiro_palpites_dia.json")
    monkeypatch.setattr(storage, "ARTILHEIRO_RODADA_PATH", state_dir / "artilheiro_palpites_rodada.json")
    monkeypatch.setattr(storage, "ARTILHEIRO_RESULTADO_DIA_PATH", state_dir / "artilheiro_resultado_dia.json")
    monkeypatch.setattr(storage, "ARTILHEIRO_RESULTADO_RODADA_PATH", state_dir / "artilheiro_resultado_rodada.json")


def test_backup_restore_preserves_artilheiro(tmp_path, monkeypatch):
    """R3: export/import_all_state devem preservar os 4 arquivos de artilheiro
    (palpites e resultados de dia/rodada), evitando perda de dados em backup/restore."""
    import streamlit as st
    from pathlib import Path
    from src.bolao.storage import (
        export_all_state,
        import_all_state,
        load_artilheiro_palpites_dia,
        load_artilheiro_palpites_rodada,
        load_artilheiro_resultado_dia,
        load_artilheiro_resultado_rodada,
        save_artilheiro_palpite_dia,
        save_artilheiro_palpite_rodada,
        save_artilheiro_resultado_dia,
        save_artilheiro_resultado_rodada,
    )
    import src.bolao.storage as storage

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "submissions").mkdir(parents=True, exist_ok=True)
    _patch_state_dir(monkeypatch, state_dir)

    st.cache_data.clear()

    palpite_dia = {
        "participante_nome": "Baruja",
        "data": "2026-06-18",
        "jogador": "Vini Jr",
        "selecao": "Brasil",
    }
    palpite_rod = {
        "participante_nome": "Baruja",
        "rodada": "1",
        "jogador": "Neymar",
        "selecao": "Brasil",
    }
    res_dia = {"data": "2026-06-18", "jogador": "Vini Jr", "selecao": "Brasil"}
    res_rod = {"rodada": "1", "jogador": "Neymar", "selecao": "Brasil"}

    save_artilheiro_palpite_dia(palpite_dia)
    save_artilheiro_palpite_rodada(palpite_rod)
    save_artilheiro_resultado_dia(res_dia)
    save_artilheiro_resultado_rodada(res_rod)
    st.cache_data.clear()

    assert load_artilheiro_palpites_dia() == [palpite_dia]
    assert load_artilheiro_palpites_rodada() == [palpite_rod]
    assert load_artilheiro_resultado_dia() == [res_dia]
    assert load_artilheiro_resultado_rodada() == [res_rod]

    exported = export_all_state()
    assert exported["artilheiro_palpites_dia"] == [palpite_dia]
    assert exported["artilheiro_palpites_rodada"] == [palpite_rod]
    assert exported["artilheiro_resultado_dia"] == [res_dia]
    assert exported["artilheiro_resultado_rodada"] == [res_rod]

    for p in (
        storage.ARTILHEIRO_DIA_PATH,
        storage.ARTILHEIRO_RODADA_PATH,
        storage.ARTILHEIRO_RESULTADO_DIA_PATH,
        storage.ARTILHEIRO_RESULTADO_RODADA_PATH,
    ):
        if Path(p).exists():
            Path(p).unlink()
    st.cache_data.clear()

    assert load_artilheiro_palpites_dia() == []
    assert load_artilheiro_resultado_dia() == []

    import_all_state(exported)
    st.cache_data.clear()

    assert load_artilheiro_palpites_dia() == [palpite_dia]
    assert load_artilheiro_palpites_rodada() == [palpite_rod]
    assert load_artilheiro_resultado_dia() == [res_dia]
    assert load_artilheiro_resultado_rodada() == [res_rod]


def test_partial_backup_restore(tmp_path, monkeypatch):
    import streamlit as st
    from pathlib import Path
    from src.bolao.models import Prediction, LivePrediction
    from src.bolao.storage import (
        import_participants_predictions_only,
        save_registered_participants,
        load_registered_participants,
        save_official,
        load_official,
        save_config,
        load_config,
        load_submissions,
        load_live_predictions,
    )
    import src.bolao.storage as storage

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "submissions").mkdir(parents=True, exist_ok=True)
    _patch_state_dir(monkeypatch, state_dir)

    st.cache_data.clear()

    # 1. Set current state
    current_config = {"scoring_mode": "v2", "live_lock_minutes_before_match": 10}
    save_config(current_config)

    current_official = Prediction(participant="Resultado oficial", submission_id="official")
    current_official.champion = "Brasil"
    save_official(current_official)

    save_registered_participants(["Alice"])

    # 2. Build backup data with different values
    backup_data = {
        "config": {"scoring_mode": "ponderado", "live_lock_minutes_before_match": 20},
        "official": {"participant": "Resultado oficial", "submission_id": "official", "champion": "Alemanha"},
        "registered_participants": ["Alice", "Bob"],
        "submissions": [
            {
                "participant": "Bob",
                "submission_id": "bob123",
                "submitted_at": "2026-06-20T12:00:00",
                "groups": {},
                "best_thirds": {},
                "knockout": {},
                "champion": "França",
                "status": "aprovado",
                "meta": {}
            }
        ],
        "live_predictions": [
            {
                "id": "bob_1",
                "participant_name": "Bob",
                "participant_key": "bob",
                "match_id": "1",
                "predicted_home_goals": 2,
                "predicted_away_goals": 1,
                "submitted_at": "2026-06-20T12:00:00",
                "updated_at": "2026-06-20T12:00:00"
            }
        ]
    }

    # 3. Import partial restore
    import_participants_predictions_only(backup_data)
    st.cache_data.clear()

    # 4. Verify that config is intact (not overwritten)
    assert load_config()["scoring_mode"] == "v2"

    # 5. Verify that official results are intact (not overwritten)
    assert load_official().champion == "Brasil"

    # 6. Verify that participants list is merged
    assert sorted(load_registered_participants(include_archived=True)) == ["Alice", "Bob"]
    
    # 7. Verify submissions and predictions were imported
    assert len(load_submissions()) == 1
    assert len(load_live_predictions()) == 1
