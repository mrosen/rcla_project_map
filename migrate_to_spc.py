#!/usr/bin/env python3
"""
migrate_to_spc.py — Automated Migration from Supabase to Rotary Service Project Center (SPC)

Uses the exact REST API schema captured from Playwright trace:
- Authenticates with My Rotary via Playwright
- Pulls project data, narratives, links, and media from Supabase / CSV
- Resolves contributing districts and partner clubs
- Submits each project to https://spc.rotary.org/api/Project/CreateProject
- Tracks progress in spc_migration_state.json
"""

import asyncio
import base64
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# --- Configuration & Constants ---
ENV_PATHS = [Path("/home/msr/grantcenter/.env"), Path(__file__).resolve().parent.parent / ".env", Path(".env")]
for p in ENV_PATHS:
    if p.exists():
        load_dotenv(p)
STATE_PATH = Path("/home/msr/rcla_project_map/spc_migration_state.json")

SUPABASE_URL = "https://rqhmsincnmxrgtipvkif.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxaG1zaW5jbm14cmd0aXB2a2lmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1MTgwMzUsImV4cCI6MjEwNTA5NDAzNX0.XJY9Q6akA4KF0Ei5Ri8blJ1yxfNM75l-oNK9nR1H40o"

ROTARY_LAKE_ATITLAN_CLUB_KEY = "c575902e-aae0-4b82-9aba-54947c09f4fe"
ROTARY_LAKE_ATITLAN_CLUB_ID  = "84633"
ROTARY_GUATEMALA_COUNTRY_KEY = "884813f1-8178-450a-9402-b0b658d3a8ec"
MEMBER_KEY = "277b2562-0575-4eb6-b044-6e3655a44264"
MEMBER_ID  = "8225782"
MEMBER_NAME = "Michael Rosen"
MEMBER_EMAIL = "michael.rosen@gmail.com"

AREA_OF_FOCUS_MAP = {
    "water": ("db66058c-bb64-452e-92bf-405fdb8aa2cf", "Water, sanitation, and hygiene"),
    "education": ("a5d5e449-36a9-446b-bf8f-2a691953873e", "Basic education and literacy"),
    "economic": ("ecb970bf-b8e0-497a-828a-e0af3fefa28e", "Community economic development"),
    "environment": ("3d1955c4-87fc-4f33-b75e-a8f7c3230cbc", "Environment"),
    "health": ("6d9a56cd-9ca4-4e85-bb0b-9ff68cc1fb3c", "Maternal and child health"),
    "disease": ("855c0e81-10bb-4560-9b92-2819867335d0", "Disease prevention and treatment"),
    "peace": ("5a49b16b-8dc8-4e19-b0f8-fa092c9976d4", "Peacebuilding and conflict prevention"),
}

US_STATE_ABBR = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR', 'california': 'CA',
    'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE', 'florida': 'FL', 'georgia': 'GA',
    'hawaii': 'HI', 'idaho': 'ID', 'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA',
    'kansas': 'KS', 'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS', 'missouri': 'MO',
    'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV', 'new hampshire': 'NH', 'new jersey': 'NJ',
    'new mexico': 'NM', 'new york': 'NY', 'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH',
    'oklahoma': 'OK', 'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT', 'vermont': 'VT',
    'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV', 'wisconsin': 'WI', 'wyoming': 'WY'
}

# Runtime cache for dynamically resolved Rotary Clubs
# Persistent cache file for resolved Rotary Clubs
RESOLVED_CLUBS_PATH = Path(__file__).resolve().parent / "spc_resolved_clubs.json"
if not RESOLVED_CLUBS_PATH.exists():
    RESOLVED_CLUBS_PATH = Path(__file__).resolve().parent.parent / "spc_resolved_clubs.json"
if not RESOLVED_CLUBS_PATH.exists():
    RESOLVED_CLUBS_PATH = Path("spc_resolved_clubs.json")

# Runtime cache for dynamically resolved Rotary Clubs
RESOLVED_CLUBS_CACHE = {
    "lake atitlan": {"key": ROTARY_LAKE_ATITLAN_CLUB_KEY, "name": "Lake Atitlan", "id": "84633", "district": "4250"},
}

def load_resolved_clubs():
    if RESOLVED_CLUBS_PATH.exists():
        try:
            with open(RESOLVED_CLUBS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for k, v in data.items():
                        RESOLVED_CLUBS_CACHE[k.lower().strip()] = v
        except Exception as e:
            print(f"Warning: Failed to load {RESOLVED_CLUBS_PATH}: {e}")

def save_resolved_clubs():
    try:
        with open(RESOLVED_CLUBS_PATH, "w", encoding="utf-8") as f:
            json.dump(RESOLVED_CLUBS_CACHE, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save {RESOLVED_CLUBS_PATH}: {e}")

load_resolved_clubs()

KNOWN_DISTRICTS = {
    "7620": {"key": "9445e695-1a25-4e21-941e-3eff587a0a8f", "name": "7620"},
    "6330": {"key": "", "name": "6330"},
    "5440": {"key": "", "name": "5440"}
}

# Rotary International official global Partners in Service GUIDs
RI_SERVICE_PARTNERS = {
    "ashoka": "9367DB34-E7FA-494A-909E-8A363A2B8F54",
    "habitat for humanity": "23284EBE-1A9A-459C-BCBD-E63A8E1403B9",
    "iep": "08359657-3EEC-4385-B64F-C5AF428FB7B5",
    "peace corps": "AEFC46C7-A13A-4C33-B324-B342D136123E",
    "shelterbox": "428CE9D0-E7E4-4B6A-A8B5-3232D8D60BE7",
    "usaid": "49E5D5B0-8A6F-46BA-80F4-F12120F18FDC",
}


def _search_rotary_org_api(q_name: str, q_district: str = "") -> list:
    """Executes a search against the Rotary International Organization Search API with retries and throttling."""
    if not q_name or len(q_name.strip()) < 3:
        return []
    url = "https://spc.rotary.org/api/Search/Organization"
    req_body = json.dumps({
        "type": "Rotary Club",
        "clubName": q_name.strip(),
        "districtNumber": q_district.strip() if q_district else "",
        "countrykey": ""
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "subscriptionkey": "ROTARY_API_KEY"
    }

    max_retries = 3
    for attempt in range(max_retries):
        time.sleep(0.2)  # Pacing delay to avoid tripping 503 / Cloudflare limits
        try:
            req = urllib.request.Request(url, data=req_body, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                data = json.loads(resp.read().decode())
                if isinstance(data, list):
                    return data
                return []
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and attempt < max_retries - 1:
                wait_sec = (attempt + 1) * 1.5
                time.sleep(wait_sec)
                continue
            return []
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retries - 1:
                wait_sec = (attempt + 1) * 1.5
                time.sleep(wait_sec)
                continue
            return []
        except Exception:
            return []
    return []


def find_partner_club(club_name_str: str) -> dict:
    """Dynamically searches or looks up cached Rotary International Organization for partner clubs."""
    if not club_name_str:
        return None
    s = club_name_str.strip()
    s_lower = s.lower()

    # Fast-path 1: Exact raw string in cache
    if s_lower in RESOLVED_CLUBS_CACHE:
        return RESOLVED_CLUBS_CACHE[s_lower]

    # Normalize name variations
    clean = re.sub(r'\(d\d+\)', '', s, flags=re.IGNORECASE).strip()
    clean = re.sub(r'^(?:RC\s+of\s+|RC\s+|Rotary\s+Club\s+(?:of\s+)?|Club\s+Rotario\s+(?:de\s+)?)', '', clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\brotary\b', '', clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\bclub\b', '', clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r'\s+', ' ', clean).strip()

    clean_lower = clean.lower()
    # Fast-path 2: Cleaned string in cache
    if clean_lower in RESOLVED_CLUBS_CACHE:
        entry = RESOLVED_CLUBS_CACHE[clean_lower]
        RESOLVED_CLUBS_CACHE[s_lower] = entry
        return entry

    # Extract district if present in input string (e.g. '(D7620)' or '(d4250)')
    m_dist = re.search(r'\b[dD](\d{4})\b', s)
    district_num = m_dist.group(1) if m_dist else ""

    parts = [p.strip() for p in clean.split(',') if p.strip()]
    club_query = parts[0]
    loc_hint = parts[1] if len(parts) > 1 else ''

    if not loc_hint:
        m = re.match(r'^(.*?)\s+([A-Za-z]{2})$', club_query)
        if m and (m.group(2).lower() in US_STATE_ABBR or m.group(2).upper() in US_STATE_ABBR.values()):
            club_query = m.group(1).strip()
            loc_hint = m.group(2).strip()

    state_code = US_STATE_ABBR.get(loc_hint.lower(), loc_hint.upper()) if loc_hint else ''

    # Fast-path 3: First part in cache
    if club_query.lower() in RESOLVED_CLUBS_CACHE:
        entry = RESOLVED_CLUBS_CACHE[club_query.lower()]
        RESOLVED_CLUBS_CACHE[s_lower] = entry
        RESOLVED_CLUBS_CACHE[clean_lower] = entry
        return entry

    # Fast-path 4: Query without parentheses (e.g. 'Carroll Creek (Frederick)' -> 'Carroll Creek')
    no_paren = re.sub(r'\(.*?\)', '', club_query).strip()
    if no_paren.lower() in RESOLVED_CLUBS_CACHE:
        entry = RESOLVED_CLUBS_CACHE[no_paren.lower()]
        RESOLVED_CLUBS_CACHE[s_lower] = entry
        return entry

    # Fast-path 5: Mount / Mt. substitution
    mt_var = re.sub(r'\bMount\b', 'Mt.', club_query, flags=re.IGNORECASE) if "mount" in club_query.lower() else re.sub(r'\bMt\b\.?', 'Mount', club_query, flags=re.IGNORECASE)
    if mt_var.lower() in RESOLVED_CLUBS_CACHE:
        entry = RESOLVED_CLUBS_CACHE[mt_var.lower()]
        RESOLVED_CLUBS_CACHE[s_lower] = entry
        return entry

    # Multi-pass candidate queries for live API lookup
    candidate_queries = []
    # 1. Full query with district (if district known)
    if district_num:
        candidate_queries.append((club_query, district_num))
        candidate_queries.append((no_paren, district_num))
    # 2. Main club query without district
    candidate_queries.append((club_query, ""))
    # 3. Mount / Mt. variant
    if mt_var != club_query:
        candidate_queries.append((mt_var, ""))
    # 4. Without parentheses
    if no_paren != club_query and len(no_paren) >= 3:
        candidate_queries.append((no_paren, ""))
    # 5. Without prefix words like 'E-Club of', 'CdGuatemala', 'San Rafael'
    strip_prefix = re.sub(r'^(?:e-club of|cdguatemala|cd\s*guatemala)\s*', '', club_query, flags=re.IGNORECASE).strip()
    if strip_prefix != club_query and len(strip_prefix) >= 3:
        candidate_queries.append((strip_prefix, ""))

    seen_attempts = set()
    results = []
    for q_name, q_dist in candidate_queries:
        call_key = (q_name.lower().strip(), q_dist)
        if call_key in seen_attempts or len(q_name.strip()) < 3:
            continue
        seen_attempts.add(call_key)
        res = _search_rotary_org_api(q_name, q_dist)
        if res:
            results = res
            break

    if results:
        match = None
        # Priority match: state match if state known
        if state_code:
            for r in results:
                if r.get('orgName', '').lower() == club_query.lower() and (r.get('stateAddress') == state_code or state_code in str(r.get('countryAddress') or '')):
                    match = r
                    break
            if not match:
                for r in results:
                    if r.get('stateAddress') == state_code or state_code in str(r.get('countryAddress') or '') or state_code in str(r.get('provinceIntlAddress') or ''):
                        match = r
                        break
        # Exact name match
        if not match:
            for r in results:
                if r.get('orgName', '').lower() == club_query.lower():
                    match = r
                    break
        if not match and no_paren:
            for r in results:
                if r.get('orgName', '').lower() == no_paren.lower():
                    match = r
                    break
        if not match:
            match = results[0]

        entry = {
            "key": match.get("orgKey"),
            "name": match.get("orgName"),
            "id": match.get("clubIdExt"),
            "district": match.get("districtAddress"),
            "state": match.get("stateAddress"),
            "country": match.get("countryAddress")
        }
        RESOLVED_CLUBS_CACHE[s_lower] = entry
        RESOLVED_CLUBS_CACHE[clean_lower] = entry
        save_resolved_clubs()
        return entry

    return None


# --- Load Environment Variables ---
for p in ENV_PATHS:
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# --- Load Migration State ---
def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except Exception:
            return {}
    # Seed with the project already created in walkthrough
    return {
        "GG1529575": {
            "spc_id": "ba58cdaf-e167-47da-8b79-68b322ce8df0",
            "title": "SANIK-YA/ CHITULUL GUATEMALA WATER PROJECT",
            "migrated_at": "2026-09-16T16:56:58"
        }
    }

def sync_spc_state_to_supabase(pid: str, spc_id: str, spc_url: str, migrated_at: str):
    """Updates Supabase projects.sync_status and project_links for a migrated project."""
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY") or SUPABASE_ANON_KEY
    headers = {
        "apikey": service_key,
        "Authorization": f"Bearer {service_key}",
        "Content-Type": "application/json"
    }
    try:
        # 1. Update projects.sync_status
        req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}&select=id,sync_status", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data:
                row = data[0]
                sync_status = row.get("sync_status") or {}
                spc_status = sync_status.get("spc") or {}
                spc_status.update({
                    "exported": True,
                    "in_sync": True,
                    "spc_project_id": spc_id,
                    "spc_url": spc_url,
                    "last_exported": migrated_at
                })
                sync_status["spc"] = spc_status

                patch_req = urllib.request.Request(
                    f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}",
                    data=json.dumps({"sync_status": sync_status}).encode("utf-8"),
                    headers=headers,
                    method="PATCH"
                )
                urllib.request.urlopen(patch_req, timeout=10)
                print(f"  ✓ Synced SPC export status to Supabase projects ({pid})")

        # 2. Add or update link in project_links
        links_req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/project_links?project_id=eq.{pid}", headers=headers)
        with urllib.request.urlopen(links_req, timeout=10) as resp:
            existing_links = json.loads(resp.read().decode())
            spc_link = next((l for l in existing_links if "spc.rotary.org" in (l.get("url") or "") or l.get("label") == "Rotary Service Project Center (SPC)"), None)
            if spc_link:
                l_id = spc_link["id"]
                up_req = urllib.request.Request(
                    f"{SUPABASE_URL}/rest/v1/project_links?id=eq.{l_id}",
                    data=json.dumps({"url": spc_url, "label": "Rotary Service Project Center (SPC)"}).encode("utf-8"),
                    headers=headers,
                    method="PATCH"
                )
                urllib.request.urlopen(up_req, timeout=10)
            else:
                new_order = len(existing_links)
                ins_req = urllib.request.Request(
                    f"{SUPABASE_URL}/rest/v1/project_links",
                    data=json.dumps({
                        "project_id": pid,
                        "label": "Rotary Service Project Center (SPC)",
                        "url": spc_url,
                        "display_order": new_order
                    }).encode("utf-8"),
                    headers=headers,
                    method="POST"
                )
                urllib.request.urlopen(ins_req, timeout=10)
            print(f"  ✓ Recorded SPC link in project_links ({pid})")
    except Exception as e:
        print(f"  [Warning] Could not sync SPC state to Supabase for {pid}: {e}")

def save_state(state: dict, updated_pid: str = None):
    STATE_PATH.write_text(json.dumps(state, indent=2))
    if updated_pid and updated_pid in state:
        info = state[updated_pid]
        sync_spc_state_to_supabase(
            updated_pid,
            info.get("spc_id"),
            info.get("spc_url"),
            info.get("migrated_at")
        )

# --- Fetch Projects from Supabase & CSV ---
def fetch_supabase_projects() -> list:
    url = f"{SUPABASE_URL}/rest/v1/projects?select=*,project_links(*),project_assets(*)&order=id"
    req = urllib.request.Request(url, headers={
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}"
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"Error: Could not fetch from Supabase: {e}")
        return []

def build_project_list() -> list:
    """Loads all projects directly from Supabase, the single source of truth."""
    return fetch_supabase_projects()

# --- Helper to Clean Text & Build Overviews ---
def clean_text(s: str) -> str:
    if not s:
        return ""
    # Strip excessive markdown headers/dividers
    s = re.sub(r'#{1,6}\s*', '', s)
    s = re.sub(r'[*_~`]', '', s)
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()

def build_overview(description: str, narrative: str) -> str:
    src = description or narrative or "Rotary Club of Lake Atitlán community service project."
    cleaned = clean_text(src)
    lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
    if not lines:
        return "Community project in Sololá, Guatemala."
    first = lines[0]
    if len(first) > 180:
        return first[:177] + "..."
    return first

def match_area_of_focus(cat_str: str) -> tuple:
    s = (cat_str or "").lower()
    for key, (aof_key, aof_name) in AREA_OF_FOCUS_MAP.items():
        if key in s:
            return aof_key, aof_name
    # Default to Water or Economic Development
    if "wash" in s:
        return AREA_OF_FOCUS_MAP["water"]
    return AREA_OF_FOCUS_MAP["economic"]

# Rotary SPC Constants
SPC_FUND_TYPE_MAP = {
    "NonGovernmentalOrganization": "123456be-cece-4096-ab1b-4a554f213f14",
    "GovernmentEntity": "123456be-cece-4096-ab1b-4a554f213f13",
    "LocalCommunityGroup": "123456be-cece-4096-ab1b-4a554f213f16",
    "Foundation": "123456be-cece-4096-ab1b-4a554f213f15",
    "Rotary Club": "123456be-cece-4096-ab1b-4a554f213f05",
    "Other": "123456be-cece-4096-ab1b-4a554f213f07",
}

SPC_PARTNER_CATEGORY_FUNDING = "09b7b3de-56b4-4d12-95b1-eaa58b53f573" # Funding partner
SPC_PARTNER_CATEGORY_IMPLEMENTING = "b8d43fa6-15a2-4398-b60e-ef07a3f09f16" # Implementing Partner
SPC_PARTNER_CATEGORY_BOTH = "8881284b-572b-4247-8546-6f5a9ead9ae8" # Funding partner, Implementing Partner

def clean_partner_name(name: str) -> str:
    if not name:
        return ""
    clean = str(name).strip()
    # 1. Normalize curly quotes and apostrophes to standard ASCII
    clean = clean.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    clean = clean.replace("**", "").replace("*", "").strip()
    clean = re.sub(r'^[•\-\*\s]+', '', clean)

    # 2. Strip em-dash / hyphen descriptions
    clean = re.split(r'\s+[—–-]\s+(?:Cooperating|Implementing|Local|Partner|School|Municipal)', clean, flags=re.I)[0].strip()
    clean = re.split(r'\s+[—–-]\s+', clean)[0].strip()

    # 3. Strip noisy descriptive parentheticals (roles, websites, geographic notes)
    clean = re.sub(r'\s*\([^)]*(?:https?://|www\.)[^)]*\)', '', clean, flags=re.I)
    clean = re.sub(r'\s*\([^)]*\b(?:partner|cooperating|implementing|councils|consejo|non-rotarian|donor|usa|guatemala|eagan|hopedale|spain|minnesota)\b[^)]*\)', '', clean, flags=re.I)

    # 4. Strip standalone URLs and website links
    clean = re.sub(r'https?://\S+', '', clean)
    clean = re.sub(r'www\.\S+', '', clean)

    # 5. Strip trailing geographic metadata suffixes (e.g. ", Panajachel, Sololá, Guatemala")
    clean = re.sub(r',\s*(?:Panajachel|Sololá|Solola|Guatemala|Quetzaltenango|Antigua|San Francisco|Black Mountain|Eagan|Hopedale).*$', '', clean, flags=re.I)

    # 6. Strip unclosed opening parentheses at end or unopened closing parentheses at start
    if clean.startswith('(') and clean.endswith(')') and clean.count('(') == 1 and clean.count(')') == 1:
        clean = clean[1:-1].strip()
    if clean.count('(') > clean.count(')'):
        clean = re.sub(r'\s*\([^)]*$', '', clean)
    if clean.count(')') > clean.count('('):
        clean = re.sub(r'^[^(]*\)\s*', '', clean)

    # 7. Clean boundary punctuation and truncate to SPC max length
    clean = re.sub(r'^[,\.\s;:\-]+', '', clean).strip()
    clean = re.sub(r'[,\.\s;:\-]+$', '', clean).strip()
    return clean[:100].strip()

def extract_partner_organizations(p: dict) -> list:
    """Dynamically extracts all non-Rotary partner organizations (NGOs, Government, Community groups)
    from Supabase details, partner fields, and grant narratives."""
    orgs = []
    seen_keys = set()
    seen_names = []

    def add_org(name: str, org_type: str = "NonGovernmentalOrganization"):
        clean = clean_partner_name(name)
        if not clean or len(clean) < 2:
            return
        clean_lower = clean.lower()
        if any(w in clean_lower for w in ["rotary club", "rc ", "rotary international", "district "]):
            return
        if clean_lower in ("none stated", "none", "n/a", "test", "various", "tbd", "unknown", "guatemala", "san francisco"):
            return

        words_clean = set(re.findall(r'[a-z0-9]+', clean_lower))
        for idx, existing in enumerate(seen_names):
            ex_lower = existing.lower()
            if clean_lower == ex_lower:
                return
            if clean_lower in ex_lower:
                return
            if ex_lower in clean_lower:
                seen_names[idx] = clean
                orgs[idx]["name"] = clean
                return
            words_ex = set(re.findall(r'[a-z0-9]+', ex_lower))
            if words_clean and words_ex:
                overlap = len(words_clean.intersection(words_ex)) / min(len(words_clean), len(words_ex))
                if overlap >= 0.6:
                    if len(clean) > len(existing):
                        seen_names[idx] = clean
                        orgs[idx]["name"] = clean
                    return

        key = re.sub(r'[^a-z0-9]', '', clean_lower)
        if key in seen_keys:
            return
        seen_keys.add(key)
        seen_names.append(clean)

        t = "NonGovernmentalOrganization"
        if any(w in clean_lower for w in ["municipality", "municipal", "department of education", "ministry", "government", "mayor", "alcaldia"]):
            t = "GovernmentEntity"
        elif any(w in clean_lower for w in ["committee", "cocode", "community", "church", "iglesia", "aldea", "caserio"]):
            t = "LocalCommunityGroup"
        elif any(w in clean_lower for w in ["foundation", "fundacion"]):
            t = "Foundation"
        elif any(w in clean_lower for w in ["hospital", "clinic", "health", "salud"]):
            t = "NonGovernmentalOrganization"

        orgs.append({
            "name": clean,
            "type": t,
            "fundTypeId": SPC_FUND_TYPE_MAP.get(t, SPC_FUND_TYPE_MAP["NonGovernmentalOrganization"])
        })

    details = p.get("details") or {}
    if isinstance(details, str):
        try: details = json.loads(details)
        except Exception: details = {}

    for ip in details.get("implementing_partners", []):
        if isinstance(ip, dict):
            add_org(ip.get("name"), ip.get("source"))
        elif isinstance(ip, str):
            add_org(ip)

    co_list = details.get("cooperating_organizations") or []
    if isinstance(co_list, str):
        co_list = [c.strip() for c in co_list.split(",") if c.strip()]
    for co in co_list:
        if isinstance(co, str):
            for sub in co.split(","):
                add_org(sub.strip())

    partner_str = str(p.get("partner") or "").strip()
    if partner_str:
        for sub in partner_str.split(","):
            add_org(sub.strip())

    narrative = str(p.get("narrative") or "")
    if "Partner Organizations" in narrative or "NGOs & Local Organizations" in narrative or "Cooperating Organization" in narrative:
        in_ngo_section = False
        for line in narrative.splitlines():
            line_str = line.strip()
            if "NGOs & Local Organizations" in line_str or "Cooperating Organization" in line_str:
                in_ngo_section = True
                continue
            if in_ngo_section:
                if line_str.startswith("#") or line_str.startswith("**Rotary Clubs**"):
                    in_ngo_section = False
                    continue
                if line_str.startswith("-") or line_str.startswith("*"):
                    item = line_str.lstrip("-* ").strip()
                    # 1. Strip em-dash / en-dash / double-hyphen description
                    item_org = re.split(r'\s+[—–-]\s+', item)[0].strip()
                    # 2. Check if the remaining org part is a comma-separated list of multiple distinct orgs
                    if len(item_org.split(",")) > 3 and not any(loc in item_org.lower() for loc in ["sololá", "panajachel", "guatemala"]):
                        for sub_item in item_org.split(","):
                            add_org(sub_item.strip())
                    else:
                        add_org(item_org)

    # Final deduplication pass: remove any org that is a substring of another org
    final_orgs = []
    for org in orgs:
        o_lower = org["name"].lower()
        if any(o_lower != other["name"].lower() and o_lower in other["name"].lower() for other in orgs):
            continue
        final_orgs.append(org)

    return final_orgs

# --- Build SPC Payload ---
def construct_spc_payload(p: dict) -> dict:
    gid = String(p.get("id") or p.get("grant_id") or "").strip()
    title = p.get("title") or gid or "Untitled Project"
    narrative = p.get("narrative") or ""
    description = p.get("description") or ""

    details = p.get("details") or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except Exception:
            details = {}

    partner_name = (p.get("partner") or "").strip()

    # Dynamically extract all cooperating organizations / implementing partners
    extracted_partners = extract_partner_organizations(p)
    cooperating_orgs = [o["name"] for o in extracted_partners]

    full_desc = description.strip()
    if narrative.strip() and narrative.strip() != description.strip():
        if full_desc:
            full_desc += "\n\n" + clean_text(narrative)
        else:
            full_desc = clean_text(narrative)

    # Prioritize complete_overview if available
    complete = (p.get("complete_overview") or "").strip()
    if complete:
        full_desc = clean_text(complete)
    elif not full_desc:
        full_desc = f"{title}. Project facilitated by the Rotary Club of Lake Atitlán."

    # Highlight cooperating organizations prominently in description
    if cooperating_orgs:
        org_names = [o for o in cooperating_orgs if "rotary" not in o.lower()]
        if org_names and not any("cooperating partner" in full_desc.lower() for _ in [1]):
            callout = "Cooperating Partner(s): " + ", ".join(org_names) + "."
            max_desc_len = 1000 - len(callout) - 2
            if len(full_desc) > max_desc_len:
                full_desc = full_desc[:max_desc_len].rsplit(' ', 1)[0].rstrip('.,;:') + "..."
            full_desc = full_desc.rstrip() + "\n\n" + callout



    # Prioritize brief_overview if available
    brief = (p.get("brief_overview") or "").strip()
    overview = clean_text(brief) if brief else build_overview(description, narrative)

    # --- Rotary SPC Character Length Validation Constraints ---
    # 1. prjTitle: max 50 characters
    if len(title) > 50:
        title = title.replace("Water, Sanitation, Hygiene", "WASH").replace("Water, Sanitation and Hygiene", "WASH")
    if len(title) > 50:
        title = title[:50].rsplit(' ', 1)[0].strip()
    if len(title) > 50 or not title:
        title = (p.get("title") or gid)[:50].strip()

    # 2. prjOverview: max 100 characters
    if len(overview) > 100:
        overview = overview[:97].rsplit(' ', 1)[0].strip() + "..."
    if len(overview) > 100:
        overview = overview[:100]

    # 3. prjDetailedDescription: max 1,000 characters
    if len(full_desc) > 1000:
        full_desc = full_desc[:997].rsplit(' ', 1)[0].strip() + "..."
    if len(full_desc) > 1000:
        full_desc = full_desc[:1000]

    # Dates
    def to_spc_date(dt_str, fallback_m, fallback_d, fallback_y):
        if not dt_str:
            return f"{fallback_m}/{fallback_d}/{fallback_y}"
        parts = str(dt_str).strip().split("-")
        if len(parts) == 3:
            return f"{parts[1].zfill(2)}/{parts[2].zfill(2)}/{parts[0]}"
        elif len(parts) == 2:
            return f"{parts[1].zfill(2)}/15/{parts[0]}"
        elif len(parts) == 1 and parts[0].isdigit():
            return f"01/15/{parts[0]}"
        return f"{fallback_m}/{fallback_d}/{fallback_y}"

    start_y = str(p.get("start_year") or "2020").strip()
    end_y = str(p.get("end_year") or start_y).strip()
    if not start_y.isdigit(): start_y = "2020"
    if not end_y.isdigit(): end_y = start_y

    start_date = to_spc_date(p.get("start_date"), "01", "15", start_y)
    end_date = to_spc_date(p.get("end_date"), "12", "15", end_y)

    # Coordinates & Location
    lat = str(p.get("position_lat") or "14.703454")
    lng = str(p.get("position_lng") or "-91.191623")
    partner_name = (p.get("partner") or "").strip()
    location_name = partner_name if partner_name else "Lake Atitlán Region"

    # Status
    raw_status = (p.get("status") or "completed").lower()
    is_completed = raw_status in ["closed", "completed", "actual"]
    is_proposed = raw_status in ["proposed", "proposal", "draft"]
    status_type = "Proposed" if is_proposed else "Actual"

    # Budget
    budget_raw = p.get("amount") or p.get("budget") or "0"
    try:
        num_budget = int(float(re.sub(r'[^0-9.]', '', str(budget_raw)) or 0))
    except Exception:
        num_budget = 0
    budget_str = str(num_budget) if num_budget > 0 else "5000"

    # Area of Focus
    category = p.get("category") or ""
    aof_key, aof_name = match_area_of_focus(category)

    # Category flags
    is_international = "global" in (p.get("project_type") or "").lower() or gid.startswith("GG")
    is_foundation = is_international or "district grant" in (p.get("project_type") or "").lower()

    # Rel Links
    rel_links = []
    # Always include the permanent deep link back to our project archive map!
    map_url = f"https://mrosen.github.io/rcla_project_map/?source=supabase&project={gid}"
    b64_map_url = base64.b64encode(map_url.encode()).decode()
    rel_links.append({
        "relLinkType": "5",
        "url": b64_map_url,
        "caption": "RCLA Project Map Archive Record",
        "IsCoverPhoto": "0"
    })

    # Add external links if present (skipping existing SPC links)
    for link in p.get("project_links") or []:
        url_raw = link.get("url")
        if url_raw and "spc.rotary.org" not in url_raw:
            b64_url = base64.b64encode(url_raw.encode()).decode()
            raw_cap = (link.get("label") or "Project Link")[:50]
            rel_links.append({
                "relLinkType": "6",
                "url": b64_url,
                "caption": raw_cap,
                "IsCoverPhoto": "0"
            })

    # Funding Sources & Partners
    details = p.get("details") or {}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except Exception:
            details = {}

    partners = []
    fundings = []

    # Always ensure host club is registered
    partners.append({
        "partnerOrganizationKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
        "Hour": "",
        "MoneyDonated": "",
        "NoOfVolunteer": "",
        "year": ""
    })

    has_custom_details = bool(details.get("world_fund") or details.get("district_ddf") or details.get("club_contributions") or details.get("partner_clubs") or details.get("partner_districts") or details.get("cooperating_organizations"))

    if has_custom_details:
        # 1. World Fund
        wf_amt = details.get("world_fund") or 0
        if not wf_amt and is_international and gid.startswith("GG") and num_budget:
            wf_amt = int(num_budget * 0.45)
        try:
            num_wf = float(re.sub(r'[^0-9.]', '', str(wf_amt)) or 0)
        except Exception:
            num_wf = 0
        if num_wf > 0:
            fundings.append({
                "fundingSource": "Global grant",
                "fundingAmount": str(int(num_wf)),
                "fundingClubKey": gid,
                "fundingOtherName": gid
            })

        # 2. Districts (DDF)
        explicit_dist_contribs = details.get("district_contributions")
        if explicit_dist_contribs and isinstance(explicit_dist_contribs, list):
            for dc in explicit_dist_contribs:
                dnum = re.sub(r'[^0-9]', '', str(dc.get("district", ""))) or str(dc.get("district", "")).strip()
                amt_val = float(re.sub(r'[^0-9.]', '', str(dc.get("amount", 0))) or 0)
                if dnum and amt_val > 0:
                    fundings.append({
                        "fundingSource": dc.get("source", "District(DDF)"),
                        "fundingAmount": str(int(amt_val)),
                        "fundingClubKey": dnum,
                        "fundingOtherName": dnum
                    })
        else:
            raw_pdist = details.get("partner_districts") or []
            if isinstance(raw_pdist, str):
                raw_pdist = [d.strip() for d in raw_pdist.split(",") if d.strip()]
            intl_dist_raw = str(details.get("international_district") or p.get("international_club_district") or "").strip()
            intl_clean_d = re.sub(r'[^0-9]', '', intl_dist_raw) or intl_dist_raw
            if intl_clean_d and intl_clean_d not in raw_pdist:
                raw_pdist.append(intl_clean_d)

            total_ddf = details.get("district_ddf") or 0
            try:
                num_ddf = float(re.sub(r'[^0-9.]', '', str(total_ddf)) or 0)
            except Exception:
                num_ddf = 0

            target_d = intl_clean_d if (intl_clean_d and intl_clean_d != "4250") else None
            if not target_d:
                non_host = [re.sub(r'[^0-9]', '', str(d)) for d in raw_pdist if re.sub(r'[^0-9]', '', str(d)) and re.sub(r'[^0-9]', '', str(d)) != "4250"]
                target_d = non_host[0] if non_host else (raw_pdist[0] if raw_pdist else None)

            if target_d and num_ddf > 0:
                clean_target = re.sub(r'[^0-9]', '', str(target_d)) or str(target_d).strip()
                fundings.append({
                    "fundingSource": "District(DDF)",
                    "fundingAmount": str(int(num_ddf)),
                    "fundingClubKey": clean_target,
                    "fundingOtherName": clean_target
                })

        # 3. Contributing / Partner Clubs
        explicit_club_contribs = details.get("club_contributions_list")
        if explicit_club_contribs and isinstance(explicit_club_contribs, list):
            for cc in explicit_club_contribs:
                c_name = str(cc.get("name", "")).strip()
                if not c_name:
                    continue
                matched_club = find_partner_club(c_name)
                ckey = cc.get("club_key") or (matched_club.get("key") if matched_club else None)
                amt_val = float(re.sub(r'[^0-9.]', '', str(cc.get("amount", 0))) or 0)
                amt_str = str(int(amt_val)) if amt_val > 0 else ""

                is_host = (ckey == ROTARY_LAKE_ATITLAN_CLUB_KEY or "lake atitlan" in c_name.lower())
                use_key = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else (ckey or c_name)

                existing_p = next((pt for pt in partners if str(pt.get("partnerOrganizationKey", "")).lower() == str(use_key).lower()), None)
                if not existing_p:
                    partners.append({
                        "partnerOrganizationKey": use_key,
                        "Hour": "",
                        "MoneyDonated": amt_str,
                        "NoOfVolunteer": "",
                        "year": ""
                    })
                elif amt_str and not existing_p.get("MoneyDonated"):
                    existing_p["MoneyDonated"] = amt_str

                if amt_val > 0:
                    f_item = {
                        "fundingSource": "Rotary Club",
                        "fundingAmount": amt_str,
                        "fundingClubKey": use_key if ckey or is_host else ""
                    }
                    if ckey or is_host:
                        f_item["fundingSourceKey"] = use_key
                    else:
                        f_item["fundingOtherName"] = c_name
                    fundings.append(f_item)

            # Ensure any non-contributing clubs named in partner_clubs are still represented in partners
            for c_raw in (details.get("partner_clubs") or []):
                c_name = str(c_raw).strip()
                if not c_name:
                    continue
                matched = find_partner_club(c_name)
                k = matched.get("key") if matched else c_name
                is_host = (k == ROTARY_LAKE_ATITLAN_CLUB_KEY or "lake atitlan" in c_name.lower())
                use_k = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else k
                existing_p = next((pt for pt in partners if str(pt.get("partnerOrganizationKey", "")).lower() == str(use_k).lower()), None)
                if not existing_p:
                    partners.append({
                        "partnerOrganizationKey": use_k,
                        "Hour": "",
                        "MoneyDonated": "",
                        "NoOfVolunteer": "",
                        "year": ""
                    })
        else:
            raw_pclubs = details.get("partner_clubs") or []
            if isinstance(raw_pclubs, str):
                raw_pclubs = [c.strip() for c in raw_pclubs.split(",") if c.strip()]
            intl_club_raw = str(details.get("international_club") or p.get("international_club_name") or "").strip()
            if intl_club_raw and intl_club_raw not in raw_pclubs:
                raw_pclubs.insert(0, intl_club_raw)

            total_cash = details.get("club_contributions") or 0
            try:
                num_cash = float(re.sub(r'[^0-9.]', '', str(total_cash)) or 0)
            except Exception:
                num_cash = 0

            for idx, c_name in enumerate(raw_pclubs):
                c_str = str(c_name).strip()
                if not c_str:
                    continue
                matched_club = find_partner_club(c_str)
                ckey = matched_club.get("key") if matched_club else None
                amt_val = num_cash if (idx == 0 and num_cash > 0) else 0
                amt_str = str(int(amt_val)) if amt_val > 0 else ""

                is_host = (ckey == ROTARY_LAKE_ATITLAN_CLUB_KEY or "lake atitlan" in c_str.lower())
                use_key = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else (ckey or c_str)

                existing_p = next((pt for pt in partners if str(pt.get("partnerOrganizationKey", "")).lower() == str(use_key).lower()), None)
                if not existing_p:
                    partners.append({
                        "partnerOrganizationKey": use_key,
                        "Hour": "",
                        "MoneyDonated": amt_str,
                        "NoOfVolunteer": "",
                        "year": ""
                    })
                elif amt_str and not existing_p.get("MoneyDonated"):
                    existing_p["MoneyDonated"] = amt_str

                if amt_val > 0:
                    f_item = {
                        "fundingSource": "Rotary Club",
                        "fundingAmount": amt_str,
                        "fundingClubKey": use_key if ckey or is_host else ""
                    }
                    if ckey or is_host:
                        f_item["fundingSourceKey"] = use_key
                    else:
                        f_item["fundingOtherName"] = c_str
                    fundings.append(f_item)

        # 4. Other Contributions (e.g. Donor Advised Funds, Cooperating Partners)
        other_contribs = details.get("other_contributions")
        if other_contribs and isinstance(other_contribs, list):
            for oc in other_contribs:
                o_name = str(oc.get("name", "")).strip()
                amt_val = float(re.sub(r'[^0-9.]', '', str(oc.get("amount", 0))) or 0)
                amt_str = str(int(amt_val)) if amt_val > 0 else ""
                if amt_val > 0 and o_name:
                    fundings.append({
                        "fundingSource": "Other",
                        "fundingAmount": amt_str,
                        "fundingClubKey": "",
                        "fundingOtherName": o_name
                    })
    else:
        intl_club = str(p.get("international_club_name") or p.get("internationalClub_name") or "").strip()
        partner_club = find_partner_club(intl_club)
        partner_club_key = partner_club.get("key") if partner_club else None

        fundings = []
        intl_dist_raw = str(p.get("international_club_district") or p.get("internationalClub_district") or "").strip()
        dist_digits = re.sub(r'[^0-9]', '', intl_dist_raw)
        intl_dist = dist_digits if dist_digits else intl_dist_raw

        if is_international and gid.startswith("GG"):
            fundings.append({
                "fundingSource": "Global grant",
                "fundingAmount": str(int(num_budget * 0.45)) if num_budget else "20000",
                "fundingClubKey": gid,
                "fundingOtherName": gid
            })
            if intl_dist:
                fundings.append({
                    "fundingSource": "District(Cash)",
                    "fundingAmount": str(int(num_budget * 0.35)) if num_budget else "15000",
                    "fundingClubKey": intl_dist,
                    "fundingOtherName": intl_dist
                })
            if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.15)) if num_budget else "5000",
                    "fundingClubKey": partner_club_key,
                    "fundingSourceKey": partner_club_key
                })
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.05)) if num_budget else "2000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "fundingSourceKey": ROTARY_LAKE_ATITLAN_CLUB_KEY
                })
            else:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.20)) if num_budget else "5000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "fundingSourceKey": ROTARY_LAKE_ATITLAN_CLUB_KEY
                })
        else:
            if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": budget_str,
                    "fundingClubKey": partner_club_key
                })
            elif intl_dist:
                fundings.append({
                    "fundingSource": "District(Cash)",
                    "fundingAmount": budget_str,
                    "fundingClubKey": intl_dist
                })
            else:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": budget_str,
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY
                })

        if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
            partners.append({
                "partnerOrganizationKey": partner_club_key,
                "Hour": "",
                "MoneyDonated": budget_str if num_budget else "",
                "NoOfVolunteer": "",
                "year": ""
            })
        elif intl_club and "lake atitlan" not in intl_club.lower():
            partners.append({
                "partnerOrganizationKey": intl_club,
                "Hour": "",
                "MoneyDonated": budget_str if num_budget else "",
                "NoOfVolunteer": "",
                "year": ""
            })

    # Strict Funding Cleanup: ONLY entries with fundingAmount > 0 are allowed in Rotary SPC
    clean_fundings = []
    for f in fundings:
        f_amt = float(re.sub(r'[^0-9.]', '', str(f.get("fundingAmount", 0))) or 0)
        if f_amt > 0:
            clean_fundings.append(f)
    fundings = clean_fundings

    # Project search tags (semicolon-delimited for Rotary SPC, max 100 chars)
    tag_list = []
    for org in cooperating_orgs:
        if org and org not in tag_list and "rotary" not in org.lower():
            tag_list.append(org)
    if aof_name and aof_name not in tag_list:
        tag_list.append(aof_name)
    tag_list.append("Guatemala")
    tag_list.append("Lake Atitlan")

    shortened_tags = []
    cur_len = 0
    for t in tag_list:
        add_len = len(t) + (1 if shortened_tags else 0)
        if cur_len + add_len <= 100:
            shortened_tags.append(t)
            cur_len += add_len
        else:
            break
    tags_str = ";".join(shortened_tags)

    # Map any official Rotary International Service Partners (Peace Corps, USAID, etc.)
    matched_ri_partners = []
    for ep in extracted_partners:
        ep_clean = ep["name"].lower()
        for ri_name, ri_guid in RI_SERVICE_PARTNERS.items():
            if ri_name in ep_clean and ri_guid not in matched_ri_partners:
                matched_ri_partners.append(ri_guid)

    payload = {
        "projectSource": "4",
        "individualEmail": MEMBER_EMAIL,
        "currentSignedInIndividualKey": MEMBER_KEY,
        "currentSignedInMemberId": MEMBER_ID,
        "currentSignedInMemberName": MEMBER_NAME,
        "title": title,
        "overview": overview,
        "description": full_desc,
        "startDate": start_date,
        "endDate": end_date if is_completed else "",
        "countryId": ROTARY_GUATEMALA_COUNTRY_KEY,
        "tags": tags_str,
        "communityImpact": "",
        "projectImpact": "",
        "sustainImpact": "",
        "difficultyLevel": "",
        "estimatedBudget": budget_str,
        "estimatedAmount": "",
        "projectTypeCompleteStatus": status_type,
        "year": "",
        "month": "",
        "location": location_name,
        "address1": "",
        "address2": "",
        "address3": "",
        "locationCity": "Panajachel",
        "locationState": "Sololá Department",
        "stateId": "",
        "locationPostalCode": "",
        "latitude": lat,
        "longitude": lng,
        "optGlobalGrants": False,
        "isBasicLevel": False,
        "isIntermediateLevel": False,
        "isAdvancedLevel": True if is_completed else False,
        "isOptGlobalGrants": False,
        "isEstimatedStartTime": False,
        "isEstimatedDuration": False,
        "estimatedDuration": "",
        "durationType": "Days",
        "isCompleted": is_completed,
        "projectCategoryFund": {
            "communityFlag": "1" if not is_international else "0",
            "internationalFlag": "1" if is_international else "0",
            "vocationalFlag": "0",
            "newGenerationFlag": "0",
            "fundRaiserFlag": "0",
            "polioFlag": "0",
            "environmentalFlag": "1" if "environment" in category.lower() else "",
            "disasterResponseFlag": "1" if "emergency" in category.lower() else "0",
            "areaOfFocusFlag": "1",
            "areaOfFocusValue": aof_key,
            "clubFoundationFlag": "",
            "publicRelationGrantFlag": "",
            "rotaryFoundationGrantFlag": is_foundation,
            "otherFlag": "",
            "otherValue": ""
        },
        "projectRelLinks": rel_links,
        "projectContacts": [{
            "individualContactKey": MEMBER_KEY,
            "individualContactId": MEMBER_ID
        }],
        "projectFundings": fundings,
        "projectPartnerClubMembers": partners,
        "projectInkindDonations": [],
        "projectNonRotaryPartners": [
            {"nonRotaryPartnerKey": guid}
            for guid in matched_ri_partners
        ],
        "language1": "Spanish",
        "language2": ""
    }

    return payload

def String(val):
    return str(val) if val is not None else ""

# --- Main Automation Runner ---
async def main():
    print("=" * 70)
    print("  ROTARY SERVICE PROJECT CENTER (SPC) — AUTOMATED MIGRATOR")
    print("=" * 70)

    state = load_state()
    projects = build_project_list()
    print(f"Total projects loaded: {len(projects)}")
    print(f"Projects tracked in state file: {len(state)}")

    # Parse CLI arguments
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = [a.lower() for a in sys.argv[1:] if a.startswith("-")]

    is_dry_run = (
        "--dry-run" in flags
        or "-d" in flags
        or os.environ.get("SPC_DRY_RUN", "").lower() in ("true", "1", "yes")
    )
    migrate_all = "--all" in flags or "-a" in flags
    force_update = "--update" in flags or "-u" in flags or "--force" in flags

    unmigrated = [p for p in projects if not state.get(String(p.get("id")).strip(), {}).get("spc_id")]
    print(f"Projects unmigrated in local state: {len(unmigrated)}")

    # Check if a specific project ID was passed
    if args:
        if args[0].isdigit():
            limit = int(args[0])
            to_migrate = (projects if force_update else unmigrated)[:limit]
            print(f"Running limited batch of: {limit} project(s)")
        else:
            target_pid = args[0].strip().lower()
            matched = [p for p in projects if String(p.get("id")).strip().lower() == target_pid]
            if not matched:
                print(f"Error: Project '{args[0]}' not found in database/CSV.")
                return
            to_migrate = matched
            print(f"Targeting single specific project: {matched[0].get('id')}")
    elif migrate_all:
        to_migrate = projects if force_update else unmigrated
        print(f"Targeting all {len(to_migrate)} project(s)...")
    else:
        # Default safety mode: migrate ONLY 1 project!
        if not unmigrated:
            print("✓ All projects are already marked as migrated in local state!")
            print("  Use 'python migrate_to_spc.py <project_id>' to inspect or update a specific project.")
            print("  Use 'python migrate_to_spc.py --update --all' to force re-check/update all projects.")
            return
        to_migrate = unmigrated[:1]
        print("\n[SAFE MODE ACTIVE] Processing ONLY 1 single project for verification.")
        print("-> To target a specific project: python migrate_to_spc.py <project_id>")
        print("-> To migrate all pending projects: python migrate_to_spc.py --all")
        print("-> To dry-run without connecting: python migrate_to_spc.py --dry-run")

    if is_dry_run:
        print("\n=== DRY RUN MODE (No browser or API calls) ===")
        for p in to_migrate:
            pid = String(p.get("id"))
            payload = construct_spc_payload(p)
            print(f"\n--- Payload Preview for {pid} ---")
            print(json.dumps(payload, indent=2))
        print("\n✓ Dry run complete.")
        return

    force_headful = "--headful" in flags or os.getenv("HEADFUL", "").lower() in ("true", "1")
    force_headless = "--headless" in flags
    headless_mode = not force_headful

    async with async_playwright() as pw:
        print(f"\n[1/4] Launching Playwright browser (headless={headless_mode})...")
        browser = await pw.chromium.launch(headless=headless_mode, slow_mo=50 if not headless_mode else 0)
        context = await browser.new_context()
        page = await context.new_page()

        # Step 1: Login
        print("[2/4] Logging into My Rotary...")
        await page.goto("https://my.rotary.org/en/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        email = os.getenv("ROTARY_EMAIL", "")
        password = os.getenv("ROTARY_PASSWORD", "")

        if email and password:
            try:
                # Accept OneTrust cookies if present to allow Okta sign-in widget to render
                try:
                    accept_btn = await page.wait_for_selector("#onetrust-accept-btn-handler", timeout=6000)
                    if accept_btn:
                        await accept_btn.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                user_input = None
                for selector in ["#okta-signin-username", "input[name='username']", "input[name='identifier']", "input[type='email']"]:
                    try:
                        user_input = await page.wait_for_selector(selector, timeout=6000)
                        if user_input:
                            break
                    except Exception:
                        pass
                if not user_input:
                    user_input = await page.wait_for_selector("#okta-signin-username", timeout=15000)
                await user_input.fill(email)
                await page.fill("#okta-signin-password, input[name='password']", password)

                submitted = False
                try:
                    await page.click("#okta-signin-submit, input[type='submit']", force=True, timeout=5000)
                    submitted = True
                except Exception:
                    pass

                if not submitted:
                    try:
                        await page.keyboard.press("Enter")
                        submitted = True
                    except Exception:
                        pass

                if not submitted:
                    await page.evaluate("() => { const b = document.querySelector('#okta-signin-submit, input[type=\\'submit\\']'); if (b) b.click(); }")

                print("  Submitted login form. Waiting for authentication...", flush=True)
            except Exception as e:
                print(f"  Note on auto-fill: {e}", flush=True)

        # Wait until we leave the login page
        await page.wait_for_timeout(3000)
        if "login" in page.url.lower():
            try:
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=30000)
            except Exception:
                print("  Waiting for authentication to finalize...", flush=True)
                await page.wait_for_url(lambda u: "login" not in u.lower(), timeout=60000)
        print("  ✓ Successfully authenticated with My Rotary.")

        # Step 2: Navigate to SPC
        print("[3/4] Establishing session on spc.rotary.org...")
        await page.goto("https://spc.rotary.org/", wait_until="domcontentloaded")
        await page.wait_for_timeout(3000)

        # Step 3: Fetch existing club projects from SPC to prevent duplicates
        print("\n[3.5/4] Querying Rotary SPC for existing Lake Atitlán projects to prevent duplicates...")
        existing_spc_projects = await page.evaluate("""async (clubKey) => {
            try {
                const res = await fetch('https://spc.rotary.org/api/Search', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'accept': '*/*',
                        'subscriptionkey': 'ROTARY_API_KEY'
                    },
                    body: JSON.stringify({
                        clubKey: clubKey,
                        limit: '500',
                        funding: '', areaOfFocus: '', category: '', riyear: '', country: '',
                        zone: '', district: '', clubType: '', clubName: 'Lake Atitlan',
                        status: '', keyword: '', photo: '', memberId: '', languages: '',
                        City: '', latitude: '', longitude: '', distance: '', variation: 'en'
                    })
                });
                if (!res.ok) return [];
                return await res.json();
            } catch (e) {
                return [];
            }
        }""", ROTARY_LAKE_ATITLAN_CLUB_KEY)

        print(f"  Found {len(existing_spc_projects)} existing project(s) on SPC for our club.")
        for ep in existing_spc_projects:
            print(f"   • {ep.get('title')} (Key: {ep.get('nfKey')})")

        # Step 4: Migration / Update Loop
        print(f"\n[4/4] Beginning processing of {len(to_migrate)} project(s)...")

        for idx, p in enumerate(to_migrate, start=1):
            pid = String(p.get("id") or p.get("grant_id") or "").strip()
            title = p.get("title") or pid
            print(f"\n[{idx}/{len(to_migrate)}] Processing: {pid} — {title[:45]}...")

            payload = construct_spc_payload(p)
            payload_title = payload.get("title") or title

            # Check if this project already exists on SPC
            existing_match = None
            norm_title = re.sub(r'[\s\-_\/]+', ' ', title.lower()).strip()
            norm_payload_title = re.sub(r'[\s\-_\/]+', ' ', payload_title.lower()).strip()
            norm_pid = pid.lower().strip()

            # First check local state
            if pid in state and state[pid].get("spc_id"):
                existing_match = {"nfKey": state[pid]["spc_id"], "title": state[pid].get("title", title)}

            # Also check against the live SPC list
            if not existing_match:
                for ep in existing_spc_projects:
                    ep_title = re.sub(r'[\s\-_\/]+', ' ', (ep.get("title") or "").lower()).strip()
                    ep_desc = (ep.get("description") or "").lower()
                    ep_summary = (ep.get("summary") or "").lower()

                    # Match by exact/partial title or Grant ID
                    if (norm_title and (norm_title == ep_title or norm_title in ep_title or ep_title in norm_title)) or \
                       (norm_payload_title and (norm_payload_title == ep_title or norm_payload_title in ep_title or ep_title in norm_payload_title)):
                        existing_match = ep
                        break
                    if norm_pid and len(norm_pid) > 3 and (norm_pid in ep_title or norm_pid in ep_desc or norm_pid in ep_summary):
                        existing_match = ep
                        break

            if existing_match:
                spc_key = existing_match.get("nfKey")
                print(f"  ⚡ Duplicate Check: FOUND EXISTING in SPC!")
                print(f"     SPC Project Key: {spc_key}")
                print(f"     Action: UPDATING existing project in-place (No duplicate created)...")

                payload["currentProjectKey"] = spc_key

                # Call PUT /api/Project/UpdateProject with existing detail context
                result = await page.evaluate("""async (payload) => {
                    try {
                        const spcKey = payload.currentProjectKey;
                        // Fetch existing project detail to retain backend category keys
                        let existingDetail = null;
                        try {
                            const detRes = await fetch(`https://spc.rotary.org/api/Project/ProjectDetail/en/${spcKey}`, {
                                method: 'GET',
                                headers: {
                                    'accept': '*/*',
                                    'subscriptionkey': 'ROTARY_API_KEY'
                                }
                            });
                            if (detRes.ok) {
                                existingDetail = await detRes.json();
                            }
                        } catch (e) {
                            // Non-fatal
                        }

                        let redux = null;
                        for (const k in window) {
                            try {
                                if (window[k] && typeof window[k].getState === 'function') {
                                    redux = window[k].getState();
                                    break;
                                }
                            } catch(e){}
                        }
                        const user = redux?.user?.userDeatils;
                        if (user) {
                            if (user.individualkey) payload.currentSignedInIndividualKey = user.individualkey;
                            if (user.memberId) payload.currentSignedInMemberId = user.memberId;
                            if (user.userName) payload.currentSignedInMemberName = user.userName;
                            if (user.userLoginEmail) payload.individualEmail = user.userLoginEmail;
                        }

                        payload.isChangedProjectDetail = true;
                        if (payload.projectCategoryFund) {
                            if (existingDetail && existingDetail.categories && existingDetail.categories.length > 0) {
                                payload.projectCategoryFund.projectCategoryFundKey = existingDetail.categories[0].projectCategoryFundKey;
                                payload.projectCategoryFund.isChangedProjectCategoryFund = false;
                            } else {
                                payload.projectCategoryFund.isChangedProjectCategoryFund = true;
                            }
                            payload.projectCategoryFund.rotaryFoundationGrantFlag = !!payload.projectCategoryFund.rotaryFoundationGrantFlag;
                        }

                        if (existingDetail && existingDetail.profile) {
                            if (existingDetail.profile.locationName) payload.location = existingDetail.profile.locationName;
                            if (existingDetail.profile.tags && existingDetail.profile.tags.length > 0) {
                                payload.tags = existingDetail.profile.tags.join(';');
                            }
                            if (existingDetail.profile.currentProjectAddressKey) {
                                payload.currentProjectAddressKey = existingDetail.profile.currentProjectAddressKey;
                            }
                            if (existingDetail.profile.currentEstablishedProjectKey) {
                                payload.currentEstablishedProjectKey = existingDetail.profile.currentEstablishedProjectKey;
                            }
                            if (existingDetail.profile.currentProposedProjectKey) {
                                payload.currentProposedProjectKey = existingDetail.profile.currentProposedProjectKey;
                            }
                        }
                        if (payload.location && payload.location.length > 50) {
                            payload.location = payload.location.slice(0, 50);
                        }
                        if (payload.tags && payload.tags.length > 100) {
                            payload.tags = payload.tags.slice(0, 100);
                        }

                        // Reconcile Medias / RelLinks (prevents duplicate links)
                        if (existingDetail && existingDetail.medias && existingDetail.medias.length > 0) {
                            const existingMedias = existingDetail.medias;
                            const newRelLinks = [];
                            const usedExistingMediaKeys = new Set();

                            for (const link of (payload.projectRelLinks || [])) {
                                const rawUrl = atob(link.url);
                                const match = existingMedias.find(m => (!usedExistingMediaKeys.has(m.mediaKey)) && (m.url === rawUrl || m.title === link.caption));
                                if (match) {
                                    usedExistingMediaKeys.add(match.mediaKey);
                                    newRelLinks.push({
                                        ...link,
                                        mediaKey: match.mediaKey,
                                        isChangedProjectRelLink: false,
                                        isDeleted: false
                                    });
                                } else {
                                    newRelLinks.push({
                                        ...link,
                                        isChangedProjectRelLink: true,
                                        isDeleted: false
                                    });
                                }
                            }

                            // Mark any unreferenced existing media as deleted to clean up duplicates
                            for (const m of existingMedias) {
                                if (!usedExistingMediaKeys.has(m.mediaKey)) {
                                    newRelLinks.push({
                                        mediaKey: m.mediaKey,
                                        relLinkType: m.type || "5",
                                        caption: m.title || "",
                                        url: btoa(m.url),
                                        isCoverPhoto: "0",
                                        isDeleted: true,
                                        isChangedProjectRelLink: true
                                    });
                                }
                            }
                            payload.projectRelLinks = newRelLinks;
                        }

                        // Reconcile FundingSources (prevents duplicate fundings)
                        const existingFundings = (existingDetail && existingDetail.fundingSources) ? existingDetail.fundingSources : [];
                        const newFundings = [];
                        const usedFundingKeys = new Set();

                        for (const f of (payload.projectFundings || [])) {
                            delete f.fundingOrgName;
                            delete f.isImplementingPartnerFlag;

                            const match = existingFundings.find(ef => (!usedFundingKeys.has(ef.projectFundingSourceKey)) && (
                                (ef.fundingSource === f.fundingSource && (
                                    (ef.fundingSourceKey && (ef.fundingSourceKey === f.fundingClubKey || ef.fundingSourceKey === f.fundingSourceKey)) ||
                                    (ef.fundingOtherName && (ef.fundingOtherName === f.fundingClubKey || ef.fundingOtherName === f.fundingOtherName))
                                )) ||
                                (f.fundingClubKey && ef.fundingOtherName === f.fundingClubKey)
                            ));

                            const isClub = (f.fundingSource === 'Rotary Club');
                            const fundingItem = {
                                ...f,
                                fundingSourceKey: match?.fundingSourceKey || f.fundingSourceKey || (isClub ? f.fundingClubKey : null),
                                fundingOtherName: match?.fundingOtherName || f.fundingOtherName || (!isClub ? f.fundingClubKey : null),
                                fundingClubKey: f.fundingClubKey || match?.fundingSourceKey || match?.fundingOtherName || "",
                                isChangedProjectFundingSource: true,
                                isDeleted: false
                            };

                            if (match) {
                                usedFundingKeys.add(match.projectFundingSourceKey);
                                fundingItem.projectFundingSourceKey = match.projectFundingSourceKey;
                            } else {
                                const unused = existingFundings.find(ef => !usedFundingKeys.has(ef.projectFundingSourceKey) && ef.fundingSource === f.fundingSource);
                                if (unused) {
                                    usedFundingKeys.add(unused.projectFundingSourceKey);
                                    fundingItem.projectFundingSourceKey = unused.projectFundingSourceKey;
                                }
                            }
                            newFundings.push(fundingItem);
                        }

                        // Mark any unreferenced existing funding as deleted
                        for (const ef of existingFundings) {
                            if (!usedFundingKeys.has(ef.projectFundingSourceKey)) {
                                newFundings.push({
                                    projectFundingSourceKey: ef.projectFundingSourceKey,
                                    fundingSource: ef.fundingSource || "",
                                    fundingAmount: ef.fundingAmount || "",
                                    fundingClubKey: ef.fundingSourceKey || "",
                                    fundingSourceKey: ef.fundingSourceKey || null,
                                    fundingOtherName: ef.fundingOtherName || null,
                                    isDeleted: true,
                                    isChangedProjectFundingSource: true
                                });
                            }
                        }
                        payload.projectFundings = newFundings;

                        // Reconcile Partners (prevents duplicate partners)
                        const existingPartners = (existingDetail && existingDetail.partners) ? existingDetail.partners : [];
                        const newPartners = [];
                        const usedPartnerKeys = new Set();

                        const hostClubKey = "c575902e-aae0-4b82-9aba-54947c09f4fe";
                        const bothCat = "8881284b-572b-4247-8546-6f5a9ead9ae8";
                        const fundingCat = "09b7b3de-56b4-4d12-95b1-eaa58b53f573";
                        const clubFundType = "123456be-cece-4096-ab1b-4a554f213f05";

                        for (const pcm of (payload.projectPartnerClubMembers || [])) {
                            const pcmKey = (pcm.partnerOrganizationKey || '').toLowerCase().trim();
                            const isHost = (pcmKey === hostClubKey.toLowerCase());
                            const catId = pcm.partnerCategoryId || (isHost ? bothCat : fundingCat);
                            const fTypeId = pcm.fundTypeId || clubFundType;

                            const match = existingPartners.find(ep => (!usedPartnerKeys.has(ep.key)) && (
                                (ep.partnerKey && ep.partnerKey.toLowerCase().trim() === pcmKey) ||
                                (ep.organizationName && ep.organizationName.toLowerCase().trim() === pcmKey) ||
                                (ep.clubName && ep.clubName.toLowerCase().trim() === pcmKey)
                            ));
                            if (match) {
                                usedPartnerKeys.add(match.key);
                                newPartners.push({
                                    partnerOrganizationKey: pcm.partnerOrganizationKey,
                                    partnerCategoryId: catId,
                                    fundTypeId: fTypeId,
                                    Hour: pcm.Hour || "",
                                    MoneyDonated: pcm.MoneyDonated || "",
                                    NoOfVolunteer: pcm.NoOfVolunteer || "",
                                    year: pcm.year || "",
                                    projectPartnerClubMemberKey: match.key,
                                    isChangedProjectPartnerClubMember: true,
                                    isDeleted: false
                                });
                            } else {
                                newPartners.push({
                                    partnerOrganizationKey: pcm.partnerOrganizationKey,
                                    partnerCategoryId: catId,
                                    fundTypeId: fTypeId,
                                    Hour: pcm.Hour || "",
                                    MoneyDonated: pcm.MoneyDonated || "",
                                    NoOfVolunteer: pcm.NoOfVolunteer || "",
                                    year: pcm.year || "",
                                    isChangedProjectPartnerClubMember: true,
                                    isDeleted: false
                                });
                            }
                        }

                        // Mark unreferenced duplicate partners as deleted
                        for (const ep of existingPartners) {
                            if (!usedPartnerKeys.has(ep.key)) {
                                newPartners.push({
                                    projectPartnerClubMemberKey: ep.key,
                                    partnerOrganizationKey: ep.partnerKey || ep.organizationName || ep.clubName || "",
                                    partnerCategoryId: ep.partnerCategoryId || fundingCat,
                                    fundTypeId: ep.fundTypeId || clubFundType,
                                    year: ep.year || "",
                                    Hour: ep.numberOfHours ? String(ep.numberOfHours) : "",
                                    NoOfVolunteer: ep.numberOfVolunteer ? String(ep.numberOfVolunteer) : "",
                                    MoneyDonated: ep.moneyDonated ? String(ep.moneyDonated) : "",
                                    isDeleted: true,
                                    isChangedProjectPartnerClubMember: true
                                });
                            }
                        }
                        payload.projectPartnerClubMembers = newPartners;

                        // Reconcile Non-Rotary Partners (Partners in Service)
                        const existingNonRotary = (existingDetail && existingDetail.nonRotaryPartners) ? existingDetail.nonRotaryPartners : [];
                        const newNonRotary = [];
                        const usedNonRotaryKeys = new Set();

                        for (const pnr of (payload.projectNonRotaryPartners || [])) {
                            const pnrGuid = (pnr.nonRotaryPartnerKey || '').trim().toUpperCase();
                            if (!pnrGuid) continue;
                            const match = existingNonRotary.find(enr => (!usedNonRotaryKeys.has(enr.projectNonRotaryPartnerKey)) && (
                                (enr.nonRotaryPartnerKey && enr.nonRotaryPartnerKey.toUpperCase() === pnrGuid)
                            ));
                            if (match) {
                                usedNonRotaryKeys.add(match.projectNonRotaryPartnerKey);
                                newNonRotary.push({
                                    projectNonRotaryPartnerKey: match.projectNonRotaryPartnerKey,
                                    nonRotaryPartnerKey: pnrGuid,
                                    isChangedNonRotaryPartner: false,
                                    isDeleted: false
                                });
                            } else {
                                newNonRotary.push({
                                    nonRotaryPartnerKey: pnrGuid,
                                    isChangedNonRotaryPartner: true,
                                    isDeleted: false
                                });
                            }
                        }

                        // Mark any unreferenced existing non-rotary partners as deleted
                        for (const enr of existingNonRotary) {
                            if (!usedNonRotaryKeys.has(enr.projectNonRotaryPartnerKey)) {
                                newNonRotary.push({
                                    projectNonRotaryPartnerKey: enr.projectNonRotaryPartnerKey,
                                    nonRotaryPartnerKey: enr.nonRotaryPartnerKey,
                                    isDeleted: true,
                                    isChangedNonRotaryPartner: true
                                });
                            }
                        }
                        payload.projectNonRotaryPartners = newNonRotary;

                        // Reconcile Contacts / Joiners (deduplicates so each individual appears only once active)
                        if (existingDetail && existingDetail.joiners && existingDetail.joiners.length > 0) {
                            const existingContacts = existingDetail.joiners.map(j => j.contacts).filter(Boolean);
                            const seenIndividuals = new Set();
                            const newContacts = [];
                            for (const ec of existingContacts) {
                                const indKey = ec.individualId || ec.memberId;
                                if (!seenIndividuals.has(indKey)) {
                                    seenIndividuals.add(indKey);
                                    newContacts.push({
                                        projectContactKey: ec.key,
                                        individualContactKey: ec.individualId,
                                        individualContactId: ec.memberId,
                                        isChangedProjectContact: false,
                                        isDeleted: false
                                    });
                                } else {
                                    // Mark duplicate joiner for the same individual as deleted to resolve conflict
                                    newContacts.push({
                                        projectContactKey: ec.key,
                                        individualContactKey: ec.individualId,
                                        individualContactId: ec.memberId,
                                        isChangedProjectContact: true,
                                        isDeleted: true
                                    });
                                }
                            }
                            payload.projectContacts = newContacts;
                        }

                        payload.isChangedProjectPartnerDetail = true;
                        payload.isChangedProjectNonRotaryPartnerDetail = newNonRotary.some(x => x.isChangedNonRotaryPartner !== false);
                        payload.isChangedProjectFundingDetail = true;
                        payload.isChangedProjectDetail = true;

                        const res = await fetch('https://spc.rotary.org/api/Project/UpdateProject', {
                            method: 'PUT',
                            headers: {
                                'Content-Type': 'application/json',
                                'accept': '*/*',
                                'subscriptionkey': 'ROTARY_API_KEY'
                            },
                            body: JSON.stringify(payload)
                        });
                        if (!res.ok) {
                            const errTxt = await res.text();
                            return { ok: false, status: res.status, error: errTxt, sentPayload: payload };
                        }
                        const resText = await res.text();
                        let data = null;
                        try { data = JSON.parse(resText); } catch (e) { data = resText; }
                        if (data === false || data === "false") {
                            return { ok: false, status: 200, error: "Rotary SPC backend rejected project update payload (returned false)", sentPayload: payload };
                        }
                        return { ok: true, spc_id: payload.currentProjectKey, res_data: data };
                    } catch (e) {
                        return { ok: false, error: e.message };
                    }
                }""", payload)

                if result.get("ok"):
                    print(f"  ✓ SUCCESS! Updated in SPC: {spc_key}")
                    state[pid] = {
                        "spc_id": spc_key,
                        "title": title,
                        "action": "updated",
                        "migrated_at": datetime.now().isoformat(),
                        "spc_url": f"https://spc.rotary.org/project?guid={spc_key}"
                    }
                    save_state(state, pid)
                else:
                    print(f"  ✗ UPDATE FAILED: Status {result.get('status')} — {result.get('error')}")
                    if result.get("sentPayload"):
                        Path('/tmp/failed_payload.json').write_text(json.dumps(result.get("sentPayload"), indent=2))
                        print("  [DEBUG] Dumped sent payload to /tmp/failed_payload.json")

            else:
                print(f"  ✓ Duplicate Check: Clean (no existing project found in SPC).")
                print(f"     Action: CREATING new project in SPC...")

                # Call POST /api/Project/CreateProject
                result = await page.evaluate("""async (payload) => {
                    try {
                        const res = await fetch('https://spc.rotary.org/api/Project/CreateProject', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'accept': '*/*',
                                'subscriptionkey': 'ROTARY_API_KEY'
                            },
                            body: JSON.stringify(payload)
                        });
                        if (!res.ok) {
                            const errTxt = await res.text();
                            return { ok: false, status: res.status, error: errTxt };
                        }
                        const text = await res.text();
                        let data = null;
                        try { data = JSON.parse(text); } catch (e) { data = text; }
                        const spcId = (typeof data === 'string' ? data.replace(/^"|"$/g, '') : data);
                        if (!spcId || typeof spcId !== 'string' || spcId.trim() === '') {
                            return { ok: false, status: res.status, error: 'Empty GUID returned (validation failed)' };
                        }
                        return { ok: true, spc_id: spcId.trim() };
                    } catch (e) {
                        return { ok: false, error: e.message };
                    }
                }""", payload)

                if result.get("ok") and result.get("spc_id"):
                    spc_id = result.get("spc_id")
                    print(f"  ✓ SUCCESS! Created in SPC: {spc_id}")
                    state[pid] = {
                        "spc_id": spc_id,
                        "title": title,
                        "action": "created",
                        "migrated_at": datetime.now().isoformat(),
                        "spc_url": f"https://spc.rotary.org/project?guid={spc_id}"
                    }
                    save_state(state, pid)
                else:
                    print(f"  ✗ CREATE FAILED: Status {result.get('status')} — {result.get('error')}")

            await asyncio.sleep(2)

        print("\n" + "=" * 70)
        print("  MIGRATION BATCH COMPLETE")
        print("=" * 70)
        print(f"Total tracked projects in state: {len(state)} / {len(projects)}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())

