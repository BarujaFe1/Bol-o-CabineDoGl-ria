from __future__ import annotations

import os
import shutil
from pathlib import Path

import streamlit as st

from .constants import DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES, DEFAULT_WEIGHTED_RULES
from .models import Prediction, LiveMatch, LivePrediction, ActivityEvent
from .utils import now_iso, read_json, safe_filename, stable_id, write_json, normalize_participant_key
from dataclasses import dataclass, field
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
STATE_DIR = DATA_DIR / "state"
SUBMISSIONS_DIR = STATE_DIR / "submissions"
UPLOADS_DIR = STATE_DIR / "uploads"
OFFICIAL_PATH = STATE_DIR / "official_result.json"
CONFIG_PATH = STATE_DIR / "config.json"
EVENTS_PATH = STATE_DIR / "events.json"
MATCHES_PATH = STATE_DIR / "matches_2026.json"
LIVE_PREDICTIONS_PATH = STATE_DIR / "live_predictions.json"
MIGRATIONS_PATH = STATE_DIR / "migrations.json"
REGISTERED_PARTICIPANTS_PATH = STATE_DIR / "registered_participants.json"
ARCHIVED_PARTICIPANTS_PATH = STATE_DIR / "archived_participants.json"


def get_storage_backend() -> str:
    try:
        client = _get_supabase_client()
        if client is not None:
            return "supabase"
    except Exception:
        pass
    return "local"


import time

def _supabase_retry(fn, max_retries=2, delay=1.0):
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception:
            if attempt < max_retries:
                time.sleep(delay * (attempt + 1))
            else:
                raise

@st.cache_resource
def _get_supabase_client():
    try:
        from supabase import create_client
    except ImportError:
        return None

    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY")
        if not url or url == "SUA_SUPABASE_URL_AQUI" or not url.startswith("https://"):
            return None
        return create_client(url, key)
    except Exception:
        return None


def _supabase_table_exists(client, table: str) -> bool:
    try:
        client.table(table).select("*").limit(1).execute()
        return True
    except Exception:
        return False


REQUIRED_TABLES = [
    "bolao_config",
    "bolao_submissions",
    "bolao_official",
    "bolao_live_predictions",
    "bolao_matches",
    "bolao_events",
]

def _ensure_supabase_tables(client) -> None:
    """Verify required tables exist. Attempt creation via REST API if missing."""
    existing = set()
    for table in REQUIRED_TABLES:
        if _supabase_table_exists(client, table):
            existing.add(table)

    if len(existing) == len(REQUIRED_TABLES):
        return

    missing = [t for t in REQUIRED_TABLES if t not in existing]
    _maybe_create_tables(client, missing)


def _maybe_create_tables(client, missing_tables: list[str]) -> None:
    """Try to create missing tables via direct DB connection or REST API."""
    sql_lines = []
    for table in missing_tables:
        sql_lines.append(TABLE_DDL.get(table, ""))

    sql = "\n".join(sql_lines)
    if not sql.strip():
        return

    # Method 1: Try direct PostgreSQL connection (via psycopg2 with DB password in secrets)
    try:
        client.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS bolao_config (
                key TEXT PRIMARY KEY,
                value JSONB NOT NULL,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        client.execute_sql(
            """
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
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        client.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS bolao_official (
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
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        client.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS bolao_matches (
                match_id TEXT PRIMARY KEY,
                phase TEXT,
                "group" TEXT,
                round_label TEXT,
                home_team TEXT,
                away_team TEXT,
                starts_at TEXT,
                starts_at_timezone TEXT,
                lock_at TEXT,
                status TEXT DEFAULT 'scheduled',
                sort_order INT,
                home_goals INT,
                away_goals INT,
                official_home_goals INT,
                official_away_goals INT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        client.execute_sql(
            """
            CREATE TABLE IF NOT EXISTS bolao_events (
                id SERIAL PRIMARY KEY,
                event_type TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """
        )
        return
    except Exception:
        pass

    # Method 2: Try REST API (may fail - PostgREST doesn't support DDL)
    try:
        import os as _os, requests as _requests

        url = _os.environ.get("SUPABASE_URL") or ""
        key = _os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
        if not url or not key:
            try:
                url = st.secrets.get("SUPABASE_URL", "")
                key = st.secrets.get("SUPABASE_SERVICE_ROLE_KEY", "")
            except Exception:
                pass

        if url and key:
            headers = {
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            }
            resp = _requests.post(
                f"{url.rstrip('/')}/rest/v1/rpc/",
                json={"query": sql},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                for t in missing_tables:
                    if _supabase_table_exists(client, t):
                        st.success(f"Tabela {t} criada automaticamente no Supabase.")
                        return
    except Exception:
        pass

    _warn_missing_tables(missing_tables)


def _warn_missing_tables(tables: list[str]) -> None:
    st.warning(
        f"Tabelas do Supabase ausentes: {', '.join(tables)}. "
        f"Execute supabase_migrations/001_initial_schema.sql no SQL Editor do Supabase Dashboard. "
        f"Os dados serão salvos localmente até a migração ser concluída."
    )


TABLE_DDL = {
    "bolao_config": """
CREATE TABLE IF NOT EXISTS bolao_config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",
    "bolao_submissions": """
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
);""",
    "bolao_official": """
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
);""",
    "bolao_live_predictions": """
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
);""",
    "bolao_matches": """
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
);""",
    "bolao_events": """
CREATE TABLE IF NOT EXISTS bolao_events (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    metadata JSONB DEFAULT '{}'::jsonb
);""",
}


def _sync_local_to_supabase(client) -> None:
    try:
        # Sync local submissions
        for path in sorted(SUBMISSIONS_DIR.glob("*.json")):
            try:
                data = read_json(path, {})
                if not data or "participant" not in data:
                    continue
                prediction = Prediction.from_dict(data)
                if not prediction.submission_id:
                    continue
                # Upsert to Supabase
                client.table("bolao_submissions").upsert({
                    "id": prediction.submission_id,
                    "participant": prediction.participant,
                    "groups": prediction.groups,
                    "best_thirds": prediction.best_thirds,
                    "knockout": {k: [m.to_dict() if hasattr(m, 'to_dict') else m for m in v] for k, v in prediction.knockout.items()},
                    "champion": prediction.champion,
                    "submission_id": prediction.submission_id,
                    "submitted_at": prediction.submitted_at,
                    "status": prediction.status,
                    "meta": prediction.meta,
                }, on_conflict="id").execute()
            except Exception:
                pass

        # Sync official result
        if OFFICIAL_PATH.exists():
            try:
                data = read_json(OFFICIAL_PATH, {})
                if data and "participant" in data:
                    prediction = Prediction.from_dict(data)
                    prediction.participant = "Resultado oficial"
                    client.table("bolao_official").upsert({
                        "id": "official",
                        "participant": prediction.participant,
                        "groups": prediction.groups,
                        "best_thirds": prediction.best_thirds,
                        "knockout": {k: [m.to_dict() if hasattr(m, 'to_dict') else m for m in v] for k, v in prediction.knockout.items()},
                        "champion": prediction.champion,
                        "submission_id": prediction.submission_id,
                        "submitted_at": prediction.submitted_at,
                        "status": prediction.status,
                        "meta": prediction.meta,
                        "updated_at": now_iso(),
                    }, on_conflict="id").execute()
            except Exception:
                pass

        # Sync local live predictions
        if LIVE_PREDICTIONS_PATH.exists():
            try:
                live_data = read_json(LIVE_PREDICTIONS_PATH, [])
                if live_data and _supabase_table_exists(client, "bolao_live_predictions"):
                    client.table("bolao_live_predictions").upsert(live_data, on_conflict="id").execute()
            except Exception:
                pass

        # Sync registered participants
        if REGISTERED_PARTICIPANTS_PATH.exists():
            try:
                parts = read_json(REGISTERED_PARTICIPANTS_PATH, [])
                if parts:
                    result = client.table("bolao_config").select("value").eq("key", "registered_participants").execute()
                    existing = result.data[0].get("value", []) if result.data else []
                    merged = list(dict.fromkeys(existing + [p for p in parts if p.lower() not in {x.lower() for x in existing}]))
                    if len(merged) != len(existing):
                        client.table("bolao_config").upsert({
                            "key": "registered_participants",
                            "value": merged,
                            "updated_at": now_iso(),
                        }, on_conflict="key").execute()
            except Exception:
                pass
    except Exception:
        pass


def ensure_state() -> None:
    global _submissions_synced
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            _ensure_supabase_tables(client)
            _seed_initial_state()
            if not _submissions_synced:
                _sync_local_to_supabase(client)
                _submissions_synced = True
        return

    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_json(CONFIG_PATH, default_config())
    _seed_initial_state()


INITIAL_PARTICIPANTS = ["Baruja", "Fantato", "Henrique", "Murilov", "Lucão", "Mantovas"]

MERGE_PREDS = [
    ("Murilov", "13381", 2, 0),
    ("Murilov", "13382", 1, 1),
    ("Mantovas", "13382", 0, 1),
    ("Lucão", "13381", 2, 0),
    ("Lucão", "13382", 1, 0),
]


def _seed_initial_state() -> None:
    backend = get_storage_backend()

    if backend == "supabase":
        _seed_initial_state_supabase()
    else:
        _seed_initial_state_local()


def _seed_initial_state_supabase() -> None:
    client = _get_supabase_client()
    if not client:
        _seed_initial_state_local()
        return

    # Seed registered participants
    try:
        result = client.table("bolao_config").select("value").eq("key", "registered_participants").execute()
        existing = result.data[0].get("value", []) if result.data else []
    except Exception:
        existing = []

    missing = [p for p in INITIAL_PARTICIPANTS if p.lower() not in {x.lower() for x in existing}]
    if missing:
        existing.extend(missing)
        try:
            client.table("bolao_config").upsert({
                "key": "registered_participants",
                "value": existing,
                "updated_at": now_iso(),
            }, on_conflict="key").execute()
        except Exception:
            pass

    # Seed live predictions
    try:
        result = client.table("bolao_live_predictions").select("id").execute()
        existing_ids = {r["id"] for r in result.data}
    except Exception:
        existing_ids = set()

    now = now_iso()
    new_preds = []
    for name, m_id, h, a in MERGE_PREDS:
        key = normalize_participant_key(name)
        pid = f"{key}_{m_id}"
        if pid not in existing_ids:
            new_preds.append({
                "id": pid,
                "participant_name": name,
                "participant_key": key,
                "match_id": m_id,
                "predicted_home_goals": h,
                "predicted_away_goals": a,
                "submitted_at": now,
                "updated_at": now,
                "confirmation_code": None,
                "locked_at": None,
                "is_locked": False,
                "is_late": False,
                "points": None,
                "scoring_breakdown": [],
                "schema_version": "live-v1",
            })

    if new_preds:
        try:
            client.table("bolao_live_predictions").insert(new_preds).execute()
        except Exception:
            pass


def _seed_initial_state_local() -> None:
    if REGISTERED_PARTICIPANTS_PATH.exists():
        parts = read_json(REGISTERED_PARTICIPANTS_PATH, [])
        missing = [p for p in INITIAL_PARTICIPANTS if p.lower() not in {x.lower() for x in parts}]
        if missing:
            parts.extend(missing)
            write_json(REGISTERED_PARTICIPANTS_PATH, parts)
    else:
        write_json(REGISTERED_PARTICIPANTS_PATH, list(INITIAL_PARTICIPANTS))

    from .utils import normalize_participant_key
    if LIVE_PREDICTIONS_PATH.exists():
        current = read_json(LIVE_PREDICTIONS_PATH, [])
        existing_ids = {p["id"] for p in current}
        now = now_iso()
        for name, m_id, h, a in MERGE_PREDS:
            key = normalize_participant_key(name)
            pid = f"{key}_{m_id}"
            if pid not in existing_ids:
                current.append({
                    "id": pid,
                    "participant_name": name,
                    "participant_key": key,
                    "match_id": m_id,
                    "predicted_home_goals": h,
                    "predicted_away_goals": a,
                    "submitted_at": now,
                    "updated_at": now,
                    "confirmation_code": None,
                    "locked_at": None,
                    "is_locked": False,
                    "is_late": False,
                    "points": None,
                    "scoring_breakdown": [],
                    "schema_version": "live-v1"
                })
                existing_ids.add(pid)
        write_json(LIVE_PREDICTIONS_PATH, current)
    else:
        now = now_iso()
        base = []
        for name, m_id, h, a in MERGE_PREDS:
            key = normalize_participant_key(name)
            base.append({
                "id": f"{key}_{m_id}",
                "participant_name": name,
                "participant_key": key,
                "match_id": m_id,
                "predicted_home_goals": h,
                "predicted_away_goals": a,
                "submitted_at": now,
                "updated_at": now,
                "confirmation_code": None,
                "locked_at": None,
                "is_locked": False,
                "is_late": False,
                "points": None,
                "scoring_breakdown": [],
                "schema_version": "live-v1"
            })
        write_json(LIVE_PREDICTIONS_PATH, base)


def default_config() -> dict:
    return {
        "scoring_mode": "v2",
        "weighted_rules": dict(DEFAULT_WEIGHTED_RULES),
        "uniform_rules": dict(DEFAULT_UNIFORM_RULES),
        "v2_rules": dict(DEFAULT_V2_RULES),
        "status_label": "Recebendo palpites",
        "admin_password_enabled": False,
        "last_api_sync": None,
        "is_bolao_locked": False,
        "classic_enabled": True,
        "live_mode_enabled": True,
        "combined_ranking_enabled": False,
        "classic_submissions_locked": False,
        "live_lock_minutes_before_match": 0,
        "default_timezone": "America/Sao_Paulo",
        "public_features": {
            "show_public_analytics": True,
            "show_public_duels": True,
            "show_public_group_predictions": True,
            "show_public_transparency": True,
            "show_public_match_center": True,
            "show_public_activity_feed": True,
            "reveal_classic_predictions_after_close": True,
            "reveal_live_predictions_after_lock": True,
            "hide_confirmation_codes_publicly": True,
        },
        "theme": {
            "allow_theme_toggle": True,
            "default_theme": "system",
            "available_themes": ["light", "dark", "system"]
        },
        "combined_ranking": {
            "classic_weight": 1.0,
            "live_weight": 1.0,
            "include_classic_only_players": True,
            "include_live_only_players": True,
            "missing_mode_points_strategy": "zero"
        },
        "live_scoring": {
            "exact_score": 5,
            "outcome": 3,
            "one_team_goals": 1,
            "goal_difference": 1,
            "exact_score_mode": "isolated_max"
        }
    }



@st.cache_data(ttl=15, show_spinner=False)
def load_config() -> dict:
    ensure_state()
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_config").select("value").eq("key", "main").execute()
                if result.data:
                    data = result.data[0].get("value", {})
                    merged = default_config()
                    merged.update(data or {})
                    merged["weighted_rules"] = {**DEFAULT_WEIGHTED_RULES, **(merged.get("weighted_rules") or {})}
                    merged["uniform_rules"] = {**DEFAULT_UNIFORM_RULES, **(merged.get("uniform_rules") or {})}
                    merged["v2_rules"] = {**DEFAULT_V2_RULES, **(merged.get("v2_rules") or {})}
                    return merged
            except Exception:
                pass

    data = read_json(CONFIG_PATH, {})
    merged = default_config()
    merged.update(data or {})
    merged["weighted_rules"] = {**DEFAULT_WEIGHTED_RULES, **(merged.get("weighted_rules") or {})}
    merged["uniform_rules"] = {**DEFAULT_UNIFORM_RULES, **(merged.get("uniform_rules") or {})}
    merged["v2_rules"] = {**DEFAULT_V2_RULES, **(merged.get("v2_rules") or {})}
    return merged


def save_config(config: dict) -> None:
    st.cache_data.clear()
    append_event("config_changed", "Configurações do bolão foram atualizadas.")
    ensure_state()
    write_json(CONFIG_PATH, config)
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_config").upsert({"key": "main", "value": config, "updated_at": now_iso()}, on_conflict="key").execute()
            except Exception:
                pass


@st.cache_data(ttl=15, show_spinner=False)
def load_submissions(include_archived: bool = False) -> list[Prediction]:
    ensure_state()
    backend = get_storage_backend()
    archived_keys = set() if include_archived else get_archived_keys()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_submissions").select("*").execute()
                preds = [Prediction.from_dict(row) for row in result.data if row.get("active") is not False]
                if not include_archived:
                    from .utils import normalize_participant_key
                    preds = [p for p in preds if normalize_participant_key(p.participant) not in archived_keys]
                return preds
            except Exception:
                pass

    submissions = []
    for path in sorted(SUBMISSIONS_DIR.glob("*.json")):
        try:
            submissions.append(Prediction.from_dict(read_json(path, {})))
        except Exception:
            continue
            
    if not include_archived:
        from .utils import normalize_participant_key
        submissions = [p for p in submissions if normalize_participant_key(p.participant) not in archived_keys]
        
    return submissions


def save_submission(prediction: Prediction, overwrite: bool = True) -> Path:
    st.cache_data.clear()
    append_event("submission_saved", f"Palpite de {prediction.participant} foi enviado/atualizado.")
    ensure_state()
    if not prediction.submission_id:
        prediction.submission_id = stable_id(prediction.participant, now_iso())
    if not prediction.submitted_at:
        prediction.submitted_at = now_iso()
    prediction.status = "confirmado"

    backend = get_storage_backend()

    filename = f"{safe_filename(prediction.participant)}-{prediction.submission_id}.json"
    path = SUBMISSIONS_DIR / filename
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    write_json(path, prediction.to_dict())

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                data = prediction.to_dict()
                client.table("bolao_submissions").upsert({
                    "id": prediction.submission_id,
                    "participant": prediction.participant,
                    "groups": prediction.groups,
                    "best_thirds": prediction.best_thirds,
                    "knockout": {k: [m.to_dict() if hasattr(m, 'to_dict') else m for m in v] for k, v in prediction.knockout.items()},
                    "champion": prediction.champion,
                    "submission_id": prediction.submission_id,
                    "submitted_at": prediction.submitted_at,
                    "status": prediction.status,
                    "meta": prediction.meta,
                }, on_conflict="id").execute()
            except Exception:
                pass

    return path


def delete_submission(submission_id: str) -> bool:
    st.cache_data.clear()
    ensure_state()
    
    participant_name = "desconhecido"
    try:
        submissions = load_submissions()
        for p in submissions:
            if p.submission_id == submission_id:
                participant_name = p.participant
                break
    except Exception:
        pass

    deleted = False
    for path in SUBMISSIONS_DIR.glob("*.json"):
        try:
            data = read_json(path, {})
            if data.get("submission_id") == submission_id:
                path.unlink()
                deleted = True
                break
        except Exception:
            pass

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").delete().eq("id", submission_id).execute()
                deleted = True
            except Exception:
                pass
                
    if deleted:
        append_event("submission_deleted", f"Palpite de {participant_name} foi excluído.")
    return deleted


@st.cache_data(ttl=15, show_spinner=False)
def load_official() -> Prediction | None:
    ensure_state()
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_official").select("*").eq("id", "official").execute()
                if result.data:
                    return Prediction.from_dict(result.data[0])
            except Exception:
                pass

    if not OFFICIAL_PATH.exists():
        return None
    try:
        return Prediction.from_dict(read_json(OFFICIAL_PATH, {}))
    except Exception:
        return None


def save_official(prediction: Prediction) -> Path:
    st.cache_data.clear()
    append_event("official_saved", "Resultado oficial do bolão foi cadastrado/atualizado.")
    ensure_state()
    prediction.participant = "Resultado oficial"
    if not prediction.submitted_at:
        prediction.submitted_at = now_iso()

    write_json(OFFICIAL_PATH, prediction.to_dict())

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                data = prediction.to_dict()
                client.table("bolao_official").upsert({
                    "id": "official",
                    "participant": prediction.participant,
                    "groups": prediction.groups,
                    "best_thirds": prediction.best_thirds,
                    "knockout": {k: [m.to_dict() if hasattr(m, 'to_dict') else m for m in v] for k, v in prediction.knockout.items()},
                    "champion": prediction.champion,
                    "submission_id": prediction.submission_id,
                    "submitted_at": prediction.submitted_at,
                    "status": prediction.status,
                    "meta": prediction.meta,
                    "updated_at": now_iso(),
                }, on_conflict="id").execute()
            except Exception:
                pass

    return OFFICIAL_PATH


def export_all_state() -> dict:
    return {
        "config": load_config(),
        "official": load_official().to_dict() if load_official() else None,
        "submissions": [p.to_dict() for p in load_submissions(include_archived=True)],
        "live_predictions": [p.to_dict() for p in load_live_predictions(include_archived=True)],
        "matches": [m.to_dict() for m in load_matches()],
        "events": load_events(limit=1000),
        "migrations": load_migrations(),
        "registered_participants": load_registered_participants(include_archived=True),
        "archived_participants": load_archived_participants(),
        "brasil_palpites_goleadores": load_brasil_palpites_goleadores(),
        "brasil_resultados_goleadores": list(load_brasil_resultados_goleadores().values()),
        "brasil_palpites_classicos": load_brasil_palpites_classicos(),
        "ranking_snapshots": load_ranking_snapshots(),
        "comentarios_jogo": read_json(COMENTARIOS_JOGO_PATH, []),
        "timestamp": now_iso(),
        "app_version": "2026-live-mode-v1"
    }


def import_all_state(data: dict) -> None:
    st.cache_data.clear()
    append_event("state_imported", "Um backup completo do bolão foi importado pelo administrador.")
    ensure_state()

    # 1. Config
    if "config" in data and data["config"]:
        save_config(data["config"])

    # 2. Official result
    if "official" in data:
        if data["official"]:
            save_official(Prediction.from_dict(data["official"]))
        else:
            if OFFICIAL_PATH.exists():
                try:
                    OFFICIAL_PATH.unlink()
                except Exception:
                    pass

    # 3. Submissions (classic predictions)
    # Clear existing submissions first
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").delete().neq("id", "").execute()
            except Exception:
                pass
    else:
        for p in SUBMISSIONS_DIR.glob("*.json"):
            try:
                p.unlink()
            except Exception:
                pass

    if "submissions" in data and data["submissions"]:
        for sub in data["submissions"]:
            pred = Prediction.from_dict(sub)
            save_submission(pred, overwrite=True)

    # 4. Live predictions
    if "live_predictions" in data:
        preds = [LivePrediction.from_dict(lp) for lp in data["live_predictions"]]
        save_live_predictions(preds)

    # 5. Matches
    if "matches" in data:
        matches = [LiveMatch.from_dict(m) for m in data["matches"]]
        save_matches(matches)

    # 6. Events
    if "events" in data:
        write_json(EVENTS_PATH, data["events"])

    # 7. Migrations
    if "migrations" in data:
        save_migrations(data["migrations"])

    # 8. Reconstruct & Save registered participants
    registered = []
    if "registered_participants" in data and data["registered_participants"]:
        registered = data["registered_participants"]
    else:
        # Reconstruct from submissions and live predictions
        from .utils import normalize_participant_key
        seen_keys = set()
        # From submissions
        if "submissions" in data and data["submissions"]:
            for sub in data["submissions"]:
                pname = sub.get("participant")
                if pname:
                    pkey = normalize_participant_key(pname)
                    if pkey not in seen_keys:
                        seen_keys.add(pkey)
                        registered.append(pname)
        # From live predictions
        if "live_predictions" in data and data["live_predictions"]:
            for lp in data["live_predictions"]:
                pname = lp.get("participant_name")
                if pname:
                    pkey = normalize_participant_key(pname)
                    if pkey not in seen_keys:
                        seen_keys.add(pkey)
                        registered.append(pname)
    save_registered_participants(registered)

    # 9. Archived participants
    if "archived_participants" in data:
        save_archived_participants(data["archived_participants"])

    # 10. Advanced Brazil module files
    if "brasil_palpites_goleadores" in data:
        write_json(BRASIL_PALPITES_GOLEADORES_PATH, data["brasil_palpites_goleadores"])
    
    if "brasil_resultados_goleadores" in data:
        write_json(BRASIL_RESULTADOS_GOLEADORES_PATH, data["brasil_resultados_goleadores"])
        
    if "brasil_palpites_classicos" in data:
        write_json(BRASIL_PALPITES_CLASSICOS_PATH, data["brasil_palpites_classicos"])
        
    if "ranking_snapshots" in data:
        write_json(RANKING_SNAPSHOTS_PATH, data["ranking_snapshots"])
        
    if "comentarios_jogo" in data:
        write_json(COMENTARIOS_JOGO_PATH, data["comentarios_jogo"])



def reset_state() -> None:
    st.cache_data.clear()
    append_event("state_reset", "Todo o estado do bolão foi reiniciado pelo administrador.")
    ensure_state()

    for path in SUBMISSIONS_DIR.glob("*.json"):
        path.unlink()
    if OFFICIAL_PATH.exists():
        OFFICIAL_PATH.unlink()
    if MATCHES_PATH.exists():
        MATCHES_PATH.unlink()
    if LIVE_PREDICTIONS_PATH.exists():
        LIVE_PREDICTIONS_PATH.unlink()

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").delete().neq("id", "").execute()
                client.table("bolao_official").delete().eq("id", "official").execute()
                client.table("bolao_matches").delete().neq("match_id", "").execute()
                client.table("bolao_live_predictions").delete().neq("id", "").execute()
                client.table("bolao_events").delete().neq("id", "").execute()
                client.table("brasil_palpites_goleadores").delete().neq("id", "").execute()
                client.table("brasil_resultados_goleadores").delete().neq("jogo_id", "").execute()
            except Exception:
                pass


def load_demo_state() -> None:
    st.cache_data.clear()
    append_event("demo_loaded", "Dados de demonstração foram carregados pelo administrador.")
    ensure_state()
    backend = get_storage_backend()

    demo = DATA_DIR / "demo_state"
    demo_submissions = demo / "submissions"

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            for path in demo_submissions.glob("*.json"):
                pred = Prediction.from_dict(read_json(path, {}))
                save_submission(pred, overwrite=True)
            official = demo / "official_result.json"
            if official.exists():
                pred = Prediction.from_dict(read_json(official, {}))
                save_official(pred)
            return

    for path in demo_submissions.glob("*.json"):
        shutil.copy2(path, SUBMISSIONS_DIR / path.name)
    official = demo / "official_result.json"
    if official.exists():
        shutil.copy2(official, OFFICIAL_PATH)


from .events import append_event, load_events


class AppDataContext:
    def __init__(
        self,
        submissions: list[Prediction],
        official: Prediction | None,
        config: dict,
        matches: list[LiveMatch] | None = None,
        live_predictions: list[LivePrediction] | None = None,
        events: list[dict] | None = None
    ) -> None:
        self.submissions = submissions
        self.official = official
        self.config = config
        self.matches = matches if matches is not None else []
        self.live_predictions = live_predictions if live_predictions is not None else []
        self.events = events if events is not None else []


@st.cache_data(ttl=15, show_spinner=False)
def load_app_data_cached() -> AppDataContext:
    submissions = load_submissions()
    official = load_official()
    config = load_config()
    matches = load_matches()
    live_predictions = load_live_predictions()
    events = load_events(limit=100)
    return AppDataContext(
        submissions=submissions,
        official=official,
        config=config,
        matches=matches,
        live_predictions=live_predictions,
        events=events
    )


def load_app_context(include_events: bool = False) -> AppDataContext:
    ctx = load_app_data_cached()
    if not include_events:
        ctx.events = []
    return ctx


@st.cache_data(ttl=15, show_spinner=False)
def load_matches() -> list[LiveMatch]:
    ensure_state()

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_matches"):
            try:
                result = client.table("bolao_matches").select("*").execute()
                if result.data:
                    return _override_first_match_lock([LiveMatch.from_dict(row) for row in result.data])
            except Exception:
                pass

    # Seed matches from worldcup_2026_data.py if none exist in Supabase or locally
    from .worldcup_2026_data import GROUP_MATCHES, TEAMS
    matches = []
    for idx, gm in enumerate(GROUP_MATCHES):
        starts_at = f"{gm['date'].split('/')[2]}-{gm['date'].split('/')[1]}-{gm['date'].split('/')[0]}T{gm['hour']}:00"
        m = LiveMatch(
            match_id=str(gm["id"]),
            phase="grupos",
            group=gm["group"],
            round_label=f"Rodada {gm['round']}",
            home_team=TEAMS.get(gm["home_id"], {}).get("name", "Mandante"),
            away_team=TEAMS.get(gm["away_id"], {}).get("name", "Visitante"),
            starts_at=starts_at,
            starts_at_timezone="America/Sao_Paulo",
            lock_at=None,
            status="scheduled",
            sort_order=idx
        )
        matches.append(m)
    _override_first_match_lock(matches)
    save_matches(matches)
    return matches


def save_matches(matches: list[LiveMatch]) -> None:
    st.cache_data.clear()
    ensure_state()
    config = load_config()
    lock_mins = int(config.get("live_lock_minutes_before_match", 10))
    from datetime import datetime, timedelta
    for m in matches:
        if m.starts_at and not getattr(m, "has_custom_lock", False):
            try:
                dt = datetime.fromisoformat(m.starts_at)
                m.lock_at = (dt - timedelta(minutes=lock_mins)).isoformat()
            except Exception:
                pass
    
    write_json(MATCHES_PATH, [m.to_dict() for m in matches])

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_matches"):
            try:
                data = [m.to_dict() for m in matches]
                client.table("bolao_matches").upsert(data, on_conflict="match_id").execute()
            except Exception:
                pass


@st.cache_data(ttl=15, show_spinner=False)
def load_live_predictions(include_archived: bool = False) -> list[LivePrediction]:
    ensure_state()
    backend = get_storage_backend()
    archived_keys = set() if include_archived else get_archived_keys()

    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_live_predictions"):
            try:
                result = client.table("bolao_live_predictions").select("*").execute()
                preds = [LivePrediction.from_dict(row) for row in result.data if row.get("active") is not False]
                
                # Deduplicate loaded records
                from .utils import normalize_participant_key
                seen = {}
                for p in preds:
                    pkey = p.participant_key or normalize_participant_key(p.participant_name)
                    key = (pkey, str(p.match_id))
                    if key not in seen or (p.updated_at or p.submitted_at or "") >= (seen[key].updated_at or seen[key].submitted_at or ""):
                        seen[key] = p
                preds = list(seen.values())
                
                if not include_archived:
                    preds = [p for p in preds if p.participant_key not in archived_keys]
                return preds
            except Exception:
                pass

    if not LIVE_PREDICTIONS_PATH.exists():
        return []
    data = read_json(LIVE_PREDICTIONS_PATH, [])
    preds = [LivePrediction.from_dict(p) for p in data]
    
    # Deduplicate loaded records
    from .utils import normalize_participant_key
    seen = {}
    for p in preds:
        pkey = p.participant_key or normalize_participant_key(p.participant_name)
        key = (pkey, str(p.match_id))
        if key not in seen or (p.updated_at or p.submitted_at or "") >= (seen[key].updated_at or seen[key].submitted_at or ""):
            seen[key] = p
    preds = list(seen.values())

    if not include_archived:
        preds = [p for p in preds if p.participant_key not in archived_keys]
    return preds


def save_live_predictions(predictions: list[LivePrediction]) -> None:
    st.cache_data.clear()
    ensure_state()
    
    # Deduplicate in-memory to prevent duplicates
    from .utils import normalize_participant_key
    seen = {}
    for p in predictions:
        pkey = p.participant_key or normalize_participant_key(p.participant_name)
        key = (pkey, str(p.match_id))
        
        if key not in seen:
            seen[key] = p
        else:
            prev = seen[key]
            prev_is_std = (prev.id == f"{pkey}_{prev.match_id}")
            curr_is_std = (p.id == f"{pkey}_{p.match_id}")
            
            if curr_is_std and not prev_is_std:
                seen[key] = p
            elif prev_is_std and not curr_is_std:
                pass
            else:
                p_up = p.updated_at or p.submitted_at or ""
                prev_up = prev.updated_at or prev.submitted_at or ""
                if p_up >= prev_up:
                    seen[key] = p
                    
    predictions = list(seen.values())

    write_json(LIVE_PREDICTIONS_PATH, [p.to_dict() for p in predictions])

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_live_predictions"):
            try:
                data = [p.to_dict() for p in predictions]
                client.table("bolao_live_predictions").upsert(data, on_conflict="id").execute()
            except Exception:
                pass


def upsert_live_prediction(
    participant_name: str,
    match_id: str,
    home_goals: int,
    away_goals: int,
    confirmation_code: str | None = None
) -> LivePrediction:
    from .utils import format_display_name, normalize_participant_key, now_iso
    from .events import append_event
    
    # 1. Normalize name and key
    name_clean = format_display_name(participant_name)
    pkey = normalize_participant_key(name_clean)
    match_id = str(match_id)
    pred_id = f"{pkey}_{match_id}"
    
    # 2. Load live predictions
    preds = load_live_predictions(include_archived=True)
    
    existing = next((p for p in preds if p.id == pred_id), None)
    now = now_iso()
    
    if existing:
        if existing.predicted_home_goals != int(home_goals) or existing.predicted_away_goals != int(away_goals):
            existing.contador_edicoes = getattr(existing, "contador_edicoes", 0) + 1
        existing.predicted_home_goals = int(home_goals)
        existing.predicted_away_goals = int(away_goals)
        existing.updated_at = now
        if confirmation_code:
            existing.confirmation_code = confirmation_code
        pred_obj = existing
    else:
        pred_obj = LivePrediction(
            id=pred_id,
            participant_name=name_clean,
            participant_key=pkey,
            match_id=match_id,
            predicted_home_goals=int(home_goals),
            predicted_away_goals=int(away_goals),
            submitted_at=now,
            updated_at=now,
            confirmation_code=confirmation_code,
            is_locked=False,
            is_late=False,
            points=None,
            scoring_breakdown=[],
            contador_edicoes=0,
        )
        preds.append(pred_obj)
        
    save_live_predictions(preds)
    
    # 3. Handle registration on the fly for new participants
    registered = load_registered_participants(include_archived=True)
    if name_clean not in registered:
        registered.append(name_clean)
        save_registered_participants(registered)
        append_event("participant_registered", f"Participante {name_clean} se registrou jogando Jogo a Jogo.")
        
    return pred_obj


def load_migrations() -> dict:
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_config").select("value").eq("key", "migrations").execute()
                if result.data:
                    return result.data[0].get("value", {})
            except Exception:
                pass

    if not MIGRATIONS_PATH.exists():
        return {}
    return read_json(MIGRATIONS_PATH, {})


def save_migrations(migrations: dict) -> None:
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_config").upsert({
                    "key": "migrations",
                    "value": migrations,
                    "updated_at": now_iso(),
                }, on_conflict="key").execute()
                return
            except Exception:
                pass

    write_json(MIGRATIONS_PATH, migrations)


def load_registered_participants(include_archived: bool = False) -> list[str]:
    ensure_state()
    backend = get_storage_backend()
    archived_keys = set() if include_archived else get_archived_keys()

    parts_set = set()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_config").select("value").eq("key", "registered_participants").execute()
                if result.data:
                    parts = result.data[0].get("value", [])
                    for p in parts:
                        if p:
                            parts_set.add(p.strip())
            except Exception:
                pass
    if REGISTERED_PARTICIPANTS_PATH.exists():
        parts = read_json(REGISTERED_PARTICIPANTS_PATH, [])
        for p in parts:
            if p:
                parts_set.add(p.strip())

    # Include any participant from live predictions (so Jogo a Jogo users are first class)
    try:
        live_preds = load_live_predictions(include_archived=True)
        for lp in live_preds:
            if lp.participant_name:
                parts_set.add(lp.participant_name.strip())
    except Exception:
        pass

    # Include any participant from classic submissions
    try:
        submissions = load_submissions(include_archived=True)
        for s in submissions:
            if s.participant:
                parts_set.add(s.participant.strip())
    except Exception:
        pass

    # Convert to sorted list and filter out archived keys
    from .utils import normalize_participant_key
    sorted_parts = sorted(list(parts_set), key=lambda x: x.lower())
    if not include_archived:
        sorted_parts = [p for p in sorted_parts if normalize_participant_key(p) not in archived_keys]
    return sorted_parts


def load_archived_participants() -> list[dict]:
    if not ARCHIVED_PARTICIPANTS_PATH.exists():
        return []
    return read_json(ARCHIVED_PARTICIPANTS_PATH, [])


def save_archived_participants(archived: list[dict]) -> None:
    write_json(ARCHIVED_PARTICIPANTS_PATH, archived)


def get_archived_keys() -> set[str]:
    archived = load_archived_participants()
    return {p.get("participant_key") for p in archived if p.get("participant_key")}


def save_registered_participants(participants: list[str]) -> None:
    ensure_state()
    write_json(REGISTERED_PARTICIPANTS_PATH, participants)
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_config").upsert({
                    "key": "registered_participants",
                    "value": participants
                }, on_conflict="key").execute()
            except Exception:
                pass


def register_participant(name: str) -> None:
    name_clean = name.strip()
    if not name_clean:
        return
    current = load_registered_participants()
    exists = any(p.strip().lower() == name_clean.lower() for p in current)
    if not exists:
        current.append(name_clean)
        save_registered_participants(current)


def delete_registered_participant(name: str) -> None:
    name_clean = name.strip().lower()
    current = load_registered_participants()
    updated = [p for p in current if p.strip().lower() != name_clean]
    if len(updated) != len(current):
        save_registered_participants(updated)


def sync_official_results_to_matches() -> int:
    """
    Sincroniza os resultados oficiais do Modo Clássico (official_result.json)
    para os objetos LiveMatch, permitindo que o ranking Jogo a Jogo pontue.
    Retorna quantos matches foram atualizados.
    """
    official = load_official()
    if not official:
        return 0

    group_matches = official.meta.get("group_matches", {})
    if not group_matches:
        return 0

    matches = load_matches()
    config = load_config()
    live_preds = load_live_predictions()
    updated = 0

    matches_by_id = {m.match_id: m for m in matches}

    for m_id, scores in group_matches.items():
        if m_id not in matches_by_id:
            continue
        m = matches_by_id[m_id]
        if m.status == "result_approved":
            continue
        if not scores or len(scores) < 2:
            continue
        h, a = scores
        if h is None or a is None:
            continue

        m.official_home_goals = int(h)
        m.official_away_goals = int(a)
        m.status = "result_approved"
        if int(h) > int(a):
            m.winner = m.home_team
        elif int(h) < int(a):
            m.winner = m.away_team
        else:
            m.winner = "draw"
        updated += 1

    # Recalcular pontos de TODOS os palpites para matches aprovados
    # (sempre executa, mesmo sem novos syncs, pois palpites podem ter mudado)
    from .live_scoring import calculate_live_prediction_points
    for lp in live_preds:
        if lp.match_id in matches_by_id and matches_by_id[lp.match_id].status == "result_approved":
            m = matches_by_id[lp.match_id]
            res = calculate_live_prediction_points(lp, m, config)
            lp.points = res["points"]
            lp.scoring_breakdown = res["breakdown"]

    save_matches(matches)
    save_live_predictions(live_preds)
    return updated


def archive_participant(name: str, reason: str = "cleanup_requested_by_admin", backup_ref: str = "") -> bool:
    from .utils import normalize_participant_key, now_iso
    name_clean = name.strip()
    if not name_clean:
        return False
    key = normalize_participant_key(name_clean)
    
    # 1. Load active submissions to get info
    submissions = load_submissions(include_archived=True)
    live_preds = load_live_predictions(include_archived=True)
    
    had_classic = any(normalize_participant_key(s.participant) == key for s in submissions)
    live_count = sum(1 for lp in live_preds if lp.participant_key == key)
    
    # 2. Add to archived_participants.json
    archived = load_archived_participants()
    if any(p.get("participant_key") == key for p in archived):
        return False # already archived
        
    archived_entry = {
        "name": name_clean,
        "participant_key": key,
        "archived_at": now_iso(),
        "reason": reason,
        "had_classic_prediction": had_classic,
        "live_predictions_count": live_count,
        "backup_reference": backup_ref
    }
    archived.append(archived_entry)
    save_archived_participants(archived)
    
    # 3. Remove from registered_participants.json if present
    registered = load_registered_participants(include_archived=True)
    updated_registered = [p for p in registered if normalize_participant_key(p) != key]
    save_registered_participants(updated_registered)
    
    append_event("participant_archived", f"Participante {name_clean} foi arquivado.")
    return True


def restore_participant(pkey: str) -> bool:
    archived = load_archived_participants()
    match = next((p for p in archived if p.get("participant_key") == pkey), None)
    if not match:
        return False
        
    # Remove from archived_participants.json
    updated_archived = [p for p in archived if p.get("participant_key") != pkey]
    save_archived_participants(updated_archived)
    
    # Add back to registered_participants.json
    registered = load_registered_participants(include_archived=True)
    if pkey not in {normalize_participant_key(p) for p in registered}:
        registered.append(match["name"])
        save_registered_participants(registered)
        
    append_event("participant_restored", f"Participante {match['name']} foi restaurado.")
    return True

# Helper paths for advanced features
BRASIL_PALPITES_GOLEADORES_PATH = STATE_DIR / "brasil_palpites_goleadores.json"
BRASIL_RESULTADOS_GOLEADORES_PATH = STATE_DIR / "brasil_resultados_goleadores.json"
BRASIL_PALPITES_CLASSICOS_PATH = STATE_DIR / "brasil_palpites_classicos.json"
RANKING_SNAPSHOTS_PATH = STATE_DIR / "ranking_snapshots.json"
COMENTARIOS_JOGO_PATH = STATE_DIR / "comentarios_jogo.json"

def load_brasil_palpites_goleadores() -> list[dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("brasil_palpites_goleadores").select("*").execute()
                return res.data
            except Exception:
                pass
    if BRASIL_PALPITES_GOLEADORES_PATH.exists():
        return read_json(BRASIL_PALPITES_GOLEADORES_PATH, [])
    return []

def save_brasil_palpite_goleadores(palpite: dict) -> None:
    ensure_state()
    backend = get_storage_backend()
    current = load_brasil_palpites_goleadores()
    for i, p in enumerate(current):
        if p["participante_nome"] == palpite["participante_nome"] and p["jogo_id"] == palpite["jogo_id"]:
            current[i] = palpite
            break
    else:
        current.append(palpite)
    write_json(BRASIL_PALPITES_GOLEADORES_PATH, current)
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("brasil_palpites_goleadores").upsert(palpite, on_conflict="participante_nome,jogo_id").execute()
            except Exception:
                pass

def load_brasil_resultados_goleadores() -> dict[str, dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("brasil_resultados_goleadores").select("*").execute()
                return {row["jogo_id"]: row for row in res.data}
            except Exception:
                pass
    if BRASIL_RESULTADOS_GOLEADORES_PATH.exists():
        data = read_json(BRASIL_RESULTADOS_GOLEADORES_PATH, [])
        return {row["jogo_id"]: row for row in data}
    return {}

def save_brasil_resultado_goleadores(jogo_id: str, resultado: dict) -> None:
    ensure_state()
    backend = get_storage_backend()
    resultado["jogo_id"] = jogo_id
    current = load_brasil_resultados_goleadores()
    current[jogo_id] = resultado
    write_json(BRASIL_RESULTADOS_GOLEADORES_PATH, list(current.values()))
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("brasil_resultados_goleadores").upsert(resultado, on_conflict="jogo_id").execute()
            except Exception:
                pass

def load_brasil_palpites_classicos() -> list[dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("brasil_palpites_classicos").select("*").execute()
                return res.data
            except Exception:
                pass
    if BRASIL_PALPITES_CLASSICOS_PATH.exists():
        return read_json(BRASIL_PALPITES_CLASSICOS_PATH, [])
    return []

def save_brasil_palpite_classico(palpite: dict) -> None:
    ensure_state()
    backend = get_storage_backend()
    current = load_brasil_palpites_classicos()
    for i, p in enumerate(current):
        if p["participante_nome"] == palpite["participante_nome"]:
            current[i] = palpite
            break
    else:
        current.append(palpite)
    write_json(BRASIL_PALPITES_CLASSICOS_PATH, current)
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("brasil_palpites_classicos").upsert(palpite, on_conflict="participante_nome").execute()
            except Exception:
                pass

def load_ranking_snapshots() -> list[dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("ranking_snapshots").select("*").execute()
                return res.data
            except Exception:
                pass
    if RANKING_SNAPSHOTS_PATH.exists():
        return read_json(RANKING_SNAPSHOTS_PATH, [])
    return []

def save_ranking_snapshots(snapshots: list[dict]) -> None:
    ensure_state()
    backend = get_storage_backend()
    current = load_ranking_snapshots()
    for snap in snapshots:
        for i, existing in enumerate(current):
            if existing["rodada"] == snap["rodada"] and existing["participante_nome"] == snap["participante_nome"]:
                current[i] = snap
                break
        else:
            current.append(snap)
    write_json(RANKING_SNAPSHOTS_PATH, current)
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("ranking_snapshots").upsert(snapshots, on_conflict="rodada,participante_nome").execute()
            except Exception:
                pass

def load_comentarios_jogo(jogo_id: str) -> list[dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("comentarios_jogo").select("*").eq("jogo_id", jogo_id).order("created_at", desc=False).execute()
                return res.data
            except Exception:
                pass
    if COMENTARIOS_JOGO_PATH.exists():
        data = read_json(COMENTARIOS_JOGO_PATH, [])
        return [c for c in data if c["jogo_id"] == jogo_id and not c.get("deletado", False)]
    return []

def save_comentario_jogo(comentario: dict) -> None:
    ensure_state()
    backend = get_storage_backend()
    current = []
    if COMENTARIOS_JOGO_PATH.exists():
        current = read_json(COMENTARIOS_JOGO_PATH, [])
    current.append(comentario)
    write_json(COMENTARIOS_JOGO_PATH, current)
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("comentarios_jogo").insert(comentario).execute()
            except Exception:
                pass

def delete_comentario_jogo(comentario_id: str) -> None:
    ensure_state()
    backend = get_storage_backend()
    if COMENTARIOS_JOGO_PATH.exists():
        current = read_json(COMENTARIOS_JOGO_PATH, [])
        for c in current:
            if c.get("id") == comentario_id:
                c["deletado"] = True
        write_json(COMENTARIOS_JOGO_PATH, current)
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("comentarios_jogo").update({"deletado": True}).eq("id", comentario_id).execute()
            except Exception:
                pass


def load_all_comentarios() -> list[dict]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                res = client.table("comentarios_jogo").select("*").order("created_at", desc=True).execute()
                return res.data
            except Exception:
                pass
    if COMENTARIOS_JOGO_PATH.exists():
        return read_json(COMENTARIOS_JOGO_PATH, [])
    return []


def recalcular_pontos_modulo_brasil(jogo_id: str) -> None:
    from .live_scoring import calcular_pontos_goleadores
    config = load_config()
    palpites = load_brasil_palpites_goleadores()
    resultados = load_brasil_resultados_goleadores()
    
    real_res = resultados.get(jogo_id)
    if not real_res:
        return
        
    goleadores_reais = real_res.get("goleadores_reais", [])
    assistentes_reais = real_res.get("assistentes_reais", [])
    
    for gp in palpites:
        if gp.get("jogo_id") == jogo_id:
            pts_breakdown = calcular_pontos_goleadores(
                gp.get("goleadores", []),
                gp.get("assistentes", []),
                goleadores_reais,
                assistentes_reais,
                config,
                reservas_palpitadas=gp.get("reservas", [])
            )
            gp["pontos_ganhos"] = pts_breakdown["total"]
            save_brasil_palpite_goleadores(gp)


# ─── Artilheiro por Dia / Rodada ─────────────────────────────────────────────

ARTILHEIRO_DIA_PATH = STATE_DIR / "artilheiro_palpites_dia.json"
ARTILHEIRO_RODADA_PATH = STATE_DIR / "artilheiro_palpites_rodada.json"

def load_artilheiro_palpites_dia() -> list[dict]:
    ensure_state()
    if ARTILHEIRO_DIA_PATH.exists():
        return read_json(ARTILHEIRO_DIA_PATH, [])
    return []

def save_artilheiro_palpite_dia(palpite: dict) -> None:
    ensure_state()
    current = load_artilheiro_palpites_dia()
    key = (palpite["participante_nome"], palpite["data"])
    for i, p in enumerate(current):
        if p["participante_nome"] == key[0] and p["data"] == key[1]:
            current[i] = palpite
            break
    else:
        current.append(palpite)
    write_json(ARTILHEIRO_DIA_PATH, current)

def load_artilheiro_palpites_rodada() -> list[dict]:
    ensure_state()
    if ARTILHEIRO_RODADA_PATH.exists():
        return read_json(ARTILHEIRO_RODADA_PATH, [])
    return []

def save_artilheiro_palpite_rodada(palpite: dict) -> None:
    ensure_state()
    current = load_artilheiro_palpites_rodada()
    key = (palpite["participante_nome"], palpite["rodada"])
    for i, p in enumerate(current):
        if p["participante_nome"] == key[0] and p["rodada"] == key[1]:
            current[i] = palpite
            break
    else:
        current.append(palpite)
    write_json(ARTILHEIRO_RODADA_PATH, current)