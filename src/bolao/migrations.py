from __future__ import annotations

import os
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime
import streamlit as st

from .storage import (
    load_submissions,
    save_submission,
    load_migrations,
    save_migrations,
    append_event,
    get_storage_backend,
    DATA_DIR,
    STATE_DIR,
    SUBMISSIONS_DIR,
    OFFICIAL_PATH,
    CONFIG_PATH,
    EVENTS_PATH,
    MATCHES_PATH,
    LIVE_PREDICTIONS_PATH,
    MIGRATIONS_PATH,
    load_config,
    save_config,
    load_live_predictions,
    load_matches
)
from .utils import now_iso, write_json, read_json

def get_git_info() -> tuple[str, str]:
    try:
        # Run git commands to get branch and commit
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], 
            stderr=subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parents[2])
        ).decode().strip()
        
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], 
            stderr=subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parents[2])
        ).decode().strip()
        return branch, commit
    except Exception:
        return "unknown", "unknown"

def migrate_to_parallel_modes() -> dict:
    """
    Realiza backup completo e migração idempotente para suportar os modos paralelos.
    """
    migrations = load_migrations()
    
    if migrations.get("parallel_modes_migration"):
        return {
            "status": "already_done",
            "message": "Migração de modos paralelos já executada anteriormente.",
            "migrated_count": 0
        }
        
    # 1. Realizar backup
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = DATA_DIR / "backups" / f"backup_before_public_analytics_live_parallel_{timestamp_str}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    files_copied = []
    # Copia a pasta state de forma recursiva
    if STATE_DIR.exists():
        state_backup_dest = backup_dir / "state"
        shutil.copytree(STATE_DIR, state_backup_dest, dirs_exist_ok=True)
        # Lista arquivos copiados para o manifest
        for root, _, files in os.walk(STATE_DIR):
            for file in files:
                rel_path = Path(root).relative_to(DATA_DIR) / file
                files_copied.append(str(rel_path))
                
    # Outros arquivos JSON diretamente em data/
    for p in DATA_DIR.glob("*.json"):
        shutil.copy2(p, backup_dir / p.name)
        files_copied.append(p.name)
        
    # Informações de Git
    branch, commit = get_git_info()
    
    # Contagens atuais
    try:
        submissions = load_submissions()
        classic_count = len(submissions)
    except Exception:
        classic_count = 0
        submissions = []
        
    try:
        live_preds = load_live_predictions()
        live_count = len(live_preds)
    except Exception:
        live_count = 0
        
    try:
        matches = load_matches()
        matches_count = len(matches)
    except Exception:
        matches_count = 0
        
    backend = get_storage_backend()
    
    # Criar manifest
    manifest = {
        "timestamp": now_iso(),
        "branch": branch,
        "commit": commit,
        "files_copied": files_copied,
        "classic_predictions_count": classic_count,
        "live_predictions_count": live_count,
        "matches_count": matches_count,
        "storage_backend": backend,
        "notes": "Backup executado antes da migração para modos paralelos (Clássico e Jogo a Jogo)."
    }
    
    # Cria o arquivo de manifest
    write_json(backup_dir / "backup_manifest.json", manifest)
    
    # 2. Executar migração de submissions clássicas
    migrated_count = 0
    for pred in submissions:
        needs_save = False
        if not pred.mode or pred.mode != "classic":
            pred.mode = "classic"
            needs_save = True
        if not pred.schema_version or pred.schema_version != "classic-v1":
            pred.schema_version = "classic-v1"
            needs_save = True
            
        if needs_save:
            save_submission(pred, overwrite=True)
            migrated_count += 1
            
    # 3. Criar arquivos vazios se não existirem
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not EVENTS_PATH.exists():
        write_json(EVENTS_PATH, [])
    if not LIVE_PREDICTIONS_PATH.exists():
        write_json(LIVE_PREDICTIONS_PATH, [])
    if not MATCHES_PATH.exists():
        # O arquivo será criado no primeiro load_matches()
        pass
        
    # 4. Estender as configurações padrão
    try:
        config = load_config()
        # Mesclar valores padrão
        from .storage import default_config
        defaults = default_config()
        updated = False
        for k, v in defaults.items():
            if k not in config:
                config[k] = v
                updated = True
            elif isinstance(v, dict) and isinstance(config[k], dict):
                # Update inner dicts (like live_scoring)
                for sub_k, sub_v in v.items():
                    if sub_k not in config[k]:
                        config[k][sub_k] = sub_v
                        updated = True
        if updated:
            save_config(config)
    except Exception:
        pass
        
    # 5. Registrar evento de migração
    append_event(
        kind="migration_executed",
        message=f"Migração parallel_modes executada. {migrated_count} submissões clássicas atualizadas."
    )
    
    # Salvar estado no log de migrations
    migrations["parallel_modes_migration"] = now_iso()
    save_migrations(migrations)
    
    return {
        "status": "success",
        "message": "Migração para modos paralelos e backup concluídos.",
        "migrated_count": migrated_count,
        "backup_path": str(backup_dir)
    }

def migrate_existing_submissions_to_classic_schema() -> dict:
    """
    Função legada para compatibilidade de inicialização em app.py.
    Executa a migração parallel_modes que engloba tudo.
    """
    return migrate_to_parallel_modes()


def sync_classic_to_live_predictions() -> int:
    """
    Sincroniza os palpites de fase de grupos clássicos para o Jogo a Jogo.
    Garante que todos os participantes com cartela clássica tenham seus palpites
    de grupos copiados para o banco de dados Jogo a Jogo, evitando que desapareçam.
    """
    try:
        from .storage import load_submissions, load_live_predictions, save_live_predictions
        from .models import LivePrediction
        from .utils import normalize_participant_key, now_iso
        
        submissions = load_submissions()
        live_preds = load_live_predictions()
        
        existing_ids = {p.id for p in live_preds}
        added_live_preds = False
        added_count = 0
        
        for pred in submissions:
            pkey = normalize_participant_key(pred.participant)
            group_matches = pred.meta.get("group_matches", {})
            for match_id, scores in group_matches.items():
                pred_id = f"{pkey}_{match_id}"
                if pred_id not in existing_ids:
                    home, away = scores
                    new_lp = LivePrediction(
                        id=pred_id,
                        participant_name=pred.participant,
                        participant_key=pkey,
                        match_id=str(match_id),
                        predicted_home_goals=int(home),
                        predicted_away_goals=int(away),
                        submitted_at=pred.submitted_at or now_iso(),
                        updated_at=pred.submitted_at or now_iso(),
                        confirmation_code=pred.submission_id,
                        locked_at=None,
                        is_locked=False,
                        is_late=False,
                        points=None,
                        scoring_breakdown=[],
                        schema_version="live-v1"
                    )
                    live_preds.append(new_lp)
                    existing_ids.add(pred_id)
                    added_live_preds = True
                    added_count += 1
                    
        if added_live_preds:
            save_live_predictions(live_preds)
        return added_count
    except Exception:
        return 0


def perform_pre_cleanup_backup() -> tuple[Path, Path]:
    """
    Executa backup completo de todos os dados do bolão antes da limpeza.
    """
    from .storage import (
        load_submissions,
        load_live_predictions,
        load_matches,
        load_official,
        load_config,
        load_events,
        get_storage_backend,
        _get_supabase_client
    )
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = DATA_DIR / "backups" / f"backup_before_cleanup_ui_mobile_{timestamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Copiar arquivos locais
    files_copied = []
    if STATE_DIR.exists():
        state_backup_dest = backup_dir / "state"
        shutil.copytree(STATE_DIR, state_backup_dest, dirs_exist_ok=True)
        for root, _, files in os.walk(STATE_DIR):
            for file in files:
                rel_path = Path(root).relative_to(DATA_DIR) / file
                files_copied.append(str(rel_path))
                
    for p in DATA_DIR.glob("*.json"):
        shutil.copy2(p, backup_dir / p.name)
        files_copied.append(p.name)
        
    # 2. Copiar dados do Supabase se ativo
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                for table in ["bolao_submissions", "bolao_live_predictions", "bolao_matches", "bolao_official", "bolao_config", "bolao_events"]:
                    res = client.table(table).select("*").execute()
                    with open(backup_dir / f"supabase_{table}.json", "w", encoding="utf-8") as f:
                        json.dump(res.data, f, ensure_ascii=False, indent=2)
                    files_copied.append(f"supabase_{table}.json")
            except Exception as e:
                raise RuntimeError(f"Falha ao realizar backup das tabelas do Supabase: {str(e)}")
                
    # 3. Informações de Git e estatísticas
    branch, commit = get_git_info()
    
    try:
        submissions = load_submissions()
        classic_count = len(submissions)
        names = set(s.participant for s in submissions)
    except Exception:
        classic_count = 0
        names = set()
        submissions = []
        
    try:
        live_preds = load_live_predictions()
        live_count = len(live_preds)
        for lp in live_preds:
            names.add(lp.participant_name)
    except Exception:
        live_count = 0
        
    manifest = {
        "timestamp": now_iso(),
        "branch": branch,
        "commit": commit,
        "storage_detected": backend,
        "classic_submissions_count": classic_count,
        "live_predictions_count": live_count,
        "participants_count": len(names),
        "participants_names": list(names),
        "files_copied": files_copied,
        "notes": "Backup executado antes da limpeza de participantes ativos."
    }
    
    write_json(backup_dir / "backup_manifest.json", manifest)
    
    archive_file = DATA_DIR / f"archived_removed_participants_{timestamp}.json"
    return backup_dir, archive_file


def cleanup_active_participants(allowed_names: set[str]) -> dict:
    """
    Remove do app ativo todos os participantes fora da allowlist,
    preservando backup/arquivo de arquivamento.
    """
    from .storage import (
        load_submissions,
        load_live_predictions,
        load_events,
        get_storage_backend,
        _get_supabase_client,
        save_live_predictions
    )
    from .utils import normalize_participant_key, safe_filename
    
    # 1. Executar backup obrigatório
    backup_dir, archive_file = perform_pre_cleanup_backup()
    
    submissions = load_submissions()
    live_preds = load_live_predictions()
    events = load_events(limit=1000)
    
    removed_participants = set()
    kept_participants = set()
    
    # Identificar removidos e mantidos
    for s in submissions:
        pkey = normalize_participant_key(s.participant)
        if pkey not in allowed_names:
            removed_participants.add(s.participant)
        else:
            kept_participants.add(s.participant)
            
    for lp in live_preds:
        pkey = lp.participant_key or normalize_participant_key(lp.participant_name)
        if pkey not in allowed_names:
            removed_participants.add(lp.participant_name)
        else:
            kept_participants.add(lp.participant_name)
            
    removed_subs = []
    kept_subs = []
    removed_live_preds = []
    kept_live_preds = []
    
    for s in submissions:
        pkey = normalize_participant_key(s.participant)
        if pkey not in allowed_names:
            removed_subs.append(s.to_dict())
        else:
            kept_subs.append(s)
            
    for lp in live_preds:
        pkey = lp.participant_key or normalize_participant_key(lp.participant_name)
        if pkey not in allowed_names:
            removed_live_preds.append(lp.to_dict())
        else:
            kept_live_preds.append(lp)
            
    # Filtrar eventos
    removed_events = []
    kept_events = []
    for ev in events:
        msg_lower = ev.get("message", "").lower()
        is_removed_rel = False
        for name in removed_participants:
            if name.lower() in msg_lower:
                is_removed_rel = True
                break
        if is_removed_rel:
            removed_events.append(ev)
        else:
            kept_events.append(ev)
            
    # 2. Criar arquivo de arquivamento dos removidos
    archive_data = {
        "timestamp": now_iso(),
        "reason": "cleanup_requested_by_admin_keep_only_baruja_henrique_fantato",
        "removed_participants": list(removed_participants),
        "submissions": removed_subs,
        "live_predictions": removed_live_preds,
        "events": removed_events
    }
    write_json(archive_file, archive_data)
    
    files_modified = [str(archive_file)]
    
    # 3. Aplicar exclusão/desativação no banco de dados ativo
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            # Soft delete no Supabase
            for name in removed_participants:
                pkey = normalize_participant_key(name)
                client.table("bolao_submissions").update({
                    "active": False,
                    "archived_reason": "cleanup_requested_by_admin"
                }).eq("participant", name).execute()
                
                client.table("bolao_live_predictions").update({
                    "active": False,
                    "archived_reason": "cleanup_requested_by_admin"
                }).eq("participant_key", pkey).execute()
                
            write_json(EVENTS_PATH, kept_events)
            files_modified.append(str(EVENTS_PATH))
    else:
        # Local JSON delete
        # Excluir arquivos de submissão
        for sub_dict in removed_subs:
            sub_id = sub_dict.get("submission_id")
            name = sub_dict.get("participant")
            filename = f"{safe_filename(name)}-{sub_id}.json"
            sub_file = SUBMISSIONS_DIR / filename
            if sub_file.exists():
                sub_file.unlink()
                files_modified.append(str(sub_file))
                
        # Atualizar live predictions
        save_live_predictions(kept_live_preds)
        files_modified.append(str(LIVE_PREDICTIONS_PATH))
        
        # Atualizar events
        write_json(EVENTS_PATH, kept_events)
        files_modified.append(str(EVENTS_PATH))
        
    st.cache_data.clear()
    
    return {
        "status": "success",
        "backup_path": str(backup_dir),
        "archive_path": str(archive_file),
        "kept_participants": list(kept_participants),
        "removed_participants": list(removed_participants),
        "files_modified": files_modified
    }


def load_archived_participants() -> dict:
    """
    Carrega todos os participantes arquivados nos arquivos de backup.
    Retorna dicionário agrupado por chave do participante.
    """
    from .utils import normalize_participant_key
    archived_data = {}
    if not DATA_DIR.exists():
        return archived_data
        
    for p in DATA_DIR.glob("archived_removed_participants_*.json"):
        try:
            data = read_json(p, {})
            if not data or "removed_participants" not in data:
                continue
            
            subs = {s.get("participant"): s for s in data.get("submissions", [])}
            preds_by_user = {}
            for lp in data.get("live_predictions", []):
                name = lp.get("participant_name")
                if name not in preds_by_user:
                    preds_by_user[name] = []
                preds_by_user[name].append(lp)
                
            for name in data.get("removed_participants", []):
                pkey = normalize_participant_key(name)
                if pkey not in archived_data:
                    archived_data[pkey] = {
                        "name": name,
                        "submission": subs.get(name),
                        "live_predictions": preds_by_user.get(name, []),
                        "archive_file": p.name
                    }
        except Exception:
            continue
            
    return archived_data


def restore_archived_participant(pkey: str) -> bool:
    """
    Restaura um participante arquivado re-adicionando seus dados no sistema ativo.
    """
    from .storage import save_submission, load_live_predictions, save_live_predictions, get_storage_backend, _get_supabase_client
    from .models import Prediction, LivePrediction
    
    archived = load_archived_participants()
    if pkey not in archived:
        return False
        
    p_data = archived[pkey]
    name = p_data["name"]
    
    backend = get_storage_backend()
    if backend == "supabase":
        client = _get_supabase_client()
        if client:
            try:
                client.table("bolao_submissions").update({
                    "active": True,
                    "archived_reason": None
                }).eq("participant", name).execute()
                
                client.table("bolao_live_predictions").update({
                    "active": True,
                    "archived_reason": None
                }).eq("participant_key", pkey).execute()
                
                st.cache_data.clear()
                return True
            except Exception:
                pass
                
    # Restaurar localmente
    if p_data["submission"]:
        pred = Prediction.from_dict(p_data["submission"])
        save_submission(pred, overwrite=True)
        
    if p_data["live_predictions"]:
        live_preds = load_live_predictions()
        existing_ids = {lp.id for lp in live_preds}
        
        for raw_lp in p_data["live_predictions"]:
            lp = LivePrediction.from_dict(raw_lp)
            if lp.id not in existing_ids:
                live_preds.append(lp)
        save_live_predictions(live_preds)
        
    st.cache_data.clear()
    return True


