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
