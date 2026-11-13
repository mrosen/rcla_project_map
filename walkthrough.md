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
  Total Master Contact Roster Entries : 516
  Direct Project Contacts Harvested   : 346
  Enriched Gap Leadership Entries     : 170
  Contacts with Verified Email        : 253 (104 in Water & Sanitation — 72%)
  Countries Represented               : 7 (Guatemala, USA, Canada, Brazil, Honduras, Belize, Germany)
  Unique Rotary Clubs Involved        : 95
  Unique Rotary Districts Involved    : 22
======================================================
```

### Harvest Highlights
- **Direct Project Contacts (346)**:
  - Extracted from Global Grant Application PDFs, Final Reports, Progress Reports (including `Monitoring and evaluation` blocks), Supabase metadata, and Markdown `narrative` Key Personnel sections.
  - Automatically resolved all recurring RCLA project champions and shepherds (`Michael Rosen`, `Terrence (Joe) Wakely`, `Duncan Aitken`, `Armand Boissy`, `Bruce Clemens`, `Candis Krummel`, `Michelle Fajkus`, `Clinton White`, `Shad Qudsi`, `William Boegel`, `Emilio Crespo Morales`, `Dwight Mara-Poage`).
  - Extracted direct personal emails from volunteer traveler tables, `Monitoring and evaluation` report tables, `matchinggrants.org` historical project pages, district directories, and narrative records (e.g. Todd Thompson, Patrick Coyle, Glenn Kubiak, Jeff Youngsma, Catherine Patel, Brad Fischer, Don Baldus, Dr. Paul Wise, Tom Tocco, Erick Tok, Juanita Hernandez, Carlos Simon, Mark Mains, Lydia Hohman, Sue Weber, Geetha Jayaram, John Trone, August Muller, Dewitt DeLawter, Jim Zenner, Karen Gosling, Cecelia Babkirk, Jennifer Strong, Jim O'Grady, Kyle Haugen, Gary Campbell, Charles Cogan, Dr. Peter Rohloff, Jennifer Brewer).
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
- **Instant Search**: Type any name, email, club name, country, category, district number, role keyword, or project title into the search box for real-time filtering.
- **Category Filter (Live Synced with Supabase)**: Dropdown menu populated with project categories from Supabase (`Water & Sanitation`, `Health`, `Economic Development`, `Education`, `Environment`, `Community Service`, `Emergency Relief`) with live record counts. Automatically refreshes from Supabase on page load if project categories are updated. Supports direct URL deep-linking (e.g. `./contacts_directory.html?category=Water+%26+Sanitation`).
- **Country Filter**: Dropdown menu dynamically populated with all represented countries and record counts.
- **Has Email Only Toggle**: Instant checkbox filter to show only contacts with valid email addresses.
- **Dynamic KPI Cards**: The 5 top statistics cards automatically recalculate to show counts for the currently active filter.
- **Interactive Column Sorting**: Click any table header (**Name**, **Email**, **Club**, **Country**, **Dist.**, **Role**, **Date**, **Category**, **Project Title**, **Type**) to sort ascending (`▲`) or descending (`▼`).
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

---

# 🌎 Multi-Club & Per-User MyRotary Account Support

The Project Map now supports multiple Rotary Clubs on the shared Supabase database while defaulting to **Rotary Club of Lake Atitlán** (`lake-atitlan`).

## 1. Club Switcher & Shared Global Grants ([index.html](./index.html), [main.js](./main.js))
- **Header Club Switcher (`#club-selector`)**:
  - Defaults to `Rotary Club of Lake Atitlán (D4250)` when no `?club=` query parameter is present.
  - Supports switching to any registered Rotary Club (e.g., `?club=annapolis`, `?club=northfield`, `?club=fort-collins`), viewing `🌎 All Rotary Clubs` (`?club=all`), or clicking `➕ Add Rotary Club…` to register a new club.
- **Shared Global Grants**:
  - Global Grants (`GGxxxxxxx`) remain single canonical records in `projects` and automatically appear in the view of **every participating club** (whether that club is the Host Club, International Sponsor, or listed in `details.partner_clubs`), while Club Direct/Donation and District Grant projects are scoped to their owning club (`details.club_id`).
- **Dynamic Map Bounds & Club Onboarding (`#add-club-modal`)**:
  - Switching clubs automatically updates the header title, overview description, KPI totals, and pans/fits the Google Map to the selected club's projects (or default coordinates).
  - Registering a new club automatically resolves its Rotary Club ID and Service Project Center (`spc_club_key`) GUID from [spc_resolved_clubs.json](./spc_resolved_clubs.json) and persists the registry to Supabase (`public.clubs` and `project-media/system/clubs_registry.json`).

## 2. Per-User MyRotary Session Credentials & MFA ([orchestrator.py](./orchestrator.py), [scripts/download_grant_center.py](./scripts/download_grant_center.py), [scripts/migrate_to_spc.py](./scripts/migrate_to_spc.py))
- **Session-Only MyRotary Modal (`#rotary-auth-modal`)**:
  - Clicking `🔐 MyRotary Account` in the Maintainer Bar (or triggering **Grant Sync** / **SPC Export** / **Fetch RI Files**) prompts for the user's MyRotary.org email and password, or allows selecting **Use Server Default** for local `.env` credentials.
  - Credentials are stored strictly in browser tab memory (`sessionStorage`) and passed per-job to the backend without ever being written to Supabase or disk.
- **Dynamic Identity & Club Metadata in SPC Exports**:
  - [scripts/migrate_to_spc.py](./scripts/migrate_to_spc.py) dynamically extracts the logged-in user's `individualkey`, `memberId`, `userName`, and `userLoginEmail` from Rotary's Redux/Auth state and uses the active club's `spc_club_key`, country, city, state/department, and language when constructing SPC payloads.
- **Interactive Okta MFA Support**:
  - If MyRotary challenges a user's login with an Okta 2FA/MFA verification prompt, the backend emits `[MFA_REQUIRED]` and the UI automatically opens the 6-digit MFA code input inside `#rotary-auth-modal`, forwarding the code to `/api/rotary/mfa-code` so the Playwright session completes authentication seamlessly.
- **Automated Grant Center Import + Gemini AI Synthesis**:
  - Running `Grant Sync (Dry)` or `Grant Sync (Live)` executes [scripts/download_grant_center.py](./scripts/download_grant_center.py) (`--audit` or `--sync-new --club <slug>`), creates/updates stub records in Supabase `projects`, uploads Application & Report PDFs to `project-media`, and automatically invokes Gemini AI synthesis (including community geolocation coordinates) for newly imported grants.
