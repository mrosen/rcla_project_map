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

res = requests.get(f"{SUPABASE_URL}/rest/v1/project_links?project_id=eq.GG2574529", headers=headers)
print("GG2574529 links:", res.json())

