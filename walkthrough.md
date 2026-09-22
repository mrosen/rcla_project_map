# Walkthrough: Sync Badges, Live SPC State Reflection, Bi-Directional Linking, Photo Deduplication & SPC Route Fix

We have addressed the SPC URL failure along with all previous requirements:

---

## 1. SPC URL Routing Fix (Why the Link Failed & How It Was Resolved)

### Root Cause
- Previously, the code generated SPC URLs in the format:
  `https://spc.rotary.org/project/detail/{spc_id}`
- However, Rotary's Service Project Center is a React Single Page Application (SPA). Inspection of Rotary's frontend bundle reveals its route structure:
  ```javascript
  { path: "project", component: cBe, pageName: "Project detail Page" }
  ```
  and the project GUID is parsed from the query string:
  ```javascript
  new URLSearchParams(location.search).get("guid")
  ```
- Because Rotary's router only listens on `/project` with query parameter `?guid=...`, navigating to `/project/detail/{id}` missed the route and resulted in a failed / 404 / blank page.

### The Fix
1. **Frontend Normalization (`main.js`)**:
   - Added `normalizeSpcUrl(url, guid)` helper function which replaces `/project/detail/` with `/project?guid=` and constructs clean URLs: `https://spc.rotary.org/project?guid={guid}`.
   - Applied `normalizeSpcUrl` to the project detail SPC button, edit form sync badge, web links renderer (`renderFilesAndLinksFromProject`), and edit form links loader (`loadEditForm`).
2. **Backend Normalization (`orchestrator.py`)**:
   - Updated `sync_spc_state_to_supabase` and `get_project_sync_status` to always produce and return `https://spc.rotary.org/project?guid={guid}`.
3. **Migration Scripts (`scripts/migrate_to_spc.py` & `migrate_to_spc.py`)**:
   - Updated export payload and state writer to use `/project?guid={guid}`.
4. **Local State & Supabase Cloud Backfill**:
   - Updated all 7 entries in `spc_migration_state.json`.
   - Executed a database migration script across Supabase Cloud to update both `project_links` and `projects.sync_status` for all 7 migrated projects.

---

## 2. Clarified Application PDF Badge & AI Button Labels ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))

- **Document Tag**: Changed ambiguous `RI App` tag on the file card to **`📋 GG Application`** (or `📋 DG Application` / `📋 Grant Application` dynamically based on project type).
- **AI Action Button**: Changed ambiguous `✨ Draft` tag to an explicit action button: **`✨ AI Auto-fill`** (with tooltip: *"Use Gemini AI to extract project details and auto-fill form fields from this PDF"*).
- **Toolbar Buttons**: Updated top assistant toolbar buttons to **`📄 Auto-fill from App PDF`** and **`📝 Auto-fill from Notes / Paste`** to maintain consistent terminology.

---

## 3. GitHub Pages Static Hosting & Document Badges Fix ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))

1. **Top Sync Badges on Static Hosting (GitHub Pages)**:
   - When hosted on GitHub Pages (`https://mrosen.github.io/rcla_project_map/`), there is no live Python backend on port 8000.
   - Previously, the failed `fetch('/api/projects/.../sync-status')` caused `loadProjectSyncStatus` to wipe out the badges and display `"Sync status offline"`.
   - Now, `loadProjectSyncStatus` immediately and optimistically renders the badges directly from Supabase / in-memory project data (`p.sync_status`, `p.project_assets`, `p.project_links`), preserving the active **`📄 GG Appl PDF on file (+2 status report PDFs)`** and **`✓ Synced to SPC ↗`** badges even when running statically on GitHub Pages.
2. **File Cards in "Manage Staged Photos & Files"**:
   - Fixed cover photo logic: `isCover` is now strictly restricted to images (`isImg && a.display_order === 0`), preventing document PDFs from incorrectly showing as "★ Cover Photo" when their database `display_order` is 0.
   - Added badges for Status Reports: files matching `report.*\.pdf` receive dynamic tags (e.g., **`📊 Status Report #1`**, **`📊 Status Report #2`**) with dedicated `📊` icons.
   - Non-grant attachments receive a **`📄 Attachment`** badge.

---

## 4. Verification

### A. Rotary SPC API Verification
Direct query to Rotary SPC API (`GET /api/Project/ProjectDetail/en/3bc03b3f-a2f3-4743-a373-27f9150dc40c`):
- **Project**: "Reforesting Santiago"
- **Status**: Actual / Active
- **Medias / RelLinks**: Contains `"https://mrosen.github.io/rcla_project_map/?source=supabase&project=GG2574529"` with title `"RCLA Project Map Archive Entry"`.
- **Target URL**: [https://spc.rotary.org/project?guid=3bc03b3f-a2f3-4743-a373-27f9150dc40c](https://spc.rotary.org/project?guid=3bc03b3f-a2f3-4743-a373-27f9150dc40c) (HTTP 200 OK, loads project detail page in browser).

### B. Sync Status Endpoint Verification
`GET http://127.0.0.1:8000/api/projects/GG2574529/sync-status`:
```json
{
  "project_id": "GG2574529",
  "grant_center": {
    "has_application_pdf": true,
    "application_pdf_name": "GG2574529_Application.pdf",
    "report_count": 1,
    "report_names": ["GG2574529_Report_01.pdf"],
    "total_assets": 4,
    "local_folder_exists": true,
    "local_files_count": 4
  },
  "spc": {
    "exported": true,
    "spc_project_id": "3bc03b3f-a2f3-4743-a373-27f9150dc40c",
    "spc_url": "https://spc.rotary.org/project?guid=3bc03b3f-a2f3-4743-a373-27f9150dc40c",
    "last_exported": "2026-09-22T11:20:50.458395",
    "in_sync": true
  }
}
```

### C. Supabase Cloud Database Verification
All 7 projects in `project_links` and `projects.sync_status` have been updated with `https://spc.rotary.org/project?guid={guid}`.
