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
