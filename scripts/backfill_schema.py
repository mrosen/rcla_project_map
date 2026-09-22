#!/usr/bin/env python3
"""
scripts/backfill_schema.py
--------------------------
Checks for new columns on 'projects' table (brief_overview, complete_overview,
start_date, end_date, timeline, details, sync_status) and populates initial values
for all projects in Supabase Cloud.
"""

import os
import sys
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

if not SERVICE_KEY:
    print("ERROR: SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY not found in .env")
    sys.exit(1)

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json"
}

NEW_COLUMNS = ["brief_overview", "complete_overview", "start_date", "end_date", "timeline", "details", "sync_status"]

def check_columns_exist():
    url = f"{SUPABASE_URL}/rest/v1/projects?limit=1"
    res = httpx.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Error checking Supabase projects: {res.status_code} {res.text}")
        return False, []
    
    data = res.json()
    if not data:
        print("Warning: projects table is empty.")
        return False, []
    
    present_cols = set(data[0].keys())
    missing = [c for c in NEW_COLUMNS if c not in present_cols]
    return len(missing) == 0, missing

def backfill():
    exist, missing = check_columns_exist()
    if not exist:
        print(f"\n[!] New columns are missing from Supabase 'projects' table:")
        for col in missing:
            print(f"    - {col}")
        print("\nPlease execute 'schema_migration.sql' in your Supabase Dashboard SQL Editor:")
        print(f"  https://supabase.com/dashboard/project/rqhmsincnmxrgtipvkif/sql/new\n")
        return False

    print("✓ All new columns exist in Supabase! Fetching all projects for backfill...")
    url = f"{SUPABASE_URL}/rest/v1/projects?select=*"
    res = httpx.get(url, headers=HEADERS)
    if res.status_code != 200:
        print(f"Error fetching projects: {res.status_code} {res.text}")
        return False

    projects = res.json()
    print(f"Processing {len(projects)} projects...")

    # Load SPC migration state if available
    spc_state = {}
    spc_state_file = os.path.join(os.path.dirname(__file__), "..", "spc_migration_state.json")
    if os.path.exists(spc_state_file):
        try:
            with open(spc_state_file, "r", encoding="utf-8") as f:
                raw_spc = json.load(f)
                spc_state = raw_spc.get("projects", raw_spc)
        except Exception:
            pass

    # Load project_assets to check for RI documents
    assets_url = f"{SUPABASE_URL}/rest/v1/project_assets?select=project_id,filename"
    assets_res = httpx.get(assets_url, headers=HEADERS)
    assets_by_proj = {}
    if assets_res.status_code == 200:
        for a in assets_res.json():
            pid = a["project_id"]
            assets_by_proj.setdefault(pid, []).append(a["filename"].lower())

    updates = []
    for p in projects:
        pid = p["id"]
        title = (p.get("title") or "").strip()
        p_type = (p.get("project_type") or "").strip()
        desc = (p.get("description") or "").strip()
        narrative = (p.get("narrative") or "").strip()
        start_yr = p.get("start_year")

        # 1. Brief Overview (<= 100 chars)
        brief = p.get("brief_overview")
        if not brief:
            raw_brief = desc if desc else (narrative if narrative else title)
            brief = raw_brief.strip()[:100].strip()

        # 2. Complete Overview (<= 1000 chars)
        complete = p.get("complete_overview")
        if not complete:
            raw_complete = narrative if narrative else (desc if desc else title)
            complete = raw_complete.strip()[:1000].strip()

        # 3. Start Date & End Date
        s_date = p.get("start_date")
        if not s_date and start_yr:
            s_date = f"{start_yr}-01-01"
        e_date = p.get("end_date")

        # 4. Timeline
        timeline = p.get("timeline")
        if not timeline or not isinstance(timeline, dict) or not timeline.get("milestones"):
            milestones = []
            if p_type == "Global Grant":
                milestones.append({
                    "id": "m1",
                    "name": "Submitted",
                    "date": s_date or "",
                    "notes": "Application submitted to Rotary International"
                })
                milestones.append({
                    "id": "m2",
                    "name": "Approved",
                    "date": s_date or "",
                    "notes": "Grant approved by TRF"
                })
            else:
                milestones.append({
                    "id": "m1",
                    "name": "Project Initiated",
                    "date": s_date or "",
                    "notes": ""
                })
            timeline = {
                "backstory": narrative[:300] if narrative else "",
                "milestones": milestones
            }

        # 5. Details (financial, partners, personnel)
        details = p.get("details")
        if not details or not isinstance(details, dict):
            details = {
                "budget": p.get("budget") or p.get("amount") or 0,
                "partner": p.get("partner") or "",
                "international_club": p.get("international_club_name") or "",
                "international_district": p.get("international_club_district") or "",
                "shepherd": p.get("shepherd") or p.get("shepard") or "",
                "beneficiaries": p.get("beneficiaries") or "",
                "partner_clubs": [],
                "partner_districts": [],
                "cooperating_organizations": []
            }
        else:
            if "partner_clubs" not in details:
                details["partner_clubs"] = []
            if "partner_districts" not in details:
                details["partner_districts"] = []
            if "cooperating_organizations" not in details:
                details["cooperating_organizations"] = []

        # 6. Sync Status
        sync = p.get("sync_status")
        if not sync or not isinstance(sync, dict):
            proj_files = assets_by_proj.get(pid, [])
            has_app = any("application" in fn for fn in proj_files)
            report_count = sum(1 for fn in proj_files if "report" in fn)

            spc_info = spc_state.get(pid, {})
            is_spc = bool(spc_info.get("spc_id"))

            sync = {
                "grant_center": {
                    "has_application_pdf": has_app,
                    "has_report_pdfs": report_count > 0,
                    "report_count": report_count
                },
                "spc": {
                    "exported": is_spc,
                    "spc_project_id": spc_info.get("spc_id") or None,
                    "last_exported": spc_info.get("created_at") or None,
                    "in_sync": is_spc
                }
            }

        update_payload = {
            "id": pid,
            "brief_overview": brief,
            "complete_overview": complete,
            "start_date": s_date,
            "end_date": e_date,
            "timeline": timeline,
            "details": details,
            "sync_status": sync
        }
        updates.append(update_payload)

    # Update projects in Supabase via PATCH
    print(f"Uploading backfilled schema data for {len(updates)} projects...")
    success_count = 0
    fail_count = 0

    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        for p_update in updates:
            pid = p_update.pop("id")
            patch_url = f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}"
            patch_res = client.patch(patch_url, json=p_update)
            if patch_res.status_code in (200, 204):
                success_count += 1
                print(f"  ✓ [{pid}] Backfilled successfully")
            else:
                fail_count += 1
                print(f"  [X] [{pid}] Failed: {patch_res.status_code} {patch_res.text}")

    print(f"\n✓ Backfill complete: {success_count} succeeded, {fail_count} failed.")
    return fail_count == 0

if __name__ == "__main__":
    backfill()
