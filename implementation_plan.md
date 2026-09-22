# Restore "Export to SPC" / "View on SPC" Links and Action Buttons

The user reported: `"I no longer have an export to spc link"`. This plan details why the SPC export link and action buttons disappeared and provides the technical changes to restore them across the application.

## Root Cause Analysis

1. **Edit Drawer Sync Actions Wiped on Fetch Failure**:
   - In `main.js`, `loadProjectSyncStatus` only rendered action buttons (`🧪 SPC Dry Run`, `🚀 SPC Live Export`) inside the `try` block that fetched `BACKEND_URL + '/api/projects/.../sync-status'`.
   - On GitHub Pages (`https://mrosen.github.io/`), `BACKEND_URL` is `window.location.origin`, which returns 404 for `/api/...`.
   - In the `catch (err)` block, the code executed `actionsEl.innerHTML = '';`, completely erasing the SPC export buttons.
2. **Maintainer Bar SPC Export Buttons Hidden on Static/GitHub Pages**:
   - In `index.html`, `btn-spc-dry` and `btn-spc-live` had the CSS class `local-only-btn`.
   - `applyMaintenanceModeUI` sets `el.style.display = 'none'` on all `.local-only-btn` elements when not on localhost, hiding the SPC Export buttons in Maintainer Mode on GitHub Pages.
3. **Missing Direct "Export to SPC" Action in Project Detail View**:
   - In `showDetail`, the project header only displayed `🌐 View on SPC` (if already exported).
   - If a project was not yet exported, or if a maintainer wanted to trigger/re-run an export directly from the detail view, no button was rendered.
4. **Local Orchestrator Process Had Halted**:
   - The background Python orchestrator daemon had stopped due to a reload shutdown, causing requests to `http://localhost:8000` to fail until restarted.

---

## Proposed Changes

### 1. Robust SPC URL Extraction & Normalization
#### [MODIFY] [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js)
- Fix `normalizeSpcUrl(url, guid)` to support bare GUID strings and correctly prepend `https://spc.rotary.org/project?guid=`.
- Add `getProjectSpcUrl(project)` helper to check `project.sync_status.spc.spc_url`, `project.sync_status.spc.spc_project_id`, `project.spc_url`, `project.spc_id`, and `project.project_links`.

### 2. Project Detail View Header Actions
#### [MODIFY] [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js)
- In `showDetail(idx)`:
  - If project has an SPC link: render `🌐 View on SPC ↗` (opens Rotary SPC project page).
  - In Maintainer Mode: render `🚀 Export to SPC` (or `🚀 Re-export to SPC`) button directly in the detail view header next to `✏️ Edit Project`.

### 3. Edit Drawer Sync Actions & Status
#### [MODIFY] [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js)
- In `loadProjectSyncStatus(projectId)`:
  - Add `renderSyncActions(projectId, spc)` that generates:
    - `🌐 View on SPC ↗` link (if exported).
    - `🧪 SPC Dry Run` button.
    - `🚀 Export to SPC` / `🚀 Re-export to SPC` button.
  - Optimistically render `renderSyncActions` in Step 1 immediately upon opening the drawer.
  - Do NOT wipe out `actionsEl` in `catch` block on fetch failure; retain the action buttons and links.

### 4. Maintainer Toolbar Buttons
#### [MODIFY] [index.html](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/index.html)
- Remove `local-only-btn` from `btn-spc-dry` and `btn-spc-live` so they remain accessible whenever Maintainer Mode is enabled.

### 5. Actionable Guidance for Static GitHub Pages
#### [MODIFY] [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js)
- In `triggerProjectSpcExport` and `triggerSpcExport`:
  - When invoked from GitHub Pages, explain that live Playwright browser automation runs through the local orchestrator, and offer a one-click prompt to open `http://localhost:8000/?project={id}`.
  - When invoked from `localhost:8000`, run the export immediately and stream logs.

---

## Verification Plan

### Automated / Syntax Verification
- Validate `main.js` syntax: `node -c main.js`
- Test endpoints against live orchestrator:
  - `GET http://127.0.0.1:8000/api/projects/GG1633934/sync-status`
  - `GET http://127.0.0.1:8000/api/status`

### Manual Verification
1. Inspect detail view for `GG1633934`: confirm `🌐 View on SPC ↗` and `🚀 Export to SPC` are visible.
2. Inspect detail view for an unexported project (e.g. `GG1871794`): confirm `🚀 Export to SPC` appears in Maintainer Mode.
3. Open Edit drawer: confirm `🌐 View on SPC ↗`, `🧪 SPC Dry Run`, and `🚀 Re-export to SPC` buttons are present.
4. Test clicking export from static origin to verify the orchestrator guidance prompt.
