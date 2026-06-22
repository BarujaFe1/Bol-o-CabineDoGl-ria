"""
After sync_from_cloud.py, the LP file has both "Henrique" (72 from Cloud) 
and "Henrique O Terrível" (72 from local). Merge them into one.
"""
import json
from collections import Counter

with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    lp = json.load(f)

print(f"Total LP before merge: {len(lp)}")

# Count by name
counts = Counter(p.get('participant_name', '?') for p in lp)
for n, c in sorted(counts.items()):
    print(f"  {n}: {c}")

# Map old "Henrique" entries to "Henrique O Terrível"
import sys
sys.path.insert(0, 'src')
from bolao.utils import normalize_participant_key

henrique_plain = [p for p in lp if p.get('participant_name') == 'Henrique']
henrique_terrivel = [p for p in lp if p.get('participant_name') == 'Henrique O Terrível']

print(f"\nHenrique (plain): {len(henrique_plain)}")
print(f"Henrique O Terrível: {len(henrique_terrivel)}")

# For each Henrique plain entry, check if it already exists in Henrique O Terrível
ht_by_key = {}
for p in henrique_terrivel:
    pk = p.get('participant_key') or normalize_participant_key(p.get('participant_name', ''))
    mid = str(p.get('match_id', ''))
    ht_by_key[(pk, mid)] = p

new_entries = 0
overwritten = 0
final_lp = [p for p in lp if p.get('participant_name') != 'Henrique']

for p in henrique_plain:
    old_key = p.get('participant_key', '')
    p['participant_name'] = 'Henrique O Terrível'
    p['participant_key'] = 'henrique-o-terrivel'
    
    pk = 'henrique-o-terrivel'
    mid = str(p.get('match_id', ''))
    
    if (pk, mid) in ht_by_key:
        existing = ht_by_key[(pk, mid)]
        # Keep the one with newer timestamp
        ets = existing.get('updated_at') or existing.get('submitted_at') or ''
        pts = p.get('updated_at') or p.get('submitted_at') or ''
        if pts > ets:
            # Remove old, add new
            final_lp = [x for x in final_lp if not (
                x.get('participant_key') == pk and str(x.get('match_id', '')) == mid
            )]
            final_lp.append(p)
            overwritten += 1
    else:
        final_lp.append(p)
        new_entries += 1

print(f"\nNew entries from Supabase: {new_entries}")
print(f"Overwritten (newer ts): {overwritten}")

final_counts = Counter(p.get('participant_name', '?') for p in final_lp)
print(f"\nTotal LP after merge: {len(final_lp)}")
for n, c in sorted(final_counts.items()):
    print(f"  {n}: {c}")

with open('data/state/live_predictions.json', 'w', encoding='utf-8') as f:
    json.dump(final_lp, f, ensure_ascii=False, indent=2)
print("\nSaved.")
