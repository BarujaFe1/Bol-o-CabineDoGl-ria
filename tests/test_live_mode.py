import pytest
from datetime import datetime, timedelta
from src.bolao.models import LiveMatch, LivePrediction, Prediction
from src.bolao.simulator_engine import normalize_slots, serialize_slots_to_prediction
from src.bolao.ui_live_matches import is_match_open_for_prediction
from src.bolao.live_scoring import calculate_live_prediction_points, calculate_live_ranking
from src.bolao.migrations import migrate_existing_submissions_to_classic_schema
from src.bolao.utils import normalize_participant_key

def test_normalize_slots():
    assert normalize_slots(None) == {}
    assert normalize_slots({"0": "Brasil"}) == {0: "Brasil"}
    assert normalize_slots(["Brasil", "França"]) == {0: "Brasil", 1: "França"}
    assert normalize_slots({"16": "Argentina"}) == {16: "Argentina"}

def test_serialize_slots_to_prediction_handling():
    # Empty slots
    pred = Prediction(participant="Teste")
    serialize_slots_to_prediction({}, pred)
    assert pred.champion is None

    # Slots with champion
    pred2 = Prediction(participant="Teste")
    slots = {0: "Brasil"}
    serialize_slots_to_prediction(slots, pred2)
    assert pred2.champion == "Brasil"

def test_is_match_open_for_prediction():
    starts_at = (datetime.now() + timedelta(minutes=15)).isoformat()
    match = LiveMatch(
        match_id="1",
        phase="grupos",
        group="A",
        round_label="Rodada 1",
        home_team="Brasil",
        away_team="França",
        starts_at=starts_at,
        starts_at_timezone="America/Sao_Paulo",
        lock_at=None,
        status="scheduled",
        sort_order=0
    )
    # 15 minutes before starts_at (lock is at starts_at - 10 mins) -> should be open
    assert is_match_open_for_prediction(match) is True

    # 5 minutes before starts_at -> should be locked (since lock is 10 mins before)
    now_past_lock = (datetime.now() + timedelta(minutes=7)).isoformat()
    match.lock_at = (datetime.fromisoformat(starts_at) - timedelta(minutes=10)).isoformat()
    assert is_match_open_for_prediction(match, now=now_past_lock) is False

def test_calculate_live_prediction_points():
    match = LiveMatch(
        match_id="1",
        phase="grupos",
        group="A",
        round_label="Rodada 1",
        home_team="Brasil",
        away_team="França",
        starts_at="2026-06-11T16:00:00",
        starts_at_timezone="America/Sao_Paulo",
        lock_at="2026-06-11T15:50:00",
        status="result_approved",
        official_home_goals=2,
        official_away_goals=1,
        winner="Brasil",
        sort_order=0
    )

    config = {
        "live_scoring": {
            "exact_score": 5,
            "outcome": 3,
            "goal_one_team": 1,
            "goal_difference": 1
        },
        "exact_score_mode": "isolated_max"
    }

    # Exact score: Brasil 2 x 1 França
    pred_exact = LivePrediction(
        id="user_1",
        participant_name="César",
        participant_key="cesar",
        match_id="1",
        predicted_home_goals=2,
        predicted_away_goals=1,
        submitted_at="2026-06-11T16:00:00",
        updated_at="2026-06-11T16:00:00"
    )
    res = calculate_live_prediction_points(pred_exact, match, config)
    assert res["points"] == 5
    assert "Placar exato" in res["breakdown"][0]

    # Outcome + Home goals: Brasil 2 x 0 França
    pred_outcome_gols = LivePrediction(
        id="user_2",
        participant_name="Pedro",
        participant_key="pedro",
        match_id="1",
        predicted_home_goals=2,
        predicted_away_goals=0,
        submitted_at="2026-06-11T16:00:00",
        updated_at="2026-06-11T16:00:00"
    )
    res = calculate_live_prediction_points(pred_outcome_gols, match, config)
    assert res["points"] == 4 # 3 (outcome) + 1 (home goals)

    # Wrong outcome: Brasil 0 x 2 França
    pred_wrong = LivePrediction(
        id="user_3",
        participant_name="Maria",
        participant_key="maria",
        match_id="1",
        predicted_home_goals=0,
        predicted_away_goals=2,
        submitted_at="2026-06-11T16:00:00",
        updated_at="2026-06-11T16:00:00"
    )
    res = calculate_live_prediction_points(pred_wrong, match, config)
    assert res["points"] == 0

def test_calculate_live_ranking():
    matches = [
        LiveMatch(
            match_id="1",
            phase="grupos",
            group="A",
            round_label="Rodada 1",
            home_team="Brasil",
            away_team="França",
            starts_at="2026-06-11T16:00:00",
            starts_at_timezone="America/Sao_Paulo",
            status="result_approved",
            official_home_goals=2,
            official_away_goals=1,
            winner="Brasil",
            sort_order=0
        )
    ]

    preds = [
        LivePrediction(
            id="cesar_1",
            participant_name="César",
            participant_key="cesar",
            match_id="1",
            predicted_home_goals=2,
            predicted_away_goals=1,
            submitted_at="2026-06-11T16:00:00",
            updated_at="2026-06-11T16:00:00"
        ),
        LivePrediction(
            id="pedro_1",
            participant_name="Pedro",
            participant_key="pedro",
            match_id="1",
            predicted_home_goals=2,
            predicted_away_goals=0,
            submitted_at="2026-06-11T16:00:00",
            updated_at="2026-06-11T16:00:00"
        )
    ]

    config = {
        "live_scoring": {
            "exact_score": 5,
            "outcome": 3,
            "goal_one_team": 1,
            "goal_difference": 1
        },
        "exact_score_mode": "isolated_max"
    }

    ranking = calculate_live_ranking(preds, matches, config)
    assert len(ranking) == 2
    assert ranking[0]["participant"] == "César"
    assert ranking[0]["total"] == 5
    assert ranking[0]["position"] == 1
    assert ranking[1]["participant"] == "Pedro"
    assert ranking[1]["total"] == 4
    assert ranking[1]["position"] == 2


def test_match_team_badge_resolution():
    from src.bolao.storage import load_matches
    from src.bolao.ui_simulator import get_team_badge_path
    from src.bolao.simulator_engine import name_to_id
    
    matches = load_matches()
    for m in matches:
        h_id = name_to_id(m.home_team)
        a_id = name_to_id(m.away_team)
        
        h_badge = get_team_badge_path(h_id) if h_id else None
        a_badge = get_team_badge_path(a_id) if a_id else None
        
        assert h_badge is None or isinstance(h_badge, str)
        assert a_badge is None or isinstance(a_badge, str)


def test_live_prediction_from_dict_normalization():
    from src.bolao.models import LivePrediction
    
    # 1. Prediction ID fallback & mismatch
    d1 = {
        "prediction_id": "legacy_123",
        "participant_name": "César",
        "match_id": 45,
        "predicted_home_goals": "2",
        "predicted_away_goals": "3",
        "scoring_breakdown": {"outcome": 3, "goals": 1}
    }
    lp = LivePrediction.from_dict(d1)
    assert lp.id == "legacy_123"
    assert lp.match_id == "45"
    assert lp.predicted_home_goals == 2
    assert lp.predicted_away_goals == 3
    assert "outcome: 3" in lp.scoring_breakdown
    assert "goals: 1" in lp.scoring_breakdown
    
    # 2. String breakdown
    d2 = {
        "participant_name": "Pedro",
        "match_id": "99",
        "predicted_home_goals": "invalid_number",
        "scoring_breakdown": "Cravou tudo!"
    }
    lp2 = LivePrediction.from_dict(d2)
    assert lp2.id == "pedro_99"
    assert lp2.predicted_home_goals == 0
    assert lp2.scoring_breakdown == ["Cravou tudo!"]


def test_upsert_live_prediction_flow(tmp_path, monkeypatch):
    import streamlit as st
    import src.bolao.storage as storage
    
    # Mock REGISTERED_PARTICIPANTS_PATH and LIVE_PREDICTIONS_PATH to use tmp_path
    monkeypatch.setattr(storage, "REGISTERED_PARTICIPANTS_PATH", tmp_path / "registered_participants.json")
    monkeypatch.setattr(storage, "LIVE_PREDICTIONS_PATH", tmp_path / "live_predictions.json")
    monkeypatch.setattr(storage, "ARCHIVED_PARTICIPANTS_PATH", tmp_path / "archived_participants.json")
    monkeypatch.setattr(storage, "SUBMISSIONS_DIR", tmp_path / "submissions")
    
    # Clear cache
    st.cache_data.clear()
    
    # 1. Upsert first prediction for a new participant
    from src.bolao.storage import upsert_live_prediction, load_live_predictions, load_registered_participants
    pred = upsert_live_prediction(participant_name="Henrique", match_id="1337", home_goals=2, away_goals=1)
    
    # Henrique must be normalized to "Henrique O Terrível" due to display name aliases
    assert pred.participant_name == "Henrique O Terrível"
    assert pred.participant_key == "henrique-o-terrivel"
    assert pred.match_id == "1337"
    assert pred.predicted_home_goals == 2
    assert pred.predicted_away_goals == 1
    
    # Check that registered participants lists "Henrique O Terrível"
    registered = load_registered_participants()
    assert "Henrique O Terrível" in registered
    
    # Guarantee no duplicate entry is created
    all_preds_before = len(load_live_predictions())
    
    # 2. Upsert update (edit)
    pred_updated = upsert_live_prediction(participant_name="Henrique O Terrível", match_id="1337", home_goals=3, away_goals=3)
    assert pred_updated.predicted_home_goals == 3
    assert pred_updated.predicted_away_goals == 3
    
    all_preds_after = len(load_live_predictions())
    assert all_preds_after == all_preds_before


def test_archiving_participants_flow(tmp_path, monkeypatch):
    import streamlit as st
    import src.bolao.storage as storage
    
    # Mock registered participants paths
    monkeypatch.setattr(storage, "REGISTERED_PARTICIPANTS_PATH", tmp_path / "registered_participants.json")
    monkeypatch.setattr(storage, "LIVE_PREDICTIONS_PATH", tmp_path / "live_predictions.json")
    monkeypatch.setattr(storage, "ARCHIVED_PARTICIPANTS_PATH", tmp_path / "archived_participants.json")
    monkeypatch.setattr(storage, "SUBMISSIONS_DIR", tmp_path / "submissions")
    
    # Clear cache
    st.cache_data.clear()
    
    from src.bolao.storage import save_registered_participants, load_registered_participants, archive_participant, restore_participant, get_archived_keys
    
    save_registered_participants(["Baruja", "Fantato", "Henrique O Terrível", "Murilov"])
    
    # 1. Archive "Murilov"
    success = archive_participant("Murilov", reason="Inativo")
    assert success is True
    
    # 2. Key must be in archived keys
    archived_keys = get_archived_keys()
    assert "murilov" in archived_keys
    
    # 3. Reading registered participants by default must hide archived ones
    active = load_registered_participants(include_archived=False)
    assert "Murilov" not in active
    assert "Baruja" in active
    
    # 4. Restore "Murilov"
    restored = restore_participant("murilov")
    assert restored is True
    
    active_post_restore = load_registered_participants(include_archived=False)
    assert "Murilov" in active_post_restore

