import json, re

# Root live predictions
with open('live_predictions.json', 'r') as f:
    content = f.read()
    root_lp = json.loads(content)

names = {}
for p in root_lp:
    n = p.get('participant_name', '?')
    names[n] = names.get(n, 0) + 1

print('=== ROOT live_predictions.json ===')
print('Total:', len(root_lp))
for n, c in sorted(names.items()):
    print('  {}: {}'.format(repr(n), c))

print()

# State live predictions
with open('data/state/live_predictions.json', 'r') as f:
    state_lp = json.load(f)

names2 = {}
for p in state_lp:
    n = p.get('participant_name', '?')
    names2[n] = names2.get(n, 0) + 1

print('=== STATE data/state/live_predictions.json ===')
print('Total:', len(state_lp))
for n, c in sorted(names2.items()):
    print('  {}: {}'.format(repr(n), c))

print()

# Backup live predictions
with open('backup_geral_completo.json', 'r') as f:
    bdata = json.load(f)
backup_lp = bdata.get('live_predictions', [])

names3 = {}
for p in backup_lp:
    n = p.get('participant_name', '?')
    names3[n] = names3.get(n, 0) + 1

print('=== BACKUP live_predictions ===')
print('Total:', len(backup_lp))
for n, c in sorted(names3.items()):
    print('  {}: {}'.format(repr(n), c))

# Check what Henrique O Terrivel preds look like in root
print()
print('=== Henrique O Terrivel in ROOT ===')
for p in root_lp:
    n = p.get('participant_name', '')
    if 'Henrique' in n:
        print('  match={} home={} away={}'.format(
            p.get('match_id'), p.get('predicted_home_goals'), p.get('predicted_away_goals')))

print()
print('=== Henrique O Terrivel in STATE ===')
for p in state_lp:
    n = p.get('participant_name', '')
    if 'Henrique' in n:
        print('  match={} home={} away={}'.format(
            p.get('match_id'), p.get('predicted_home_goals'), p.get('predicted_away_goals')))
