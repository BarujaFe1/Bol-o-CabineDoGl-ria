"""Remove old 'Henrique' entries from Cloud LP (keep only Henrique O Terrível)"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)
from supabase import create_client
client = create_client(url, key)

# Find all Henrique (plain) entries
r = client.table("bolao_live_predictions").select("id").eq("participant_name", "Henrique").execute()
ids = [row['id'] for row in r.data]
print(f"Old 'Henrique' entries to remove: {len(ids)}")

if ids:
    # Delete in batches
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]
        # Supabase delete with 'in' filter
        client.table("bolao_live_predictions").delete().in_("id", batch).execute()
        print(f"  Deleted batch {i//batch_size + 1}")

# Verify
r = client.table("bolao_live_predictions").select("participant_name").execute()
from collections import Counter
counts = Counter(p['participant_name'] for p in r.data)
print(f"\nAfter cleanup: {len(r.data)} entries")
for n, c in sorted(counts.items()):
    print(f"  {n}: {c}")
