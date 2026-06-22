import json

# Backup live predictions
with open('backup_geral_completo.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
b_lp = {p.get('id', 'no-id'): p for p in data.get('live_predictions', [])}

# State live predictions
with open('data/state/live_predictions.json', 'r', encoding='utf-8') as f:
    s_lp = {p.get('id', 'no-id'): p for p in json.load(f)}

# Root live predictions
with open('live_predictions.json', 'r', encoding='utf-8') as f:
    r_lp = {p.get('id', 'no-id'): p for p in json.load(f)}

print('Backup IDs:', len(b_lp))
print('State IDs:', len(s_lp))
print('Root IDs:', len(r_lp))

in_backup_not_state = set(b_lp.keys()) - set(s_lp.keys())
in_backup_not_root = set(b_lp.keys()) - set(r_lp.keys())
in_state_not_backup = set(s_lp.keys()) - set(b_lp.keys())
in_state_not_root = set(s_lp.keys()) - set(r_lp.keys())
in_root_not_backup = set(r_lp.keys()) - set(b_lp.keys())

print()
if in_backup_not_state:
    print('In backup but NOT in state:', len(in_backup_not_state))
    for rid in sorted(list(in_backup_not_state))[:10]:
        p = b_lp[rid]
        print('  {}: {} match={}'.format(rid, p.get('participant_name', '?'), p.get('match_id', '?')))
else:
    print('In backup but NOT in state: NONE')

if in_backup_not_root:
    print('In backup but NOT in root:', len(in_backup_not_root))
else:
    print('In backup but NOT in root: NONE')

if in_state_not_backup:
    print('In state but NOT in backup:', len(in_state_not_backup))
else:
    print('In state but NOT in backup: NONE')

if in_state_not_root:
    print('In state but NOT in root:', len(in_state_not_root))
    for rid in sorted(list(in_state_not_root))[:5]:
        p = s_lp[rid]
        print('  {}: {} match={}'.format(rid, p.get('participant_name', '?'), p.get('match_id', '?')))
else:
    print('In state but NOT in root: NONE')

if in_root_not_backup:
    print('In root but NOT in backup:', len(in_root_not_backup))
    for rid in sorted(list(in_root_not_backup))[:5]:
        p = r_lp[rid]
        print('  {}: {} match={}'.format(rid, p.get('participant_name', '?'), p.get('match_id', '?')))
else:
    print('In root but NOT in backup: NONE')
