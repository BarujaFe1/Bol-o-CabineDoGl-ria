import os
import shutil
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATE_DIR = DATA_DIR / "state"
SUBMISSIONS_DIR = STATE_DIR / "submissions"
BACKUPS_DIR = DATA_DIR / "backups"

def get_git_info():
    try:
        branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT)).decode().strip()
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(ROOT)).decode().strip()
        return branch, commit
    except Exception:
        return "unknown", "unknown"

def make_backup():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUPS_DIR / f"backup_before_uniformizacao_{timestamp}"
    backup_path.mkdir(parents=True, exist_ok=True)

    copied_files = []
    
    # Files in state dir to copy
    files_to_copy = [
        "config.json",
        "events.json",
        "live_predictions.json",
        "matches_2026.json",
        "migrations.json",
        "official_result.json",
        "registered_participants.json"
    ]
    
    # Copy direct state files
    for filename in files_to_copy:
        file_path = STATE_DIR / filename
        if file_path.exists():
            shutil.copy2(file_path, backup_path / filename)
            copied_files.append(filename)

    # Copy submissions
    backup_subs_dir = backup_path / "submissions"
    if SUBMISSIONS_DIR.exists():
        backup_subs_dir.mkdir(exist_ok=True)
        for sub_file in SUBMISSIONS_DIR.glob("*.json"):
            shutil.copy2(sub_file, backup_subs_dir / sub_file.name)
            copied_files.append(f"submissions/{sub_file.name}")

    # Count classic submissions
    num_submissions = 0
    if SUBMISSIONS_DIR.exists():
        num_submissions = len(list(SUBMISSIONS_DIR.glob("*.json")))

    # Count live predictions
    num_live_preds = 0
    live_preds_file = STATE_DIR / "live_predictions.json"
    if live_preds_file.exists():
        try:
            with open(live_preds_file, "r", encoding="utf-8") as f:
                num_live_preds = len(json.load(f))
        except Exception:
            pass

    # Git info
    branch, commit = get_git_info()

    # Create README.txt
    readme_content = f"""Data/Hora: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Branch Atual: {branch}
Commit Atual: {commit}
Arquivos Copiados:
{chr(10).join(f"- {f}" for f in copied_files)}
Quantidade de palpites clássicos encontrados: {num_submissions}
Quantidade de palpites jogo a jogo: {num_live_preds}
Storage Backend Detectado: local
Observações: Backup completo e timestampado antes da uniformização de produto.
"""
    with open(backup_path / "README.txt", "w", encoding="utf-8") as f:
        f.write(readme_content)

    # Create backup_manifest.json
    manifest = {
        "timestamp": datetime.now().isoformat(),
        "branch": branch,
        "commit": commit,
        "copied_files": copied_files,
        "num_classic_predictions": num_submissions,
        "num_live_predictions": num_live_preds,
        "secrets_ignored": True,
        "storage_backend": "local"
    }
    with open(backup_path / "backup_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print(f"Backup concluído com sucesso em: {backup_path}")
    print(f"Total de palpites clássicos: {num_submissions}")
    print(f"Total de palpites jogo a jogo: {num_live_preds}")
    return str(backup_path)

if __name__ == "__main__":
    make_backup()
