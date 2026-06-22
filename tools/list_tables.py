"""List all tables in Supabase schema"""
import json, os, re

with open('.streamlit/secrets.toml', 'r', encoding='utf-8') as f:
    c = f.read()
url = re.search(r'SUPABASE_URL\s*=\s*"([^"]+)"', c).group(1)
key = re.search(r'SUPABASE_SERVICE_ROLE_KEY\s*=\s*"([^"]+)"', c).group(1)

print(f"URL: {url}")

from supabase import create_client
client = create_client(url, key)

# Try querying information_schema.tables
r = client.table("information_schema.tables").select("table_name,table_schema").eq("table_schema","public").execute()
if r.data:
    print("Tables in public schema:")
    for t in r.data:
        print(f"  {t['table_name']}")
else:
    print(f"No data or error: {r}")
    # Try raw query
    try:
        r2 = client.rpc("get_tables").execute()
        print("RPC result:", r2)
    except Exception as e:
        print(f"RPC error: {e}")
    
    # Try rest.get directly
    try:
        import requests
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        r3 = requests.get(f"{url}/rest/v1/", headers=headers)
        print(f"GET /: {r3.status_code} {r3.text[:200]}")
    except Exception as e2:
        print(f"Request error: {e2}")
