import os
import requests
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

res = requests.get(f"{SUPABASE_URL}/rest/v1/projects?id=eq.GG1633934&select=*,project_assets(*),project_links(*)", headers=headers)
data = res.json()
if not data:
    print("Project GG1633934 not found in Supabase")
else:
    p = data[0]
    print("Project title:", p.get("title"))
    print("Sync status:", p.get("sync_status"))
    print("Assets count:", len(p.get("project_assets", [])))
    for a in p.get("project_assets", []):
        print("  Asset:", a.get("filename"), "| type:", a.get("file_type"), "| display_order:", a.get("display_order"), "| url:", a.get("public_url"))
    print("Links count:", len(p.get("project_links", [])))
    for l in p.get("project_links", []):
        print("  Link:", l.get("label"), "| url:", l.get("url"))

