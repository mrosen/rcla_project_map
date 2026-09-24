import json, os, glob, re, urllib.request
import fitz
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
headers = {"apikey": key, "Authorization": f"Bearer {key}"}

# 1. Fetch Supabase projects
req = urllib.request.Request(f"{url}/rest/v1/projects?select=*&order=id", headers=headers)
with urllib.request.urlopen(req) as resp:
    projects = json.loads(resp.read().decode())

print(f"Loaded {len(projects)} projects from Supabase.")

# Function to parse an Application PDF for Primary Contacts, Committees, Funding Clubs, Authorizations
def parse_application_pdf(pdf_path):
    info = {
        "primary_host": None,
        "primary_intl": None,
        "host_committee": [],
        "intl_committee": [],
        "funding_clubs": [],
        "funding_districts": [],
        "authorizations": [],
        "emails": []
    }
    try:
        doc = fitz.open(pdf_path)
        full_text = "\n".join([page.get_text() for page in doc])
        
        # Extract emails
        emails = set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', full_text))
        info["emails"] = [e for e in emails if not e.lower().endswith(('rotary.org', 'rotary.org.', 'example.com'))]
        
        # Primary Contacts section
        # Look for table pattern: Name, Club, District, Sponsor, Role
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        for i, line in enumerate(lines):
            if "primary contact" in line.lower():
                # scan next 25 lines
                for j in range(i+1, min(len(lines), i+30)):
                    l = lines[j]
                    if "international" == l.lower():
                        # Previous lines might be name, club, district
                        info["authorizations"].append(f"Primary Intl Contact near line {j}: {lines[max(0, j-4):j]}")
                    if "host" == l.lower():
                        info["authorizations"].append(f"Primary Host Contact near line {j}: {lines[max(0, j-4):j]}")

        # Let's also do a structured regex for Primary Contacts table if possible
        # In Rotary PDF:
        # Primary Contacts
        # Name
        # Club
        # District
        # Sponsor
        # Role
        # <Name>
        # <Club>
        # <District>
        # <Sponsor>
        # <Role>
    except Exception as e:
        info["error"] = str(e)
    return info

print("Testing PDF parser...")
test_res = parse_application_pdf("/home/msr/rcla_project_map/projects/GG1410846/GG1410846_Application.pdf")
print("Emails found:", test_res["emails"])
