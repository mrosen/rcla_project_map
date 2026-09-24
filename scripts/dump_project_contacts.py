import json, os, urllib.request
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

req = urllib.request.Request(f"{url}/rest/v1/projects?select=*", headers=headers)
with urllib.request.urlopen(req) as resp:
    projects = json.loads(resp.read().decode())

print(f"Total projects: {len(projects)}")
print("=" * 80)
for p in projects:
    pid = p.get("id")
    title = p.get("title")
    ptype = p.get("project_type")
    intl_club = p.get("international_club_name")
    intl_dist = p.get("international_club_district")
    shep = p.get("shepherd") or p.get("shepard")
    partner = p.get("partner")
    details = p.get("details") or {}
    
    print(f"[{pid}] {title}")
    print(f"  Type: {ptype} | Dates: {p.get('start_date') or p.get('start_year')} to {p.get('end_date') or p.get('end_year')}")
    print(f"  Intl Club: '{intl_club}' | Intl Dist: '{intl_dist}' | Shepherd: '{shep}'")
    if partner:
        print(f"  Partner col: '{partner}'")
    if details:
        # print non-empty keys in details
        non_empty = {k: v for k, v in details.items() if v}
        print(f"  Details keys: {list(non_empty.keys())}")
        if "partner_clubs" in details:
            print(f"    details.partner_clubs: {details['partner_clubs']}")
        if "funding_sources" in details:
            print(f"    details.funding_sources: {details['funding_sources']}")
        if "partners" in details:
            print(f"    details.partners: {details['partners']}")
        if "committee" in details or "contacts" in details or "personnel" in details:
            print(f"    details committee/contacts/personnel: {details.get('committee')} | {details.get('contacts')} | {details.get('personnel')}")
    print("-" * 40)
