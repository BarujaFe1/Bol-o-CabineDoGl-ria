import streamlit as st
import src.bolao.storage as storage


def test_submissions_synced_module_initialized():
    """R1: _submissions_synced deve existir no escopo de modulo de storage.

    Sem essa inicializacao, a primeira chamada de ensure_state() no caminho
    Supabase (storage.py ~L462-472) levanta NameError ao ler `if not _submissions_synced`.
    """
    assert hasattr(storage, "_submissions_synced"), (
        "storage._submissions_synced deve ser inicializado no escopo de modulo"
    )


def test_ensure_state_supabase_branch_syncs_once(tmp_path, monkeypatch):
    """R1/comportamento: ensure_state() no caminho Supabase chama _sync_local_to_supabase
    exatamente uma vez e nao levanta NameError em _submissions_synced."""
    monkeypatch.setattr(storage, "get_storage_backend", lambda: "supabase")
    monkeypatch.setattr(storage, "_get_supabase_client", lambda: object())
    monkeypatch.setattr(storage, "_ensure_supabase_tables", lambda client: None)
    monkeypatch.setattr(storage, "_seed_initial_state", lambda: None)

    calls = {"n": 0}

    def fake_sync(client):
        calls["n"] += 1

    monkeypatch.setattr(storage, "_sync_local_to_supabase", fake_sync)
    monkeypatch.setattr(storage, "STATE_DIR", tmp_path)
    monkeypatch.setattr(storage, "CONFIG_PATH", tmp_path / "config.json")
    monkeypatch.setattr(storage, "SUBMISSIONS_DIR", tmp_path / "submissions")
    monkeypatch.setattr(storage, "UPLOADS_DIR", tmp_path / "uploads")

    storage._submissions_synced = False
    try:
        storage.ensure_state()
        storage.ensure_state()
    finally:
        storage._submissions_synced = False

    assert calls["n"] == 1


def test_sync_official_skips_save_when_unchanged(monkeypatch):
    """R10: sync_official_results_to_matches nao deve gravar/limpar cache quando
    nada mudou (sem novas aprovacoes e pontos ja calculados)."""
    from src.bolao.models import LiveMatch, LivePrediction, Prediction
    import src.bolao.storage as storage

    match = LiveMatch(
        match_id="13379", phase="grupos", group="A", round_label="R1",
        home_team="Mexico", away_team="RSA",
        starts_at="2026-06-11T16:00:00", status="scheduled",
        official_home_goals=None, official_away_goals=None, sort_order=0,
    )
    lp = LivePrediction(
        id="baruja_13379", participant_name="Baruja", participant_key="baruja",
        match_id="13379", predicted_home_goals=2, predicted_away_goals=0,
        submitted_at="2026-06-11T10:00:00", updated_at="2026-06-11T10:00:00",
        points=None, scoring_breakdown=[],
    )
    official = Prediction(participant="Resultado oficial")
    official.meta = {"group_matches": {"13379": [2, 0]}}

    monkeypatch.setattr(storage, "load_official", lambda: official)
    monkeypatch.setattr(storage, "load_matches", lambda: [match])
    monkeypatch.setattr(storage, "load_live_predictions", lambda: [lp])
    monkeypatch.setattr(storage, "load_config", lambda: {"live_scoring": {}})

    saves = {"m": 0, "lp": 0}
    monkeypatch.setattr(storage, "save_matches", lambda matches: saves.__setitem__("m", saves["m"] + 1))
    monkeypatch.setattr(storage, "save_live_predictions", lambda preds: saves.__setitem__("lp", saves["lp"] + 1))

    # 1a sincronizacao: aprova jogo + calcula pontos (None->N) => DEVE gravar
    assert storage.sync_official_results_to_matches() == 1
    assert match.status == "result_approved"
    assert lp.points is not None
    assert saves["m"] == 1 and saves["lp"] == 1

    # 2a sincronizacao: nada mudou => NAO deve gravar
    assert storage.sync_official_results_to_matches() == 0
    assert saves["m"] == 1 and saves["lp"] == 1

    # 3a: predicao volta a mudar (points None) => deve gravar (points_changed True)
    lp.points = None
    lp.scoring_breakdown = []
    assert storage.sync_official_results_to_matches() == 0
    assert saves["m"] == 2 and saves["lp"] == 2