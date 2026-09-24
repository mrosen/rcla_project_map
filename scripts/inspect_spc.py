import json, urllib.request

url = "https://spc.rotary.org/api/Project/ProjectDetail/en/3734461f-2ef4-40d9-9d6b-5195761f27d1"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    print("TITLE:", data.get("title"))
    print("TAGS:", repr(data.get("tags")))
    print("OVERVIEW:", data.get("overview"))
    print("DESCRIPTION:")
    print(data.get("description"))
    print("PARTNER CLUBS:")
    for pcm in data.get("projectPartnerClubMembers") or []:
        print(" -", pcm.get("partnerOrganizationName") or pcm.get("partnerOrganizationKey"), pcm.get("MoneyDonated"))
    print("NON ROTARY:", data.get("nonRotaryPartners"))
    print("FUNDINGS:")
    for f in data.get("projectFundings") or []:
        print(" -", f.get("fundingSource"), f.get("fundingAmount"), f.get("fundingClubKey"), f.get("fundingOtherName"))
except Exception as e:
    print("Error:", e)

