"""
Henrique (plain) and Henrique O Terrivel are the SAME person.
The normalize function maps both to 'henrique-o-terrivel'.
This script:
1. Changes all 'Henrique' predictions to use pkey='henrique-o-terrivel' and pname='Henrique O Terrivel'
2. For duplicate (pkey, match_id) pairs, keeps the one with newer timestamp
3. Removes duplicate registered participant entries
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Step 1: Fix live_predictions.json
with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    lp = json.load(f)

print("=== LIVE PREDICTIONS ===")
henrique_plain = [p for p in lp if p.get('participant_name') == 'Henrique']
henrique_ot = [p for p in lp if p.get('participant_name') == 'Henrique O Terr\u00edvel']
print("Henrique (plain): {} entries".format(len(henrique_plain)))
print("Henrique O Terrivel: {} entries".format(len(henrique_ot)))

# Change all "Henrique" entries to "Henrique O Terrivel" + correct key
updated = 0
for p in lp:
    if p.get('participant_name') == 'Henrique':
        old_key = p.get('participant_key', '')
        old_id = p.get('id', '')
        p['participant_name'] = 'Henrique O Terr\u00edvel'
        p['participant_key'] = 'henrique-o-terrivel'
        new_id = p['id'].replace(old_key, 'henrique-o-terrivel')
        if new_id == old_id:
            new_id = 'henrique-o-terrivel_' + p.get('match_id', '')
        p['id'] = new_id
        updated += 1

print("Updated {} entries to Henrique O Terrivel".format(updated))

# Now dedup: for (pkey, match_id) keep the best one
from src.bolao.utils import normalize_participant_key
from src.bolao.models import LivePrediction

preds = [LivePrediction.from_dict(p) for p in lp]
seen = {}
deduped_count = 0
for p in preds:
    pkey = p.participant_key or normalize_participant_key(p.participant_name)
    key = (pkey, str(p.match_id))
    if key not in seen:
        seen[key] = p
    else:
        prev = seen[key]
        prev_is_std = (prev.id == "{}_{}".format(pkey, prev.match_id))
        curr_is_std = (p.id == "{}_{}".format(pkey, p.match_id))
        if curr_is_std and not prev_is_std:
            seen[key] = p
        elif prev_is_std and not curr_is_std:
            pass
        else:
            p_up = p.updated_at or p.submitted_at or ""
            prev_up = prev.updated_at or prev.submitted_at or ""
            if p_up >= prev_up:
                seen[key] = p
            elif prev_up > p_up:
                pass
        deduped_count += 1

deduped = list(seen.values())
print("Dedup removed {} duplicates".format(deduped_count))
print("Total after dedup: {} entries".format(len(deduped)))

# Write cleaned file
with open('data/state/live_predictions.json', 'w', encoding='utf-8') as f:
    json.dump([p.to_dict() for p in deduped], f, ensure_ascii=False, indent=2)

from collections import Counter
counts = Counter(p.participant_name for p in deduped)
for name, c in sorted(counts.items()):
    print("  {}: {}".format(name, c))

# Step 2: Fix registered_participants.json
print("\n=== REGISTERED PARTICIPANTS ===")
with open('data/state/registered_participants.json', 'r', encoding='utf-8') as f:
    rp = json.load(f)
print("Before:", len(rp), rp)

# Remove "Henrique" duplicate, keep "Henrique O Terrivel"
rp = [p for p in rp if p != 'Henrique']
with open('data/state/registered_participants.json', 'w', encoding='utf-8') as f:
    json.dump(rp, f, ensure_ascii=False, indent=2)
print("After:", len(rp), rp)

print("\nDone!")
