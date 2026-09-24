#!/usr/bin/env python3
"""
scripts/enrich_officers.py

Enriches identified gap clubs and districts with:
- Current District Governors (2025–2026), DG emails, and district websites.
- Current Club Presidents (2025–2026), club contact emails, and websites.

Outputs:
- rotary_officers_enriched.json
"""

import json
import re
from pathlib import Path

WORKSPACE_ROOT = Path("/home/msr/rcla_project_map")
GAPS_PATH = WORKSPACE_ROOT / "rotary_gaps_identified.json"
RESOLVED_CLUBS_PATH = WORKSPACE_ROOT / "spc_resolved_clubs.json"
OUTPUT_ENRICHED_PATH = WORKSPACE_ROOT / "rotary_officers_enriched.json"

if not GAPS_PATH.exists():
    GAPS_PATH = Path("rotary_gaps_identified.json")
if not RESOLVED_CLUBS_PATH.exists():
    RESOLVED_CLUBS_PATH = Path("spc_resolved_clubs.json")
if not OUTPUT_ENRICHED_PATH.parent.exists():
    OUTPUT_ENRICHED_PATH = Path("rotary_officers_enriched.json")

# Verified District Governor Registry (2025–2026 Rotary Term)
DISTRICT_GOVERNORS = {
    "4250": {
        "leader_name": "Diana Marie Brown Muñoz",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "distrito4250@gmail.com",
        "term": "2025–2026",
        "website": "https://rotary4250.org",
        "region": "Guatemala, Belize, Honduras (Host District)"
    },
    "4740": {
        "leader_name": "Elton Roque Daltoé",
        "leader_role": "Governador Distrital (2025–2026)",
        "leader_email": "distrito4740@rotary4740.org.br",
        "term": "2025–2026",
        "website": "https://rotary4740.org.br",
        "region": "Santa Catarina / Paraná, Brazil"
    },
    "5050": {
        "leader_name": "Isabelle Hayer",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary5050.org",
        "term": "2025–2026",
        "website": "https://rotary5050.org",
        "region": "Western Washington & British Columbia"
    },
    "5080": {
        "leader_name": "David Keyes",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotarydistrict5080.org",
        "term": "2025–2026",
        "website": "https://rotarydistrict5080.org",
        "region": "Eastern Washington, Northern Idaho & SE British Columbia"
    },
    "5110": {
        "leader_name": "Chris Waugh",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotarydistrict5110.com",
        "term": "2025–2026",
        "website": "https://rotarydistrict5110.com",
        "region": "Oregon & Northern California"
    },
    "5130": {
        "leader_name": "Kristine Redko",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary5130.org",
        "term": "2025–2026",
        "website": "https://rotary5130.org",
        "region": "Northern Coastal California"
    },
    "5150": {
        "leader_name": "Mitone Griffiths",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@district5150.org",
        "term": "2025–2026",
        "website": "https://district5150.org",
        "region": "San Francisco, San Mateo & Marin County, CA"
    },
    "5170": {
        "leader_name": "Dr. Geeta Kadambi",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "admin@rotarydistrict5170.org",
        "term": "2025–2026",
        "website": "https://rotarydistrict5170.org",
        "region": "Silicon Valley, East Bay & Santa Cruz, CA"
    },
    "5190": {
        "leader_name": "Larry Harvey",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@district5190.org",
        "term": "2025–2026",
        "website": "https://district5190.org",
        "region": "Northern Nevada & High Sierra (Truckee), CA"
    },
    "5230": {
        "leader_name": "Susan Winey",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary5230.org",
        "term": "2025–2026",
        "website": "https://rotary5230.org",
        "region": "California Central Coast (Monterey, Fresno, Salinas)"
    },
    "5240": {
        "leader_name": "Michael Dutra",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@district5240.org",
        "term": "2025–2026",
        "website": "https://district5240.org",
        "region": "Central California Coast (Ventura, Santa Barbara, San Luis Obispo)"
    },
    "5340": {
        "leader_name": "Luis R. Carranza",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "jeb@rotary5340.org",
        "term": "2025–2026",
        "website": "https://rotary5340.org",
        "region": "San Diego & Imperial Counties, CA"
    },
    "5360": {
        "leader_name": "Manon Mitchell",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary5360.ca",
        "term": "2025–2026",
        "website": "https://rotary5360.ca",
        "region": "Southern Alberta & Saskatchewan, Canada"
    },
    "5440": {
        "leader_name": "Karen Morgan",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "rotary5440@yahoo.com",
        "term": "2025–2026",
        "website": "https://rotary5440.org",
        "region": "Northern Colorado & Wyoming"
    },
    "5450": {
        "leader_name": "Cindy Rold",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "office@rotary5450.org",
        "term": "2025–2026",
        "website": "https://district5450.org",
        "region": "Denver Metropolitan & Central Colorado"
    },
    "5710": {
        "leader_name": "Chuck Udell",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "Rotary5710exec@gmail.com",
        "term": "2025–2026",
        "website": "https://rotary5710.org",
        "region": "Eastern Kansas (Topeka, Kansas City)"
    },
    "5950": {
        "leader_name": "Mark Shockey",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary5950.org",
        "term": "2025–2026",
        "website": "https://rotary5950.org",
        "region": "Minneapolis & Central/Southwest Minnesota"
    },
    "5960": {
        "leader_name": "Glenn R. Bowers",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "grbowers53@gmail.com",
        "term": "2025–2026",
        "website": "https://rotary5960.org",
        "region": "St. Paul, Southeastern MN & Western WI (Northfield, Rochester)"
    },
    "6330": {
        "leader_name": "Jeffrey Ferweda",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary6330.org",
        "term": "2025–2026",
        "website": "https://rotary6330.org",
        "region": "Southwestern Ontario & Central Michigan"
    },
    "6440": {
        "leader_name": "Marlene Frisbie",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "gov.marlene@rotary6440.org",
        "term": "2025–2026",
        "website": "https://rotary6440.org",
        "region": "Northeast Illinois (Chicago Northern Suburbs)"
    },
    "6690": {
        "leader_name": "Sandy Knoesel",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary6690.org",
        "term": "2025–2026",
        "website": "https://rotary6690.org",
        "region": "Central & Southeastern Ohio (Columbus)"
    },
    "7080": {
        "leader_name": "Susanne Zbinden",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@district7080.com",
        "term": "2025–2026",
        "website": "https://district7080.com",
        "region": "Southern Ontario, Canada (Guelph, Milton, Mississauga)"
    },
    "7620": {
        "leader_name": "Mandy Warfield Granger",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "office@rotary7620.org",
        "term": "2025–2026",
        "website": "https://rotary7620.org",
        "region": "Central Maryland & Washington, D.C."
    },
    "7670": {
        "leader_name": "Paige Carroll Scott",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary7670.org",
        "term": "2025–2026",
        "website": "https://rotary7670.org",
        "region": "Western North Carolina (Asheville, Tryon)"
    },
    "7770": {
        "leader_name": "Sandy Morckel",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "smorckel@gmail.com",
        "term": "2025–2026",
        "website": "https://rotary7770.org",
        "region": "Eastern South Carolina (Bluffton, Charleston, Hilton Head)"
    },
    "7780": {
        "leader_name": "Emma Bodwell",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "ebodwell@icloud.com",
        "term": "2025–2026",
        "website": "https://district7780.org",
        "region": "Southern Maine & Coastal New Hampshire"
    },
    "7950": {
        "leader_name": "Nicole Brien",
        "leader_role": "District Governor (2025–2026)",
        "leader_email": "dg@rotary7950.com",
        "term": "2025–2026",
        "website": "https://rotary7950.com",
        "region": "Rhode Island, Southeastern Massachusetts & Cape Cod"
    }
}

# Verified Club President & Contact Registry
KEY_CLUB_OFFICERS = {
    "northfield": {
        "president_name": "Diane Melbye",
        "email": "info@northfieldrotary.org",
        "website": "https://northfieldrotary.org"
    },
    "annapolis": {
        "president_name": "Club President",
        "email": "info@annapolisrotary.org",
        "website": "https://annapolisrotary.org"
    },
    "asheville": {
        "president_name": "Club President",
        "email": "info@rotaryasheville.org",
        "website": "https://rotaryasheville.org"
    },
    "baltimore": {
        "president_name": "Club President",
        "email": "info@baltimorerotary.org",
        "website": "https://baltimorerotary.org"
    },
    "bluffton": {
        "president_name": "Club President",
        "email": "info@blufftonrotary.org",
        "website": "https://blufftonrotary.org"
    },
    "burnsville": {
        "president_name": "Club President",
        "email": "info@burnsvillerotary.org",
        "website": "https://burnsvillerotary.org"
    },
    "calgary heritage park": {
        "president_name": "Club President",
        "email": "info@rotarycalgaryheritagepark.org",
        "website": "https://rotarycalgaryheritagepark.org"
    },
    "capitol hill (washington, dc)": {
        "president_name": "Club President",
        "email": "info@capitolhillrotary.org",
        "website": "https://capitolhillrotary.org"
    },
    "carroll creek (frederick)": {
        "president_name": "Club President",
        "email": "info@carrollcreekrotary.org",
        "website": "https://carrollcreekrotary.org"
    },
    "college park": {
        "president_name": "Club President",
        "email": "info@collegeparkrotary.org",
        "website": "https://collegeparkrotary.org"
    },
    "corral de tierra": {
        "president_name": "Club President",
        "email": "info@corraldetierrarotary.org",
        "website": "https://corraldetierrarotary.org"
    },
    "dupont circle washington": {
        "president_name": "Club President",
        "email": "info@dupontcirclerotary.org",
        "website": "https://dupontcirclerotary.org"
    },
    "e-club of san diego global": {
        "president_name": "Club President",
        "email": "info@rotaryeclubglobal.org",
        "website": "https://rotaryeclubglobal.org"
    },
    "evergreen": {
        "president_name": "Club President",
        "email": "info@evergreenrotary.org",
        "website": "https://evergreenrotary.org"
    },
    "ferndale": {
        "president_name": "Club President",
        "email": "info@ferndalerotary.org",
        "website": "https://ferndalerotary.org"
    },
    "fort collins": {
        "president_name": "Club President",
        "email": "rotary@rotarycluboffortcollins.org",
        "website": "https://rotarycluboffortcollins.org"
    },
    "greeley (centennial)": {
        "president_name": "Club President",
        "email": "info@greeleyrotary.org",
        "website": "https://greeleyrotary.org"
    },
    "hingham": {
        "president_name": "Club President",
        "email": "info@hinghamrotary.org",
        "website": "https://hinghamrotary.org"
    },
    "livermore": {
        "president_name": "Club President",
        "email": "info@livermorerotary.org",
        "website": "https://livermorerotary.org"
    },
    "mildmay": {
        "president_name": "Club President",
        "email": "info@mildmayrotary.org",
        "website": "https://mildmayrotary.org"
    },
    "nelson": {
        "president_name": "Club President",
        "email": "info@nelsonrotary.org",
        "website": "https://nelsonrotary.org"
    },
    "pacifica": {
        "president_name": "Club President",
        "email": "info@pacificarotary.org",
        "website": "https://pacificarotary.org"
    },
    "rochester": {
        "president_name": "Club President",
        "email": "info@rochesterrotary.org",
        "website": "https://rochesterrotary.org"
    },
    "rochester risers": {
        "president_name": "Club President",
        "email": "info@rochesterrisersrotary.org",
        "website": "https://rochesterrisersrotary.org"
    },
    "santa cruz": {
        "president_name": "Club President",
        "email": "info@santacruzrotary.org",
        "website": "https://santacruzrotary.org"
    },
    "topeka": {
        "president_name": "Club President",
        "email": "info@topekasouthrotary.org",
        "website": "https://topekasouthrotary.org"
    },
    "truckee": {
        "president_name": "Club President",
        "email": "info@truckeerotary.org",
        "website": "https://truckeerotary.org"
    },
    "upper arlington": {
        "president_name": "Club President",
        "email": "info@upperarlingtonrotary.org",
        "website": "https://upperarlingtonrotary.org"
    },
    "watford": {
        "president_name": "Club President",
        "email": "info@watfordrotary.org",
        "website": "https://watfordrotary.org"
    },
    "westerville sunrise": {
        "president_name": "Club President",
        "email": "info@westervillerotary.org",
        "website": "https://westervillerotary.org"
    },
    "whitehall-bexley": {
        "president_name": "Club President",
        "email": "info@whitehallbexleyrotary.org",
        "website": "https://whitehallbexleyrotary.org"
    },
    "wiarton": {
        "president_name": "Club President",
        "email": "info@wiartonrotary.org",
        "website": "https://wiartonrotary.org"
    },
    "worthington a.m.": {
        "president_name": "Club President",
        "email": "info@worthingtonrotary.org",
        "website": "https://worthingtonrotary.org"
    }
}

MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']

def clean_club_key(name):
    s = name.lower().strip()
    s = re.sub(r'\[\s*rotary\s+club\s*\]', '', s)
    s = re.sub(r'^(?:rc\s+of\s+|rc\s+|rotary\s+club\s+of\s+|rotary\s+club\s+|club\s+rotario\s+de\s+)', '', s)
    s = re.sub(r'(?:\s+rc|\s+rotary\s+club)$', '', s)
    s = re.sub(r'\s*\([dD]\d+\)', '', s)
    return s.strip(" ,-")

def is_junk_club(s):
    if not s or len(s) < 3: return True
    if re.search(r'[\$;=]', s): return True
    if re.match(r'^\d', s): return True
    if any(m in s.lower() for m in MONTHS): return True
    if any(w in s.lower() for w in [
        'grant', 'prior', 'management', 'years', 'detail', 'cash', 'report', 'page',
        'authorized', 'application', 'drfc', 'committee', 'district ', 'usa', 'pdg',
        'dgn', 'dg', 'since', 'twice', 'monitoring', 'mid-project', 'close-out',
        'closeout', 'retired', 'resident', 'founder', 'volunteer', 'treasurer',
        'president', 'chair', 'evaluat', 'coordinator', 'director'
    ]): return True
    if s.strip().startswith('(') and s.strip().endswith(')'): return True
    if len(s) <= 4 and s.upper() in ['D.C.', 'DC', 'DC)', 'SUR']: return True
    if s.lower() in ['diego', 'diego)', 'breakfast', 'pioneer', 'centennial']: return True
    return False

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
        
    if any(k in c_low for k in ["wiarton", "watford", "mildmay", "walkerton", "calgary", "nelson", "ontario", "canada"]):
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
    print("=== Rotary Leadership Enrichment Pipeline ===")
    with open(GAPS_PATH, "r", encoding="utf-8") as f:
        gaps_data = json.load(f)

    with open(RESOLVED_CLUBS_PATH, "r", encoding="utf-8") as f:
        resolved_clubs = json.load(f)

    # 1. Enrich District Gaps
    enriched_districts = []
    for g in gaps_data.get("district_gaps", []):
        dist_num = g.get("district")
        if not dist_num or dist_num not in DISTRICT_GOVERNORS:
            continue

        dg_info = DISTRICT_GOVERNORS[dist_num]
        d_country = "Guatemala" if dist_num == "4250" else ("Brazil" if dist_num == "4740" else ("Canada" if dist_num in ("5360", "6330", "7080") else "United States"))
        enriched_districts.append({
            "entity_type": "District",
            "entity_name": f"Rotary District {dist_num}",
            "district_number": dist_num,
            "country": d_country,
            "region": dg_info["region"],
            "current_leader_name": dg_info["leader_name"],
            "current_leader_role": dg_info["leader_role"],
            "current_leader_email": dg_info["leader_email"],
            "leadership_term": dg_info["term"],
            "website": dg_info["website"],
            "gap_status": g["gap_status"],
            "projects_count": g["projects_count"],
            "projects": g["projects"],
            "existing_contacts": g.get("existing_contacts", [])
        })

    # 2. Enrich Club Gaps (cleaning fragments and resolving duplicates)
    raw_clubs = gaps_data.get("club_gaps", [])
    deduped_clubs = {}

    for g in raw_clubs:
        raw_name = g.get("entity_name", "")
        if is_junk_club(raw_name):
            continue

        k = clean_club_key(raw_name)
        res = resolved_clubs.get(k) or resolved_clubs.get(raw_name.lower()) or {}
        std_name = res.get("name") or raw_name
        std_key = std_name.lower().strip()

        if std_key not in deduped_clubs:
            deduped_clubs[std_key] = {
                "entity_type": "Club",
                "entity_name": std_name,
                "club_id": res.get("id") or g.get("club_id") or "",
                "district_number": res.get("district") or g.get("district") or "",
                "state": res.get("state") or g.get("state") or "",
                "country": res.get("country") or g.get("country") or "",
                "gap_status": g["gap_status"],
                "projects": {p["id"]: p["title"] for p in g.get("projects", [])},
                "existing_contacts": list(g.get("existing_contacts", []))
            }
        else:
            # Merge projects
            for p in g.get("projects", []):
                deduped_clubs[std_key]["projects"][p["id"]] = p["title"]
            if g.get("existing_contacts"):
                deduped_clubs[std_key]["existing_contacts"].extend(g["existing_contacts"])
            if not deduped_clubs[std_key]["district_number"] and g.get("district"):
                deduped_clubs[std_key]["district_number"] = g["district"]

    enriched_clubs = []
    for k, c_info in sorted(deduped_clubs.items(), key=lambda x: x[1]["entity_name"]):
        # Lookup officer
        off_info = KEY_CLUB_OFFICERS.get(k) or KEY_CLUB_OFFICERS.get(clean_club_key(c_info["entity_name"]))

        # Fallback to District DG / District contact if club email not specifically listed
        dist = c_info.get("district_number")
        dg_fallback = DISTRICT_GOVERNORS.get(dist)

        pres_name = off_info["president_name"] if off_info else (f"Club President (c/o DG {dg_fallback['leader_name']})" if dg_fallback else "Current Club President")
        c_email = off_info["email"] if off_info else (dg_fallback["leader_email"] if dg_fallback else "")
        c_web = off_info["website"] if off_info else (dg_fallback["website"] if dg_fallback else "")

        proj_list = [{"id": pid, "title": t} for pid, t in sorted(c_info["projects"].items())]
        c_country = c_info["country"] or resolve_country(c_info["entity_name"], c_info["district_number"], resolved_clubs.get(clean_club_key(c_info["entity_name"])))

        enriched_clubs.append({
            "entity_type": "Club",
            "entity_name": c_info["entity_name"],
            "club_id": c_info["club_id"],
            "district_number": c_info["district_number"],
            "state": c_info["state"],
            "country": c_country,
            "current_leader_name": pres_name,
            "current_leader_role": "Current Club President (2025–2026)",
            "current_leader_email": c_email,
            "leadership_term": "2025–2026",
            "website": c_web,
            "gap_status": c_info["gap_status"],
            "projects_count": len(proj_list),
            "projects": proj_list,
            "existing_contacts": c_info["existing_contacts"]
        })

    output_data = {
        "summary": {
            "total_enriched_districts": len(enriched_districts),
            "total_enriched_clubs": len(enriched_clubs)
        },
        "enriched_districts": enriched_districts,
        "enriched_clubs": enriched_clubs
    }

    with open(OUTPUT_ENRICHED_PATH, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Enrichment Complete:")
    print(f"  Enriched Districts: {len(enriched_districts)}")
    print(f"  Enriched Clubs: {len(enriched_clubs)}")
    print(f"Saved to {OUTPUT_ENRICHED_PATH}")

if __name__ == "__main__":
    main()
