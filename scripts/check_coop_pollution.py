import json, os, urllib.request
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
req = urllib.request.Request(f"{url}/rest/v1/projects?select=id,title,partner,details", headers={"apikey": key, "Authorization": f"Bearer {key}"})
with urllib.request.urlopen(req) as resp:
    projects = json.loads(resp.read().decode())

print(f"Checking {len(projects)} projects for comma pollution in details.cooperating_organizations...")
polluted = []
for p in projects:
    pid = p.get("id")
    details = p.get("details") or {}
    if isinstance(details, str):
        try: details = json.loads(details)
        except Exception: details = {}
    coop = details.get("cooperating_organizations") or []
    if isinstance(coop, list):
        has_comma = any(isinstance(x, str) and "," in x for x in coop)
        if has_comma:
            polluted.append((pid, coop))

print(f"Found {len(polluted)} polluted projects:")
for pid, coop in polluted:
    print(f"  [{pid}]: {coop}")

