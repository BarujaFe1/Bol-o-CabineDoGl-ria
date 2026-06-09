from __future__ import annotations

import os
import shutil
from pathlib import Path

import streamlit as st

from .constants import DEFAULT_UNIFORM_RULES, DEFAULT_V2_RULES, DEFAULT_WEIGHTED_RULES
from .models import Prediction
from .utils import now_iso, read_json, safe_filename, stable_id, write_json
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
STATE_DIR = DATA_DIR / "state"
SUBMISSIONS_DIR = STATE_DIR / "submissions"
UPLOADS_DIR = STATE_DIR / "uploads"
OFFICIAL_PATH = STATE_DIR / "official_result.json"
CONFIG_PATH = STATE_DIR / "config.json"
EVENTS_PATH = STATE_DIR / "events.json"


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


def _ensure_supabase_tables(client) -> None:
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
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
    )


def ensure_state() -> None:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_PATH.exists():
        write_json(CONFIG_PATH, default_config())

    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            _ensure_supabase_tables(client)


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
    }


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


def load_submissions() -> list[Prediction]:
    ensure_state()
    backend = get_storage_backend()

    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                result = client.table("bolao_submissions").select("*").execute()
                return [Prediction.from_dict(row) for row in result.data]
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
    prediction.status = "aprovado"
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


def append_event(kind: str, message: str, metadata: dict | None = None) -> None:
    ensure_state()
    events = load_events(limit=200)
    
    from .utils import now_iso
    new_event = {
        "timestamp": now_iso(),
        "kind": kind,
        "message": message,
        "metadata": metadata or {}
    }
    events.insert(0, new_event)
    events = events[:100]
    write_json(EVENTS_PATH, events)


def load_events(limit: int = 20) -> list[dict]:
    ensure_state()
    if not EVENTS_PATH.exists():
        return []
    try:
        events = read_json(EVENTS_PATH, [])
        return events[:limit]
    except Exception:
        return []


@dataclass
class AppDataContext:
    submissions: list[Prediction]
    official: Prediction | None
    config: dict


@st.cache_data(ttl=15, show_spinner=False)
def load_app_data_cached() -> AppDataContext:
    submissions = load_submissions()
    official = load_official()
    config = load_config()
    return AppDataContext(submissions=submissions, official=official, config=config)