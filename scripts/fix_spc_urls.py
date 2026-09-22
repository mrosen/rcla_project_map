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

# 1. Check and update project_links
res = requests.get(f"{SUPABASE_URL}/rest/v1/project_links?select=*", headers=headers)
print("project_links type:", type(res.json()), "raw:", res.json() if not isinstance(res.json(), list) else f"count: {len(res.json())}")
if isinstance(res.json(), list):
    for link in res.json():
        old_url = link.get("url", "")
        if "/project/detail/" in old_url:
            new_url = old_url.replace("/project/detail/", "/project?guid=")
            print(f"Updating link {link.get('id')} ({link.get('project_id')}): {old_url} -> {new_url}")
            up_res = requests.patch(
                f"{SUPABASE_URL}/rest/v1/project_links?id=eq.{link['id']}",
                headers=headers,
                json={"url": new_url}
            )
            print("  Update status:", up_res.status_code)
else:
    print("Error fetching project_links:", res.json())

# 2. Check and update projects sync_status
res2 = requests.get(f"{SUPABASE_URL}/rest/v1/projects?select=id,sync_status", headers=headers)
if isinstance(res2.json(), list):
    for p in res2.json():
        sync_status = p.get("sync_status")
        if sync_status and isinstance(sync_status, dict) and "spc" in sync_status:
            spc = sync_status["spc"]
            old_url = spc.get("spc_url", "")
            if "/project/detail/" in old_url:
                spc["spc_url"] = old_url.replace("/project/detail/", "/project?guid=")
                print(f"Updating projects.sync_status for {p['id']}: {old_url} -> {spc['spc_url']}")
                up_res = requests.patch(
                    f"{SUPABASE_URL}/rest/v1/projects?id=eq.{p['id']}",
                    headers=headers,
                    json={"sync_status": sync_status}
                )
                print("  Update status:", up_res.status_code)

