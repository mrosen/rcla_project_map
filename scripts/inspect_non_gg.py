import urllib.request, os, json
from dotenv import load_dotenv

load_dotenv('/home/msr/rcla_project_map/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
req = urllib.request.Request(f'{url}/rest/v1/projects?select=*&order=id', headers=headers)
with urllib.request.urlopen(req) as resp:
    projects = json.loads(resp.read().decode())

for p in projects:
    if p.get('project_type') != 'Global Grant':
        print(f"[{p.get('id')}] ({p.get('project_type')}) {p.get('title')}")
        print(f"   Dates: {p.get('start_date') or p.get('start_year')} to {p.get('end_date') or p.get('end_year')}")
        print(f"   Intl Club: '{p.get('international_club_name')}' | Dist: '{p.get('international_club_district')}' | Shep: '{p.get('shepherd') or p.get('shepard')}' | Partner: '{p.get('partner')}'")
        desc = (p.get('brief_overview') or p.get('description') or '')
        print(f"   Brief/Desc: {desc[:100]}")
        print(f"   Details: {p.get('details')}")
        print()
