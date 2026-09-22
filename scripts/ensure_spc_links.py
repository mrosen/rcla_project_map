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

# Fetch all projects with sync_status.spc.exported == true
res = requests.get(f"{SUPABASE_URL}/rest/v1/projects?select=id,sync_status", headers=headers)
for p in res.json():
    pid = p.get("id")
    sync_status = p.get("sync_status") or {}
    spc = sync_status.get("spc") or {}
    if spc.get("exported") and spc.get("spc_project_id"):
        spc_id = spc["spc_project_id"]
        spc_url = f"https://spc.rotary.org/project?guid={spc_id}"
        
        # Check if already in project_links
        l_res = requests.get(f"{SUPABASE_URL}/rest/v1/project_links?project_id=eq.{pid}", headers=headers)
        links = l_res.json() if isinstance(l_res.json(), list) else []
        spc_link = next((l for l in links if "spc.rotary.org" in (l.get("url") or "") or l.get("label") == "Rotary Service Project Center (SPC)"), None)
        
        if spc_link:
            requests.patch(f"{SUPABASE_URL}/rest/v1/project_links?id=eq.{spc_link['id']}", headers=headers, json={"url": spc_url})
            print(f"Updated {pid} link to {spc_url}")
        else:
            requests.post(f"{SUPABASE_URL}/rest/v1/project_links", headers=headers, json={
                "project_id": pid,
                "label": "Rotary Service Project Center (SPC)",
                "url": spc_url,
                "display_order": len(links)
            })
            print(f"Inserted {pid} link: {spc_url}")

