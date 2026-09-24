#!/usr/bin/env python3
"""
clean_coop_organizations.py
Cleans polluted details.cooperating_organizations and partner columns in Supabase
so that all organizations are individual, clean items without un-split strings or duplicate tags.
"""

import json
import os
import urllib.request
from dotenv import load_dotenv

load_dotenv("/home/msr/rcla_project_map/.env")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    print("Error: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    exit(1)

SPECIFIC_FIXES = {
    "GG2091778": [
        "Asociación Pro Agua del Pueblo (ADP)",
        "Mil Milagros",
        "Municipality of Santa Lucía Utatlán",
        "Municipality of San Andrés Semetabaj",
        "COCODE of Santa Lucía Utatlán",
        "COCODE of San Andrés Semetabaj"
    ],
    "GG2125241": [
        "Asociación Pro Agua del Pueblo",
        "Engineers Without Borders-USA Guatemala",
        "COCODE (Los Consejos Comunitarios de Desarrollo Urbano y Rural)"
    ],
    "GG2570080": [
        "Hospitalito Atitlán",
        "Asociación Pro Salud Educación y Desarrollo K’aslimaal",
        "IZUMI Foundation",
        "Ministry of Health (MoH)",
        "SESAN",
        "COMUSAN",
        "Children’s Mercy Hospital",
        "Seattle Children’s Hospital",
        "University of Pennsylvania"
    ],
    "GG2684872": [
        "Wellkind",
        "Water4Life",
        "Agua para La Vida",
        "COCODEs",
        "Indigenous Mayor’s Office"
    ],
    "GG2578692": [
        "Asociacion Pro Agua del Pueblo (ADP)",
        "Municipality of Santa Lucia Utatlan",
        "Guatemala Federal Department of Education",
        "Vista Hermosa Water Committee",
        "COCODE"
    ],
    "GG2570516": [
        "Asociacion Pro Agua del Pueblo (ADP)",
        "Municipalidad Santa Lucía Utatlán",
        "Vista Hermosa Water Committee",
        "COCODE",
        "WASH-RAG"
    ],
    "GG2574529": [
        "Wellkind Guatemala",
        "Tuik Ruch Lew"
    ]
}

def clean_project(pid, current_details, current_partner):
    if pid in SPECIFIC_FIXES:
        clean_orgs = SPECIFIC_FIXES[pid]
    else:
        raw_list = current_details.get("cooperating_organizations") or []
        if isinstance(raw_list, str):
            raw_list = [raw_list]
        clean_orgs = []
        seen = set()
        for item in raw_list:
            if isinstance(item, str):
                # Don't split if it's a known single entity with city name like "St. Aidan's Episcopal Church, San Francisco"
                if "St. Aidan's" in item:
                    sub_items = [item]
                else:
                    sub_items = [s.strip() for s in item.split(",") if s.strip()]
                for s in sub_items:
                    k = s.lower()
                    if k not in seen:
                        seen.add(k)
                        clean_orgs.append(s)

    new_details = dict(current_details)
    new_details["cooperating_organizations"] = clean_orgs
    new_partner = ", ".join(clean_orgs)

    return new_details, new_partner

def main():
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/projects?select=id,title,partner,details", headers=headers)
    with urllib.request.urlopen(req) as resp:
        projects = json.loads(resp.read().decode())

    print(f"Auditing {len(projects)} projects in Supabase...")
    updated_count = 0

    for p in projects:
        pid = p.get("id")
        details = p.get("details") or {}
        if isinstance(details, str):
            try: details = json.loads(details)
            except: details = {}

        current_coop = details.get("cooperating_organizations") or []
        current_partner = p.get("partner") or ""

        needs_update = False
        if pid in SPECIFIC_FIXES:
            needs_update = True
        elif any(isinstance(x, str) and "," in x and "St. Aidan's" not in x for x in current_coop):
            needs_update = True
        elif len(current_coop) != len(set(x.lower() for x in current_coop if isinstance(x, str))):
            needs_update = True

        if needs_update:
            new_details, new_partner = clean_project(pid, details, current_partner)
            print(f"\nUpdating {pid} ({p.get('title')}):")
            print(f"  Old coop: {current_coop}")
            print(f"  New coop: {new_details['cooperating_organizations']}")
            print(f"  New partner: {new_partner}")

            patch_data = json.dumps({
                "details": new_details,
                "partner": new_partner
            }).encode("utf-8")

            patch_req = urllib.request.Request(
                f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}",
                data=patch_data,
                headers=headers,
                method="PATCH"
            )
            with urllib.request.urlopen(patch_req) as resp:
                pass
            updated_count += 1

    print(f"\n✓ Successfully updated {updated_count} projects in Supabase.")

if __name__ == "__main__":
    main()

