
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def render_countdown(horario_jogo: datetime, minutos_antes: int) -> str:
    br_tz = timezone(timedelta(hours=-3))
    agora = datetime.now(br_tz)
    # Ensure horario_jogo is timezone-aware for comparison
    if horario_jogo.tzinfo is None:
        horario_jogo = horario_jogo.replace(tzinfo=br_tz)
    else:
        horario_jogo = horario_jogo.astimezone(br_tz)
        
    fechamento = horario_jogo - timedelta(minutes=minutos_antes)
    delta = fechamento - agora
    segundos_restantes = int(delta.total_seconds())
    if segundos_restantes <= 0:
        return "🔒 FECHADO"
    
    dias, resto = divmod(segundos_restantes, 86400)
    h, resto = divmod(resto, 3600)
    m, s = divmod(resto, 60)
    if dias > 0:
        texto = f"{dias}d {h:02d}h{m:02d}m"
    else:
        texto = f"{h:02d}:{m:02d}:{s:02d}"
        
    if segundos_restantes < 1800:
        emoji = "🔴"
    elif segundos_restantes < 3600:
        emoji = "🟡"
    else:
        emoji = "🟢"
    return f"{emoji} Fecha em {texto}"


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
    import uuid
    import os
    import time
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        for i in range(5):
            try:
                os.replace(str(tmp_path), str(path))
                return
            except PermissionError:
                time.sleep(0.1)
            except FileNotFoundError:
                break
    except Exception:
        pass
    
    # Fallback to direct write if anything failed
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


def normalize_participant_key(name: str) -> str:
    """
    Gera chave estável a partir do nome.
    Lowercase, remove acento, trim, troca espaços por hífen.
    """
    val = strip_accents(name or "").lower().strip()
    val = re.sub(r"\s+", "-", val)
    if val == "henrique":
        return "henrique-o-terrivel"
    return val


def format_display_name(name: str) -> str:
    """
    Retorna o nome de exibição formatado/com alias.
    """
    key = normalize_participant_key(name)
    if key == "henrique-o-terrivel":
        return "Henrique O Terrível"
    if key == "baruja":
        return "Baruja"
    if key == "fantato":
        return "Fantato"
    return name.strip()


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


def buscar_jogador_copa(query: str, limite: int = 8) -> list[dict]:
    from .constants import JOGADORES_COPA_2026
    resultados = []
    q = strip_accents(query).lower().strip()
    if not q:
        return []
    for selecao, jogadores in JOGADORES_COPA_2026.items():
        for nome in jogadores:
            nome_clean = strip_accents(nome).lower()
            if q in nome_clean:
                resultados.append({"nome": nome, "selecao": selecao})
    # Prioritize matches that start with the query
    resultados.sort(key=lambda x: (not strip_accents(x["nome"]).lower().startswith(q), x["nome"]))
    return resultados[:limite]


def avatar_url(nome: str) -> str:
    import urllib.parse
    seed = urllib.parse.quote(nome.strip())
    return (f"https://api.dicebear.com/7.x/initials/svg"
            f"?seed={seed}&backgroundColor=1a472a&textColor=ffd700"
            f"&fontSize=38&fontWeight=700")


def foto_jogador(camisa: int, nome: str) -> str:
    import os
    import urllib.parse
    caminho_local = f"assets/players/camisa_{camisa:02d}.jpg"
    if os.path.exists(caminho_local):
        return caminho_local
    # Fallback: avatar DiceBear com iniciais, cores do bolão
    seed = urllib.parse.quote(nome.strip())
    return (f"https://api.dicebear.com/7.x/initials/svg"
            f"?seed={seed}&backgroundColor=1a472a&textColor=ffd700"
            f"&fontSize=38&fontWeight=700")
