"""Push matches to Supabase"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)
from supabase import create_client
client = create_client(url, key)

# Get Cloud match columns
r = client.table('bolao_matches').select('*').limit(1).execute()
cloud_keys = set(r.data[0].keys()) if r.data else set()
print(f"Cloud match columns: {sorted(cloud_keys)}")

with open('data/state/matches_2026.json', 'r', encoding='utf-8') as f:
    matches = json.load(f)

local_approved = sum(1 for m in matches if m.get('status') == 'result_approved')
print(f"Local: {len(matches)} matches, {local_approved} approved")

# Strip extra fields
local_keys = set(matches[0].keys()) if matches else set()
extra = local_keys - cloud_keys
safe = []
for m in matches:
    safe.append({k: v for k, v in m.items() if k in cloud_keys})

print(f"Stripped extra fields: {sorted(extra)}")

batch_size = 50
for i in range(0, len(safe), batch_size):
    batch = safe[i:i+batch_size]
    client.table("bolao_matches").upsert(batch, on_conflict="match_id").execute()
    print(f"  batch {i//batch_size + 1} OK")

print(f"Matches push complete!")
