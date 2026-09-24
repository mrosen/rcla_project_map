#!/usr/bin/env python3
"""
scripts/analyze_rotary_gaps.py

Analyzes all participating Rotary clubs and districts across the 37 projects to identify:
1. Complete Gaps: Clubs or districts with NO named Rotarian contact on file.
2. Email Gaps: Clubs or districts with named contacts, but missing an email address.
3. Covered Entities: Clubs or districts that already have a named contact with an email address.

Outputs:
- rotary_gaps_identified.json
"""

import json
import re
from pathlib import Path

WORKSPACE_ROOT = Path("/home/msr/rcla_project_map")
HARVESTED_PATH = WORKSPACE_ROOT / "harvested_contacts.json"
RESOLVED_CLUBS_PATH = WORKSPACE_ROOT / "spc_resolved_clubs.json"
OUTPUT_GAPS_PATH = WORKSPACE_ROOT / "rotary_gaps_identified.json"

if not HARVESTED_PATH.exists():
    HARVESTED_PATH = Path("harvested_contacts.json")
if not RESOLVED_CLUBS_PATH.exists():
    RESOLVED_CLUBS_PATH = Path("spc_resolved_clubs.json")
if not OUTPUT_GAPS_PATH.parent.exists():
    OUTPUT_GAPS_PATH = Path("rotary_gaps_identified.json")

def norm_club(name):
    if not name:
        return ""
    c = name.strip()
    c = re.sub(r'\[\s*Rotary\s+Club\s*\]', '', c, flags=re.IGNORECASE)
    c = re.sub(r'^(?:RC\s+of\s+|RC\s+|Rotary\s+Club\s+of\s+|Rotary\s+Club\s+|Club\s+Rotario\s+de\s+)', '', c, flags=re.IGNORECASE)
    c = re.sub(r'\s*\([dD]\d+\)', '', c)
    c = re.sub(r'\s+', ' ', c).strip(" ,-")
    return c

def main():
    print("=== Rotary Gap Analyzer ===")
    with open(HARVESTED_PATH, "r", encoding="utf-8") as f:
        harvested = json.load(f)

    resolved_clubs = {}
    if RESOLVED_CLUBS_PATH.exists():
        with open(RESOLVED_CLUBS_PATH, "r", encoding="utf-8") as f:
            resolved_clubs = json.load(f)

    projects = harvested.get("projects", [])
    all_contacts = harvested.get("all_contacts", [])

    participating_clubs = {}     # norm_key -> {name, district, state, country, projects: dict(id->title)}
    participating_districts = {} # dist_num -> {projects: dict(id->title)}

    # 1. Collect all participating entities from project summaries
    for p in projects:
        pid = p["project_id"]
        title = p["project_title"]

        for c in p.get("participating_clubs", []):
            c_clean = norm_club(c)
            if not c_clean or c_clean.lower() in ("details", "cash from club", "rotary club", "[ rotary club ]"):
                continue
            key = c_clean.lower()
            if key not in participating_clubs:
                res = resolved_clubs.get(key) or {}
                participating_clubs[key] = {
                    "raw_name": c_clean,
                    "name": res.get("name") or c_clean,
                    "club_id": res.get("id") or "",
                    "district": res.get("district") or "",
                    "state": res.get("state") or "",
                    "country": res.get("country") or "",
                    "projects": {}
                }
            participating_clubs[key]["projects"][pid] = title

        for d in p.get("participating_districts", []):
            d_clean = str(d).strip()
            if re.match(r'^\d{4}$', d_clean) and not (1900 <= int(d_clean) <= 2099):
                if d_clean not in participating_districts:
                    participating_districts[d_clean] = {"projects": {}}
                participating_districts[d_clean]["projects"][pid] = title

    # Also include clubs/districts from individual contacts (in case not in financing/partner lists)
    for c in all_contacts:
        c_club = norm_club(c.get("club", ""))
        c_dist = str(c.get("district", "")).strip()
        pid = c.get("project_id")
        title = c.get("project_title")

        if c_club and c_club.lower() not in ("details", "cash from club", "rotary club"):
            key = c_club.lower()
            if key not in participating_clubs:
                res = resolved_clubs.get(key) or {}
                participating_clubs[key] = {
                    "raw_name": c_club,
                    "name": res.get("name") or c_club,
                    "club_id": res.get("id") or "",
                    "district": res.get("district") or c_dist,
                    "state": res.get("state") or "",
                    "country": res.get("country") or "",
                    "projects": {}
                }
            if pid and title:
                participating_clubs[key]["projects"][pid] = title
            if not participating_clubs[key]["district"] and c_dist:
                participating_clubs[key]["district"] = c_dist

        if re.match(r'^\d{4}$', c_dist) and not (1900 <= int(c_dist) <= 2099):
            if c_dist not in participating_districts:
                participating_districts[c_dist] = {"projects": {}}
            if pid and title:
                participating_districts[c_dist]["projects"][pid] = title

    # Map contacts by club and district
    contacts_by_club = {} # club_key -> list of contacts
    contacts_by_dist = {} # dist_num -> list of contacts

    for c in all_contacts:
        c_club = norm_club(c.get("club", ""))
        if c_club:
            k = c_club.lower()
            if k not in contacts_by_club:
                contacts_by_club[k] = []
            contacts_by_club[k].append(c)

        c_dist = str(c.get("district", "")).strip()
        if re.match(r'^\d{4}$', c_dist):
            if c_dist not in contacts_by_dist:
                contacts_by_dist[c_dist] = []
            contacts_by_dist[c_dist].append(c)

    # Analyze Club Gaps
    club_gaps = []
    club_covered = []

    for k, info in sorted(participating_clubs.items(), key=lambda x: x[1]["name"]):
        # Do not treat Lake Atitlán as a gap (that is the host club)
        if "atitlan" in k or "atitlán" in k:
            continue

        c_list = contacts_by_club.get(k, [])
        c_with_email = [c for c in c_list if c.get("email")]

        proj_list = [{"id": pid, "title": t} for pid, t in sorted(info["projects"].items())]

        if not c_list:
            club_gaps.append({
                "entity_type": "Club",
                "entity_name": info["name"],
                "club_id": info["club_id"],
                "district": info["district"],
                "state": info["state"],
                "country": info["country"],
                "gap_status": "No Contact",
                "projects_count": len(proj_list),
                "projects": proj_list,
                "existing_contacts": []
            })
        elif not c_with_email:
            club_gaps.append({
                "entity_type": "Club",
                "entity_name": info["name"],
                "club_id": info["club_id"],
                "district": info["district"] or (c_list[0].get("district") if c_list else ""),
                "state": info["state"],
                "country": info["country"],
                "gap_status": "Missing Email",
                "projects_count": len(proj_list),
                "projects": proj_list,
                "existing_contacts": [{
                    "name": c["name"],
                    "role": c["role"],
                    "project_id": c["project_id"]
                } for c in c_list]
            })
        else:
            club_covered.append({
                "entity_name": info["name"],
                "district": info["district"],
                "contacts_with_email": [f"{c['name']} <{c['email']}>" for c in c_with_email]
            })

    # Analyze District Gaps
    dist_gaps = []
    dist_covered = []

    for d, info in sorted(participating_districts.items()):
        # District 4250 is Lake Atitlán's home district
        d_list = contacts_by_dist.get(d, [])
        d_with_email = [c for c in d_list if c.get("email")]

        proj_list = [{"id": pid, "title": t} for pid, t in sorted(info["projects"].items())]

        if not d_list:
            dist_gaps.append({
                "entity_type": "District",
                "entity_name": f"District {d}",
                "district": d,
                "gap_status": "No Contact",
                "projects_count": len(proj_list),
                "projects": proj_list,
                "existing_contacts": []
            })
        elif not d_with_email:
            dist_gaps.append({
                "entity_type": "District",
                "entity_name": f"District {d}",
                "district": d,
                "gap_status": "Missing Email",
                "projects_count": len(proj_list),
                "projects": proj_list,
                "existing_contacts": [{
                    "name": c["name"],
                    "role": c["role"],
                    "project_id": c["project_id"]
                } for c in d_list]
            })
        else:
            dist_covered.append({
                "district": d,
                "contacts_with_email": [f"{c['name']} <{c['email']}>" for c in d_with_email]
            })

    output_data = {
        "summary": {
            "total_participating_clubs": len(participating_clubs),
            "clubs_covered_with_email": len(club_covered),
            "total_club_gaps": len(club_gaps),
            "club_gaps_no_contact": sum(1 for g in club_gaps if g["gap_status"] == "No Contact"),
            "club_gaps_missing_email": sum(1 for g in club_gaps if g["gap_status"] == "Missing Email"),
            "total_participating_districts": len(participating_districts),
            "districts_covered_with_email": len(dist_covered),
            "total_district_gaps": len(dist_gaps),
            "district_gaps_no_contact": sum(1 for g in dist_gaps if g["gap_status"] == "No Contact"),
            "district_gaps_missing_email": sum(1 for g in dist_gaps if g["gap_status"] == "Missing Email"),
        },
        "club_gaps": club_gaps,
        "district_gaps": dist_gaps,
        "covered_clubs": club_covered,
        "covered_districts": dist_covered
    }

    with open(OUTPUT_GAPS_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Summary:")
    print(f"  Clubs: {len(participating_clubs)} total | {len(club_covered)} covered with email | {len(club_gaps)} gaps")
    print(f"  Districts: {len(participating_districts)} total | {len(dist_covered)} covered with email | {len(dist_gaps)} gaps")
    print(f"Gaps written to {OUTPUT_GAPS_PATH}")

if __name__ == "__main__":
    main()
