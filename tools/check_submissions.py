"""Check bolao_submissions table"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)

from supabase import create_client
client = create_client(url, key)

r = client.table("bolao_submissions").select("*").execute()
print(f"bolao_submissions: {len(r.data)} rows")
for row in r.data:
    print(f"  id={row.get('id')} participant={row.get('participant')} status={row.get('status')} mode={row.get('mode')} ts={row.get('submitted_at')}")
    print(f"  keys: {list(row.keys())}")
    # Print group_matches count
    gm = row.get('meta', {}).get('group_matches', {}) if isinstance(row.get('meta'), dict) else {}
    filled = sum(1 for v in gm.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
    print(f"  group_matches filled: {filled}")
    break  # just first row
