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
import csv
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# --- Configuration & Constants ---
ENV_PATHS = [Path("/home/msr/grantcenter/.env"), Path(".env")]
CSV_PATH = Path("/home/msr/rcla_project_map/RCLA_Projects_v2.csv")
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

KNOWN_PARTNER_CLUBS = {
    "clemens": {"key": "aa6158d9-e628-4776-838d-77d236513a50", "name": "Mt. Clemens", "id": "2992", "district": "6380"},
    "mount clemens": {"key": "aa6158d9-e628-4776-838d-77d236513a50", "name": "Mt. Clemens", "id": "2992", "district": "6380"},
    "santa cruz": {"key": "d4624df4-a8eb-4ec9-8664-9f202272ee57", "name": "Santa Cruz", "district": "5170"},
    "lake atitlan": {"key": "c575902e-aae0-4b82-9aba-54947c09f4fe", "name": "Lake Atitlan", "id": "84633", "district": "4250"},
    "annapolis": {"key": "2d768063-d1d0-4573-a094-a7ace36588d0", "name": "Annapolis", "id": "5853", "district": "7620"},
    "petaluma valley": {"key": "7b11cb6f-a6be-46c3-9049-d5e885c02186", "name": "Petaluma Valley", "id": "400", "district": "5130"},
    "washington": {"key": "05c7ebef-2f21-4c6f-93df-39d9940dfcd0", "name": "Washington, D.C.", "id": "5851", "district": "7620"},
    "washington, d.c.": {"key": "05c7ebef-2f21-4c6f-93df-39d9940dfcd0", "name": "Washington, D.C.", "id": "5851", "district": "7620"},
    "carroll creek": {"key": "53a43929-2e4f-402a-9977-44999b441c7d", "name": "Carroll Creek (Frederick)", "id": "29713", "district": "7620"},
    "rockville": {"key": "151cd8fb-2591-4ccf-9424-0ee852bd647f", "name": "Rockville", "id": "5890", "district": "7620"},
    "capitol hill": {"key": "d9232f9f-f95b-4fbc-95c4-35bfb25ff9ef", "name": "Capitol Hill (Washington, DC)", "id": "63814", "district": "7620"},
    "baltimore": {"key": "a909d44a-de9c-4cb8-9749-a6c321df348f", "name": "Baltimore", "id": "5855", "district": "7620"},
    "lake shore": {"key": "e819dd35-8c87-4002-a80d-a985d75a94c9", "name": "Lake Shore-Severna Park", "id": "5878", "district": "7620"},
    "lake shore-severna park": {"key": "e819dd35-8c87-4002-a80d-a985d75a94c9", "name": "Lake Shore-Severna Park", "id": "5878", "district": "7620"},
    "dupont circle": {"key": "fa68604c-4068-498f-a701-7b623b92ba50", "name": "Dupont Circle Washington", "id": "84311", "district": "7620"},
    "pacifica": {"key": "fa9079c0-a0c0-4d98-8939-c47b5c1a2ecd", "name": "Pacifica", "id": "398", "district": "5150"},
    "mill valley": {"key": "96521569-a11b-4602-93b6-c928a2a07bf5", "name": "Mill Valley", "id": "393", "district": "5150"},
    "marin evening": {"key": "ae1057de-565c-49bf-800f-a5b9fe30bdac", "name": "San Rafael Marin Evening", "id": "85885", "district": "5150"},
    "san rafael marin evening": {"key": "ae1057de-565c-49bf-800f-a5b9fe30bdac", "name": "San Rafael Marin Evening", "id": "85885", "district": "5150"},
    "peninsula starlight": {"key": "5d8ac492-7950-4a28-95d8-a0272158d2cd", "name": "Peninsula Starlight-San Mateo County", "id": "90074", "district": "5150"},
}

KNOWN_DISTRICTS = {
    "7620": {"key": "9445e695-1a25-4e21-941e-3eff587a0a8f", "name": "7620"}
}

# Detailed financial profiles for complex grants with multi-club and NGO partners
DETAILED_PROJECT_PROFILES = {
    "GG1633934": {
        "club_contributions": [
            {"club_key": "96521569-a11b-4602-93b6-c928a2a07bf5", "name": "Mill Valley", "amount": "3500"},
            {"club_key": "ae1057de-565c-49bf-800f-a5b9fe30bdac", "name": "San Rafael Marin Evening", "amount": "1500"},
            {"club_key": "fa9079c0-a0c0-4d98-8939-c47b5c1a2ecd", "name": "Pacifica", "amount": "1000"},
            {"club_key": "c575902e-aae0-4b82-9aba-54947c09f4fe", "name": "Lake Atitlan", "amount": "0"}
        ],
        "district_contributions": [
            {"district": "5150", "source": "District(DDF)", "amount": "28024"}
        ],
        "world_fund": "31024",
        "implementing_partners": [
            {"source": "Other - NGO", "name": "Fundacion Namaste Guatemaya", "amount": "0"},
            {"source": "Other - Community Group", "name": "St. Aidan's Episcopal Church, San Francisco", "amount": "980"}
        ]
    },
    "GG2578692": {
        "club_contributions": [
            {"club_key": "2d768063-d1d0-4573-a094-a7ace36588d0", "name": "Annapolis", "amount": "8450"},
            {"club_key": "05c7ebef-2f21-4c6f-93df-39d9940dfcd0", "name": "Washington, D.C.", "amount": "5000"},
            {"club_key": "a909d44a-de9c-4cb8-9749-a6c321df348f", "name": "Baltimore", "amount": "3000"},
            {"club_key": "53a43929-2e4f-402a-9977-44999b441c7d", "name": "Carroll Creek (Frederick)", "amount": "2500"},
            {"club_key": "7b11cb6f-a6be-46c3-9049-d5e885c02186", "name": "Petaluma Valley", "amount": "1600"},
            {"club_key": "151cd8fb-2591-4ccf-9424-0ee852bd647f", "name": "Rockville", "amount": "1500"},
            {"club_key": "e819dd35-8c87-4002-a80d-a985d75a94c9", "name": "Lake Shore-Severna Park", "amount": "1000"},
            {"club_key": "fa68604c-4068-498f-a701-7b623b92ba50", "name": "Dupont Circle Washington", "amount": "700"},
            {"club_key": "d9232f9f-f95b-4fbc-95c4-35bfb25ff9ef", "name": "Capitol Hill (Washington, DC)", "amount": "500"},
            {"club_key": "c575902e-aae0-4b82-9aba-54947c09f4fe", "name": "Lake Atitlan", "amount": "300"},
        ],
        "district_contributions": [
            {"district": "7620", "source": "District(DDF)", "amount": "15000"}
        ],
        "world_fund": "12000",
        "implementing_partners": [
            {"source": "Other - NGO", "name": "Asociacion Pro Agua del Pueblo (AdP)", "amount": "0"},
            {"source": "Other - Government Entity", "name": "Municipality of Santa Lucia Utatlan", "amount": "0"},
            {"source": "Other - Government Entity", "name": "Guatemala Federal Department of Education", "amount": "0"},
            {"source": "Other - Community Group", "name": "Vista Hermosa Water & Sanitation Committee / COCODE", "amount": "0"}
        ]
    }
}

def find_partner_club(club_name_str: str) -> dict:
    if not club_name_str:
        return None
    s = club_name_str.lower()
    for k, v in KNOWN_PARTNER_CLUBS.items():
        if k in s:
            return v
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
        print(f"Warning: Could not fetch from Supabase ({e}), loading local CSV.")
        return []

def load_csv_data() -> dict:
    if not CSV_PATH.exists():
        return {}
    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return {row.get("id", "").strip(): row for row in reader if row.get("id")}

def build_project_list() -> list:
    sb_projects = fetch_supabase_projects()
    csv_dict = load_csv_data()

    merged = []
    if sb_projects:
        for p in sb_projects:
            pid = p.get("id", "").strip()
            c_row = csv_dict.get(pid, {})
            # Enrich with CSV specific fields or fallback
            p["international_club_district"] = p.get("international_club_district") or c_row.get("internationalClub_district", "")
            p["international_club_name"] = p.get("international_club_name") or c_row.get("internationalClub_name", "")
            p["end_year"] = p.get("end_year") or c_row.get("end_year", "")
            merged.append(p)
    else:
        # Fallback to pure CSV
        for pid, c_row in csv_dict.items():
            c_row["international_club_district"] = c_row.get("internationalClub_district", "")
            c_row["international_club_name"] = c_row.get("internationalClub_name", "")
            merged.append(c_row)
    return merged

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

    detail_profile = DETAILED_PROJECT_PROFILES.get(gid)
    partner_name = (p.get("partner") or "").strip()

    # Collect cooperating organizations / implementing partners
    cooperating_orgs = []
    if detail_profile:
        for ip in detail_profile.get("implementing_partners", []):
            name = ip.get("name")
            if name and name not in cooperating_orgs:
                cooperating_orgs.append(name)
    for org in (details.get("cooperating_organizations") or []):
        o_clean = str(org).strip()
        if o_clean and o_clean not in cooperating_orgs:
            cooperating_orgs.append(o_clean)
    if partner_name:
        for sub_p in partner_name.split(","):
            sub_clean = sub_p.strip()
            if sub_clean and not any(sub_clean.lower() in existing.lower() or existing.lower() in sub_clean.lower() for existing in cooperating_orgs):
                cooperating_orgs.append(sub_clean)

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

    # Highlight cooperating organizations if not already mentioned
    if cooperating_orgs:
        org_names = [o for o in cooperating_orgs if "rotary" not in o.lower()]
        if org_names and not any("cooperating" in full_desc.lower() or "partnering with" in full_desc.lower() for _ in [1]):
            callout = "Cooperating Partner(s): " + ", ".join(org_names) + "."
            if len(full_desc) + len(callout) + 2 <= 1000:
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

    detail_profile = DETAILED_PROJECT_PROFILES.get(gid)
    has_custom_details = bool(details.get("world_fund") or details.get("district_ddf") or details.get("club_contributions") or details.get("partner_clubs") or details.get("partner_districts") or details.get("cooperating_organizations"))

    if detail_profile:
        # Detailed Partner Clubs & NGOs
        partners = []
        # Ensure Lake Atitlan host club is included in partners
        partners.append({
            "partnerOrganizationKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
            "Hour": "",
            "MoneyDonated": "",
            "NoOfVolunteer": "",
            "year": ""
        })

        for cc in detail_profile.get("club_contributions", []):
            ckey = cc.get("club_key") or (find_partner_club(cc.get("name")) or {}).get("key")
            amt = str(cc.get("amount", "")).strip()
            if ckey and ckey != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                partners.append({
                    "partnerOrganizationKey": ckey,
                    "Hour": "",
                    "MoneyDonated": amt if amt != "0" else "",
                    "NoOfVolunteer": "",
                    "year": ""
                })

        # Detailed Funding Sources (ONLY include sources with amount > 0)
        fundings = []
        if detail_profile.get("world_fund"):
            wf = str(detail_profile["world_fund"]).strip()
            if wf and wf != "0":
                fundings.append({
                    "fundingSource": "Global grant",
                    "fundingAmount": wf,
                    "fundingClubKey": gid
                })
        for dc in detail_profile.get("district_contributions", []):
            dnum = str(dc.get("district", "")).strip()
            amt = str(dc.get("amount", "0")).strip()
            if dnum and amt and amt != "0":
                fundings.append({
                    "fundingSource": dc.get("source", "District(DDF)"),
                    "fundingAmount": amt,
                    "fundingClubKey": dnum,
                    "isImplementingPartnerFlag": False
                })
        for cc in detail_profile.get("club_contributions", []):
            ckey = cc.get("club_key") or (find_partner_club(cc.get("name")) or {}).get("key")
            amt = str(cc.get("amount", "0")).strip()
            if ckey and amt and amt != "0":
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": amt,
                    "fundingClubKey": ckey,
                    "isImplementingPartnerFlag": False
                })
        for ip in detail_profile.get("implementing_partners", []):
            amt = str(ip.get("amount", "0")).strip()
            if amt and amt != "0":
                fundings.append({
                    "fundingSource": ip.get("source", "Other - Community Group"),
                    "fundingAmount": amt,
                    "fundingClubKey": ip.get("name"),
                    "isImplementingPartnerFlag": True
                })
    elif has_custom_details:
        partners = []
        fundings = []

        # 1. World Fund
        wf_amt = details.get("world_fund") or 0
        if not wf_amt and is_international and gid.startswith("GG") and num_budget:
            wf_amt = int(num_budget * 0.45)
        if wf_amt:
            fundings.append({
                "fundingSource": "Global grant",
                "fundingAmount": str(int(float(wf_amt))),
                "fundingClubKey": gid
            })

        # 2. Districts (DDF)
        explicit_dist_contribs = details.get("district_contributions")
        if explicit_dist_contribs and isinstance(explicit_dist_contribs, list):
            for dc in explicit_dist_contribs:
                dnum = re.sub(r'[^0-9]', '', str(dc.get("district", ""))) or str(dc.get("district", "")).strip()
                amt = str(int(float(dc.get("amount", 0))))
                if dnum and (amt != "0" or str(dnum) != "4250"):
                    fundings.append({
                        "fundingSource": dc.get("source", "District(DDF)"),
                        "fundingAmount": amt,
                        "fundingClubKey": dnum,
                        "isImplementingPartnerFlag": False
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
            # Target the international partner district first, never default to host district 4250
            target_d = intl_clean_d if (intl_clean_d and intl_clean_d != "4250") else None
            if not target_d:
                non_host = [re.sub(r'[^0-9]', '', str(d)) for d in raw_pdist if re.sub(r'[^0-9]', '', str(d)) and re.sub(r'[^0-9]', '', str(d)) != "4250"]
                target_d = non_host[0] if non_host else (raw_pdist[0] if raw_pdist else None)

            for d_val in raw_pdist:
                clean_d = re.sub(r'[^0-9]', '', str(d_val)) or str(d_val).strip()
                if clean_d:
                    is_target = (clean_d == target_d)
                    amt = str(int(float(total_ddf))) if (is_target and total_ddf) else "0"
                    if amt != "0" or clean_d != "4250":
                        fundings.append({
                            "fundingSource": "District(DDF)",
                            "fundingAmount": amt,
                            "fundingClubKey": clean_d,
                            "isImplementingPartnerFlag": False
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
                amt = str(int(float(cc.get("amount", 0))))
                if ckey:
                    partners.append({
                        "partnerOrganizationKey": ckey,
                        "Hour": "",
                        "MoneyDonated": amt if amt != "0" else "",
                        "NoOfVolunteer": "",
                        "year": ""
                    })
                    if amt != "0":
                        fundings.append({
                            "fundingSource": "Rotary Club",
                            "fundingAmount": amt,
                            "fundingClubKey": ckey,
                            "isImplementingPartnerFlag": False
                        })
                elif amt != "0":
                    fundings.append({
                        "fundingSource": "Rotary Club",
                        "fundingAmount": amt,
                        "fundingClubKey": c_name,
                        "isImplementingPartnerFlag": False
                    })
        else:
            raw_pclubs = details.get("partner_clubs") or []
            if isinstance(raw_pclubs, str):
                raw_pclubs = [c.strip() for c in raw_pclubs.split(",") if c.strip()]
            intl_club_raw = str(details.get("international_club") or p.get("international_club_name") or "").strip()
            if intl_club_raw and intl_club_raw not in raw_pclubs:
                raw_pclubs.insert(0, intl_club_raw)

            total_cash = details.get("club_contributions") or 0
            for idx, c_name in enumerate(raw_pclubs):
                c_str = str(c_name).strip()
                if not c_str:
                    continue
                matched_club = find_partner_club(c_str)
                ckey = matched_club.get("key") if matched_club else None
                amt = str(int(float(total_cash))) if (idx == 0 and total_cash) else "0"
                if ckey:
                    partners.append({
                        "partnerOrganizationKey": ckey,
                        "Hour": "",
                        "MoneyDonated": amt if amt != "0" else "",
                        "NoOfVolunteer": "",
                        "year": ""
                    })
                    if amt != "0":
                        fundings.append({
                            "fundingSource": "Rotary Club",
                            "fundingAmount": amt,
                            "fundingClubKey": ckey,
                            "isImplementingPartnerFlag": False
                        })
                elif amt != "0":
                    fundings.append({
                        "fundingSource": "Rotary Club",
                        "fundingAmount": amt,
                        "fundingClubKey": c_str,
                        "isImplementingPartnerFlag": False
                    })

        # Ensure Lake Atitlan host club is included in partners
        has_atitlan_partner = any(ROTARY_LAKE_ATITLAN_CLUB_KEY in str(p.get("partnerOrganizationKey", "")) for p in partners)
        if not has_atitlan_partner:
            partners.insert(0, {
                "partnerOrganizationKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                "Hour": "",
                "MoneyDonated": "",
                "NoOfVolunteer": "",
                "year": ""
            })

        # 4. Cooperating Partner Organizations / NGOs
        # Non-Rotary NGOs cannot be placed in projectPartnerClubMembers (which requires Rotary Organization UUIDs).
        # Any financial donations from NGOs belong in projectFundings if amount > 0.

    else:
        intl_club = str(p.get("international_club_name") or p.get("internationalClub_name") or "").strip()
        partner_club = find_partner_club(intl_club)
        partner_club_key = partner_club.get("key") if partner_club else None

        fundings = []
        intl_dist_raw = str(p.get("international_club_district") or p.get("internationalClub_district") or "").strip()
        dist_digits = re.sub(r'[^0-9]', '', intl_dist_raw)
        intl_dist = dist_digits if dist_digits else intl_dist_raw

        if is_international and gid.startswith("GG"):
            # Global Grant Breakdown
            fundings.append({
                "fundingSource": "Global grant",
                "fundingAmount": str(int(num_budget * 0.45)) if num_budget else "20000",
                "fundingClubKey": gid
            })
            if intl_dist:
                fundings.append({
                    "fundingSource": "District(Cash)",
                    "fundingAmount": str(int(num_budget * 0.35)) if num_budget else "15000",
                    "fundingClubKey": intl_dist,
                    "isImplementingPartnerFlag": False
                })
            if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.15)) if num_budget else "5000",
                    "fundingClubKey": partner_club_key,
                    "isImplementingPartnerFlag": False
                })
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.05)) if num_budget else "2000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "isImplementingPartnerFlag": False
                })
            else:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.20)) if num_budget else "5000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "isImplementingPartnerFlag": False
                })
        else:
            # Club Direct / District Grant / Other
            if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.70)) if num_budget else budget_str,
                    "fundingClubKey": partner_club_key,
                    "isImplementingPartnerFlag": False
                })
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.30)) if num_budget else "1000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "isImplementingPartnerFlag": False
                })
            elif intl_dist:
                fundings.append({
                    "fundingSource": "District(Cash)",
                    "fundingAmount": str(int(num_budget * 0.70)) if num_budget else budget_str,
                    "fundingClubKey": intl_dist,
                    "isImplementingPartnerFlag": False
                })
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": str(int(num_budget * 0.30)) if num_budget else "1000",
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "isImplementingPartnerFlag": False
                })
            else:
                fundings.append({
                    "fundingSource": "Rotary Club",
                    "fundingAmount": budget_str,
                    "fundingClubKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
                    "isImplementingPartnerFlag": False
                })

        # Partners
        partners = [{
            "partnerOrganizationKey": ROTARY_LAKE_ATITLAN_CLUB_KEY,
            "Hour": "",
            "MoneyDonated": "",
            "NoOfVolunteer": "",
            "year": ""
        }]
        if partner_club_key and partner_club_key != ROTARY_LAKE_ATITLAN_CLUB_KEY:
            partners.append({
                "partnerOrganizationKey": partner_club_key,
                "Hour": "",
                "MoneyDonated": str(int(num_budget * 0.70)) if num_budget else "",
                "NoOfVolunteer": "",
                "year": ""
            })

    # Project search tags (semicolon-delimited for Rotary SPC)
    tag_list = []
    for org in cooperating_orgs:
        if org and org not in tag_list and "rotary" not in org.lower():
            tag_list.append(org)
    if aof_name and aof_name not in tag_list:
        tag_list.append(aof_name)
    tag_list.append("Guatemala")
    tag_list.append("Lake Atitlan")
    tags_str = ";".join(tag_list[:6])

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
        "projectNonRotaryPartners": [],
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

        email = os.getenv("ROTARY_EMAIL", "")
        password = os.getenv("ROTARY_PASSWORD", "")

        if email and password:
            try:
                # 1. Dismiss any OneTrust cookie banners or modal overlays that intercept pointer events
                try:
                    await page.evaluate("""() => {
                        const ot = document.getElementById('onetrust-consent-sdk');
                        if (ot) ot.remove();
                        const btn = document.getElementById('onetrust-accept-btn-handler');
                        if (btn) btn.click();
                        document.querySelectorAll('.ReactModalPortal, .ReactModal__Overlay').forEach(e => e.remove());
                    }""")
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
                    user_input = await page.wait_for_selector("#okta-signin-username", timeout=20000)
                await user_input.fill(email)
                await page.fill("#okta-signin-password, input[name='password']", password)

                # Dismiss overlays again right before submitting
                try:
                    await page.evaluate("""() => {
                        const ot = document.getElementById('onetrust-consent-sdk');
                        if (ot) ot.remove();
                        document.querySelectorAll('.ReactModalPortal, .ReactModal__Overlay').forEach(e => e.remove());
                    }""")
                except Exception:
                    pass

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

                        payload.isChangedProjectDetail = true;
                        if (payload.projectCategoryFund) {
                            payload.projectCategoryFund.isChangedProjectCategoryFund = true;
                            if (existingDetail && existingDetail.categories && existingDetail.categories.length > 0) {
                                payload.projectCategoryFund.projectCategoryFundKey = existingDetail.categories[0].projectCategoryFundKey;
                            }
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
                        if (existingDetail && existingDetail.fundingSources && existingDetail.fundingSources.length > 0) {
                            const existingFundings = existingDetail.fundingSources;
                            const newFundings = [];
                            const usedFundingKeys = new Set();

                            for (const f of (payload.projectFundings || [])) {
                                const match = existingFundings.find(ef => (!usedFundingKeys.has(ef.projectFundingSourceKey)) && (
                                    (ef.fundingSource === f.fundingSource && (ef.fundingSourceKey === f.fundingClubKey || ef.fundingOtherName === f.fundingClubKey)) ||
                                    (f.fundingClubKey && ef.fundingOtherName === f.fundingClubKey)
                                ));
                                if (match) {
                                    usedFundingKeys.add(match.projectFundingSourceKey);
                                    newFundings.push({
                                        ...f,
                                        projectFundingSourceKey: match.projectFundingSourceKey,
                                        isChangedProjectFundingSource: true,
                                        isDeleted: false
                                    });
                                } else {
                                    const unused = existingFundings.find(ef => !usedFundingKeys.has(ef.projectFundingSourceKey) && ef.fundingSource === f.fundingSource);
                                    if (unused) {
                                        usedFundingKeys.add(unused.projectFundingSourceKey);
                                        newFundings.push({
                                            ...f,
                                            projectFundingSourceKey: unused.projectFundingSourceKey,
                                            isChangedProjectFundingSource: true,
                                            isDeleted: false
                                        });
                                    } else {
                                        newFundings.push({
                                            ...f,
                                            isChangedProjectFundingSource: true,
                                            isDeleted: false
                                        });
                                    }
                                }
                            }

                            // Mark any unreferenced existing funding as deleted
                            for (const ef of existingFundings) {
                                if (!usedFundingKeys.has(ef.projectFundingSourceKey)) {
                                    newFundings.push({
                                        projectFundingSourceKey: ef.projectFundingSourceKey,
                                        fundingSource: ef.fundingSource || "Rotary Club",
                                        fundingAmount: ef.fundingAmount || "0",
                                        fundingClubKey: ef.fundingSourceKey || ef.fundingOtherName || "",
                                        isDeleted: true,
                                        isChangedProjectFundingSource: true
                                    });
                                }
                            }
                            payload.projectFundings = newFundings;
                        }

                        // Reconcile Partners (prevents duplicate partners)
                        if (existingDetail && existingDetail.partners && existingDetail.partners.length > 0) {
                            const existingPartners = existingDetail.partners;
                            const newPartners = [];
                            const usedPartnerKeys = new Set();

                            for (const pcm of (payload.projectPartnerClubMembers || [])) {
                                const match = existingPartners.find(ep => (!usedPartnerKeys.has(ep.key)) && (ep.partnerKey === pcm.partnerOrganizationKey));
                                if (match) {
                                    usedPartnerKeys.add(match.key);
                                    newPartners.push({
                                        ...pcm,
                                        projectPartnerClubMemberKey: match.key,
                                        isChangedProjectPartnerClubMember: false,
                                        isDeleted: false
                                    });
                                } else {
                                    newPartners.push({
                                        ...pcm,
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
                                        partnerOrganizationKey: ep.partnerKey,
                                        isDeleted: true,
                                        isChangedProjectPartnerClubMember: true
                                    });
                                }
                            }
                            payload.projectPartnerClubMembers = newPartners;
                        }

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
                            return { ok: false, status: res.status, error: errTxt };
                        }
                        const data = await res.json();
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

