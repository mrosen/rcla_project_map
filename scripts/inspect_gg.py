import json, os, urllib.request
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
req = urllib.request.Request(f"{url}/rest/v1/projects?id=eq.GG2091778", headers={"apikey": key, "Authorization": f"Bearer {key}"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())

print("NARRATIVE:")
print(data[0].get("narrative"))

