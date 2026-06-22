"""Debug why Henrique's predictions are dropped during save_live_predictions"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    raw_lp = json.load(f)

print("Total raw entries:", len(raw_lp))

# Check Henrique entries
henrique = [p for p in raw_lp if 'Henrique' in p.get('participant_name', '')]
print("Henrique* entries:", len(henrique))

for p in henrique[:5]:
    print("  pkey={} pname={} match={} id={}".format(
        p.get('participant_key', 'NONE'),
        p.get('participant_name'),
        p.get('match_id'),
        p.get('id')
    ))

# Check if any Henrique entries have participant_key = 'testador-sanca' or something weird
from src.bolao.utils import normalize_participant_key
for p in henrique:
    pkey = p.get('participant_key') or normalize_participant_key(p.get('participant_name', ''))
    if pkey == 'testador-sanca':
        print("FOUND: Henrique mapped to testador-sanca!")
        print("  full:", json.dumps(p, ensure_ascii=False))

# Check TestUser
testuser = [p for p in raw_lp if 'TestUser' in p.get('participant_name', '')]
print("\nTestUser entries:", len(testuser))
for p in testuser[:5]:
    pkey = p.get('participant_key') or normalize_participant_key(p.get('participant_name', ''))
    print("  pkey={} pname={} match={} id={}".format(
        pkey, p.get('participant_name'), p.get('match_id'), p.get('id')
    ))

# Simulate the cleanup filter: remove TestUser
kept = [p for p in raw_lp if p.get('participant_name') not in ['Testador Sanca', 'TestUser']]
print("\nAfter filtering TestUser/Testador Sanca:", len(kept))

# Now simulate what save_live_predictions dedup does
from src.bolao.models import LivePrediction
preds = [LivePrediction.from_dict(p) for p in kept]

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
print("After dedup:", len(deduped))

# Count by participant
from collections import Counter
counts = Counter(p.participant_name for p in deduped)
for name, c in sorted(counts.items()):
    print("  {}: {}".format(name, c))
