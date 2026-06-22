"""
Push corrected local data to Supabase:
- official_result.json (with 16 group matches)
- live_predictions.json (284 merged entries)
- registered_participants.json (Henrique deduped)
"""
import json, os, re, sys
from datetime import datetime

# Read creds
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)

from supabase import create_client
client = create_client(url, key)

STATE = 'data/state'
now = datetime.utcnow().isoformat() + '+00:00'

# 1. Push official_result
print("[1/3] Upserting official_result (bolao_official)...")
with open(f'{STATE}/official_result.json', 'r', encoding='utf-8') as f:
    official = json.load(f)

gm = official.get('meta', {}).get('group_matches', {})
filled = sum(1 for v in gm.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
print(f"  {filled} group matches filled")

official['updated_at'] = now
client.table("bolao_official").upsert(official, on_conflict="id").execute()
print(f"  Upsert OK")

# 2. Push live_predictions
print("\n[2/3] Upserting live_predictions (bolao_live_predictions)...")
with open(f'{STATE}/live_predictions.json', 'r', encoding='utf-8') as f:
    lp = json.load(f)
print(f"  {len(lp)} predictions")

from collections import Counter
counts = Counter(p.get('participant_name','?') for p in lp)
for n, c in sorted(counts.items()):
    print(f"    {n}: {c}")

batch_size = 50
for i in range(0, len(lp), batch_size):
    batch = lp[i:i+batch_size]
    # Add updated_at if missing
    for p in batch:
        if not p.get('updated_at') and not p.get('submitted_at'):
            p['updated_at'] = now
    client.table("bolao_live_predictions").upsert(batch, on_conflict="id").execute()
print(f"  Upsert OK ({len(lp)} entries)")

# 3. Push matches (optional, only if local has more approved)
print("\n[3/3] Checking matches...")
lc = 0  # local approved count
with open(f'{STATE}/matches_2026.json', 'r', encoding='utf-8') as f:
    local_matches = json.load(f)
lc = sum(1 for m in local_matches if m.get('status') == 'result_approved')
print(f"  Local: {lc} approved")

# Check Cloud approved count
r = client.table("bolao_matches").select('match_id,status').execute()
sc = sum(1 for m in r.data if m.get('status') == 'result_approved')
print(f"  Cloud: {sc} approved")

if lc > sc:
    print(f"  Upserting {len(local_matches)} matches...")
    for i in range(0, len(local_matches), batch_size):
        batch = local_matches[i:i+batch_size]
        client.table("bolao_matches").upsert(batch, on_conflict="match_id").execute()
    print(f"  Matches upsert OK")
else:
    print(f"  Cloud has equal or more approved matches, skipping")

print("\n=== PUSH COMPLETE ===")
