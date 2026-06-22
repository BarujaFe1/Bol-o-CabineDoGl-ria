"""Full check of bolao_submissions and bolao_official"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)

from supabase import create_client
client = create_client(url, key)

print("=== bolao_submissions ===")
r = client.table("bolao_submissions").select("*").execute()
for row in r.data:
    p = row.get('participant')
    gm = row.get('meta', {}).get('group_matches', {}) if isinstance(row.get('meta'), dict) else {}
    filled = sum(1 for v in gm.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
    ko = row.get('meta', {}).get('knockout_matches', {}) if isinstance(row.get('meta'), dict) else {}
    ko_filled = sum(1 for v in ko.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
    print(f"  participant={p} status={row.get('status')} mode={row.get('mode')}")
    print(f"    submitted_at={row.get('submitted_at')} updated_at={row.get('updated_at')}")
    print(f"    group_matches: {filled}/72 filled")
    print(f"    knockout_matches: {ko_filled} filled")
    print(f"    id={row.get('id')}")
    groups = row.get('groups', {})
    if groups:
        filled_g = sum(1 for v in groups.values() if v)
        total_g = len(groups)
        print(f"    groups: {filled_g}/{total_g} filled")
    print()

print("=== bolao_official ===")
r = client.table("bolao_official").select("*").execute()
for row in r.data:
    p = row.get('participant')
    gm = row.get('meta', {}).get('group_matches', {}) if isinstance(row.get('meta'), dict) else {}
    filled = sum(1 for v in gm.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
    print(f"  participant={p} status={row.get('status')}")
    print(f"    group_matches: {filled}/72 filled")
    print(f"    updated_at={row.get('updated_at')}")
    print(f"    submited_at={row.get('submitted_at')}")
    # Check if groups is empty - this is the OFFICIAL results
    groups = row.get('groups', {})
    if groups:
        filled_g = sum(1 for v in groups.values() if v)
        print(f"    groups: {filled_g}/{len(groups)} filled")
    else:
        print(f"    groups: EMPTY")
    lk = row.get('palpites_lancados', {})
    print(f"    palpites_lancados: {len(lk)} entries")
