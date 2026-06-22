"""
Download ALL data from Supabase (Cloud), compare with local, keep latest.
Usage: python tools/sync_from_cloud.py
"""
import json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Read credentials from secrets.toml
import re
secrets_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.streamlit', 'secrets.toml')
with open(secrets_path, 'r', encoding='utf-8') as f:
    secrets_content = f.read()

url_match = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', secrets_content)
key_match = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', secrets_content)

if not url_match or not key_match:
    print("ERROR: Supabase credentials not found in secrets.toml")
    sys.exit(1)

SUPABASE_URL = url_match.group(1)
SUPABASE_SERVICE_ROLE_KEY = key_match.group(1)

if 'SUA_' in SUPABASE_URL or 'SUA_' in SUPABASE_SERVICE_ROLE_KEY:
    print("ERROR: Supabase credentials still have placeholder values")
    sys.exit(1)

# Connect to Supabase
from supabase import create_client
client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

STATE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'state')

def read_local(filename):
    path = os.path.join(STATE_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def write_local(filename, data):
    path = os.path.join(STATE_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path

def safe_get(data, *keys):
    for k in keys:
        if isinstance(data, dict):
            data = data.get(k, {})
        else:
            return None
    return data

def trunc(s, n=80):
    return str(s)[:n] if s else ''

print("=== SYNC FROM SUPABASE CLOUD ===\n")

# 1. bolao_official
print("[1/6] Official result (bolao_official)...")
try:
    result = client.table("bolao_official").select("*").eq("id", "official").execute()
    if result.data:
        sb_official = result.data[0]
        local_official = read_local("official_result.json")
        sb_ts = sb_official.get("updated_at") or sb_official.get("submitted_at") or ""
        local_ts = ""
        if local_official:
            local_ts = local_official.get("updated_at") or local_official.get("submitted_at") or ""
        print(f"  Supabase timestamp: {sb_ts}")
        print(f"  Local timestamp:    {local_ts}")
        if sb_ts >= local_ts:
            write_local("official_result.json", sb_official)
            print(f"  -> Saved from Supabase (newer or equal)")
            # Count group_matches filled
            gms = safe_get(sb_official, 'meta', 'group_matches') or {}
            filled = sum(1 for v in gms.values() if isinstance(v, list) and len(v) >= 2 and v[0] is not None)
            print(f"  -> {filled} group matches filled")
        else:
            print(f"  -> Local is newer, keeping local")
    else:
        print("  -> No data in Supabase")
except Exception as e:
    print(f"  ERROR: {e}")

# 2. bolao_matches
print("\n[2/6] Matches (bolao_matches)...")
try:
    result = client.table("bolao_matches").select("*").execute()
    if result.data:
        sb_matches = result.data
        local_matches = read_local("matches_2026.json") or []
        sb_approved = sum(1 for m in sb_matches if m.get("status") == "result_approved")
        loc_approved = sum(1 for m in local_matches if m.get("status") == "result_approved")
        print(f"  Supabase: {len(sb_matches)} matches ({sb_approved} approved)")
        print(f"  Local:    {len(local_matches)} matches ({loc_approved} approved)")
        
        # Merge: for each match, keep the one with more recent data
        sb_by_id = {m.get("match_id"): m for m in sb_matches}
        loc_by_id = {m.get("match_id"): m for m in local_matches}
        
        merged = []
        for mid in set(list(sb_by_id.keys()) + list(loc_by_id.keys())):
            sb_m = sb_by_id.get(mid)
            loc_m = loc_by_id.get(mid)
            if sb_m and loc_m:
                # Keep the one with status "result_approved" (prefer approved)
                if sb_m.get("status") == "result_approved" and loc_m.get("status") != "result_approved":
                    merged.append(sb_m)
                elif loc_m.get("status") == "result_approved" and sb_m.get("status") != "result_approved":
                    merged.append(loc_m)
                else:
                    # Compare timestamps
                    sb_ts = sb_m.get("updated_at") or sb_m.get("submitted_at") or ""
                    loc_ts = loc_m.get("updated_at") or loc_m.get("submitted_at") or ""
                    merged.append(sb_m if sb_ts >= loc_ts else loc_m)
            elif sb_m:
                merged.append(sb_m)
            else:
                merged.append(loc_m)
        
        new_approved = sum(1 for m in merged if m.get("status") == "result_approved")
        print(f"  Merged: {len(merged)} matches ({new_approved} approved)")
        write_local("matches_2026.json", merged)
        print(f"  -> Saved merged matches")
    else:
        print("  -> No data in Supabase")
except Exception as e:
    print(f"  ERROR: {e}")

# 3. bolao_live_predictions
print("\n[3/6] Live predictions (bolao_live_predictions)...")
try:
    result = client.table("bolao_live_predictions").select("*").execute()
    if result.data:
        sb_lp = result.data
        local_lp = read_local("live_predictions.json") or []
        
        # Count by participant
        from collections import Counter
        sb_counts = Counter(p.get("participant_name", "?") for p in sb_lp)
        loc_counts = Counter(p.get("participant_name", "?") for p in local_lp)
        
        print(f"  Supabase: {len(sb_lp)} predictions")
        for n, c in sorted(sb_counts.items()):
            loc_c = loc_counts.get(n, 0)
            diff = "+" if c > loc_c else ("-" if c < loc_c else "=")
            print(f"    {n}: {c} (local: {loc_c}) {diff}")
        
        print(f"  Local:    {len(local_lp)} predictions")
        for n, c in sorted(loc_counts.items()):
            if n not in sb_counts:
                print(f"    {n}: {c} (NOT in Supabase)")
        
        # Merge: keep all predictions, dedup by (participant_key, match_id)
        # For duplicates, keep the one with newer timestamp
        from src.bolao.utils import normalize_participant_key
        
        merged = {}
        for p in local_lp:
            pkey = p.get("participant_key") or normalize_participant_key(p.get("participant_name", ""))
            key = (pkey, str(p.get("match_id", "")))
            ts = p.get("updated_at") or p.get("submitted_at") or ""
            if key not in merged or ts >= (merged[key].get("updated_at") or merged[key].get("submitted_at") or ""):
                merged[key] = p
        
        merged_from_sb = 0
        for p in sb_lp:
            pkey = p.get("participant_key") or normalize_participant_key(p.get("participant_name", ""))
            key = (pkey, str(p.get("match_id", "")))
            ts = p.get("updated_at") or p.get("submitted_at") or ""
            if key not in merged:
                merged[key] = p
                merged_from_sb += 1
            elif ts > (merged[key].get("updated_at") or merged[key].get("submitted_at") or ""):
                merged[key] = p
                merged_from_sb += 1
        
        merged_list = list(merged.values())
        merged_counts = Counter(p.get("participant_name", "?") for p in merged_list)
        print(f"  Merged: {len(merged_list)} predictions ({merged_from_sb} from Supabase)")
        for n, c in sorted(merged_counts.items()):
            print(f"    {n}: {c}")
        
        write_local("live_predictions.json", merged_list)
        print(f"  -> Saved merged live predictions")
    else:
        print("  -> No data in Supabase")
except Exception as e:
    print(f"  ERROR: {e}")

# 4. bolao_events
print("\n[4/6] Events (bolao_events)...")
try:
    result = client.table("bolao_events").select("*").order("timestamp", desc=True).limit(200).execute()
    if result.data:
        sb_events = result.data
        local_events = read_local("events.json") or []
        print(f"  Supabase: {len(sb_events)} events")
        print(f"  Local:    {len(local_events)} events")
        
        # Merge by ID
        sb_by_id = {e.get("id"): e for e in sb_events}
        loc_by_id = {e.get("id"): e for e in local_events}
        merged = list({**sb_by_id, **loc_by_id}.values())
        print(f"  Merged: {len(merged)} events")
        write_local("events.json", merged)
except Exception as e:
    print(f"  ERROR: {e}")

# 5. brasil_palpites_goleadores
print("\n[5/6] Brasil goleadores...")
try:
    result = client.table("brasil_palpites_goleadores").select("*").execute()
    if result.data:
        print(f"  Supabase: {len(result.data)} entries")
        write_local("brasil_palpites_goleadores.json", result.data)
except Exception as e:
    print(f"  ERROR: {e}")

# 6. brasil_resultados_goleadores
try:
    result = client.table("brasil_resultados_goleadores").select("*").execute()
    if result.data:
        print(f"  brasil_resultados_goleadores: {len(result.data)} entries")
        write_local("brasil_resultados_goleadores.json", result.data)
except Exception as e:
    print(f"  ERROR: {e}")

# 7. brasil_palpites_classicos
try:
    result = client.table("brasil_palpites_classicos").select("*").execute()
    if result.data:
        print(f"  brasil_palpites_classicos: {len(result.data)} entries")
        write_local("brasil_palpites_classicos.json", result.data)
except Exception as e:
    print(f"  ERROR: {e}")

print("\n=== SYNC COMPLETE ===")
