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


def get_storage_backend() -> str:
    try:
        client = _get_supabase_client()
        if client is not None:
            return "supabase"
    except Exception:
        pass
    return "local"


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
        import os as _os, psycopg2 as _pg

        db_url = _os.environ.get("SUPABASE_DB_URL") or ""
        db_pass = _os.environ.get("SUPABASE_DB_PASSWORD") or ""
        if not db_pass:
            try:
                db_url = st.secrets.get("SUPABASE_DB_URL", "")
                db_pass = st.secrets.get("SUPABASE_DB_PASSWORD", "")
            except Exception:
                pass

        url = _os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")

        if db_pass and url:
            project_ref = url.rstrip("/").split("//")[1].split(".")[0]
            conn = _pg.connect(
                host=f"db.{project_ref}.supabase.co",
                port=5432,
                dbname="postgres",
                user="postgres",
                password=db_pass,
                connect_timeout=10,
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(sql)
            cur.close()
            conn.close()
            for t in missing_tables:
                if _supabase_table_exists(client, t):
                    st.success(f"Tabela {t} criada automaticamente no Supabase.")
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


_submissions_synced = False


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
        "live_lock_minutes_before_match": 10,
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
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_config").upsert({"key": "main", "value": config, "updated_at": now_iso()}, on_conflict="key").execute()
                return
            except Exception:
                pass

    write_json(CONFIG_PATH, config)


@st.cache_data(ttl=15, show_spinner=False)
def load_submissions() -> list[Prediction]:
    ensure_state()
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_submissions").select("*").execute()
                return [Prediction.from_dict(row) for row in result.data if row.get("active") is not False]
            except Exception:
                pass

    submissions = []
    for path in sorted(SUBMISSIONS_DIR.glob("*.json")):
        try:
            submissions.append(Prediction.from_dict(read_json(path, {})))
        except Exception:
            continue
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
                return Path(f"supabase://submissions/{prediction.submission_id}")
            except Exception:
                pass

    filename = f"{safe_filename(prediction.participant)}-{prediction.submission_id}.json"
    path = SUBMISSIONS_DIR / filename
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    write_json(path, prediction.to_dict())
    return path


def delete_submission(submission_id: str) -> bool:
    st.cache_data.clear()
    ensure_state()
    
    # Try to find the participant name before deleting
    participant_name = "desconhecido"
    try:
        submissions = load_submissions()
        for p in submissions:
            if p.submission_id == submission_id:
                participant_name = p.participant
                break
    except Exception:
        pass

    backend = get_storage_backend()
    deleted = False

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").delete().eq("id", submission_id).execute()
                deleted = True
            except Exception:
                pass
    else:
        for path in SUBMISSIONS_DIR.glob("*.json"):
            try:
                data = read_json(path, {})
                if data.get("submission_id") == submission_id:
                    path.unlink()
                    deleted = True
                    break
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
                return Path("supabase://official_result")
            except Exception:
                pass

    write_json(OFFICIAL_PATH, prediction.to_dict())
    return OFFICIAL_PATH


def export_all_state() -> dict:
    return {
        "config": load_config(),
        "official": load_official().to_dict() if load_official() else None,
        "submissions": [p.to_dict() for p in load_submissions()],
        "live_predictions": [p.to_dict() for p in load_live_predictions()],
        "matches": [m.to_dict() for m in load_matches()],
        "events": load_events(limit=1000),
        "migrations": load_migrations(),
        "timestamp": now_iso(),
        "app_version": "2026-live-mode-v1"
    }


def reset_state() -> None:
    st.cache_data.clear()
    append_event("state_reset", "Todo o estado do bolão foi reiniciado pelo administrador.")
    ensure_state()
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").delete().neq("id", "").execute()
                client.table("bolao_official").delete().eq("id", "official").execute()
                return
            except Exception:
                pass

    for path in SUBMISSIONS_DIR.glob("*.json"):
        path.unlink()
    if OFFICIAL_PATH.exists():
        OFFICIAL_PATH.unlink()


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
    def _override_first_match_lock(matches_list: list[LiveMatch]) -> list[LiveMatch]:
        for m in matches_list:
            if m.match_id == "13379":
                m.lock_at = "2026-06-11T23:59:00"
        return matches_list

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
        if m.match_id == "13379":
            m.lock_at = "2026-06-11T23:59:00"
        elif m.starts_at:
            try:
                dt = datetime.fromisoformat(m.starts_at)
                m.lock_at = (dt - timedelta(minutes=lock_mins)).isoformat()
            except Exception:
                pass
    
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_matches"):
            try:
                data = [m.to_dict() for m in matches]
                client.table("bolao_matches").upsert(data, on_conflict="match_id").execute()
                return
            except Exception:
                pass

    write_json(MATCHES_PATH, [m.to_dict() for m in matches])


@st.cache_data(ttl=15, show_spinner=False)
def load_live_predictions() -> list[LivePrediction]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_live_predictions"):
            try:
                result = client.table("bolao_live_predictions").select("*").execute()
                return [LivePrediction.from_dict(row) for row in result.data if row.get("active") is not False]
            except Exception:
                pass

    if not LIVE_PREDICTIONS_PATH.exists():
        return []
    data = read_json(LIVE_PREDICTIONS_PATH, [])
    return [LivePrediction.from_dict(p) for p in data]


def save_live_predictions(predictions: list[LivePrediction]) -> None:
    st.cache_data.clear()
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_live_predictions"):
            try:
                data = [p.to_dict() for p in predictions]
                client.table("bolao_live_predictions").upsert(data, on_conflict="id").execute()
                return
            except Exception:
                pass

    write_json(LIVE_PREDICTIONS_PATH, [p.to_dict() for p in predictions])


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


def load_registered_participants() -> list[str]:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_config").select("value").eq("key", "registered_participants").execute()
                if result.data:
                    return result.data[0].get("value", [])
            except Exception:
                pass
    if not REGISTERED_PARTICIPANTS_PATH.exists():
        return []
    return read_json(REGISTERED_PARTICIPANTS_PATH, [])


def save_registered_participants(participants: list[str]) -> None:
    ensure_state()
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_config").upsert({
                    "key": "registered_participants",
                    "value": participants
                }, on_conflict="key").execute()
                return
            except Exception:
                pass
    write_json(REGISTERED_PARTICIPANTS_PATH, participants)


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