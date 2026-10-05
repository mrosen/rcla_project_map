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
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# --- Configuration & Constants ---
REPO_ROOT = Path(__file__).resolve().parent if (Path(__file__).resolve().parent / "spc_migration_state.json").exists() else Path(__file__).resolve().parent.parent
ENV_PATHS = [REPO_ROOT / ".env", Path(".env"), Path("/home/msr/grantcenter/.env")]
for p in ENV_PATHS:
    if p.exists():
        load_dotenv(p)
STATE_PATH = REPO_ROOT / "spc_migration_state.json"

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJxaG1zaW5jbm14cmd0aXB2a2lmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODk1MTgwMzUsImV4cCI6MjEwNTA5NDAzNX0.XJY9Q6akA4KF0Ei5Ri8blJ1yxfNM75l-oNK9nR1H40o")

ROTARY_LAKE_ATITLAN_CLUB_KEY = "7de94f72-4330-4015-9ba9-5fac50225049"
ROTARY_LAKE_ATITLAN_CLUB_ID  = "84633"
ROTARY_GUATEMALA_COUNTRY_KEY = "884813f1-8178-450a-9402-b0b658d3a8ec"
MEMBER_KEY = "277b2562-0575-4eb6-b044-6e3655a44264"
MEMBER_ID  = "8225782"
MEMBER_NAME = "Michael Rosen"
MEMBER_EMAIL = "michael.rosen@gmail.com"

AREA_OF_FOCUS_MAP = {
    "water": ("277fa508-2453-44ff-b9c5-fa7400eaad48", "Water, sanitation, and hygiene"),
    "education": ("a0c03499-3032-4be7-88d8-92f9b3669088", "Basic education and literacy"),
    "economic": ("0a96d033-7795-4d8a-a6df-7d498ff5a30b", "Community economic development"),
    "environment": ("e336025a-df29-427b-8f80-4f34d8c0ab77", "Environment"),
    "health": ("232900f1-c143-4c9b-bf48-a15bcc2a1fee", "Maternal and child health"),
    "disease": ("dcf8d4be-82a6-4575-bd95-a2b391d35cab", "Disease prevention and treatment"),
    "peace": ("5ecd39bb-8059-4d6e-9c31-d15a61731536", "Peacebuilding and conflict prevention"),
}

FUNDING_TYPE_APINEW_MAP = {
    "Global grant": "123456be-cece-4096-ab1b-4a554f213f04",
    "District grant": "123456be-cece-4096-ab1b-4a554f213f01",
    "Disaster response grant": "123456be-cece-4096-ab1b-4a554f213f21",
    "Rotary Club": "123456be-cece-4096-ab1b-4a554f213f05",
    "Rotaract club": "123456be-cece-4096-ab1b-4a554f213f06",
    "District(Cash)": "123456be-cece-4096-ab1b-4a554f213f02",
    "District(DDF)": "123456be-cece-4096-ab1b-4a554f213f03",
    "Other": "123456be-cece-4096-ab1b-4a554f213f07",
}

PARTNER_CATEGORY_IMPLEMENTING = "8881284b-572b-4247-8546-6f5a9ead9ae8"
PARTNER_CATEGORY_CONTRIBUTING = "09b7b3de-56b4-4d12-95b1-eaa58b53f573"
FUNDING_TYPE_ROTARY_CLUB = "123456be-cece-4096-ab1b-4a554f213f05"
PROJECT_STATUS_SUSTAINABLE = "6d9a56cd-9ca4-4e85-bb0b-9ff68cc1fb3c"

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
def is_valid_guid(val) -> bool:
    if not val or not isinstance(val, str):
        return False
    return bool(re.match(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$', val.strip()))

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
    url = "https://spc.rotary.org/apiNew/Search/Organization"
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
    # 1. Normalize curly quotes, dashes, and apostrophes to standard ASCII
    clean = clean.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    clean = clean.replace("**", "").replace("*", "").strip()
    clean = re.sub(r'^[•\-\*\s]+', '', clean)

    # 2. Strip em-dash / hyphen descriptions
    clean = re.split(r'\s+[—–-]\s+(?:Cooperating|Implementing|Local|Partner|School|Municipal)', clean, flags=re.I)[0].strip()
    clean = re.split(r'\s+[—–-]\s+', clean)[0].strip()

    # 3. Strip noisy descriptive parentheticals (roles, websites, geographic notes)
    clean = re.sub(r'\s*\([^)]*(?:https?://|www\.)[^)]*\)', '', clean, flags=re.I)
    clean = re.sub(r'\s*\([^)]*\b(?:partner|cooperating|implementing|councils|consejo|non-rotarian|donor|usa|guatemala|eagan|hopedale|spain|minnesota|nc|ca|va|md|co|il|wa|ma|al|fl|tx|ny|black mountain|mountain)\b[^)]*\)', '', clean, flags=re.I)

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

    # Normalize curly quotes and dashes to standard ASCII
    title = title.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    overview = overview.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    full_desc = full_desc.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")

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

    # Dates (ISO 8601 required by Rotary apiNew backend)
    def to_spc_date(dt_str, fallback_m, fallback_d, fallback_y):
        if not dt_str:
            return f"{fallback_y}-{fallback_m}-{fallback_d}T00:00:00"
        parts = str(dt_str).strip().split("-")
        if len(parts) == 3:
            return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}T00:00:00"
        elif len(parts) == 2:
            return f"{parts[0]}-{parts[1].zfill(2)}-15T00:00:00"
        elif len(parts) == 1 and parts[0].isdigit():
            return f"{parts[0]}-01-15T00:00:00"
        return f"{fallback_y}-{fallback_m}-{fallback_d}T00:00:00"

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
    location_name = location_name.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
    location_name = re.sub(r'[,.\'"()\/\\;:!?]', ' ', location_name)
    location_name = re.sub(r'\s+', ' ', location_name).strip()
    if len(location_name) > 50:
        location_name = location_name[:50].rsplit(' ', 1)[0].strip()
    if not location_name:
        location_name = "Lake Atitlán Region"

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
                "fundingClubKey": gid
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
                        "fundingClubKey": dnum
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
                    "fundingClubKey": clean_target
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
                use_key = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else ckey

                if use_key and is_valid_guid(use_key):
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
                        "fundingClubKey": use_key if (use_key and is_valid_guid(use_key)) else ""
                    }
                    if not (use_key and is_valid_guid(use_key)):
                        f_item["fundingOtherName"] = c_name
                    fundings.append(f_item)

            # Ensure any non-contributing clubs named in partner_clubs are still represented in partners if resolved
            for c_raw in (details.get("partner_clubs") or []):
                c_name = str(c_raw).strip()
                if not c_name:
                    continue
                matched = find_partner_club(c_name)
                k = matched.get("key") if matched else None
                is_host = (k == ROTARY_LAKE_ATITLAN_CLUB_KEY or "lake atitlan" in c_name.lower())
                use_k = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else k
                if use_k and is_valid_guid(use_k):
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
                use_key = ROTARY_LAKE_ATITLAN_CLUB_KEY if is_host else ckey

                if use_key and is_valid_guid(use_key):
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
                        "fundingClubKey": use_key if (use_key and is_valid_guid(use_key)) else ""
                    }
                    if not (use_key and is_valid_guid(use_key)):
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
                "fundingClubKey": gid
            })
            if intl_dist:
                fundings.append({
                    "fundingSource": "District(Cash)",
                    "fundingAmount": str(int(num_budget * 0.35)) if num_budget else "15000",
                    "fundingClubKey": intl_dist
                })
            if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.15)) if num_budget else "5000",
                    "fundingClubKey": partner_club_key
                })
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.05)) if num_budget else "2000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY
                })
            else:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.20)) if num_budget else "5000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY
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

        if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY and is_valid_guid(partner_club_key):
            partners.append({
                "partnerOrganizationKey": partner_club_key,
                "Hour": "",
                "MoneyDonated": budget_str if num_budget else "",
                "NoOfVolunteer": "",
                "year": ""
            })

    # Strict Funding Cleanup: Format for apiNew typed model
    clean_fundings = []
    for f in fundings:
        f_amt = float(re.sub(r'[^0-9.]', '', str(f.get("fundingAmount", 0))) or 0)
        if f_amt > 0:
            f_src = f.get("fundingSource", "Other")
            f_type_id = FUNDING_TYPE_APINEW_MAP.get(f_src, FUNDING_TYPE_APINEW_MAP["Other"])
            ckey = f.get("fundingClubKey") or ""
            is_impl = (str(ckey).lower() == ROTARY_LAKE_ATITLAN_CLUB_KEY.lower() or "lake atitlan" in str(f.get("fundingOtherName", "")).lower())
            clean_fundings.append({
                "fundingTypeId": f_type_id,
                "fundingAmount": str(int(f_amt)),
                "fundingClubKey": ckey,
                "isImplementingPartnerFlag": is_impl
            })
    fundings = clean_fundings

    # Strict Partner Cleanup: Format for apiNew typed model
    clean_partners = []
    for pt in partners:
        pkey = pt.get("partnerOrganizationKey")
        if is_valid_guid(pkey):
            is_host = (str(pkey).lower() == ROTARY_LAKE_ATITLAN_CLUB_KEY.lower())
            clean_partners.append({
                "partnerOrganizationKey": pkey,
                "partnerCategoryId": PARTNER_CATEGORY_IMPLEMENTING if is_host else PARTNER_CATEGORY_CONTRIBUTING,
                "FundTypeId": FUNDING_TYPE_ROTARY_CLUB,
                "Hour": pt.get("Hour") or "",
                "MoneyDonated": pt.get("MoneyDonated") or "",
                "NoOfVolunteer": pt.get("NoOfVolunteer") or "",
                "year": pt.get("year") or ""
            })
    partners = clean_partners

    # Project search tags (List of KeyValue objects for apiNew)
    tag_list = []
    for org in cooperating_orgs:
        if org and "rotary" not in org.lower():
            clean_t = re.sub(r'\s*\([^)]*\)', '', org)
            clean_t = clean_t.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
            clean_t = re.sub(r'[,.\'\"()\/\\;:!?]', ' ', clean_t)
            clean_t = re.sub(r'\s+', ' ', clean_t).strip()
            if clean_t and len(clean_t) >= 2 and clean_t not in tag_list:
                tag_list.append(clean_t[:35].strip())
    if aof_name:
        clean_aof = aof_name.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("—", "-").replace("–", "-")
        clean_aof = re.sub(r'[,.\'\"()\/\\;:!?]', ' ', clean_aof)
        clean_aof = re.sub(r'\s+', ' ', clean_aof).strip()
        if clean_aof and clean_aof not in tag_list:
            tag_list.append(clean_aof[:35].strip())
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
    tags_payload = [{"value": t} for t in shortened_tags]

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
        "countryId": "Guatemala",
        "tags": tags_payload,
        "communityImpact": "",
        "projectImpact": "",
        "sustainImpact": "",
        "difficultyLevel": "",
        "estimatedBudget": budget_str,
        "estimatedAmount": "",
        "projectStatusId": PROJECT_STATUS_SUSTAINABLE,
        "isEradicationEffortsInitiative": False,
        "isFundraiserInitiative": False,
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
        "optGlobalGrants": is_international,
        "isOptGlobalGrants": is_international,
        "isBasicLevel": False,
        "isIntermediateLevel": False,
        "isAdvancedLevel": True if is_completed else False,
        "isEstimatedStartTime": False,
        "isEstimatedDuration": False,
        "estimatedDuration": "",
        "durationType": "",
        "isCompleted": is_completed,
        "rotaryFoundationGrantFlag": is_foundation,
        "projectXAreaOfFocuses": [
            {"areaOfFocusTypeId": aof_key}
        ],
        "projectRelLinks": rel_links,
        "projectContacts": [{
            "individualContactKey": MEMBER_KEY,
            "individualContactId": MEMBER_ID,
            "creator": True
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
        print(f"\n[1/4] Launching Playwright browser (headless={headless_mode})...", flush=True)
        browser = await pw.chromium.launch(
            headless=headless_mode,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-extensions",
                "--no-first-run",
            ],
            slow_mo=50 if not headless_mode else 0
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900}
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        context.set_default_navigation_timeout(60000)
        context.set_default_timeout(60000)
        page = await context.new_page()

        # Step 1: Login
        print("[2/4] Logging into My Rotary...", flush=True)
        email = (os.getenv("ROTARY_EMAIL") or os.getenv("ROTARY_USERNAME") or "").strip()
        password = (os.getenv("ROTARY_PASSWORD") or "").strip()

        if not email or not password:
            print("  ❌ ERROR: Missing credentials in environment variables!", flush=True)
            print(f"     ROTARY_EMAIL present: {bool(email)}", flush=True)
            print(f"     ROTARY_PASSWORD present: {bool(password)}", flush=True)
            print("     Configure ROTARY_EMAIL and ROTARY_PASSWORD in Google Cloud Run (Variables & Secrets).", flush=True)
            raise ValueError("ROTARY_EMAIL and ROTARY_PASSWORD environment variables are required for My Rotary login.")

        masked_email = email[:3] + "..." + email[email.find("@"):] if "@" in email else "..."
        print(f"  Authenticating as: {masked_email}", flush=True)

        async def dismiss_cookie_banner():
            cookie_selectors = [
                "#onetrust-accept-btn-handler",
                "button:has-text('Accept All Cookies')",
                "button:has-text('Accept All')",
                "button[id*='onetrust']",
                ".optanon-allow-all"
            ]
            for sel in cookie_selectors:
                try:
                    btn = await page.query_selector(sel)
                    if btn and await btn.is_visible():
                        await btn.click()
                        print("  Accepted cookie consent banner.", flush=True)
                        await page.wait_for_timeout(800)
                        break
                except Exception:
                    pass
            try:
                await page.evaluate("""() => {
                    const el = document.getElementById('onetrust-banner-sdk');
                    if (el) el.remove();
                    const dark = document.querySelector('.onetrust-pc-dark-filter');
                    if (dark) dark.remove();
                    const group = document.getElementById('onetrust-consent-sdk');
                    if (group) group.remove();
                }""")
            except Exception:
                pass

        login_urls = [
            "https://my.rotary.org/login?destination=/en/secure/showcase",
            "https://my.rotary.org/en/login"
        ]
        navigated = False
        for l_url in login_urls:
            try:
                print(f"  Navigating to My Rotary login page ({l_url})...", flush=True)
                await page.goto(l_url, wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2000)
                navigated = True
                break
            except Exception as e:
                print(f"  [Warning] Navigation to {l_url} failed: {e}", flush=True)

        if not navigated:
            raise RuntimeError("Could not load any My Rotary login page.")

        # Find Okta username input, polling and dismissing cookies for up to 30 seconds
        user_input = None
        for attempt in range(15):
            await dismiss_cookie_banner()
            for selector in ["#okta-signin-username", "input[name='username']", "input[name='identifier']", "input[type='email']"]:
                try:
                    el = await page.query_selector(selector)
                    if el:
                        user_input = el
                        break
                except Exception:
                    pass
            if user_input:
                break
            await page.wait_for_timeout(2000)

        if not user_input:
            page_title = await page.title()
            page_text = await page.evaluate("() => (document.body ? document.body.innerText.slice(0, 500) : '')")
            all_inputs = await page.evaluate("() => Array.from(document.querySelectorAll('input')).map(i => ({id: i.id, name: i.name, type: i.type}))")
            print(f"  ❌ Username input not found! URL: {page.url} | Title: {page_title}", flush=True)
            print(f"  Page inputs: {all_inputs}", flush=True)
            print(f"  Page text: {page_text[:300]}...", flush=True)
            raise RuntimeError(f"Okta login input not found on page: {page.url} ({page_title})")

        print("  Filling credentials in login form...", flush=True)
        await user_input.fill(email)
        await page.wait_for_timeout(500)

        pwd_input = None
        for sel in ["#okta-signin-password", "input[name='password']", "input[type='password']"]:
            try:
                el = await page.query_selector(sel)
                if el:
                    pwd_input = el
                    break
            except Exception:
                pass
        if pwd_input:
            await pwd_input.fill(password)
        else:
            await page.fill("#okta-signin-password, input[name='password']", password)

        await page.wait_for_timeout(500)

        submitted = False
        for btn_sel in ["#okta-signin-submit", "input[type='submit']", "button[type='submit']"]:
            try:
                btn = await page.query_selector(btn_sel)
                if btn:
                    await btn.click(force=True)
                    submitted = True
                    break
            except Exception:
                pass

        if not submitted:
            try:
                await page.keyboard.press("Enter")
                submitted = True
            except Exception:
                pass

        if not submitted:
            await page.evaluate("() => { const b = document.querySelector('#okta-signin-submit, input[type=\\'submit\\'], button[type=\\'submit\\']'); if (b) b.click(); }")

        print("  Submitted login form. Waiting for authentication to finalize...", flush=True)

        # Wait until we leave the login page
        await page.wait_for_timeout(3000)
        authenticated = False
        for _ in range(60):
            cur_url = page.url.lower()
            if "login" not in cur_url and ("rotary.org" in cur_url):
                authenticated = True
                break
            err_box = await page.query_selector(".okta-form-infobox-error, .infobox-error")
            if err_box and await err_box.is_visible():
                err_text = await err_box.inner_text()
                if "error" in err_text.lower() or "unable" in err_text.lower():
                    print(f"  ❌ Okta error banner: {err_text}", flush=True)
            await page.wait_for_timeout(1000)

        if not authenticated:
            page_title = await page.title()
            page_text = await page.evaluate("() => (document.body ? document.body.innerText.slice(0, 500) : '')")
            print(f"  ❌ Authentication timeout! URL: {page.url} | Title: {page_title}", flush=True)
            print(f"  Page text: {page_text[:300]}...", flush=True)
            raise RuntimeError(f"Authentication failed: Page remained at login URL: {page.url}")
        print("  ✓ Successfully authenticated with My Rotary.")

        # Step 2: SSO Token Handshake from My Rotary to SPC
        print("[3/4] Exchanging SSO credentials and establishing authenticated session on spc.rotary.org...", flush=True)

        dest_url = None
        sso_info = {}
        if "spc.rotary.org" in page.url.lower():
            print("  ✓ Login redirect already landed on spc.rotary.org.", flush=True)
            dest_url = page.url
        else:
            # Ensure we are on my.rotary.org origin to make authorized API calls
            if "my.rotary.org" not in page.url.lower():
                await page.goto("https://my.rotary.org/en", wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2000)

            # 1. Fetch individualId and request SSO token for SPC from My Rotary API
            sso_info = await page.evaluate("""async () => {
            let indId = null;
            let memberId = null;
            let userName = null;
            let email = null;

            // Fetch current user details via GraphQL
            try {
                const gqlRes = await fetch("https://my-api.rotary.org/api/graphql", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "accept": "*/*"
                    },
                    credentials: "include",
                    body: JSON.stringify({
                        operationName: "AuthGetUser",
                        variables: {},
                        query: "query AuthGetUser { currentUser { individualId memberId login profile { firstName lastName } riIndividualId } }"
                    })
                });
                if (gqlRes.ok) {
                    const gqlData = await gqlRes.json();
                    const cu = gqlData?.data?.currentUser;
                    if (cu) {
                        indId = cu.individualId;
                        memberId = cu.riIndividualId || cu.memberId;
                        email = cu.login;
                        if (cu.profile?.firstName && cu.profile?.lastName) {
                            userName = `${cu.profile.firstName} ${cu.profile.lastName}`;
                        }
                    }
                }
            } catch (e) {
                console.warn("GraphQL AuthGetUser lookup:", e);
            }

            if (!indId) {
                indId = "481046f7-2587-4c7e-b14c-2eca3769bf69";
            }

            // Request SSO token for SPC
            try {
                const ssoRes = await fetch("https://my-api.rotary.org/api/domui/authorizerwf/sSOToken", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "accept": "application/json, text/plain, */*"
                    },
                    credentials: "include",
                    body: JSON.stringify({
                        data: {
                            postData: {
                                applicationToken: "SPC",
                                individual_pk: indId
                            },
                            apiMethod: "post"
                        }
                    })
                });
                if (ssoRes.ok) {
                    const ssoData = await ssoRes.json();
                    return {
                        ok: true,
                        individualId: indId,
                        memberId: memberId,
                        userName: userName,
                        email: email,
                        destinationUrl: ssoData?.wfRes?.destinationUrl
                    };
                } else {
                    return {
                        ok: false,
                        individualId: indId,
                        status: ssoRes.status,
                        error: await ssoRes.text()
                    };
                }
            } catch (e) {
                return { ok: false, individualId: indId, error: e.message };
            }
        }""")

            dest_url = sso_info.get("destinationUrl") if sso_info.get("ok") else None

        ticket_val = None
        iv_val = None

        if "spc.rotary.org" in page.url.lower():
            dest_url = page.url
        elif dest_url:
            print(f"  ✓ SSO ticket obtained for individualId: {sso_info.get('individualId')}", flush=True)
            print(f"  Navigating to SPC via SSO destination URL...", flush=True)
            await page.goto(dest_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(4000)
        else:
            print(f"  [Notice] SSO ticket endpoint returned: {sso_info.get('error') or sso_info.get('status')}. Falling back to direct navigation...", flush=True)
            await page.goto("https://spc.rotary.org/", wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)

        if dest_url:
            try:
                parsed_dest = urllib.parse.urlparse(dest_url)
                qs = urllib.parse.parse_qs(parsed_dest.query)
                ticket_val = qs.get("frmTicketInfo", [None])[0]
                iv_val = qs.get("iv", [None])[0]
            except Exception:
                pass

        # 2. Finalize and verify authenticated session on spc.rotary.org
        auth_status = await page.evaluate("""async ({ ticket, iv }) => {
            // Check Redux store for authenticated user details
            let reduxUser = null;
            for (let attempt = 0; attempt < 5; attempt++) {
                for (const k of ['__REDUX_STORE__', 'store']) {
                    try {
                        if (window[k] && window[k].getState) {
                            reduxUser = window[k].getState()?.user?.userDeatils;
                            if (reduxUser && reduxUser.individualkey) break;
                        }
                    } catch(e){}
                }
                if (reduxUser && reduxUser.individualkey) break;
                await new Promise(r => setTimeout(r, 600));
            }

            if (reduxUser && reduxUser.individualkey) {
                document.cookie = "ssoToken=true; path=/";
                return { ok: true, source: 'redux', user: reduxUser };
            }

            // If not yet populated in Redux, invoke /api/Auth explicitly with ticket & iv
            const urlParams = new URLSearchParams(window.location.search);
            const tokenVal = urlParams.get('frmTicketInfo') || ticket;
            const ivVal = urlParams.get('iv') || iv;

            if (tokenVal && ivVal) {
                try {
                    const res = await fetch('https://spc.rotary.org/api/Auth', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'accept': '*/*',
                            'subscriptionkey': 'ROTARY_API_KEY'
                        },
                        body: JSON.stringify({ token: tokenVal, iv: ivVal })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        document.cookie = "ssoToken=true; path=/";
                        return { ok: true, source: 'api/Auth', user: data };
                    } else {
                        return { ok: false, status: res.status, error: await res.text() };
                    }
                } catch(e) {
                    return { ok: false, error: e.message };
                }
            }

            // Always ensure ssoToken cookie is set
            document.cookie = "ssoToken=true; path=/";
            return { ok: true, source: 'cookie_only', user: null };
        }""", {"ticket": ticket_val, "iv": iv_val})

        if auth_status.get("ok"):
            u = auth_status.get("user") or {}
            global MEMBER_KEY, MEMBER_ID, MEMBER_NAME, MEMBER_EMAIL
            if u.get("individualkey"):
                MEMBER_KEY = u["individualkey"]
            if u.get("memberId"):
                MEMBER_ID = str(u["memberId"])
            if u.get("userName"):
                MEMBER_NAME = u["userName"]
            if u.get("userLoginEmail"):
                MEMBER_EMAIL = u["userLoginEmail"]
            print(f"  ✓ Authenticated session active on SPC (via {auth_status.get('source')}): {MEMBER_NAME} ({MEMBER_KEY})", flush=True)
        else:
            print(f"  [Notice] SPC auth status: {auth_status.get('error')}", flush=True)

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

        # Resolve any partner clubs using the authenticated browser session
        print("[3.6/4] Resolving partner Rotary clubs via SPC search API...", flush=True)
        for p_item in to_migrate:
            p_details = p_item.get("details") or {}
            if isinstance(p_details, str):
                try: p_details = json.loads(p_details)
                except Exception: p_details = {}
            clubs_to_lookup = []
            for c_raw in (p_details.get("partner_clubs") or []):
                if c_raw and str(c_raw).strip():
                    clubs_to_lookup.append(str(c_raw).strip())
            for cc in (p_details.get("club_contributions_list") or []):
                c_name = str(cc.get("name", "")).strip()
                if c_name and c_name not in clubs_to_lookup:
                    clubs_to_lookup.append(c_name)
            intl_c = str(p_details.get("international_club") or p_item.get("international_club_name") or "").strip()
            if intl_c and intl_c not in clubs_to_lookup:
                clubs_to_lookup.append(intl_c)

            for c_name in clubs_to_lookup:
                clean_name = re.sub(r'^(?:RC\s+of\s+|RC\s+|Rotary\s+Club\s+(?:of\s+)?|Club\s+Rotario\s+(?:de\s+)?)', '', c_name, flags=re.I).strip()
                clean_name = re.sub(r'\s*\(D\d+\)', '', clean_name, flags=re.I).strip()
                clean_name = re.sub(r'\s*,\s*[A-Z]{2}\b', '', clean_name).strip()
                clean_key = clean_name.lower()

                # Extract district if specified in club string or project details
                m_dist = re.search(r'\b[dD](\d{4})\b', c_name)
                district_num = m_dist.group(1) if m_dist else ""
                if not district_num:
                    p_dists = p_details.get("partner_districts") or []
                    if isinstance(p_dists, list) and len(p_dists) == 1:
                        district_num = re.sub(r'[^0-9]', '', str(p_dists[0]))

                cached = RESOLVED_CLUBS_CACHE.get(clean_key) or find_partner_club(c_name)
                if cached and cached.get("key") and is_valid_guid(cached.get("key")):
                    print(f"  ✓ Partner club resolved from cache: '{c_name}' -> {cached.get('name')} ({cached.get('key')})", flush=True)
                    continue
                try:
                    res = await page.evaluate("""async ([clubName, districtNumber]) => {
                        try {
                            const res = await fetch('https://spc.rotary.org/apiNew/Search/Organization', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'accept': '*/*',
                                    'subscriptionkey': 'ROTARY_API_KEY'
                                },
                                body: JSON.stringify({
                                    type: 'Rotary Club',
                                    clubName: clubName,
                                    districtNumber: districtNumber || '',
                                    countrykey: ''
                                })
                            });
                            if (!res.ok) return null;
                            return await res.json();
                        } catch (e) {
                            return null;
                        }
                    }""", [clean_name, district_num])
                    if res and isinstance(res, list) and len(res) > 0:
                        m = None
                        for cand in res:
                            c_cand = cand.get("orgName", "").lower()
                            if f"rotary club of {clean_name.lower()}," in c_cand:
                                m = cand
                                break
                        if not m:
                            for cand in res:
                                c_cand = cand.get("orgName", "").lower()
                                if clean_name.lower() in c_cand:
                                    m = cand
                                    break
                        if not m:
                            m = res[0]
                        org_key = m.get("orgKey")
                        if org_key and is_valid_guid(org_key):
                            entry = {
                                "key": org_key,
                                "name": m.get("orgName"),
                                "id": m.get("clubIdExt"),
                                "district": m.get("districtAddress")
                            }
                            RESOLVED_CLUBS_CACHE[clean_key] = entry
                            RESOLVED_CLUBS_CACHE[c_name.lower().strip()] = entry
                            print(f"  ✓ Resolved partner club via live SPC API: {c_name} -> {m.get('orgName')} ({org_key})", flush=True)
                            save_resolved_clubs()
                except Exception as ex:
                    print(f"  [Notice] Could not resolve club '{c_name}' in browser: {ex}", flush=True)

        # Step 4: Migration / Update Loop
        print(f"\n[4/4] Beginning processing of {len(to_migrate)} project(s)...")
        failed_projects = []

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
                payload["projectId"] = spc_key
                payload["projectKey"] = spc_key

                # Call PUT /apiNew/Project/UpdateProject
                result = await page.evaluate("""async (payload) => {
                    try {
                        let redux = null;
                        for (const k of ['__REDUX_STORE__', 'store']) {
                            try {
                                if (window[k] && window[k].getState) {
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
                            if (payload.projectContacts && payload.projectContacts.length > 0) {
                                payload.projectContacts[0].individualContactKey = user.individualkey || payload.projectContacts[0].individualContactKey;
                                payload.projectContacts[0].individualContactId = user.memberId || payload.projectContacts[0].individualContactId;
                            }
                        }
                        document.cookie = "ssoToken=true; path=/";

                        // Ensure all partner members and funding sources have valid initial keys
                        for (const p of (payload.projectPartnerClubMembers || [])) {
                            if (!p.projectPartnerClubMemberKey) {
                                p.projectPartnerClubMemberKey = "00000000-0000-0000-0000-000000000000";
                            }
                            p.isChangedProjectPartnerClubMember = true;
                            p.isDeleted = false;
                        }
                        for (const f of (payload.projectFundings || [])) {
                            if (!f.projectFundingSourceKey) {
                                f.projectFundingSourceKey = "00000000-0000-0000-0000-000000000000";
                            }
                            f.isChangedProjectFundingSource = true;
                            f.isDeleted = false;
                        }

                        // Reconcile existing partners and funding sources to update/delete cleanly
                        try {
                            const exRes = await fetch(`https://spc.rotary.org/apiNew/Project?projectId=${payload.currentProjectKey}`, {
                                headers: { 'accept': '*/*', 'subscriptionkey': 'ROTARY_API_KEY' }
                            });
                            if (exRes.ok) {
                                const exData = await exRes.json();
                                if (exData) {
                                    // 1. Reconcile Partners
                                    const exPartners = exData.partners || [];
                                    const newPartners = payload.projectPartnerClubMembers || [];
                                    const reconciledPartners = [];
                                    const usedExistingPartnerPKIds = new Set();

                                    for (const np of newPartners) {
                                        const npKey = (np.partnerOrganizationKey || '').toLowerCase();
                                        const match = exPartners.find(ep =>
                                            !usedExistingPartnerPKIds.has(ep.partnerPKId) &&
                                            (ep.partnerKey || '').toLowerCase() === npKey
                                        );
                                        if (match) {
                                            usedExistingPartnerPKIds.add(match.partnerPKId);
                                            reconciledPartners.push({
                                                ...np,
                                                projectPartnerClubMemberKey: match.partnerPKId,
                                                isChangedProjectPartnerClubMember: true,
                                                isDeleted: false
                                            });
                                        } else {
                                            reconciledPartners.push({
                                                ...np,
                                                projectPartnerClubMemberKey: '00000000-0000-0000-0000-000000000000',
                                                isChangedProjectPartnerClubMember: true,
                                                isDeleted: false
                                            });
                                        }
                                    }

                                    for (const ep of exPartners) {
                                        if (!usedExistingPartnerPKIds.has(ep.partnerPKId)) {
                                            reconciledPartners.push({
                                                projectPartnerClubMemberKey: ep.partnerPKId,
                                                partnerOrganizationKey: ep.partnerKey || '',
                                                partnerCategoryId: ep.partnerCategoryId || '09b7b3de-56b4-4d12-95b1-eaa58b53f573',
                                                FundTypeId: ep.fundTypeId || '123456be-cece-4096-ab1b-4a554f213f05',
                                                Hour: ep.numberOfHours ? String(ep.numberOfHours) : '',
                                                MoneyDonated: ep.moneyDonated ? String(ep.moneyDonated) : '',
                                                NoOfVolunteer: ep.numberOfVolunteer ? String(ep.numberOfVolunteer) : '',
                                                year: ep.year || '',
                                                isDeleted: true,
                                                isChangedProjectPartnerClubMember: true
                                            });
                                        }
                                    }
                                    payload.projectPartnerClubMembers = reconciledPartners;

                                    // 2. Reconcile Funding Sources
                                    const exFundings = exData.fundingSources || [];
                                    const newFundings = payload.projectFundings || [];
                                    const reconciledFundings = [];
                                    const usedExistingFundingKeys = new Set();

                                    for (const nf of newFundings) {
                                        const nfType = nf.fundingTypeId;
                                        const nfClub = (nf.fundingClubKey || '').toLowerCase();
                                        const match = exFundings.find(ef =>
                                            !usedExistingFundingKeys.has(ef.projectFundingSourceKey) &&
                                            ef.fundingTypeId === nfType &&
                                            ((ef.fundingClubKey || ef.organizationId || ef.fundingOtherName || '').toLowerCase() === nfClub)
                                        );
                                        if (match) {
                                            usedExistingFundingKeys.add(match.projectFundingSourceKey);
                                            reconciledFundings.push({
                                                ...nf,
                                                projectFundingSourceKey: match.projectFundingSourceKey,
                                                isChangedProjectFundingSource: true,
                                                isDeleted: false
                                            });
                                        } else {
                                            reconciledFundings.push({
                                                ...nf,
                                                projectFundingSourceKey: '00000000-0000-0000-0000-000000000000',
                                                isChangedProjectFundingSource: true,
                                                isDeleted: false
                                            });
                                        }
                                    }

                                    for (const ef of exFundings) {
                                        if (!usedExistingFundingKeys.has(ef.projectFundingSourceKey)) {
                                            reconciledFundings.push({
                                                projectFundingSourceKey: ef.projectFundingSourceKey,
                                                fundingTypeId: ef.fundingTypeId,
                                                fundingAmount: ef.fundingAmount || '',
                                                fundingClubKey: ef.fundingClubKey || ef.organizationId || ef.fundingOtherName || '',
                                                isDeleted: true,
                                                isChangedProjectFundingSource: true
                                            });
                                        }
                                    }
                                    payload.projectFundings = reconciledFundings;
                                }
                            }
                        } catch(e){}

                        payload.isChangedProjectPartnerDetail = true;
                        payload.isChangedProjectFundingDetail = true;
                        payload.isChangedProjectDetail = true;

                        const res = await fetch('https://spc.rotary.org/apiNew/Project/UpdateProject', {
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
                    err_msg = result.get('error') or f"Status {result.get('status')}"
                    print(f"  ✗ UPDATE FAILED: {err_msg}")
                    failed_projects.append((pid, err_msg))
                    if result.get("sentPayload"):
                        Path('/tmp/failed_payload.json').write_text(json.dumps(result.get("sentPayload"), indent=2))
                        print("  [DEBUG] Dumped sent payload to /tmp/failed_payload.json")

            else:
                print(f"  ✓ Duplicate Check: Clean (no existing project found in SPC).")
                print(f"     Action: CREATING new project in SPC...")

                # Call POST /apiNew/Project/CreateProject
                result = await page.evaluate("""async (payload) => {
                    let redux = null;
                    for (const k of ['__REDUX_STORE__', 'store']) {
                        try {
                            if (window[k] && window[k].getState) {
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
                        if (payload.projectContacts && payload.projectContacts.length > 0) {
                            payload.projectContacts[0].individualContactKey = user.individualkey || payload.projectContacts[0].individualContactKey;
                            payload.projectContacts[0].individualContactId = user.memberId || payload.projectContacts[0].individualContactId;
                            payload.projectContacts[0].creator = true;
                        }
                    }
                    document.cookie = "ssoToken=true; path=/";

                    try {
                        const res = await fetch('https://spc.rotary.org/apiNew/Project/CreateProject', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'accept': '*/*',
                                'subscriptionkey': 'ROTARY_API_KEY'
                            },
                            body: JSON.stringify(payload)
                        });
                        const text = await res.text();
                        let spcId = text ? text.replace(/^"|"$/g, '').trim() : '';
                        try {
                            const parsed = JSON.parse(text);
                            if (parsed && typeof parsed === 'object') {
                                spcId = parsed.key || parsed.spcId || parsed.guid || spcId;
                            }
                        } catch (e) {}

                        const isValid = Boolean(spcId && spcId.length > 10 && spcId !== '00000000-0000-0000-0000-000000000000');
                        if (res.ok && isValid) {
                            return { ok: true, spc_id: spcId, status: res.status };
                        }
                        return {
                            ok: false,
                            status: res.status,
                            error: `Create failed (status ${res.status}): ${text}`
                        };
                    } catch (err) {
                        return { ok: false, error: err.message };
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
                    err_msg = result.get('error') or f"Status {result.get('status')}"
                    print(f"  ✗ CREATE FAILED for {pid}: {err_msg}", flush=True)
                    failed_projects.append((pid, err_msg))

            await asyncio.sleep(2)

        print("\n" + "=" * 70)
        print("  MIGRATION BATCH COMPLETE")
        print("=" * 70)
        print(f"Total tracked projects in state: {len(state)} / {len(projects)}")
        await browser.close()

        if failed_projects:
            print("\n" + "=" * 70, flush=True)
            print("  ❌ SPC MIGRATION ENCOUNTERED ERRORS:", flush=True)
            for f_pid, f_err in failed_projects:
                print(f"    • {f_pid}: {f_err}", flush=True)
            print("=" * 70, flush=True)
            raise RuntimeError(f"SPC migration failed for: {', '.join(f[0] for f in failed_projects)}")

if __name__ == "__main__":
    asyncio.run(main())

