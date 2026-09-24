import json, os, urllib.request
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

headers = {"apikey": key, "Authorization": f"Bearer {key}"}

def query(table, params=""):
    req = urllib.request.Request(f"{url}/rest/v1/{table}?{params}", headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

print("=== PROJECTS COUNT ===")
projects = query("projects", "select=*")
print(f"Total projects: {len(projects)}")
if projects:
    print("Project fields:", list(projects[0].keys()))

print("\n=== SAMPLE DETAILS / PARTNERS / CLUBS ===")
clubs_found = set()
districts_found = set()
for p in projects:
    details = p.get("details") or {}
    partners = details.get("partners") or []
    # check keys in project
    for k in ["lead_club", "partner_club", "international_sponsor", "host_sponsor"]:
        if p.get(k):
            print(f"Project {p.get('id')} has {k}: {p.get(k)}")
    if partners:
        for pt in partners:
            if isinstance(pt, dict):
                cname = pt.get("club") or pt.get("name")
                if cname: clubs_found.add(cname)
                dname = pt.get("district")
                if dname: districts_found.add(dname)
            else:
                clubs_found.add(str(pt))

print(f"Sample clubs from details.partners: {len(clubs_found)}")
print(list(clubs_found)[:10])

print("\n=== PROJECT LINKS ===")
links = query("project_links", "select=*")
print(f"Total project_links: {len(links)}")
if links:
    print("Sample link:", links[0])

print("\n=== PROJECT ASSETS ===")
assets = query("project_assets", "select=*")
print(f"Total project_assets: {len(assets)}")
if assets:
    print("Sample asset:", assets[0])
