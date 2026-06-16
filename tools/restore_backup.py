import json
import os
import re
import unicodedata
from pathlib import Path

# Paths
BACKUP_GERAL_PATH = Path("backup/backup_geral_completo.json")
BACKUP_LIVE_PATH = Path("backup/live_predictions.json")
STATE_DIR = Path("data/state")
SUBMISSIONS_DIR = STATE_DIR / "submissions"

def strip_accents(value: str) -> str:
    value = "" if value is None else str(value)
    normalized = unicodedata.normalize("NFD", value)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")

def norm_text(value: str) -> str:
    value = strip_accents(value).lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def safe_filename(value: str) -> str:
    value = norm_text(value)
    value = re.sub(r"\s+", "-", value).strip("-")
    return value or "participante"

def restore():
    print("Iniciando restauração a partir do backup...")

    # Ensure directories exist
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load backup_geral_completo.json
    if not BACKUP_GERAL_PATH.exists():
        print(f"Erro: {BACKUP_GERAL_PATH} não encontrado.")
        return

    with open(BACKUP_GERAL_PATH, "r", encoding="utf-8") as f:
        geral = json.load(f)

    # Restore config
    if "config" in geral and geral["config"]:
        with open(STATE_DIR / "config.json", "w", encoding="utf-8") as f:
            json.dump(geral["config"], f, indent=2, ensure_ascii=False)
        print("Configurações restauradas.")

    # Restore official_result
    if "official" in geral and geral["official"]:
        with open(STATE_DIR / "official_result.json", "w", encoding="utf-8") as f:
            json.dump(geral["official"], f, indent=2, ensure_ascii=False)
        print("Resultado oficial clássico restaurado.")

    # Restore matches
    if "matches" in geral and geral["matches"]:
        with open(STATE_DIR / "matches_2026.json", "w", encoding="utf-8") as f:
            json.dump(geral["matches"], f, indent=2, ensure_ascii=False)
        print("Agenda de partidas restaurada.")

    # Restore events
    if "events" in geral and geral["events"]:
        with open(STATE_DIR / "events.json", "w", encoding="utf-8") as f:
            json.dump(geral["events"], f, indent=2, ensure_ascii=False)
        print("Feed de eventos restaurado.")

    # Restore migrations
    if "migrations" in geral and geral["migrations"]:
        with open(STATE_DIR / "migrations.json", "w", encoding="utf-8") as f:
            json.dump(geral["migrations"], f, indent=2, ensure_ascii=False)
        print("Migrations restauradas.")

    # Restore classic submissions with canonical names
    if "submissions" in geral and geral["submissions"]:
        # Clear existing submissions to prevent mixing
        for p in SUBMISSIONS_DIR.glob("*.json"):
            p.unlink()
        
        for sub in geral["submissions"]:
            sub_id = sub.get("submission_id")
            participant = sub.get("participant", "participante")
            if sub_id:
                filename = f"{safe_filename(participant)}-{sub_id}.json"
                with open(SUBMISSIONS_DIR / filename, "w", encoding="utf-8") as f:
                    json.dump(sub, f, indent=2, ensure_ascii=False)
        print(f"{len(geral['submissions'])} palpites clássicos restaurados.")

    # 2. Restore live predictions
    live_preds = []
    if BACKUP_LIVE_PATH.exists():
        with open(BACKUP_LIVE_PATH, "r", encoding="utf-8") as f:
            live_preds = json.load(f)
        with open(STATE_DIR / "live_predictions.json", "w", encoding="utf-8") as f:
            json.dump(live_preds, f, indent=2, ensure_ascii=False)
        print(f"{len(live_preds)} palpites Jogo a Jogo restaurados de backup/live_predictions.json.")
    elif "live_predictions" in geral and geral["live_predictions"]:
        live_preds = geral["live_predictions"]
        with open(STATE_DIR / "live_predictions.json", "w", encoding="utf-8") as f:
            json.dump(live_preds, f, indent=2, ensure_ascii=False)
        print(f"{len(live_preds)} palpites Jogo a Jogo restaurados de backup_geral_completo.json.")

    # 3. Restore/Reconstruct registered participants
    registered_participants = []
    if "registered_participants" in geral and geral["registered_participants"]:
        registered_participants = geral["registered_participants"]
        print("Participantes registrados restaurados diretamente do backup.")
    else:
        # Reconstruct from submissions and live predictions
        seen_keys = set()
        if "submissions" in geral and geral["submissions"]:
            for sub in geral["submissions"]:
                pname = sub.get("participant")
                if pname:
                    pkey = norm_text(pname)
                    if pkey not in seen_keys:
                        seen_keys.add(pkey)
                        registered_participants.append(pname)
        if live_preds:
            for lp in live_preds:
                pname = lp.get("participant_name")
                if pname:
                    pkey = norm_text(pname)
                    if pkey not in seen_keys:
                        seen_keys.add(pkey)
                        registered_participants.append(pname)
        print(f"Reconstruídos {len(registered_participants)} participantes registrados a partir dos palpites.")

    if registered_participants:
        # Read currently registered participants and merge to be safe
        curr_path = STATE_DIR / "registered_participants.json"
        if curr_path.exists():
            try:
                with open(curr_path, "r", encoding="utf-8") as f:
                    curr_list = json.load(f)
                if isinstance(curr_list, list):
                    seen = set(norm_text(p) for p in registered_participants)
                    for p in curr_list:
                        if norm_text(p) not in seen:
                            registered_participants.append(p)
                            seen.add(norm_text(p))
            except Exception:
                pass
        
        with open(STATE_DIR / "registered_participants.json", "w", encoding="utf-8") as f:
            json.dump(registered_participants, f, indent=2, ensure_ascii=False)
        print(f"Total de {len(registered_participants)} participantes registrados salvos.")

    # Restore archived participants
    if "archived_participants" in geral and geral["archived_participants"]:
        with open(STATE_DIR / "archived_participants.json", "w", encoding="utf-8") as f:
            json.dump(geral["archived_participants"], f, indent=2, ensure_ascii=False)
        print("Participantes arquivados restaurados.")

    print("Restauração concluída com sucesso!")

if __name__ == "__main__":
    restore()
