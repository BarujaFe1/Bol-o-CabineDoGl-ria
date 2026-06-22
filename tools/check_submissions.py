import json, os

sub_dir = 'data/state/submissions'
for fn in sorted(os.listdir(sub_dir)):
    if not fn.endswith('.json') or fn == '.gitkeep':
        continue
    with open(os.path.join(sub_dir, fn), 'r', encoding='utf-8') as f:
        s = json.load(f)
    has_groups = bool(s.get('groups'))
    has_knockout = bool(s.get('knockout'))
    has_champion = bool(s.get('champion'))
    participant = s.get('participant', '?')
    key = s.get('participant_key', '?')
    print('{} ({}): groups={} knockout={} champion={}'.format(participant, key, has_groups, has_knockout, has_champion))
