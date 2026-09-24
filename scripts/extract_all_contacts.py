import os, json, glob, re, urllib.request
import fitz
from dotenv import load_dotenv

load_dotenv('/home/msr/rcla_project_map/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

req = urllib.request.Request(f'{url}/rest/v1/projects?select=*&order=id', headers=headers)
with urllib.request.urlopen(req) as resp:
    projects = json.loads(resp.read().decode())

with open('/home/msr/rcla_project_map/spc_resolved_clubs.json') as f:
    resolved_clubs = json.load(f)

print(f"Total projects: {len(projects)}")

def extract_pdf_data(pid):
    pdf_dir = f"/home/msr/rcla_project_map/projects/{pid}"
    if not os.path.exists(pdf_dir):
        return {}
    
    app_pdfs = glob.glob(f"{pdf_dir}/*[Aa]pplication*.pdf")
    report_pdfs = glob.glob(f"{pdf_dir}/*[Rr]eport*.pdf")
    
    data = {
        "primary_intl_contact": None,
        "primary_host_contact": None,
        "intl_committee": [],
        "host_committee": [],
        "contributing_clubs": [],
        "contributing_districts": [],
        "authorizations": [],
        "emails": set(),
        "pdf_found": bool(app_pdfs)
    }
    
    # Process application PDF
    if app_pdfs:
        app_pdf = app_pdfs[0]
        try:
            doc = fitz.open(app_pdf)
            full_text = "\n".join([page.get_text() for page in doc])
            
            # Emails
            for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', full_text):
                em_clean = em.rstrip('.').lower()
                if not any(ign in em_clean for ign in ['rotary.org', 'example.com', 'w3.org']):
                    data["emails"].add(em_clean)
            
            # Primary Contacts & Committee extraction
            lines = [l.strip() for l in full_text.splitlines() if l.strip()]
            for idx, line in enumerate(lines):
                # Primary Contacts
                if line == "Primary Contacts":
                    # Look ahead up to 25 lines
                    sub = lines[idx:idx+25]
                    # Find role occurrences: International vs Host
                    for s_idx, s in enumerate(sub):
                        if s == "International" and s_idx >= 4:
                            data["primary_intl_contact"] = {
                                "name": sub[s_idx-4],
                                "club": sub[s_idx-3],
                                "district": sub[s_idx-2],
                                "role": "Primary International Contact"
                            }
                        elif s == "Host" and s_idx >= 4:
                            data["primary_host_contact"] = {
                                "name": sub[s_idx-4],
                                "club": sub[s_idx-3],
                                "district": sub[s_idx-2],
                                "role": "Primary Host Contact"
                            }
                
                # Host committee / International committee
                if line == "Host committee":
                    sub = lines[idx:idx+35]
                    for s_idx, s in enumerate(sub):
                        if "Secondary Contact" in s and s_idx >= 3:
                            # club is often at s_idx-3 or s_idx-2 (may have [ Rotary Club ])
                            club_cand = sub[s_idx-3]
                            if "[ Rotary Club ]" in club_cand:
                                club_cand = sub[s_idx-4]
                            data["host_committee"].append({
                                "name": sub[s_idx-4] if "[ Rotary Club ]" not in sub[s_idx-4] else sub[s_idx-5],
                                "club": club_cand,
                                "district": sub[s_idx-1],
                                "role": "Host Committee Member"
                            })
                
                if line == "International committee":
                    sub = lines[idx:idx+35]
                    for s_idx, s in enumerate(sub):
                        if "Secondary Contact" in s and s_idx >= 3:
                            club_cand = sub[s_idx-3]
                            if "[ Rotary Club ]" in club_cand:
                                club_cand = sub[s_idx-4]
                            data["intl_committee"].append({
                                "name": sub[s_idx-4] if "[ Rotary Club ]" not in sub[s_idx-4] else sub[s_idx-5],
                                "club": club_cand,
                                "district": sub[s_idx-1],
                                "role": "International Committee Member"
                            })
                            
                # Financing cash / DDF contributions
                if line in ("Cash from Club", "District Designated Fund (DDF)"):
                    # Check next few lines for club or district details
                    sub = lines[idx:idx+10]
                    # pattern: line+1 details, line+2 amount
                    if line == "Cash from Club" and len(sub) > 1:
                        c_name = sub[1]
                        if c_name not in data["contributing_clubs"] and c_name not in ("[ Rotary Club ]", "Details"):
                            data["contributing_clubs"].append(c_name)
                    elif line == "District Designated Fund (DDF)" and len(sub) > 1:
                        d_num = sub[1]
                        if re.match(r'^\d{4}$', d_num) and d_num not in data["contributing_districts"]:
                            data["contributing_districts"].append(d_num)

                # Authorizations
                if "authorizations" in line.lower() or "authorization" in line.lower():
                    # check for DDF authorization or Foundation chair authorization
                    if line in ("District Rotary Foundation chair authorization", "DDF authorization", "Legal agreement"):
                        sub = lines[idx:idx+25]
                        for s_idx, s in enumerate(sub):
                            if s in ("Authorized", "Accepted") and s_idx >= 3:
                                data["authorizations"].append({
                                    "type": line,
                                    "name": sub[s_idx-3],
                                    "club": sub[s_idx-2],
                                    "district": sub[s_idx-1]
                                })
        except Exception as e:
            data["error"] = str(e)
            
    # Process report PDFs for any additional emails
    for rep in report_pdfs:
        try:
            doc = fitz.open(rep)
            full_text = "\n".join([page.get_text() for page in doc])
            for em in re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', full_text):
                em_clean = em.rstrip('.').lower()
                if not any(ign in em_clean for ign in ['rotary.org', 'example.com', 'w3.org']):
                    data["emails"].add(em_clean)
        except Exception:
            pass

    data["emails"] = sorted(list(data["emails"]))
    return data

# Test extraction across all 37 projects
summary = []
all_clubs = set()
all_districts = set()
all_contacts = []

for p in projects:
    pid = p.get("id")
    pdf_info = extract_pdf_data(pid)
    
    # Collect clubs
    proj_clubs = set()
    proj_districts = set()
    
    # From Supabase
    if p.get("international_club_name"):
        proj_clubs.add(p.get("international_club_name"))
    if p.get("international_club_district"):
        proj_districts.add(str(p.get("international_club_district")))
    
    details = p.get("details") or {}
    for c in details.get("partner_clubs") or []:
        if c: proj_clubs.add(c)
    for d in details.get("partner_districts") or []:
        if d: proj_districts.add(str(d))
    for c_item in details.get("club_contributions_list") or []:
        if isinstance(c_item, dict) and c_item.get("club"):
            proj_clubs.add(c_item.get("club"))
    for d_item in details.get("district_contributions") or []:
        if isinstance(d_item, dict) and d_item.get("district"):
            proj_districts.add(str(d_item.get("district")))
            
    # From PDF
    if pdf_info.get("primary_intl_contact"):
        c = pdf_info["primary_intl_contact"].get("club")
        d = pdf_info["primary_intl_contact"].get("district")
        if c: proj_clubs.add(c)
        if d: proj_districts.add(str(d))
    for mem in pdf_info.get("intl_committee") or []:
        if mem.get("club"): proj_clubs.add(mem.get("club"))
        if mem.get("district"): proj_districts.add(str(mem.get("district")))
    for c in pdf_info.get("contributing_clubs") or []:
        proj_clubs.add(c)
    for d in pdf_info.get("contributing_districts") or []:
        proj_districts.add(str(d))
    for auth in pdf_info.get("authorizations") or []:
        if auth.get("club"): proj_clubs.add(auth.get("club"))
        if auth.get("district"): proj_districts.add(str(auth.get("district")))

    all_clubs.update(proj_clubs)
    all_districts.update(proj_districts)
    
    summary.append({
        "id": pid,
        "title": p.get("title"),
        "type": p.get("project_type"),
        "dates": f"{p.get('start_date') or p.get('start_year')} to {p.get('end_date') or p.get('end_year')}",
        "primary_intl": p.get("international_club_name") or (pdf_info.get("primary_intl_contact") or {}).get("club"),
        "primary_intl_person": (pdf_info.get("primary_intl_contact") or {}).get("name"),
        "intl_district": p.get("international_club_district") or (pdf_info.get("primary_intl_contact") or {}).get("district"),
        "clubs_count": len(proj_clubs),
        "clubs": sorted(list(proj_clubs)),
        "districts": sorted(list(proj_districts)),
        "emails": pdf_info.get("emails", [])
    })

print(f"\nExtracted data across all {len(summary)} projects.")
print(f"Total Unique Rotary Clubs involved: {len(all_clubs)}")
print(f"Total Unique Rotary Districts involved: {len(all_districts)}")

# Print GG samples
gg_samples = [s for s in summary if s['type'] == 'Global Grant']
print(f"\nTotal Global Grants: {len(gg_samples)}")
for s in gg_samples:
    print(f"[{s['id']}] {s['title'][:35]} | Intl: {s['primary_intl']} | Person: {s['primary_intl_person']} | Dist: {s['intl_district']} | Clubs: {s['clubs_count']} | Emails: {s['emails']}")


