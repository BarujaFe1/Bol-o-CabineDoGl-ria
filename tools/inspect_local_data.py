"""Inspect local data files committed to git, then migrate them to Supabase."""
import json
import os
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA_STATE = BASE / "data" / "state"
SUBMISSIONS_DIR = DATA_STATE / "submissions"

# 1. Inspect Live Predictions
lp_path = DATA_STATE / "live_predictions.json"
if lp_path.exists():
    with open(lp_path, "r", encoding="utf-8") as f:
        live_preds = json.load(f)
    print(f"[LIVE PREDICTIONS] {len(live_preds)} registros")
    if live_preds:
        print(f"  Primeiro: participant_name={live_preds[0].get('participant_name')}, match_id={live_preds[0].get('match_id')}")
        print(f"  Chaves: {list(live_preds[0].keys())}")
else:
    print("[LIVE PREDICTIONS] Arquivo não encontrado")
    live_preds = []

# 2. Inspect Submissions
sub_files = sorted(SUBMISSIONS_DIR.glob("*.json"))
print(f"\n[SUBMISSIONS] {len(sub_files)} arquivos")
for sf in sub_files:
    with open(sf, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta = data.get("meta")
    print(f"  {sf.name}: participant={data.get('participant')}, status={data.get('status')}, meta_type={type(meta).__name__}")

# 3. Inspect Official Result
off_path = DATA_STATE / "official_result.json"
if off_path.exists():
    with open(off_path, "r", encoding="utf-8") as f:
        off = json.load(f)
    print(f"\n[OFFICIAL] participant={off.get('participant')}, status={off.get('status')}")
else:
    print("\n[OFFICIAL] Não encontrado")

# 4. Inspect Config
cfg_path = DATA_STATE / "config.json"
if cfg_path.exists():
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    print(f"\n[CONFIG] Keys: {list(cfg.keys())}")
else:
    print("\n[CONFIG] Não encontrado")

# 5. Migrate to Supabase
print("\n" + "="*60)
print("MIGRATING TO SUPABASE...")
print("="*60)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY env vars")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("supabase-py not installed")
    sys.exit(1)

sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# Migrate Submissions
for sf in sub_files:
    with open(sf, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Fix meta if needed
    meta = data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    
    pred_id = data.get("submission_id") or sf.stem.split("-")[-1]
    
    row = {
        "id": pred_id,
        "participant": data.get("participant", "Participante"),
        "groups": data.get("groups", {}),
        "best_thirds": data.get("best_thirds"),
        "knockout": data.get("knockout", {}),
        "champion": data.get("champion"),
        "submission_id": pred_id,
        "submitted_at": data.get("submitted_at"),
        "status": data.get("status", "confirmado"),
        "meta": meta,
    }
    
    try:
        sb.table("bolao_submissions").upsert(row, on_conflict="id").execute()
        print(f"  [OK] Submission: {data.get('participant')}")
    except Exception as e:
        print(f"  [ERR] Submission {data.get('participant')}: {e}")

# Migrate Live Predictions
if live_preds:
    try:
        sb.table("bolao_live_predictions").upsert(live_preds, on_conflict="id").execute()
        print(f"  [OK] Live predictions: {len(live_preds)} registros")
    except Exception as e:
        print(f"  [ERR] Live predictions: {e}")

# Migrate Official
if off_path.exists():
    with open(off_path, "r", encoding="utf-8") as f:
        off_data = json.load(f)
    meta = off_data.get("meta")
    if not isinstance(meta, dict):
        meta = {}
    off_row = {
        "id": "official",
        "participant": "Resultado oficial",
        "groups": off_data.get("groups", {}),
        "best_thirds": off_data.get("best_thirds"),
        "knockout": off_data.get("knockout", {}),
        "champion": off_data.get("champion"),
        "submission_id": off_data.get("submission_id"),
        "submitted_at": off_data.get("submitted_at"),
        "status": off_data.get("status", "aprovado"),
        "meta": meta,
    }
    try:
        sb.table("bolao_official").upsert(off_row, on_conflict="id").execute()
        print(f"  [OK] Official result")
    except Exception as e:
        print(f"  [ERR] Official result: {e}")

# Migrate Config
if cfg_path.exists():
    try:
        sb.table("bolao_config").upsert({
            "key": "main",
            "value": cfg,
            "updated_at": None,
        }, on_conflict="key").execute()
        print(f"  [OK] Config")
    except Exception as e:
        print(f"  [ERR] Config: {e}")

print("\n[DONE] Migration complete!")
