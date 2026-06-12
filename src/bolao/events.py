from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
import streamlit as st
from .utils import now_iso, read_json, write_json

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
STATE_DIR = DATA_DIR / "state"
EVENTS_PATH = STATE_DIR / "events.json"

def append_event(kind: str, message: str, metadata: dict | None = None, visibility: str = "public") -> None:
    """
    Adiciona um novo evento ao feed de auditoria/atividades.
    """
    st.cache_data.clear()
    from .storage import get_storage_backend, _get_supabase_client, _supabase_table_exists
    
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    events = load_events(limit=200)
    
    event_id = str(uuid.uuid4())[:8]
    new_event = {
        "id": event_id,
        "timestamp": now_iso(),
        "kind": kind,
        "message": message,
        "visibility": visibility,
        "metadata": metadata or {}
    }
    
    # Insert at beginning
    events.insert(0, new_event)
    events = events[:100]
    
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_events"):
            try:
                client.table("bolao_events").insert(new_event).execute()
                return
            except Exception:
                pass
                
    write_json(EVENTS_PATH, events)


@st.cache_data(ttl=15, show_spinner=False)
def load_events(limit: int = 20, visibility: str | None = None) -> list[dict]:
    """
    Carrega eventos do local ou Supabase.
    """
    from .storage import get_storage_backend, _get_supabase_client, _supabase_table_exists
    
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_events"):
            try:
                query = client.table("bolao_events").select("*").order("timestamp", desc=True)
                if visibility:
                    query = query.eq("visibility", visibility)
                result = query.limit(limit).execute()
                return result.data
            except Exception:
                pass
                
    # Fallback to local
    if not EVENTS_PATH.exists():
        return []
    try:
        events = read_json(EVENTS_PATH, [])
        if visibility:
            events = [e for e in events if e.get("visibility", "public") == visibility]
        return events[:limit]
    except Exception:
        return []
