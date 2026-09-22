# Walkthrough: Sync Badges, Live SPC State Reflection, Bi-Directional Linking & Photo Deduplication

We have addressed the three requested issues plus the bi-directional linking requirement:

---

## 1. Summary of Changes

### A. Accurate Grant Center Badge Text ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))
* Updated `loadProjectSyncStatus(projectId)` to evaluate the grant prefix (`GG`, `DG`, or `Grant`) and status report count:
  - If Global Grant with 1 report: **`📄 GG Appl PDF on file (+1 status report PDF)`**
  - If multiple reports: **`📄 GG Appl PDF on file (+N status report PDFs)`**
  - If District Grant: **`📄 DG Appl PDF on file (+1 status report PDF)`**
  - If no application PDF: **`📄 No GG Appl PDF`**
* Updated the fetch call to use `BACKEND_URL + '/api/projects/' + ...` to ensure it reliably connects across all local ports and hosts.

### B. Live SPC State Reflection & Interactive Badge ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js) & [`orchestrator.py`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/orchestrator.py))
* **Interactive Sync Chip**: When a project is migrated, the edit modal badge renders as an active, clickable link:
  `<a href="https://spc.rotary.org/project/detail/..." target="_blank" class="sync-chip chip-green">✓ Synced to SPC ↗</a>`.
* **Instant In-Memory Update**: `loadProjectSyncStatus` updates `allProjects[i].sync_status` and `allProjects[i].project_links` in memory so closing the edit modal or navigating to the project detail view immediately displays the **`🌐 View on SPC`** button without requiring a page reload.
* **Auto-Refresh on Task Completion**: In `fetchLogHistory`, when log streaming detects `"finished successfully"` or `"Synced SPC export state"`, it automatically re-invokes `loadProjectSyncStatus` for the active project.

### C. Bi-Directional Linking between SPC and Archive
1. **Link in SPC Export $\rightarrow$ Archive Record**:
   - In [`scripts/migrate_to_spc.py`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/scripts/migrate_to_spc.py), `build_spc_payload` adds a permanent deep link in `projectRelLinks` pointing back to:
     `https://mrosen.github.io/rcla_project_map/?source=supabase&project={gid}`
     with caption **`"RCLA Project Map Archive Record"`**.
2. **Link in Archive Record $\rightarrow$ SPC Export**:
   - Added `sync_spc_state_to_supabase()` to both `orchestrator.py` and `scripts/migrate_to_spc.py`.
   - When an export succeeds, it automatically updates `projects.sync_status` AND upserts a record into the `project_links` table with `label: "Rotary Service Project Center (SPC)"` and `url: "https://spc.rotary.org/project/detail/{spc_id}"`.
   - All 7 previously migrated projects (`GG2574529`, `Covid2020`, `BarAlto`, `GG1529575`, `GG2578692`, `CLUB_2026_BasketballCourtPanab`, `CLUB_2026_SchoolPlaygroundJust`) have had this link retroactively populated in Supabase Cloud!

### D. File & Photo Deduplication
* **Backend (`orchestrator.py`)**:
  - In `run_fetch_ri_files`, replaced blind `POST` with a check-then-patch mechanism: queries `GET /rest/v1/project_assets?project_id=eq.{pid}&filename=eq.{f.name}&select=id` first. If the file already exists in `project_assets`, it updates the row; otherwise it inserts. This eliminates duplicate rows caused by multiple RI re-checks.
* **Clipboard Paste (`main.js`)**:
  - In `uploadImageBlobInEdit` (Ctrl+V), now executes a delete-matching-before-insert on `project_assets` and filters `p.project_assets` to prevent duplicate paste entries.
* **Batch Uploads (`main.js`)**:
  - In `handleFileInputUpload`, deduplicates files by lowercase name before processing.
* **UI Render Defense (`main.js`)**:
  - Both `renderFilesAndLinksFromProject` and `loadEditFiles` now deduplicate assets by filename before rendering, guaranteeing that duplicate thumbnails or file cards never appear in the UI.

---

## 2. Verification Results

### A. Sync Status Endpoint Verification
Querying `GET http://localhost:8000/api/projects/GG2574529/sync-status` returns:
```json
{
  "project_id": "GG2574529",
  "grant_center": {
    "has_application_pdf": true,
    "application_pdf_name": "GG2574529_Application.pdf",
    "report_count": 1,
    "report_names": ["GG2574529_Report_01.pdf"],
    "total_assets": 1,
    "local_folder_exists": true,
    "local_files_count": 4
  },
  "spc": {
    "exported": true,
    "spc_project_id": "3bc03b3f-a2f3-4743-a373-27f9150dc40c",
    "spc_url": "https://spc.rotary.org/project/detail/3bc03b3f-a2f3-4743-a373-27f9150dc40c",
    "last_exported": "2026-09-22T11:20:50.458395",
    "in_sync": true
  }
}
```
* **Badge Text Output**: `📄 GG Appl PDF on file (+1 status report PDF)`
* **SPC Status Output**: `✓ Synced to SPC ↗` (links directly to `https://spc.rotary.org/project/detail/3bc03b3f-a2f3-4743-a373-27f9150dc40c`)

### B. Supabase Cloud Verification
Verified all 7 migrated projects in Supabase Cloud:
```
Total migrated in Supabase: 7
  CLUB_2026_BasketballCourtPanab: ['https://spc.rotary.org/project/detail/e18c9b82-aa0f-4003-90f1-f399fa241eaf']
  GG2578692: ['https://spc.rotary.org/project/detail/0c101fff-43ee-41ea-97bc-22fd018d4cff']
  CLUB_2026_SchoolPlaygroundJust: ['https://spc.rotary.org/project/detail/2148468e-8b5f-4e58-9a4b-40129da0653c']
  Covid2020: ['https://spc.rotary.org/project/detail/0409e29e-a9e1-488e-9d6f-aa8633164a19']
  GG2574529: ['https://spc.rotary.org/project/detail/3bc03b3f-a2f3-4743-a373-27f9150dc40c']
  BarAlto: ['https://spc.rotary.org/project/detail/7df85ac4-5afa-40ba-bacf-a337bdc56073']
  GG1529575: ['https://spc.rotary.org/project/detail/ba58cdaf-e167-47da-8b79-68b322ce8df0']
```

### C. Syntax Validation
* `python3 -m py_compile orchestrator.py scripts/migrate_to_spc.py migrate_to_spc.py`: **0 errors**
* `node -c main.js`: **0 errors**
