# Implementation Plan: Rotary Contacts Directory & Leadership Gap Enrichment

The Rotary Club of Lake Atitlán (RCLA) seeks to build a comprehensive directory of Rotarians connected to its 37 historical and active projects to conduct outreach for follow-on service opportunities. In addition, clubs and districts that contributed to or partnered on projects without a direct individual contact on file must be identified, and enriched with the names and contact details of their current Club Presidents and District Governors.

---

## User Review Required

> [!IMPORTANT]
> **Email Privacy vs. Club Contact Channels**:
> Many Rotary clubs and districts host their sites on ClubRunner or DaCdb, where personal emails of Club Presidents are protected behind member logins or contact forms to prevent web scrapers, but official club emails (`info@<club>.org`, `president@<club>.org`, `contact@...`) and District Office / DG emails (`distrito4250@gmail.com`, `kathy.hughitt@rotary5960.org`, `grbowers53@gmail.com`) are public.
> The enrichment pipeline will capture the President's personal email when publicly published; where protected, it will capture the President's full name alongside the club's verified contact email, noting the distinction in the roster.

> [!NOTE]
> **Canonical Datastore Compliance**:
> All project titles, IDs, and archive links will resolve directly against Supabase (`https://mrosen.github.io/rcla_project_map/?source=supabase&project={id}`). No legacy CSVs will be queried or modified. The extracted contacts catalog will be saved as structured deliverables (`rotary_contacts.csv`, `rotary_gaps.csv`, `rotary_contacts_catalog.json`) and can optionally be synchronized to a dedicated `project_contacts` table in Supabase.

---

## Open Questions

1. **Supabase Persistence**:
   - Would you like the extracted and enriched contact roster to be saved into a new Supabase table (e.g. `project_contacts`), or is the standalone export package (CSV, JSON, and interactive HTML viewer) sufficient for your club's outreach needs?
2. **Current Leadership Rotary Year**:
   - Rotary leadership terms run from July 1 through June 30. We are currently in the 2025–2026 Rotary year, transitioning toward 2026–2027. Should the enrichment default to the current active 2025–2026 officers (with incoming 2026–2027 President-Elect / DGE where noted)?
3. **Interactive Maintainer View**:
   - Would you like an interactive directory viewer (`contacts_directory.html`) generated alongside the CSV, allowing you to search by club/district, filter by role, and click "Copy All Emails" for mailing lists?

---

## Proposed Changes

### Component 1: Multi-Source Rotary Contact Harvester
A unified Python harvester that scans both Supabase datastore records and local PDF project dossiers to compile every individual Rotarian associated with each project.

#### [NEW] [scripts/harvest_rotary_contacts.py](./scripts/harvest_rotary_contacts.py)
- **Supabase Extraction**:
  - Pulls all 37 projects from Supabase REST API (`id`, `title`, `project_type`, `shepherd`, `international_club_name`, `international_club_district`, `details`, `narrative`).
  - Parses Markdown `narrative` sections ("Key Personnel", "Contacts", "Project Committee") using regex table and bullet-point parsers.
  - Captures `shepherd` (RCLA project champion) and project-level international sponsors.
- **Dossier PDF Deep Extraction**:
  - Leverages PyMuPDF (`fitz`) to parse all `projects/{pid}/*.pdf` documents (Global Grant Applications, Final Reports, Progress Reports).
  - Extracts structured tables:
    - **Primary Contacts** (Host Primary Contact, International Primary Contact).
    - **Committee Members** (Host Committee, International Committee secondary contacts).
    - **Authorizations** (District Rotary Foundation Chair / DRFC, District Governor / DDF authorizations, Club President authorizations).
    - **Volunteer Travelers & Rotarian Participants** (frequently contains direct personal emails and phone numbers).
    - **Report Cover Sheets & Signatures** (contains project managers and submitter emails).
- **Association & Canonical Deep-Links**:
  - Associates every individual contact with:
    - `Name`
    - `Email` (or flagged as missing for enrichment)
    - `Club`
    - `District`
    - `Role` (e.g., Primary International Contact, Host Committee Member, DRFC Chair, Project Shepherd)
    - `Project ID` & `Project Title`
    - `Archive Link`: `https://mrosen.github.io/rcla_project_map/?source=supabase&project={id}`

---

### Component 2: Gap Analyzer & Entity Normalizer
Identifies participating Rotary entities (clubs and districts) that do not have an identified individual contact or email address.

#### [NEW] [scripts/analyze_rotary_gaps.py](./scripts/analyze_rotary_gaps.py)
- **Entity Resolution**:
  - Cross-references club names against `spc_resolved_clubs.json` (contains official Rotary Club IDs, standardized names, districts, states, and countries).
  - Cleans and normalizes club name variations (e.g., stripping trailing parentheses like `"DC)"` or prefix labels like `"RC of"`).
- **Gap Detection**:
  - Aggregates all clubs and districts appearing in:
    - `details.partner_clubs`
    - `details.partner_districts`
    - `details.club_contributions_list` (cash donors)
    - `details.district_contributions` (DDF donors)
    - PDF financing tables
  - Compares the participating entity list against the harvester roster:
    - **Club Gap**: A club that contributed funds or partnered on a project, but has no named Rotarian contact or no email.
    - **District Gap**: A district that provided DDF funding, but has no named district leader (DRFC or DG) or no email.
- **Output**: Produces a clean list of gap entities ready for enrichment.

---

### Component 3: Leadership Enrichment Pipeline (Presidents & District Governors)
Automates the discovery and resolution of current Club Presidents and District Governors for identified gap entities.

#### [NEW] [scripts/enrich_officers.py](./scripts/enrich_officers.py)
- **District Governor Lookup**:
  - Queries known Rotary District domains (e.g. `rotary4250.org`, `rotary5960.org`, `rotary6330.org`, `rotary7620.org`, `rotary5440.org`) and public leadership directories.
  - Extracts the current District Governor (2025–2026), DG email, and district office contact.
- **Club President Lookup**:
  - For clubs in `spc_resolved_clubs.json`, queries the club's ClubRunner/web portal (e.g., `https://[club-url]/clubexecutives`) or search queries.
  - Extracts the current Club President's name and contact email (or primary club email).
- **Persistent Enriched Cache (`rotary_officers_cache.json`)**:
  - Stores discovered leadership contacts locally to enable idempotency, manual review, and rapid re-runs without redundant network calls.

---

### Component 4: Export Deliverables & Directory Viewer
Generates the final human-readable and machine-readable deliverables.

#### [NEW] [rotary_contacts.csv](./rotary_contacts.csv)
- Columns:
  1. `Name`
  2. `Email`
  3. `Club`
  4. `District`
  5. `Role`
  6. `Project Title`
  7. `Archive Record Link`
  8. `Contact Type` (`Direct Project Contact` vs `Enriched Current Officer`)

#### [NEW] [rotary_clubs_districts_gaps.csv](./rotary_clubs_districts_gaps.csv)
- Columns:
  1. `Entity Name` (Club or District)
  2. `Entity Type` (`Club` / `District`)
  3. `District Number`
  4. `Projects Supported` (List of Project IDs & Titles)
  5. `Current Leader Name` (President or District Governor)
  6. `Current Leader Email`
  7. `Leadership Year / Term`
  8. `Website / Source URL`

#### [NEW] [rotary_contacts_catalog.json](./rotary_contacts_catalog.json)
- Full structured JSON dataset containing contacts grouped both by project and deduplicated by individual Rotarian.

#### [NEW] [contacts_directory.html](./contacts_directory.html)
- A self-contained, responsive HTML directory viewer:
  - Live search across Rotarian name, club, district, role, and project.
  - Filter toggle: All Contacts / Direct Project Contacts Only / Enriched Officers (Gaps).
  - Quick-action buttons: "Copy Filtered Emails" (for email blasts) and "Export CSV".
  - Clickable links to project archive records on GitHub Pages.

---

## Verification Plan

### Automated Execution & Validation
1. **Harvester Sanity Check**:
   - Run `python3 scripts/harvest_rotary_contacts.py`.
   - Verify that all 37 projects are processed without uncaught exceptions.
   - Assert that known key contacts (e.g. Todd Thompson for GG2091778/GG1867690, Armand Boissy for GG2013637, Patricia Cavan for GG2459764/GG2684872, Jon Gresley for GG2570080) are successfully harvested with correct roles and archive links.
2. **Gap Detection Validation**:
   - Run `python3 scripts/analyze_rotary_gaps.py`.
   - Verify that all contributing clubs and DDF districts are accounted for, and gap clubs (e.g., cash-only donors without named committee members) are accurately flagged.
3. **Enrichment Verification**:
   - Run `python3 scripts/enrich_officers.py`.
   - Verify that District Governors (e.g., District 4250 Diana Brown / Tony Medina, District 5960 Ed Boeve / Glenn Bowers) and Club Presidents (e.g., Northfield RC Diane Melbye) are populated.
4. **Deliverable Integrity Check**:
   - Validate that `rotary_contacts.csv` and `rotary_clubs_districts_gaps.csv` have valid headers and no malformed rows.
   - Open and verify `contacts_directory.html` in the browser to ensure search, filtering, and copy-to-clipboard actions work smoothly.
