import json, os, urllib.request, sys
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
req = urllib.request.Request(f"{url}/rest/v1/projects?id=eq.GG2091778", headers={"apikey": key, "Authorization": f"Bearer {key}"})
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())

p = data[0]
print("raw description:", repr(p.get("description")))
sys.path.insert(0, "/home/msr/rcla_project_map")
from migrate_to_spc import construct_spc_payload

complete = (p.get("complete_overview") or "").strip()
print("complete len:", len(complete))
from migrate_to_spc import clean_text
c_desc = clean_text(complete)
print("clean len:", len(c_desc))

org_names = ["Asociación Pro Agua del Pueblo (ADP)", "Mil Milagros", "Municipalities of Santa Lucía Utatlan and San Andreas Semetabaj", "Community COCODEs"]
callout = "Cooperating Partner(s): " + ", ".join(org_names) + "."
print("callout len:", len(callout))
max_desc_len = 1000 - len(callout) - 2
print("max_desc_len:", max_desc_len)
fd = c_desc
if len(fd) > max_desc_len:
    fd = fd[:max_desc_len].rsplit(' ', 1)[0].rstrip('.,;:') + "..."
print("trimmed fd len:", len(fd))
fd = fd.rstrip() + "\n\n" + callout
print("fd after callout len:", len(fd))
if len(fd) > 1000:
    print("TRIGGERS line 681!")
    fd = fd[:997].rsplit(' ', 1)[0].strip() + "..."
print("final fd len:", len(fd))
print(fd[-60:])



print("=== TITLE ===")
print(payload.get("title"))
print("\n=== TAGS ===")
print(payload.get("tags"))
print("\n=== OVERVIEW ===")
print(payload.get("overview"))
print("\n=== DESCRIPTION ===")
desc = payload.get("description")
print(f"Length: {len(desc)}")
print(desc)

print("\n=== PARTNER CLUBS ===")
print(json.dumps(payload.get("projectPartnerClubMembers"), indent=2))
print("\n=== FUNDINGS ===")
print(json.dumps(payload.get("projectFundings"), indent=2))
