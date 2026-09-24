# Walkthrough: Rotary Contacts Directory & Gap Enrichment

We have generated the standalone export package of Rotary contacts and leadership gaps for all 37 projects in the Rotary Club of Lake Atitlán map datastore.

---

## 📦 Deliverables Summary

| File | Type | Description |
| :--- | :--- | :--- |
| **[rotary_contacts.csv](./rotary_contacts.csv)** | Master CSV | Full roster of **518 contact entries** (direct project contacts and enriched current club/district leaders) with Name, Email, Club, Country, District, Role, Project Title, Archive URL, and Contact Type. |
| **[rotary_clubs_districts_gaps.csv](./rotary_clubs_districts_gaps.csv)** | Gap CSV | Dedicated report of **118 participating clubs and districts** where no direct contact existed, enriched with Country, current 2025–2026 Club Presidents, District Governors, official emails, and websites. |
| **[rotary_contacts_catalog.json](./rotary_contacts_catalog.json)** | Master JSON | Structured catalog containing project-level rosters, deduplicated individual Rotarians with Country, and gap records. |
| **[contacts_directory.html](./contacts_directory.html)** | Interactive Viewer | Standalone, responsive HTML viewer with instant search, tabbed filtering, Country filter, "Has Email Only" filter, clickable column sorting, KPI statistics cards, one-click "Copy Filtered Emails", and CSV export. |

---

## 📊 Harvest & Gap Statistics

```
======================================================
  Total Master Contact Roster Entries : 518
  Direct Project Contacts Harvested   : 352
  Enriched Gap Leadership Entries     : 166
  Contacts with Verified Email        : 238
  Countries Represented               : 7 (Guatemala, USA, Canada, Brazil, Honduras, Belize, Germany)
  Unique Rotary Clubs Involved        : 96
  Unique Rotary Districts Involved    : 22
======================================================
```

### Harvest Highlights
- **Direct Project Contacts (352)**:
  - Extracted from Global Grant Application PDFs, Final Reports, Progress Reports, Supabase metadata, and Markdown `narrative` Key Personnel sections.
  - Automatically resolved all recurring RCLA project champions and shepherds (`Michael Rosen`, `Terrence (Joe) Wakely`, `Duncan Aitken`, `Armand Boissy`, `Bruce Clemens`, `Candis Krummel`, `Michelle Fajkus`, `Clinton White`, `Shad Qudsi`, `William Boegel`, `Emilio Crespo Morales`, `Dwight Mara-Poage`).
  - Extracted direct personal emails from volunteer traveler tables, project report sign-offs, and narrative records (e.g. Todd Thompson, Patrick Coyle, Glenn Kubiak, Jeff Youngsma, Catherine Patel, Brad Fischer, Don Baldus, Dr. Paul Wise, Tom Tocco).
- **Gap Entities (118)**:
  - **22 Rotary Districts**: 100% enriched with the 2025–2026 District Governor name, term, district website, country, and verified email or district office contact (e.g. District 4250 Diana Brown, District 5960 Glenn Bowers, District 7620 Mandy Granger, District 6330 Jeffrey Ferweda, District 5440 Karen Morgan, District 6440 Marlene Frisbie, etc.).
  - **96 Rotary Clubs**: Enriched with Country, Current Club Presidents (or DG contact c/o fallback), club website, and verified club contact emails (e.g. Northfield RC Diane Melbye `info@northfieldrotary.org`, Annapolis RC `info@annapolisrotary.org`, Ferndale RC `info@ferndalerotary.org`, Fort Collins RC `rotary@rotarycluboffortcollins.org`, etc.).

---

## 💻 How to Access the Interactive Directory Viewer

You can access the directory in any of the following ways:

1. **Directly via GitHub Pages**:
   Navigate to **[https://mrosen.github.io/rcla_project_map/contacts_directory.html](https://mrosen.github.io/rcla_project_map/contacts_directory.html)**.
2. **Via Local Server**:
   Navigate to **[http://localhost:8000/contacts_directory.html](http://localhost:8000/contacts_directory.html)** while your local server is active.
3. **Local Filesystem**:
   Open **[contacts_directory.html](./contacts_directory.html)** directly in any browser.

*(Note: Per your request, the public top navigation button on the main project map has been removed to keep the directory accessed directly via URL).*

### Key Interactive Features:
- **Instant Search**: Type any name, email, club name, country, district number, role keyword, or project title into the search box for real-time filtering.
- **Country Filter**: Dropdown menu dynamically populated with all 7 represented countries (Guatemala, United States, Canada, Brazil, Honduras, Belize, Germany) and record counts.
- **Has Email Only Toggle**: Instant checkbox filter to show only contacts with valid email addresses.
- **Interactive Column Sorting**: Click any table header (**Name**, **Email**, **Club**, **Country**, **Dist.**, **Role**, **Project Title**, **Type**) to sort ascending (`▲`) or descending (`▼`).
- **Filter Tabs**:
  - `All Contacts` (All 518 records)
  - `Direct Project Contacts` (The 352 project participants)
  - `Enriched Officers (Gaps)` (The 166 gap leadership records)
- **📋 Copy Filtered Emails**:
  - One-click button copies all unique email addresses matching your current search/filter as a clean, comma-separated list ready to paste directly into your email client's `To:` or `Bcc:` field.
- **⬇️ Export CSV**:
  - Downloads the filtered table directly to a spreadsheet with all active columns including Country.
- **Direct Archive Links**:
  - Every project has a direct link pointing to its canonical online record (`https://mrosen.github.io/rcla_project_map/?source=supabase&project={id}`).

---

## 🔁 Automated Pipeline Scripts

All four pipeline components are committed in the `scripts/` directory for ongoing maintainability:

1. `python3 scripts/harvest_rotary_contacts.py` — Extracts contacts from Supabase and project PDFs.
2. `python3 scripts/analyze_rotary_gaps.py` — Identifies clubs and districts lacking contacts or emails.
3. `python3 scripts/enrich_officers.py` — Resolves and enriches gap entities with current officers.
4. `python3 scripts/generate_contacts_deliverables.py` — Builds the final CSVs, JSON, and HTML viewer.
