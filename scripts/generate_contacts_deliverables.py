#!/usr/bin/env python3
"""
scripts/generate_contacts_deliverables.py

Generates all final deliverables:
1. rotary_contacts.csv - Comprehensive contact roster (direct contacts + enriched gap leaders), including Country and Date.
2. rotary_clubs_districts_gaps.csv - Dedicated gap report of clubs & districts and their enriched leaders, including Country and Leadership Term.
3. rotary_contacts_catalog.json - Full structured JSON catalog with Country and Date.
4. contacts_directory.html - Interactive searchable HTML directory viewer with Country filter, Non-blank Email filter, Date column, Column Sorting, and Map navigation.
"""

import json
import csv
import re
from pathlib import Path
from datetime import datetime

WORKSPACE_ROOT = Path("/home/msr/rcla_project_map")
HARVESTED_PATH = WORKSPACE_ROOT / "harvested_contacts.json"
ENRICHED_PATH = WORKSPACE_ROOT / "rotary_officers_enriched.json"

CSV_CONTACTS_PATH = WORKSPACE_ROOT / "rotary_contacts.csv"
CSV_GAPS_PATH = WORKSPACE_ROOT / "rotary_clubs_districts_gaps.csv"
JSON_CATALOG_PATH = WORKSPACE_ROOT / "rotary_contacts_catalog.json"
HTML_VIEWER_PATH = WORKSPACE_ROOT / "contacts_directory.html"

def get_country(item, default=""):
    c = item.get("country")
    if c and str(c).strip():
        return str(c).strip()
    club_name = item.get("club") or item.get("entity_name") or ""
    district = str(item.get("district") or item.get("district_number") or "").strip()
    c_low = club_name.lower()
    
    if any(k in c_low for k in ["atitlan", "atitlán", "guatemala"]):
        return "Guatemala"
    if "belize" in c_low:
        return "Belize"
    if any(k in c_low for k in ["tegucigalpa", "honduras", "usula", "real de minas"]):
        return "Honduras"
    if district == "4250":
        if "belize" in c_low: return "Belize"
        if any(k in c_low for k in ["tegucigalpa", "usula", "real de minas"]): return "Honduras"
        return "Guatemala"
    if district == "4740" or any(k in c_low for k in ["caçador", "cacador", "chapecó", "chapeco", "lajes"]):
        return "Brazil"
    if "flint" in c_low:
        return "United States"
    if any(k in c_low for k in ["wiarton", "wairton", "watford", "mildmay", "walkerton", "calgary", "nelson", "stratford", "meaford", "ontario", "canada"]):
        return "Canada"
    if district in ("5360", "6330", "7080"):
        return "Canada"
    if "rostock" in c_low or "germany" in c_low:
        return "Germany"
    return "United States" if district or c_low else default

def main():
    print("=== Generating Rotary Contacts Deliverables ===")
    with open(HARVESTED_PATH, "r", encoding="utf-8") as f:
        harvested_data = json.load(f)

    with open(ENRICHED_PATH, "r", encoding="utf-8") as f:
        enriched_data = json.load(f)

    direct_contacts = harvested_data.get("all_contacts", [])
    enriched_districts = enriched_data.get("enriched_districts", [])
    enriched_clubs = enriched_data.get("enriched_clubs", [])

    # Project date lookup mapping pid -> canonical date string
    project_date_lookup = {p["project_id"]: (p.get("date") or "") for p in harvested_data.get("projects", [])}

    # 1. Build Master Contacts List
    master_contacts_rows = []

    # Add direct contacts
    for c in direct_contacts:
        country_val = get_country(c, "Guatemala")
        pid = c.get("project_id") or ""
        p_date = c.get("date") or project_date_lookup.get(pid, "")
        master_contacts_rows.append({
            "name": c.get("name") or "",
            "email": c.get("email") or "",
            "club": c.get("club") or "",
            "country": country_val,
            "district": str(c.get("district") or ""),
            "role": c.get("role") or "",
            "date": p_date,
            "project_id": pid,
            "project_title": c.get("project_title") or "",
            "archive_link": c.get("archive_link") or "",
            "contact_type": "Direct Project Contact",
            "notes": f"Source: {c.get('source', '')}"
        })

    # Add enriched club leaders
    for c in enriched_clubs:
        country_val = get_country(c, "United States")
        for p in c.get("projects", []):
            pid = p.get("id") or ""
            p_date = project_date_lookup.get(pid) or p.get("date") or c.get("leadership_term") or "2025–2026"
            master_contacts_rows.append({
                "name": c.get("current_leader_name") or "",
                "email": c.get("current_leader_email") or "",
                "club": c.get("entity_name") or "",
                "country": country_val,
                "district": str(c.get("district_number") or ""),
                "role": c.get("current_leader_role") or "Current Club President",
                "date": p_date,
                "project_id": pid,
                "project_title": p.get("title") or "",
                "archive_link": f"https://mrosen.github.io/rcla_project_map/?source=supabase&project={pid}",
                "contact_type": "Enriched Current Officer (Club Gap)",
                "notes": f"Website: {c.get('website', '')}"
            })

    # Add enriched district governors
    for d in enriched_districts:
        country_val = get_country(d, "United States")
        for p in d.get("projects", []):
            pid = p.get("id") or ""
            p_date = project_date_lookup.get(pid) or p.get("date") or d.get("leadership_term") or "2025–2026"
            master_contacts_rows.append({
                "name": d.get("current_leader_name") or "",
                "email": d.get("current_leader_email") or "",
                "club": f"District {d.get('district_number')}",
                "country": country_val,
                "district": str(d.get("district_number") or ""),
                "role": d.get("current_leader_role") or "District Governor",
                "date": p_date,
                "project_id": pid,
                "project_title": p.get("title") or "",
                "archive_link": f"https://mrosen.github.io/rcla_project_map/?source=supabase&project={pid}",
                "contact_type": "Enriched Current Officer (District Gap)",
                "notes": f"Website: {d.get('website', '')}"
            })

    # Sort master contacts: Direct contacts first, then by Country, Club, Name
    master_contacts_rows.sort(key=lambda x: (0 if x["contact_type"] == "Direct Project Contact" else 1, x["country"], x["club"], x["name"]))

    # Write rotary_contacts.csv
    contacts_headers = ["Name", "Email", "Club", "Country", "District", "Role", "Date", "Project Title", "Archive Record Link", "Contact Type"]
    with open(CSV_CONTACTS_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(contacts_headers)
        for r in master_contacts_rows:
            writer.writerow([
                r["name"],
                r["email"],
                r["club"],
                r["country"],
                r["district"],
                r["role"],
                r["date"],
                f"[{r['project_id']}] {r['project_title']}",
                r["archive_link"],
                r["contact_type"]
            ])

    print(f"Generated {CSV_CONTACTS_PATH} ({len(master_contacts_rows)} rows)")

    # 2. Build Gap Report Rows
    gap_report_rows = []
    # Districts first
    for d in enriched_districts:
        projs_str = "; ".join([f"[{p['id']}] {p['title']}" for p in d.get("projects", [])])
        country_val = get_country(d, "United States")
        gap_report_rows.append({
            "entity_name": d["entity_name"],
            "entity_type": "District",
            "country": country_val,
            "district_number": d["district_number"],
            "projects_supported": projs_str,
            "current_leader_name": d["current_leader_name"],
            "current_leader_role": d["current_leader_role"],
            "current_leader_email": d["current_leader_email"],
            "leadership_term": d["leadership_term"],
            "website": d["website"]
        })

    # Clubs
    for c in enriched_clubs:
        projs_str = "; ".join([f"[{p['id']}] {p['title']}" for p in c.get("projects", [])])
        country_val = get_country(c, "United States")
        gap_report_rows.append({
            "entity_name": c["entity_name"],
            "entity_type": "Club",
            "country": country_val,
            "district_number": c["district_number"],
            "projects_supported": projs_str,
            "current_leader_name": c["current_leader_name"],
            "current_leader_role": c["current_leader_role"],
            "current_leader_email": c["current_leader_email"],
            "leadership_term": c["leadership_term"],
            "website": c["website"]
        })

    gap_report_rows.sort(key=lambda x: (0 if x["entity_type"] == "District" else 1, x["country"], x["district_number"], x["entity_name"]))

    # Write rotary_clubs_districts_gaps.csv
    gap_headers = [
        "Entity Name", "Entity Type", "Country", "District Number", "Projects Supported",
        "Current Leader Name", "Current Leader Role", "Current Leader Email",
        "Leadership Term", "Website / Source URL"
    ]
    with open(CSV_GAPS_PATH, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(gap_headers)
        for r in gap_report_rows:
            writer.writerow([
                r["entity_name"],
                r["entity_type"],
                r["country"],
                r["district_number"],
                r["projects_supported"],
                r["current_leader_name"],
                r["current_leader_role"],
                r["current_leader_email"],
                r["leadership_term"],
                r["website"]
            ])

    print(f"Generated {CSV_GAPS_PATH} ({len(gap_report_rows)} rows)")

    # 3. Deduplicate Individuals for Master Person Catalog
    unique_persons = {}
    for r in master_contacts_rows:
        name_key = r["name"].lower().strip()
        if not name_key or name_key in ("club president", "current club president"):
            continue
        if name_key not in unique_persons:
            unique_persons[name_key] = {
                "name": r["name"],
                "email": r["email"],
                "club": r["club"],
                "country": r.get("country") or "",
                "district": r["district"],
                "roles": set([r["role"]]),
                "dates": set([r["date"]]) if r.get("date") else set(),
                "projects": set([f"[{r['project_id']}] {r['project_title']}"]),
                "contact_type": r["contact_type"]
            }
        else:
            if not unique_persons[name_key]["email"] and r["email"]:
                unique_persons[name_key]["email"] = r["email"]
            if not unique_persons[name_key]["club"] and r["club"]:
                unique_persons[name_key]["club"] = r["club"]
            if not unique_persons[name_key]["country"] and r.get("country"):
                unique_persons[name_key]["country"] = r["country"]
            if not unique_persons[name_key]["district"] and r["district"]:
                unique_persons[name_key]["district"] = r["district"]
            unique_persons[name_key]["roles"].add(r["role"])
            if r.get("date"):
                unique_persons[name_key]["dates"].add(r["date"])
            unique_persons[name_key]["projects"].add(f"[{r['project_id']}] {r['project_title']}")

    serialized_unique_persons = []
    for k, p in sorted(unique_persons.items(), key=lambda x: x[1]["name"]):
        serialized_unique_persons.append({
            "name": p["name"],
            "email": p["email"],
            "club": p["club"],
            "country": p.get("country") or "",
            "district": p["district"],
            "roles": sorted(list(p["roles"])),
            "dates": sorted(list(p["dates"])),
            "projects_count": len(p["projects"]),
            "projects": sorted(list(p["projects"])),
            "contact_type": p["contact_type"]
        })

    # Write rotary_contacts_catalog.json
    catalog_payload = {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "source": "Canonical Supabase records & Project PDF dossiers",
            "total_master_contact_rows": len(master_contacts_rows),
            "total_unique_individuals": len(serialized_unique_persons),
            "total_enriched_gap_entities": len(gap_report_rows)
        },
        "master_roster": master_contacts_rows,
        "unique_individuals": serialized_unique_persons,
        "gap_entities": gap_report_rows
    }
    with open(JSON_CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog_payload, f, indent=2)

    print(f"Generated {JSON_CATALOG_PATH}")

    # 4. Generate Interactive contacts_directory.html
    html_content = generate_html_viewer(master_contacts_rows, gap_report_rows, serialized_unique_persons)
    with open(HTML_VIEWER_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Generated {HTML_VIEWER_PATH}")
    print("\nAll deliverables generated successfully!")

def generate_html_viewer(master_contacts, gap_rows, unique_persons):
    contacts_json = json.dumps(master_contacts)

    total_contacts = len(master_contacts)
    direct_count = sum(1 for c in master_contacts if c["contact_type"] == "Direct Project Contact")
    enriched_count = total_contacts - direct_count
    with_email_count = sum(1 for c in master_contacts if c.get("email"))
    countries_count = len(set(c.get("country") for c in master_contacts if c.get("country")))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rotary Club of Lake Atitlán - Rotary Contacts Directory</title>
  <style>
    :root {{
      --primary: #005aa9;
      --primary-dark: #003e75;
      --secondary: #d99926;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --border: #e2e8f0;
      --text: #1e293b;
      --text-muted: #64748b;
      --success: #10b981;
      --badge-direct: #e0f2fe;
      --badge-direct-text: #0369a1;
      --badge-enriched: #fef3c7;
      --badge-enriched-text: #92400e;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
      padding: 24px;
    }}
    .container {{
      max-width: 1520px;
      margin: 0 auto;
    }}
    header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 16px;
      margin-bottom: 24px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--border);
    }}
    .title-area h1 {{
      font-size: 26px;
      color: var(--primary);
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .title-area p {{
      color: var(--text-muted);
      font-size: 14px;
      margin-top: 4px;
    }}
    .stats-bar {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .stat-card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    .stat-card .label {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      color: var(--text-muted);
      letter-spacing: 0.5px;
    }}
    .stat-card .val {{
      font-size: 28px;
      font-weight: 700;
      color: var(--primary-dark);
      margin-top: 4px;
    }}
    .controls {{
      display: flex;
      flex-direction: column;
      gap: 14px;
      margin-bottom: 16px;
      background: var(--card-bg);
      padding: 16px;
      border-radius: 8px;
      border: 1px solid var(--border);
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }}
    .controls-row-1 {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
    }}
    .search-box {{
      flex: 2;
      min-width: 260px;
    }}
    .search-box input {{
      width: 100%;
      padding: 10px 14px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.15s;
    }}
    .search-box input:focus {{
      border-color: var(--primary);
      box-shadow: 0 0 0 3px rgba(0, 90, 169, 0.15);
    }}
    .filter-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .filter-group label {{
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
    }}
    .filter-select {{
      padding: 9px 12px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 13px;
      background: white;
      color: var(--text);
      outline: none;
      cursor: pointer;
      min-width: 170px;
    }}
    .filter-select:focus {{
      border-color: var(--primary);
    }}
    .filter-checkbox {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text);
      cursor: pointer;
      user-select: none;
      padding: 8px 12px;
      background: #f1f5f9;
      border-radius: 6px;
      border: 1px solid var(--border);
      transition: background 0.15s;
    }}
    .filter-checkbox:hover {{
      background: #e2e8f0;
    }}
    .filter-checkbox input[type="checkbox"] {{
      cursor: pointer;
      width: 16px;
      height: 16px;
      accent-color: var(--primary);
    }}
    .controls-row-2 {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      padding-top: 10px;
      border-top: 1px solid #f1f5f9;
    }}
    .filter-tabs {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .tab-btn {{
      padding: 7px 14px;
      border: 1px solid var(--border);
      background: #f1f5f9;
      color: var(--text-muted);
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .tab-btn.active {{
      background: var(--primary);
      color: white;
      border-color: var(--primary);
    }}
    .actions-bar {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
    }}
    .results-count {{
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 500;
      margin-right: 6px;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 15px;
      border-radius: 6px;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border: none;
      transition: all 0.15s;
      text-decoration: none;
    }}
    .btn-primary {{
      background: var(--primary);
      color: white;
    }}
    .btn-primary:hover {{
      background: var(--primary-dark);
    }}
    .btn-secondary {{
      background: #f1f5f9;
      color: var(--text);
      border: 1px solid var(--border);
    }}
    .btn-secondary:hover {{
      background: #e2e8f0;
    }}
    .toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #1e293b;
      color: white;
      padding: 12px 20px;
      border-radius: 6px;
      font-size: 14px;
      display: none;
      z-index: 999;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    .table-container {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow-x: auto;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      text-align: left;
      font-size: 13px;
    }}
    th {{
      background: #f8fafc;
      padding: 12px 14px;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      position: sticky;
      top: 0;
      z-index: 10;
      white-space: nowrap;
    }}
    th.sortable {{
      cursor: pointer;
      user-select: none;
      transition: background-color 0.15s, color 0.15s;
    }}
    th.sortable:hover {{
      background: #e2e8f0;
      color: var(--primary);
    }}
    th.sorted-asc, th.sorted-desc {{
      background: #e0f2fe;
      color: var(--primary-dark);
    }}
    .sort-icon {{
      display: inline-block;
      margin-left: 4px;
      font-size: 10px;
      color: #94a3b8;
    }}
    th.sorted-asc .sort-icon, th.sorted-desc .sort-icon {{
      color: var(--primary-dark);
      font-weight: bold;
    }}
    td {{
      padding: 11px 14px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }}
    tr:hover {{
      background: #f1f5f9;
    }}
    .badge {{
      display: inline-block;
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
      white-space: nowrap;
    }}
    .badge-direct {{
      background: var(--badge-direct);
      color: var(--badge-direct-text);
    }}
    .badge-enriched {{
      background: var(--badge-enriched);
      color: var(--badge-enriched-text);
    }}
    .country-pill {{
      display: inline-block;
      padding: 2px 7px;
      background: #f1f5f9;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
      color: #334155;
      white-space: nowrap;
    }}
    .email-link {{
      color: var(--primary);
      text-decoration: none;
      font-weight: 500;
    }}
    .email-link:hover {{
      text-decoration: underline;
    }}
    .archive-link {{
      display: inline-block;
      color: var(--primary);
      text-decoration: none;
      font-size: 12px;
      margin-top: 2px;
    }}
    .archive-link:hover {{
      text-decoration: underline;
    }}
    .nowrap {{ white-space: nowrap; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div class="title-area">
        <h1>⚙️ Rotary Contacts Directory</h1>
        <p>Rotary Club of Lake Atitlán &middot; Canonical Project Partner & Leadership Directory</p>
      </div>
      <div class="actions-bar">
        <a href="./index.html" class="btn btn-secondary" title="Return to interactive project map">🗺️ Project Map</a>
        <a href="./rotary_contacts.csv" class="btn btn-secondary" download title="Download full roster CSV">📄 Master CSV</a>
        <button class="btn btn-primary" onclick="copyEmails()">📋 Copy Filtered Emails</button>
        <button class="btn btn-secondary" onclick="exportFilteredCSV()">⬇️ Export Filtered CSV</button>
      </div>
    </header>

    <div class="stats-bar">
      <div class="stat-card">
        <div class="label">Total Roster Entries</div>
        <div class="val">{total_contacts}</div>
      </div>
      <div class="stat-card">
        <div class="label">Direct Project Contacts</div>
        <div class="val">{direct_count}</div>
      </div>
      <div class="stat-card">
        <div class="label">Enriched Gap Officers</div>
        <div class="val">{enriched_count}</div>
      </div>
      <div class="stat-card">
        <div class="label">Contacts with Email</div>
        <div class="val">{with_email_count}</div>
      </div>
      <div class="stat-card">
        <div class="label">Countries Represented</div>
        <div class="val">{countries_count}</div>
      </div>
    </div>

    <div class="controls">
      <div class="controls-row-1">
        <div class="search-box">
          <input type="text" id="searchInput" placeholder="Search by name, email, club, country, district, date, role, or project..." oninput="renderTable()">
        </div>
        <div class="filter-group">
          <label for="countryFilter">Country:</label>
          <select id="countryFilter" class="filter-select" onchange="renderTable()">
            <option value="">All Countries</option>
          </select>
        </div>
        <label class="filter-checkbox" title="Show only contacts with an email address">
          <input type="checkbox" id="emailOnlyFilter" onchange="renderTable()">
          <span>Has Email Only</span>
        </label>
      </div>
      <div class="controls-row-2">
        <div class="filter-tabs">
          <button class="tab-btn active" id="tabAll" onclick="setTab('all')">All Contacts</button>
          <button class="tab-btn" id="tabDirect" onclick="setTab('direct')">Direct Project Contacts</button>
          <button class="tab-btn" id="tabEnriched" onclick="setTab('enriched')">Enriched Officers (Gaps)</button>
        </div>
        <div class="actions-bar">
          <span class="results-count" id="resultsCount">Showing 0 of 0</span>
        </div>
      </div>
    </div>

    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th class="sortable" onclick="handleSort('name')">Name <span class="sort-icon" id="sort-name">↕</span></th>
            <th class="sortable" onclick="handleSort('email')">Email <span class="sort-icon" id="sort-email">↕</span></th>
            <th class="sortable" onclick="handleSort('club')">Club <span class="sort-icon" id="sort-club">↕</span></th>
            <th class="sortable" onclick="handleSort('country')">Country <span class="sort-icon" id="sort-country">↕</span></th>
            <th class="sortable" onclick="handleSort('district')">Dist. <span class="sort-icon" id="sort-district">↕</span></th>
            <th class="sortable" onclick="handleSort('role')">Role <span class="sort-icon" id="sort-role">↕</span></th>
            <th class="sortable" onclick="handleSort('date')">Date <span class="sort-icon" id="sort-date">↕</span></th>
            <th class="sortable" onclick="handleSort('project_title')">Project Title <span class="sort-icon" id="sort-project_title">↕</span></th>
            <th class="sortable" onclick="handleSort('contact_type')">Type <span class="sort-icon" id="sort-contact_type">↕</span></th>
          </tr>
        </thead>
        <tbody id="tableBody">
          <!-- Rows rendered via JavaScript -->
        </tbody>
      </table>
    </div>
  </div>

  <div id="toast" class="toast">Emails copied to clipboard!</div>

  <script>
    const allContacts = {contacts_json};
    let currentTab = 'all';
    let currentSortCol = 'name';
    let currentSortAsc = true;

    function initCountryFilter() {{
      const counts = {{}};
      allContacts.forEach(c => {{
        const country = c.country || 'Unknown';
        counts[country] = (counts[country] || 0) + 1;
      }});
      const select = document.getElementById('countryFilter');
      select.innerHTML = `<option value="">All Countries (${{allContacts.length}})</option>`;
      Object.keys(counts).sort().forEach(country => {{
        const opt = document.createElement('option');
        opt.value = country;
        opt.innerText = `${{country}} (${{counts[country]}})`;
        select.appendChild(opt);
      }});
    }}

    function setTab(tab) {{
      currentTab = tab;
      document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
      if (tab === 'all') document.getElementById('tabAll').classList.add('active');
      if (tab === 'direct') document.getElementById('tabDirect').classList.add('active');
      if (tab === 'enriched') document.getElementById('tabEnriched').classList.add('active');
      renderTable();
    }}

    function handleSort(col) {{
      if (currentSortCol === col) {{
        currentSortAsc = !currentSortAsc;
      }} else {{
        currentSortCol = col;
        currentSortAsc = true;
      }}
      renderTable();
    }}

    function filterData() {{
      const query = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const selectedCountry = document.getElementById('countryFilter').value;
      const emailOnly = document.getElementById('emailOnlyFilter').checked;

      return allContacts.filter(c => {{
        // Tab filter
        if (currentTab === 'direct' && c.contact_type !== 'Direct Project Contact') return false;
        if (currentTab === 'enriched' && c.contact_type === 'Direct Project Contact') return false;

        // Country filter
        if (selectedCountry && c.country !== selectedCountry) return false;

        // Non-blank Email filter
        if (emailOnly && (!c.email || !c.email.trim())) return false;

        // Full-text search
        if (!query) return true;
        return (
          (c.name && c.name.toLowerCase().includes(query)) ||
          (c.email && c.email.toLowerCase().includes(query)) ||
          (c.club && c.club.toLowerCase().includes(query)) ||
          (c.country && c.country.toLowerCase().includes(query)) ||
          (c.district && c.district.toLowerCase().includes(query)) ||
          (c.role && c.role.toLowerCase().includes(query)) ||
          (c.date && c.date.toLowerCase().includes(query)) ||
          (c.project_id && c.project_id.toLowerCase().includes(query)) ||
          (c.project_title && c.project_title.toLowerCase().includes(query)) ||
          (c.contact_type && c.contact_type.toLowerCase().includes(query))
        );
      }});
    }}

    function renderTable() {{
      let filtered = filterData();

      // Sort data
      filtered.sort((a, b) => {{
        let valA = (a[currentSortCol] || '').toString().trim();
        let valB = (b[currentSortCol] || '').toString().trim();

        // Handle numeric sorting for district
        if (currentSortCol === 'district') {{
          const numA = parseInt(valA, 10);
          const numB = parseInt(valB, 10);
          if (!isNaN(numA) && !isNaN(numB)) {{
            return currentSortAsc ? numA - numB : numB - numA;
          }}
        }}

        // Blanks sort to the bottom
        if (!valA && valB) return 1;
        if (valA && !valB) return -1;
        if (!valA && !valB) return 0;

        const cmp = valA.localeCompare(valB, undefined, {{ numeric: true, sensitivity: 'base' }});
        return currentSortAsc ? cmp : -cmp;
      }});

      // Update header sort indicators
      document.querySelectorAll('.sortable').forEach(th => {{
        th.classList.remove('sorted-asc', 'sorted-desc');
      }});
      document.querySelectorAll('.sort-icon').forEach(icon => {{
        icon.innerText = '↕';
      }});
      const activeTh = document.querySelector(`th[onclick="handleSort('${{currentSortCol}}')"]`);
      const activeIcon = document.getElementById(`sort-${{currentSortCol}}`);
      if (activeTh && activeIcon) {{
        activeTh.classList.add(currentSortAsc ? 'sorted-asc' : 'sorted-desc');
        activeIcon.innerText = currentSortAsc ? '▲' : '▼';
      }}

      // Update result count
      document.getElementById('resultsCount').innerText = `Showing ${{filtered.length}} of ${{allContacts.length}}`;

      const tbody = document.getElementById('tableBody');
      let html = '';
      filtered.forEach(c => {{
        const isDirect = c.contact_type === 'Direct Project Contact';
        const badgeClass = isDirect ? 'badge-direct' : 'badge-enriched';
        const badgeLabel = isDirect ? 'Project' : 'Enriched Officer';

        const emailCell = c.email 
          ? `<a href="mailto:${{c.email}}" class="email-link">${{c.email}}</a>`
          : `<span style="color: #94a3b8; font-style: italic;">Missing Email</span>`;

        const archiveLink = c.archive_link
          ? `<br><a href="${{c.archive_link}}" target="_blank" class="archive-link">View Archive ↗</a>`
          : '';

        const countryBadge = c.country
          ? `<span class="country-pill">${{c.country}}</span>`
          : '—';

        html += `
          <tr>
            <td class="nowrap"><strong>${{c.name || '—'}}</strong></td>
            <td>${{emailCell}}</td>
            <td>${{c.club || '—'}}</td>
            <td>${{countryBadge}}</td>
            <td>${{c.district || '—'}}</td>
            <td>${{c.role || '—'}}</td>
            <td class="nowrap">${{c.date || '—'}}</td>
            <td>
              <div><strong>[${{c.project_id}}]</strong> ${{c.project_title}}</div>
              ${{archiveLink}}
            </td>
            <td><span class="badge ${{badgeClass}}">${{badgeLabel}}</span></td>
          </tr>
        `;
      }});

      if (filtered.length === 0) {{
        html = `<tr><td colspan="9" style="text-align: center; padding: 36px; color: var(--text-muted);">No contacts match your filter criteria.</td></tr>`;
      }}

      tbody.innerHTML = html;
    }}

    function copyEmails() {{
      const filtered = filterData();
      const emails = [...new Set(filtered.map(c => c.email).filter(e => e && e.includes('@')))];
      if (emails.length === 0) {{
        showToast('No valid emails to copy with current filters!');
        return;
      }}
      const text = emails.join(', ');
      navigator.clipboard.writeText(text).then(() => {{
        showToast(`Copied ${{emails.length}} unique emails to clipboard!`);
      }}).catch(() => {{
        prompt("Copy emails manually:", text);
      }});
    }}

    function exportFilteredCSV() {{
      const filtered = filterData();
      let csv = 'Name,Email,Club,Country,District,Role,Date,Project Title,Archive Link,Contact Type\\n';
      filtered.forEach(c => {{
        const row = [
          `"${{(c.name || '').replace(/"/g, '""')}}"`,
          `"${{(c.email || '').replace(/"/g, '""')}}"`,
          `"${{(c.club || '').replace(/"/g, '""')}}"`,
          `"${{(c.country || '').replace(/"/g, '""')}}"`,
          `"${{(c.district || '').replace(/"/g, '""')}}"`,
          `"${{(c.role || '').replace(/"/g, '""')}}"`,
          `"${{(c.date || '').replace(/"/g, '""')}}"`,
          `"[${{c.project_id}}] ${{c.project_title}}".replace(/"/g, '""')`,
          `"${{(c.archive_link || '').replace(/"/g, '""')}}"`,
          `"${{(c.contact_type || '').replace(/"/g, '""')}}"`
        ];
        csv += row.join(',') + '\\n';
      }});

      const blob = new Blob([csv], {{ type: 'text/csv;charset=utf-8;' }});
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `rotary_contacts_export_${{currentTab}}.csv`;
      link.click();
    }}

    function showToast(msg) {{
      const toast = document.getElementById('toast');
      toast.innerText = msg;
      toast.style.display = 'block';
      setTimeout(() => {{ toast.style.display = 'none'; }}, 3000);
    }}

    // Initialize country dropdown and render table
    initCountryFilter();
    renderTable();
  </script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
