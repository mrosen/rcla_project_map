#!/usr/bin/env python3
"""
scripts/harvest_rotary_contacts.py

Harvests all Rotary contacts across all 37 projects in the repository by:
1. Querying canonical Supabase project records (metadata, narrative Key Personnel, shepherd, details).
2. Deep-parsing all project dossier PDFs (Application primary contacts, committee tables, volunteer travelers, authorizations, report signers).
3. Correlating names, emails, clubs, districts, roles, and project titles.
4. Outputting structured harvested data for gap analysis and export.
"""

import os
import sys
import json
import glob
import re
import urllib.request
from pathlib import Path
from dotenv import load_dotenv
import fitz  # PyMuPDF

WORKSPACE_ROOT = Path("/home/msr/rcla_project_map")
ENV_PATH = WORKSPACE_ROOT / ".env"
RESOLVED_CLUBS_PATH = WORKSPACE_ROOT / "spc_resolved_clubs.json"

if not ENV_PATH.exists():
    ENV_PATH = Path(".env")
load_dotenv(ENV_PATH)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Missing SUPABASE_URL or SUPABASE_KEY in environment.")
    sys.exit(1)

# Base URL for archive links
ARCHIVE_BASE_URL = "https://mrosen.github.io/rcla_project_map/?source=supabase&project="

# Known verified email mapping for key Rotarians across projects
KNOWN_ROTARIAN_EMAILS = {
    "todd thompson": "todd@tiddley.com",
    "bruce clemens": "bruce.wayne.clemens@gmail.com",
    "patrick coyle": "pat@coyles.com",
    "glenn kubiak": "gdkubiak@gmail.com",
    "glenn d. kubiak": "gdkubiak@gmail.com",
    "jeff youngsma": "j.youngsma@me.com",
    "jeffrey youngsma": "j.youngsma@me.com",
    "brad fischer": "bfischer@laxymca.org",
    "catherine patel": "catherine.patel@rcsedu.org",
    "don baldus": "donbaldus07@gmail.com",
    "lillyam arroyave": "lillyam.arroyave@rctc.edu",
    "paul wise": "pwise@stanford.edu",
    "tom tocco": "toccotom@gmail.com",
    "joanne rosener": "jenb@mycookkitchen.com",
    "terrence wakely": "joe.wakely@gmail.com",
    "joe wakely": "joe.wakely@gmail.com",
    "michael rosen": "michael.rosen@gmail.com",
    "mike rosen": "michael.rosen@gmail.com",
    "shad qudsi": "shad@atitlanorganics.com",
}

# RCLA Shepherd name expansion and emails
RCLA_SHEPHERDS = {
    "mike": ("Michael Rosen", "michael.rosen@gmail.com"),
    "michael rosen": ("Michael Rosen", "michael.rosen@gmail.com"),
    "joe": ("Terrence (Joe) Wakely", "joe.wakely@gmail.com"),
    "terrence wakely": ("Terrence (Joe) Wakely", "joe.wakely@gmail.com"),
    "duncan": ("Duncan Aitken", ""),
    "duncan aitken": ("Duncan Aitken", ""),
    "armand": ("Armand Boissy", ""),
    "armand boissy": ("Armand Boissy", ""),
    "candise": ("Candis Krummel", ""),
    "candis krummel": ("Candis Krummel", ""),
    "michelle": ("Michelle Fajkus", ""),
    "michelle fajkus": ("Michelle Fajkus", ""),
    "clint": ("Clinton White", ""),
    "clinton white": ("Clinton White", ""),
    "shad": ("Shad Qudsi", "shad@atitlanorganics.com"),
    "shad qudsi": ("Shad Qudsi", "shad@atitlanorganics.com"),
    "emilio": ("Emilio Crespo Morales", ""),
    "emilio crespo morales": ("Emilio Crespo Morales", ""),
    "dwight": ("Dwight Mara-Poage", ""),
    "dwight mara-poage": ("Dwight Mara-Poage", ""),
    "will": ("William Boegel", "drboegel@gmail.com"),
    "william boegel": ("William Boegel", "drboegel@gmail.com")
}

def fetch_supabase_projects():
    """Fetches all projects from Supabase REST API."""
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/projects?select=*&order=id", headers=headers)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def clean_text(s):
    if not s:
        return ""
    # Normalize non-breaking spaces and whitespace
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()

def clean_club_name(c):
    if not c:
        return ""
    c = clean_text(c)
    c = re.sub(r'\[\s*Rotary\s+Club\s*\]', '', c, flags=re.IGNORECASE)
    c = re.sub(r'^(?:RC\s+of\s+|RC\s+|Rotary\s+Club\s+of\s+|Rotary\s+Club\s+|Club\s+Rotario\s+de\s+)', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*\([dD]\d+\)', '', c)
    c = re.sub(r'\s+', ' ', c).strip(" ,-")
    return c

def extract_pdf_contacts(pid):
    """Deep-parses all PDF files for a given project ID."""
    pdf_dir = WORKSPACE_ROOT / "projects" / pid
    if not pdf_dir.exists():
        pdf_dir = Path("projects") / pid
    if not pdf_dir.exists():
        return {"contacts": [], "contributing_clubs": [], "contributing_districts": []}

    contacts = []
    contributing_clubs = set()
    contributing_districts = set()
    paired_emails = {}  # name_lower -> email

    pdf_files = sorted(glob.glob(str(pdf_dir / "*.pdf")))

    for pdf_path in pdf_files:
        try:
            doc = fitz.open(pdf_path)
            for page_idx, page in enumerate(doc):
                text = page.get_text()
                lines = [clean_text(l) for l in text.splitlines() if clean_text(l)]

                # 1. Look for Volunteer Travelers / Participants table (often has direct Name & Email)
                for i, line in enumerate(lines):
                    if line in ("Volunteer Travelers", "Rotarian Participants", "Volunteer travelers"):
                        # Table columns: No., Name, Email
                        sub = lines[i:i+40]
                        for j in range(len(sub) - 2):
                            if "@" in sub[j+2] and re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', sub[j+2]):
                                v_name = sub[j+1]
                                v_email = sub[j+2].lower()
                                if len(v_name) > 3 and not any(kw in v_name.lower() for kw in ['describe', 'email', 'name', 'phone']):
                                    paired_emails[v_name.lower()] = v_email
                                    contacts.append({
                                        "name": v_name,
                                        "email": v_email,
                                        "club": "",
                                        "district": "",
                                        "role": "Volunteer Traveler / Participant",
                                        "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                    })

                    # 2. Look for "Primary Contacts" table
                    if line == "Primary Contacts":
                        sub = lines[i:i+30]
                        for s_idx, s in enumerate(sub):
                            if s == "International" and s_idx >= 4:
                                contacts.append({
                                    "name": sub[s_idx-4],
                                    "club": clean_club_name(sub[s_idx-3]),
                                    "district": sub[s_idx-2],
                                    "role": "Primary International Contact",
                                    "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                })
                            elif s == "Host" and s_idx >= 4:
                                contacts.append({
                                    "name": sub[s_idx-4],
                                    "club": clean_club_name(sub[s_idx-3]),
                                    "district": sub[s_idx-2],
                                    "role": "Primary Host Contact",
                                    "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                })

                    # 3. Look for "Host committee" & "International committee"
                    if line == "Host committee":
                        sub = lines[i:i+35]
                        for s_idx, s in enumerate(sub):
                            if "Secondary Contact" in s and s_idx >= 3:
                                c_cand = clean_club_name(sub[s_idx-3])
                                n_cand = sub[s_idx-4]
                                if "[ Rotary Club ]" in sub[s_idx-3] or not c_cand:
                                    c_cand = clean_club_name(sub[s_idx-4])
                                    n_cand = sub[s_idx-5] if s_idx >= 5 else n_cand
                                contacts.append({
                                    "name": n_cand,
                                    "club": c_cand,
                                    "district": sub[s_idx-1],
                                    "role": "Host Committee Member",
                                    "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                })

                    if line == "International committee":
                        sub = lines[i:i+35]
                        for s_idx, s in enumerate(sub):
                            if "Secondary Contact" in s and s_idx >= 3:
                                c_cand = clean_club_name(sub[s_idx-3])
                                n_cand = sub[s_idx-4]
                                if "[ Rotary Club ]" in sub[s_idx-3] or not c_cand:
                                    c_cand = clean_club_name(sub[s_idx-4])
                                    n_cand = sub[s_idx-5] if s_idx >= 5 else n_cand
                                contacts.append({
                                    "name": n_cand,
                                    "club": c_cand,
                                    "district": sub[s_idx-1],
                                    "role": "International Committee Member",
                                    "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                })

                    # 4. Authorizations
                    if line in ("District Rotary Foundation chair authorization", "DDF authorization", "Legal agreement"):
                        auth_role = "DRFC Chair" if "Foundation chair" in line else ("DDF Authorizer" if "DDF" in line else "Club President / Signatory")
                        sub = lines[i:i+30]
                        for s_idx, s in enumerate(sub):
                            if s in ("Authorized", "Accepted") and s_idx >= 2:
                                # find 4-digit district in previous 4 lines
                                dist_idx = None
                                for back in range(s_idx - 1, max(-1, s_idx - 5), -1):
                                    if re.match(r'^\d{4}$', sub[back]):
                                        dist_idx = back
                                        break
                                if dist_idx is not None:
                                    a_dist = sub[dist_idx]
                                    club_pos = dist_idx - 1
                                    if club_pos >= 0 and sub[club_pos] == "[ Rotary Club ]":
                                        club_pos -= 1
                                    a_club = clean_club_name(sub[club_pos]) if club_pos >= 0 else ""
                                    # Name is the lines before club_pos
                                    name_parts = []
                                    for n_pos in range(club_pos - 1, max(-1, club_pos - 4), -1):
                                        cand = sub[n_pos]
                                        if cand in ("Name", "Status", "Club", "District", "Authorized", "Accepted", "Primary contact authorizations", "District Rotary Foundation chair authorization", "DDF authorization", "Legal agreement", "[ Rotary Club ]") or "Authorized on" in cand or "Accepted on" in cand:
                                            break
                                        name_parts.insert(0, cand)
                                    a_name = clean_text(" ".join(name_parts))
                                    if a_name and len(a_name) > 3 and not any(kw in a_name.lower() for kw in ["authorization", "legal", "primary"]):
                                        contacts.append({
                                            "name": a_name,
                                            "club": a_club,
                                            "district": a_dist,
                                            "role": auth_role,
                                            "source": f"{Path(pdf_path).name} (p. {page_idx+1})"
                                        })

                    # 5. Financing - Contributing Clubs and Districts
                    if line in ("Cash from Club", "Club contribution"):
                        sub = lines[i:i+8]
                        if len(sub) > 1 and sub[1] not in ("[ Rotary Club ]", "Details", "Cash from Club"):
                            contributing_clubs.add(clean_club_name(sub[1]))
                    if line in ("District Designated Fund (DDF)", "District Designated Funds (DDF)"):
                        sub = lines[i:i+8]
                        if len(sub) > 1 and re.match(r'^\d{4}$', sub[1]):
                            contributing_districts.add(sub[1])

                # Extract any inline emails paired with names (e.g. "Patrick Coyle, pat@coyles.com")
                for m in re.finditer(r'([A-Z][a-zA-Z.\'-]+(?:\s+[A-Z][a-zA-Z.\'-]+){1,3})[,\s:]+([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text):
                    p_name = clean_text(m.group(1))
                    p_email = m.group(2).lower().rstrip('.')
                    if not any(ign in p_email for ign in ['rotary.org', 'example.com', 'w3.org']):
                        paired_emails[p_name.lower()] = p_email

        except Exception as e:
            print(f"Warning parsing {pdf_path}: {e}")

    # Backfill paired emails into extracted contacts where email is missing
    for c in contacts:
        if not c.get("email"):
            name_lower = c.get("name", "").lower()
            if name_lower in paired_emails:
                c["email"] = paired_emails[name_lower]
            elif name_lower in KNOWN_ROTARIAN_EMAILS:
                c["email"] = KNOWN_ROTARIAN_EMAILS[name_lower]

    return {
        "contacts": contacts,
        "contributing_clubs": sorted(list(contributing_clubs)),
        "contributing_districts": sorted(list(contributing_districts)),
        "paired_emails": paired_emails
    }

def extract_narrative_contacts(narrative_text):
    """Extracts contacts explicitly listed in Markdown narrative Key Personnel section."""
    if not narrative_text:
        return []

    contacts = []
    # Find Key Personnel section
    m_sec = re.search(r'(?:###?\s*(?:Key Personnel|Contacts?|Rotary Contacts?|Project Leadership).*?)(?=\n###|\Z)', narrative_text, re.DOTALL | re.IGNORECASE)
    if not m_sec:
        return []

    section_text = m_sec.group(0)

    # 1. Parse Markdown Table rows: | Name | Role |
    table_rows = re.findall(r'\|\s*([^|\n]+?)\s*\|\s*([^|\n]+?)\s*\|', section_text)
    for col1, col2 in table_rows:
        col1 = clean_text(col1).strip("*_ ")
        col2 = clean_text(col2).strip("*_ ")
        if col1.lower() in ("name", "key personnel", "contact", "person", "---", ":---", "---:"):
            continue
        if len(col1) > 2 and len(col2) > 2:
            # Extract email if inside role
            em_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', col2)
            c_email = em_match.group(1).lower() if em_match else ""
            
            # Extract district if in role or col1 (require D prefix or 'District', or non-year)
            dist_match = re.search(r'(?:\b[dD]\s*|District\s*)(\d{4})\b', col2, re.IGNORECASE) or re.search(r'(?:\b[dD]\s*|District\s*)(\d{4})\b', col1, re.IGNORECASE)
            c_dist = dist_match.group(1) if dist_match else ""

            # Extract club
            c_club = ""
            club_match = re.search(r'(?:RC\s+|Rotary\s+Club\s+(?:of\s+)?|Club\s+Rotario\s+(?:de\s+)?)([A-Za-z\s]+?)(?:,|\.|\s+[dD]\d+|\Z)', col2)
            if club_match:
                c_club = clean_club_name(club_match.group(1))

            contacts.append({
                "name": col1,
                "role": col2,
                "email": c_email,
                "club": c_club,
                "district": c_dist,
                "source": "Narrative Table"
            })

    # 2. Parse Bullet points: - **Name** (Club) — role
    bullets = re.findall(r'^[*-]\s+\*\*([^*]+)\*\*(.*?)$', section_text, re.MULTILINE)
    for b_name, b_desc in bullets:
        b_name = clean_text(b_name).strip("*_ ")
        b_desc = clean_text(b_desc)

        em_match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', b_desc)
        c_email = em_match.group(1).lower() if em_match else ""

        dist_match = re.search(r'(?:\b[dD]\s*|District\s*)(\d{4})\b', b_desc, re.IGNORECASE)
        c_dist = dist_match.group(1) if dist_match else ""

        c_club = ""
        club_match = re.search(r'\(([^)]+?)(?:,\s*[dD]\d+)?\)', b_desc)
        if club_match:
            cand = clean_club_name(club_match.group(1))
            # Only accept if it looks like a legitimate club name or has RC/Rotary
            if not any(kw in cand.lower() for kw in ['usa', 'pdg', 'dgn', 'dg', 'since', 'twice', 'monitoring', 'mid-project', 'close-out', 'closeout', 'retired', 'resident', 'founder', 'volunteer', 'treasurer', 'president', 'chair', 'authoriz', 'report', 'grant', 'project', 'management', 'years', 'travel', 'coordinator', 'director', 'evaluat']) and not re.search(r'[\$;=]', cand) and not re.match(r'^\d', cand):
                c_club = cand
        if not c_club:
            club_match2 = re.search(r'(?:RC\s+|Rotary\s+Club\s+(?:of\s+)?|Club\s+Rotario\s+(?:de\s+)?)([A-Za-z\s]+?)(?:,|\.|\s+[dD]\d+|\Z)', b_desc)
            if club_match2:
                cand2 = clean_club_name(club_match2.group(1))
                if not any(kw in cand2.lower() for kw in ['usa', 'pdg', 'dgn', 'dg', 'since', 'twice', 'monitoring', 'mid-project', 'close-out', 'closeout', 'retired', 'resident', 'founder', 'volunteer', 'treasurer', 'president', 'chair', 'authoriz', 'report', 'grant', 'project', 'management', 'years', 'travel', 'coordinator', 'director', 'evaluat']):
                    c_club = cand2

        # Clean role description
        b_role = b_desc.lstrip(" —-:,")
        if not b_role:
            b_role = "Project Contributor"

        contacts.append({
            "name": b_name,
            "role": b_role,
            "email": c_email,
            "club": c_club,
            "district": c_dist,
            "source": "Narrative Bullet"
        })

    return contacts

def normalize_person_key(name):
    if not name:
        return ""
    n = name.lower()
    n = re.sub(r'\(.*?\)', '', n)
    n = re.sub(r'\b(?:dr|phd|md|prof|mr|mrs|ms)\b\.?', '', n)
    return clean_text(n)

RCLA_MEMBER_NAMES = {
    "bruce clemens", "armand boissy", "terrence wakely", "joe wakely",
    "duncan aitken", "michael rosen", "shad qudsi", "michelle fajkus",
    "clinton white", "clint white", "candis krummel", "candise krummel",
    "william boegel", "will boegel", "emilio crespo morales", "emilio crespo",
    "dwight mara-poage", "dwight mara poage", "sharon smart", "mayra tobias",
    "mayra tobías", "jaime marroquin mendoza", "jaime marroquin"
}

def deduplicate_project_contacts(raw_contacts):
    """Deduplicates and merges contacts within a single project."""
    merged = {}
    for c in raw_contacts:
        name = clean_text(c.get("name", "")).strip("*_ ")
        if not name or len(name) < 3:
            continue
        # Filter out common header labels and table separators
        if re.match(r'^[-:_| ]+$', name):
            continue
        if any(ign in name.lower() for ign in ["primary contacts", "committee members", "authorizations", "status", "role", "key personnel"]):
            continue

        norm_k = normalize_person_key(name)
        key = norm_k if norm_k else name.lower()

        c_club = clean_club_name(c.get("club") or "")
        c_dist = str(c.get("district") or "").strip()
        c_email = c.get("email") or ""

        # Auto-extract club from role if missing
        if not c_club and c.get("role"):
            m_club = re.search(r'([A-Z][A-Za-z\s–-]+?)\s+(?:RC|Rotary\s+Club)\b', c["role"])
            if not m_club:
                m_club = re.search(r'(?:RC\s+|Rotary\s+Club\s+(?:of\s+)?|Club\s+Rotario\s+(?:de\s+)?)([A-Z][A-Za-z\s]+?)(?:,|\.|\s+[dD]\d+|\s+sponsor|\s+authoriz|;|\Z)', c["role"])
            if m_club:
                cand = clean_club_name(m_club.group(1))
                if cand and len(cand) > 3 and not any(kw in cand.lower() for kw in ['sponsor', 'authoriz', 'primary', 'secondary', 'grant', 'report']):
                    c_club = cand

        # Auto-resolve RCLA home members
        if norm_k in RCLA_MEMBER_NAMES:
            if not c_club:
                c_club = "Lake Atitlán"
            if not c_dist:
                c_dist = "4250"

        if key not in merged:
            merged[key] = {
                "name": name,
                "email": c_email,
                "club": c_club,
                "district": c_dist,
                "role": c.get("role") or "",
                "source": c.get("source") or ""
            }
        else:
            # Upgrade fields if existing has blanks
            if not merged[key]["email"] and c_email:
                merged[key]["email"] = c_email
            if not merged[key]["club"] and c_club:
                merged[key]["club"] = c_club
            if not merged[key]["district"] and c_dist:
                merged[key]["district"] = c_dist
            # If current role is generic, take more specific role
            if "primary" in c.get("role", "").lower():
                merged[key]["role"] = c["role"]

    # Final email backfill check from known list
    for key, c in merged.items():
        norm_k = normalize_person_key(c["name"])
        if not c["email"]:
            if norm_k in KNOWN_ROTARIAN_EMAILS:
                c["email"] = KNOWN_ROTARIAN_EMAILS[norm_k]
            elif key in KNOWN_ROTARIAN_EMAILS:
                c["email"] = KNOWN_ROTARIAN_EMAILS[key]

    return list(merged.values())

def resolve_country(club_name, district, resolved_info=None):
    if resolved_info and resolved_info.get("country"):
        return resolved_info["country"].strip()
    
    c_low = (club_name or "").lower()
    d_str = str(district or "").strip()
    
    if any(k in c_low for k in ["atitlan", "atitlán", "guatemala"]):
        return "Guatemala"
    if "belize" in c_low:
        return "Belize"
    if any(k in c_low for k in ["tegucigalpa", "honduras", "usula", "real de minas"]):
        return "Honduras"
    if d_str == "4250":
        if "belize" in c_low: return "Belize"
        if any(k in c_low for k in ["tegucigalpa", "usula", "real de minas"]): return "Honduras"
        return "Guatemala"
        
    if d_str == "4740" or any(k in c_low for k in ["caçador", "cacador", "chapecó", "chapeco", "lajes"]):
        return "Brazil"
        
    if "flint" in c_low:
        return "United States"
    if any(k in c_low for k in ["wiarton", "wairton", "watford", "mildmay", "walkerton", "calgary", "nelson", "stratford", "meaford", "ontario", "canada"]):
        return "Canada"
    if d_str in ("5360", "7080"):
        return "Canada"
    if d_str == "6330":
        return "Canada"
        
    if "rostock" in c_low or "germany" in c_low:
        return "Germany"
        
    US_DISTRICTS = {"5050", "5080", "5110", "5130", "5150", "5170", "5190", "5230", "5240", "5340", "5440", "5450", "5710", "5950", "5960", "6440", "6690", "7620", "7670", "7770", "7780", "7950"}
    if d_str in US_DISTRICTS:
        return "United States"
        
    if any(st in c_low for st in [", mn", ", ca", ", md", ", nc", ", oh", ", sc", ", co", ", ks", ", wa", ", nv"]):
        return "United States"
        
    return "Guatemala" if not d_str and not c_low else ("United States" if d_str else "")

def main():
    print("=== Rotary Contact Harvester ===")
    print("1. Fetching canonical projects from Supabase...")
    projects = fetch_supabase_projects()
    print(f"Fetched {len(projects)} projects.")

    resolved_clubs = {}
    if RESOLVED_CLUBS_PATH.exists():
        with open(RESOLVED_CLUBS_PATH, "r", encoding="utf-8") as f:
            resolved_clubs = json.load(f)

    all_harvested_contacts = []
    projects_roster = []

    for p in projects:
        pid = p.get("id")
        title = clean_text(p.get("title") or "")
        archive_link = f"{ARCHIVE_BASE_URL}{pid}"

        # 1. Harvest from PDF dossiers
        pdf_res = extract_pdf_contacts(pid)
        raw_contacts = pdf_res["contacts"]

        # 2. Harvest from Supabase Narrative
        narrative_contacts = extract_narrative_contacts(p.get("narrative"))
        raw_contacts.extend(narrative_contacts)

        # 3. Add Project Shepherd if present
        shepherd = p.get("shepherd")
        if shepherd:
            shep_key = shepherd.strip().lower()
            if shep_key in RCLA_SHEPHERDS:
                full_name, shep_email = RCLA_SHEPHERDS[shep_key]
            else:
                full_name, shep_email = shepherd.strip(), ""
            raw_contacts.append({
                "name": full_name,
                "email": shep_email,
                "role": "Project Shepherd",
                "club": "Lake Atitlán",
                "district": "4250",
                "source": "Supabase Metadata"
            })

        # 4. Add International Primary Club if recorded at project level
        intl_club = p.get("international_club_name")
        intl_dist = p.get("international_club_district")

        # Deduplicate contacts for this project
        deduped = deduplicate_project_contacts(raw_contacts)

        # Compute canonical project date
        sd = p.get("start_date") or ""
        sy = str(p.get("start_year") or "")
        ey = str(p.get("end_year") or "")
        p_date = sd if sd and not sd.endswith("-01-01") else (f"{sy}–{ey}" if sy and ey and sy != ey else (sy or sd or ""))

        # Assign project context, country, date, and archive link
        for c in deduped:
            # If club missing, use international club for intl contacts, or Lake Atitlan for host
            if not c["club"]:
                if "host" in c["role"].lower() or "shepherd" in c["role"].lower():
                    c["club"] = "Lake Atitlán"
                    c["district"] = "4250"
                elif intl_club and ("international" in c["role"].lower() or "intl" in c["role"].lower()):
                    c["club"] = clean_club_name(intl_club)
                    if intl_dist and not c["district"]:
                        c["district"] = str(intl_dist)

            res_info = resolved_clubs.get(c["club"].lower()) if c["club"] else None
            c["country"] = resolve_country(c["club"], c["district"], res_info)
            c["project_id"] = pid
            c["project_title"] = title
            c["date"] = p_date
            c["archive_link"] = archive_link
            c["contact_type"] = "Direct Project Contact"

            all_harvested_contacts.append(c)

        # Participating clubs & districts tracking
        participating_clubs = set(pdf_res["contributing_clubs"])
        participating_districts = set(pdf_res["contributing_districts"])

        details = p.get("details") or {}
        if intl_club:
            participating_clubs.add(clean_club_name(intl_club))
        if intl_dist:
            participating_districts.add(str(intl_dist))

        for c_item in details.get("partner_clubs") or []:
            if c_item: participating_clubs.add(clean_club_name(c_item))
        for d_item in details.get("partner_districts") or []:
            if d_item: participating_districts.add(str(d_item))
        for c_item in details.get("club_contributions_list") or []:
            if isinstance(c_item, dict) and c_item.get("club"):
                participating_clubs.add(clean_club_name(c_item["club"]))
        for d_item in details.get("district_contributions") or []:
            if isinstance(d_item, dict) and d_item.get("district"):
                participating_districts.add(str(d_item["district"]))

        projects_roster.append({
            "project_id": pid,
            "project_title": title,
            "project_type": p.get("project_type"),
            "date": p_date,
            "archive_link": archive_link,
            "contacts_count": len(deduped),
            "contacts": deduped,
            "participating_clubs": sorted(list(participating_clubs)),
            "participating_districts": sorted(list(participating_districts))
        })

    # Write output JSON
    output_path = WORKSPACE_ROOT / "harvested_contacts.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_harvested_contacts": len(all_harvested_contacts),
            "projects": projects_roster,
            "all_contacts": all_harvested_contacts
        }, f, indent=2)

    print(f"\nSuccessfully harvested {len(all_harvested_contacts)} contact entries across {len(projects_roster)} projects.")
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    main()
