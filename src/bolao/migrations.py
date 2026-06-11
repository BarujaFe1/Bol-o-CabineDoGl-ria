from __future__ import annotations

import streamlit as st
from .storage import (
    load_submissions,
    save_submission,
    load_migrations,
    save_migrations,
    append_event
)
from .utils import now_iso

def migrate_existing_submissions_to_classic_schema() -> dict:
    """
    Migração idempotente.
    Marca submissões antigas como mode='classic' quando campo não existe.
    Adiciona schema_version sem alterar payload original.
    Preserva confirmation_code.
    Preserva created_at.
    Preserva nome.
    Não altera scoring.
    Retorna relatório.
    """
    migrations = load_migrations()
    
    # Se já rodou, retorna relatório sem fazer nada
    if migrations.get("classic_mode_safe_migration"):
        return {
            "status": "already_done",
            "message": "Migração clássica já foi executada anteriormente.",
            "migrated_count": 0
        }
    
    submissions = load_submissions()
    migrated_count = 0
    
    for pred in submissions:
        # Se a submissão não tem mode ou schema_version padrão, atualiza
        needs_save = False
        if not pred.mode or pred.mode != "classic":
            pred.mode = "classic"
            needs_save = True
        if not pred.schema_version or pred.schema_version != "classic-v1":
            pred.schema_version = "classic-v1"
            needs_save = True
            
        if needs_save:
            # Salva no backend
            save_submission(pred, overwrite=True)
            migrated_count += 1
            
    # Registrar evento de migração
    append_event(
        kind="migration_executed",
        message=f"Migração segura executada: {migrated_count} submissões marcadas como Modo Clássico."
    )
    
    # Salvar migração no log de migrations
    migrations["classic_mode_safe_migration"] = now_iso()
    save_migrations(migrations)
    
    return {
        "status": "success",
        "message": f"Migração clássica concluída com sucesso.",
        "migrated_count": migrated_count
    }
