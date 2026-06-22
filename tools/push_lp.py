"""Check Cloud LP columns and push with safe field mapping"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)
from supabase import create_client
client = create_client(url, key)

# 1. Get Cloud LP schema
r = client.table('bolao_live_predictions').select('*').limit(1).execute()
cloud_keys = set(r.data[0].keys()) if r.data else set()
print(f"Cloud LP columns ({len(cloud_keys)}): {sorted(cloud_keys)}")

# 2. Get local LP fields
with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    local_lp = json.load(f)
local_keys = set(local_lp[0].keys()) if local_lp else set()
print(f"\nLocal LP fields ({len(local_keys)}): {sorted(local_keys)}")

# 3. Fields in local but not in Cloud
extra = local_keys - cloud_keys
missing = cloud_keys - local_keys
print(f"\nLocal has extra fields: {sorted(extra)}")
print(f"Cloud has extra fields: {sorted(missing)}")

# 4. Strip extra fields and push
safe_lp = []
stripped = set()
for p in local_lp:
    safe = {k: v for k, v in p.items() if k in cloud_keys}
    for k in extra:
        if k in p:
            stripped.add(k)
    safe_lp.append(safe)

print(f"\nPushing {len(safe_lp)} LP entries (stripped {sorted(stripped)})...")

batch_size = 50
for i in range(0, len(safe_lp), batch_size):
    batch = safe_lp[i:i+batch_size]
    client.table("bolao_live_predictions").upsert(batch, on_conflict="id").execute()
    print(f"  batch {i//batch_size + 1}/{(len(safe_lp)+batch_size-1)//batch_size} OK ({len(batch)} entries)")

print(f"Push complete!")
