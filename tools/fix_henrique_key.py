"""Fix Henrique's participant_key from henrique-o-terrivel to henrique"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.bolao.utils import normalize_participant_key

with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    lp = json.load(f)

print("Total LP before:", len(lp))

fixed = 0
for p in lp:
    pname = p.get('participant_name', '')
    pkey = p.get('participant_key', '')
    correct_key = normalize_participant_key(pname)
    if pname == 'Henrique' and pkey != correct_key:
        old_key = pkey
        p['participant_key'] = correct_key
        # Also fix the id field to match
        old_id = p.get('id', '')
        p['id'] = p['id'].replace(old_key, correct_key)
        print("  Fixed: {} -> {} (id: {} -> {})".format(old_key, correct_key, old_id, p['id']))
        fixed += 1

if fixed > 0:
    with open('data/state/live_predictions.json', 'w', encoding='utf-8') as f:
        json.dump(lp, f, ensure_ascii=False, indent=2)
    print("\nFixed {} entries. Verifying dedup...".format(fixed))
else:
    print("No entries to fix.")

# Verify dedup now works
from src.bolao.models import LivePrediction
preds = [LivePrediction.from_dict(p) for p in lp]

seen = {}
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

deduped = list(seen.values())
print("After dedup: {} entries".format(len(deduped)))
from collections import Counter
counts = Counter(p.participant_name for p in deduped)
for name, c in sorted(counts.items()):
    print("  {}: {}".format(name, c))

# Also save the deduped version (clean)
with open('data/state/live_predictions.json', 'w', encoding='utf-8') as f:
    json.dump([p.to_dict() for p in deduped], f, ensure_ascii=False, indent=2)
print("\nSaved clean version with {} entries".format(len(deduped)))
