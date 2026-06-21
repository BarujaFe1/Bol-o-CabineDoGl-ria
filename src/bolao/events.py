from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
import streamlit as st
from .utils import now_iso, read_json, write_json

from .storage import DATA_DIR, STATE_DIR, EVENTS_PATH

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
def load_events(limit: int = 20, visibility: str | None = None, include_archived: bool = False) -> list[dict]:
    """
    Carrega eventos do local ou Supabase.
    """
    from .storage import get_storage_backend, _get_supabase_client, _supabase_table_exists
    
    events_list = []
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client and _supabase_table_exists(client, "bolao_events"):
            try:
                query = client.table("bolao_events").order("timestamp", desc=True)
                if visibility:
                    query = query.eq("visibility", visibility)
                result = query.limit(limit * 3).execute() # load extra to allow filtering
                events_list = result.data
            except Exception:
                pass
                
    if not events_list:
        # Fallback to local
        if not EVENTS_PATH.exists():
            return []
        try:
            events_list = read_json(EVENTS_PATH, [])
            if visibility:
                events_list = [e for e in events_list if e.get("visibility", "public") == visibility]
        except Exception:
            events_list = []

    if not include_archived and events_list:
        try:
            from .storage import load_archived_participants
            archived = load_archived_participants()
            archived_names = {p["name"].lower() for p in archived}
            filtered = []
            for ev in events_list:
                msg = ev.get("message", "").lower()
                if not any(name in msg for name in archived_names):
                    filtered.append(ev)
            events_list = filtered
        except Exception:
            pass

    return events_list[:limit]
