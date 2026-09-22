import os
import requests
import json
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

p = requests.get(f"{SUPABASE_URL}/rest/v1/projects?id=eq.GG1633934", headers=headers).json()[0]
print("Funding fields from Supabase:")
for k, v in p.items():
    if any(term in k.lower() for term in ("fund", "budget", "amount", "partner", "grant", "ddf", "5150", "4250")):
        print(f"  {k}: {v}")

