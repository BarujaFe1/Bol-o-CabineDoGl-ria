
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def strip_accents(value: str) -> str:
    value = "" if value is None else str(value)
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def norm_text(value: str) -> str:
    value = strip_accents(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def norm_team(value: str | None) -> str:
    return norm_text(value or "")


def safe_filename(value: str) -> str:
    value = norm_text(value)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value or "participante"


def stable_id(*parts: str) -> str:
    raw = "|".join(parts).encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()[:12]


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def decode_uploaded_file(file) -> str:
    raw = file.getvalue()
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def short(value: str, size: int = 12) -> str:
    value = value or ""
    return value if len(value) <= size else value[: size - 1] + "…"


def canonical_team(value: str | None) -> str | None:
    """Converte nomes/abreviações comuns para o nome canônico usado no sistema.

    Mantém o texto original quando não encontra alias, para não apagar dado que o
    participante informou.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        from .constants import TEAM_ALIASES
    except Exception:
        return raw
    clean = norm_text(raw)
    for canonical, aliases in TEAM_ALIASES.items():
        candidates = [canonical, *aliases]
        if any(clean == norm_text(candidate) for candidate in candidates):
            return canonical
    return raw


def is_debug_mode() -> bool:
    import os
    import streamlit as st
    try:
        if "DEBUG_MODE" in st.secrets:
            return str(st.secrets["DEBUG_MODE"]).lower() in ("true", "1", "yes")
    except Exception:
        pass
    return os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes")
