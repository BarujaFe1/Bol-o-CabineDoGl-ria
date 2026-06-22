"""Probe available Supabase tables"""
import json, os, re
with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)

from supabase import create_client
client = create_client(url, key)

tables = ['bolao_matches', 'bolao_official', 'bolao_live_predictions', 'bolao_events',
          'bolao_participants', 'brasil_grupos', 'bolao_scores', 'bolao_ranking',
          'brasil_rodadas', 'brasil_palpites_goleadores', 'brasil_resultados',
          'bolao_results', 'bolao_predictions', 'official_results', 'brasil_results',
          'bolao_submissions', 'bolao_classic_submissions']

for t in tables:
    try:
        r = client.table(t).select('*').limit(1).execute()
        print(f'{t}: OK ({len(r.data)} rows)')
    except Exception as e:
        msg = str(e)
        if 'Could not find the table' in msg:
            print(f'{t}: NOT FOUND')
        else:
            print(f'{t}: ERROR - {msg[:100]}')
