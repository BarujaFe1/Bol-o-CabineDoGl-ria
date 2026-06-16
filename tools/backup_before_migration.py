"""
Backup script: export all Supabase data to JSON before migration.

Usage:
  python tools/backup_before_migration.py

Requires:
  SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment or .env file
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

try:
    from supabase import create_client
except ImportError:
    print("❌ supabase-py not installed. Install with: pip install supabase")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Load credentials
url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("❌ SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment or .env file.")
    sys.exit(1)

sb = create_client(url, key)

tables = [
    "bolao_config",
    "bolao_submissions",
    "bolao_official",
    "bolao_live_predictions",
    "bolao_matches",
    "bolao_events",
]

backup = {}
for table in tables:
    try:
        result = sb.table(table).select("*").execute()
        backup[table] = result.data
        print(f"[OK] {table}: {len(result.data)} registros")
    except Exception as e:
        print(f"[WARN] {table}: {e}")
        backup[table] = []

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filename = f"backup_pre_migration_{timestamp}.json"

with open(filename, "w", encoding="utf-8") as f:
    json.dump(backup, f, ensure_ascii=False, indent=2, default=str)

print(f"\n[OK] Backup salvo em: {filename}")
print(f"   Total de registros: {sum(len(v) for v in backup.values())}")
