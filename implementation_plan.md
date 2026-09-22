# Implementation Plan: Fix Sync Badges, Live SPC State Sync, Bi-Directional Linking, and Photo Deduplication

This plan addresses:
1. **Accurate PDF Badge Text**: Update the Grant Center badge to read `"GG Appl PDF on file (+1 status report PDF)"` (or `DG Appl PDF...` / `Grant Appl PDF...`), with correct singular/plural status report formatting.
2. **Live SPC Sync State Reflection**: Ensure that when a project is migrated to Rotary Service Project Center (SPC), the migration state is automatically persisted into Supabase `projects.sync_status`, and the UI (both Edit modal and Project Detail view) immediately updates to `"✓ Synced to SPC"` with an active `"🌐 View on SPC ↗"` link.
3. **Bi-Directional Linking**:
   - **SPC Export $\rightarrow$ Archive**: Include permanent deep link back to the Archive record (`https://mrosen.github.io/rcla_project_map/?source=supabase&project={id}`) in SPC's `projectRelLinks`.
   - **Archive Record $\rightarrow$ SPC Export**: Record the SPC link (`https://spc.rotary.org/project/detail/{spc_id}`) in both `projects.sync_status` and the `project_links` table, displaying it in the project header badge and web links section.
4. **Prevent File & Photo Duplication**: Eliminate the mechanisms by which duplicate files and photos accrue in Supabase storage and `project_assets`.

---

## User Review Required

> [!NOTE]
> **Existing Migrated Projects**:
> All 7 currently migrated projects in `spc_migration_state.json` (including `GG2574529`, `Covid2020`, `BarAlto`, etc.) will have their `sync_status` and `project_links` updated in Supabase Cloud.

---

## Proposed Changes

### 1. Frontend (`main.js`)

#### [MODIFY] [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js)
1. **Fix Grant Center Badge Text**:
   - In `loadProjectSyncStatus(projectId)`:
     - Determine prefix dynamically: `GG` for Global Grants, `DG` for District Grants, `Grant` for others.
     - Report formatting: if `report_count > 0`, append ` (+N status report PDF)` or ` (+N status report PDFs)`.
     - Resulting text matches exact specification: `"📄 GG Appl PDF on file (+1 status report PDF)"`.
     - If no application PDF: `"📄 No GG Appl PDF"`.
2. **Fix Backend URL in `loadProjectSyncStatus`**:
   - Change `fetch('/api/projects/' + ...)` to `fetch(BACKEND_URL + '/api/projects/' + ...)`.
3. **Enhance SPC Sync Badge & Live Update**:
   - If `spc.exported` is true, render an interactive chip with the link:
     `<a href="..." target="_blank" class="sync-chip chip-green">✓ Synced to SPC ↗</a>`
   - In `startLogPolling` and `triggerProjectSpcExport`:
     - When polling detects `"✓ SPC export task finished successfully."` or completes, immediately re-invoke `loadProjectSyncStatus(currentProjectId)` and update `p.sync_status` in `allProjects`.
     - Re-render the detail view if active so the `"🌐 View on SPC"` button appears right away.
4. **Bi-Directional Link in Archive Record**:
   - When SPC export completes, automatically add `Rotary Service Project Center (SPC)` to the project's `project_links` in memory and UI.
5. **Prevent Client-Side File/Photo Duplication**:
   - In `renderFilesAndLinksFromProject` and `loadEditFiles`:
     - Deduplicate `assets` by `filename` before rendering to protect against any redundant DB rows.
   - In `uploadImageBlobInEdit` (Ctrl+V paste):
     - Check if an identical file or filename exists before inserting.
   - In `handleFileInputUpload`:
     - Deduplicate the file list by name before uploading.

---

### 2. Backend Orchestration (`orchestrator.py` & `scripts/migrate_to_spc.py`)

#### [MODIFY] [orchestrator.py](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/orchestrator.py)
1. **Safe Upsert in `run_fetch_ri_files`**:
   - Replace blind `POST` with a check-and-patch pattern:
     - Check `GET /rest/v1/project_assets?project_id=eq.{pid}&filename=eq.{filename}&select=id`.
     - If existing, `PATCH /rest/v1/project_assets?id=eq.{id}`.
     - If not, `POST /rest/v1/project_assets`.
   - This stops `run_fetch_ri_files` from ever creating duplicate rows in `project_assets`.
2. **Accurate Report Counting in `get_project_sync_status`**:
   - Also scan local project folder and grant center directory for report PDFs, or use `projects.sync_status.grant_center.report_count`.
3. **Automatic Supabase Sync Hook & Bi-Directional Link**:
   - In `run_spc_export`: immediately call `await sync_spc_state_to_supabase()` upon successful completion of the SPC export.
   - In `sync_spc_state_to_supabase`: update `projects.sync_status` AND upsert an entry in `project_links` with `label: "Rotary Service Project Center (SPC)"`, `url: spc_url`.

#### [MODIFY] [scripts/migrate_to_spc.py](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/scripts/migrate_to_spc.py)
1. **Archive URL in SPC Export**:
   - Ensure the deep link to the archive (`https://mrosen.github.io/rcla_project_map/?source=supabase&project={gid}`) is added with caption `"RCLA Project Archive Record"` to SPC's `projectRelLinks`.
2. **Persist State & Link to Supabase in `save_state`**:
   - In `save_state(state)`: send PATCH request to `{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}` updating `sync_status.spc`, and upsert into `project_links`.

---

## Verification Plan

### Automated / Backend Verification
1. Verify endpoint `/api/projects/GG2574529/sync-status` returns `has_application_pdf: true`, `report_count: 1`, and `spc.exported: true`.
2. Check that `project_links` in Supabase contains the SPC link for migrated projects.
3. Run duplicate check script to ensure no duplicate assets exist in `project_assets` or storage.

### UI / Manual Verification
1. Open the Edit modal for `GG2574529`:
   - Verify badge displays: `📄 GG Appl PDF on file (+1 status report PDF)`
   - Verify SPC chip displays: `✓ Synced to SPC ↗`
   - Verify "Web Links" includes `Rotary Service Project Center (SPC)`.
2. Open Project Detail view for `GG2574529`:
   - Verify top header displays: `🌐 View on SPC` link button.
3. Test uploading an image or file:
   - Verify no duplicate rows are inserted.
