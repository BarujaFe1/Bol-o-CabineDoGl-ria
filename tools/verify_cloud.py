"""Verify pushed data on Cloud"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)
from supabase import create_client
client = create_client(url, key)

print("=== bolao_official ===")
r = client.table("bolao_official").select("*").execute()
for row in r.data:
    gm = row.get('meta', {}).get('group_matches', {})
    filled = sum(1 for v in gm.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
    print(f"  status={row.get('status')} group_matches={filled}/72 ts={row.get('updated_at')}")

print("\n=== bolao_matches ===")
r = client.table("bolao_matches").select("match_id,status,official_home_goals,official_away_goals").execute()
approved = [m for m in r.data if m.get('status') == 'result_approved']
print(f"  Total: {len(r.data)}, Approved: {len(approved)}")
for m in approved[:5]:
    print(f"    {m['match_id']}: {m.get('official_home_goals')}x{m.get('official_away_goals')}")
if len(approved) > 5:
    print(f"    ... and {len(approved)-5} more")

print("\n=== bolao_live_predictions ===")
r = client.table("bolao_live_predictions").select("participant_name").execute()
from collections import Counter
counts = Counter(p['participant_name'] for p in r.data)
print(f"  Total: {len(r.data)}")
for n, c in sorted(counts.items()):
    print(f"    {n}: {c}")

print("\n=== VERIFICATION COMPLETE ===")
