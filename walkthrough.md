# Walkthrough: Restore "Export to SPC" and "View on SPC" Links & Action Buttons

We have resolved the missing SPC export link and restored complete SPC action functionality across both local development and static hosting environments.

---

## 1. What Happened & Why the Link Disappeared

1. **Edit Drawer Sync Actions Cleared on Static Host / Offline**:
   - In `main.js`, `loadProjectSyncStatus` only rendered `#edit-sync-actions` inside the backend `try` block.
   - On GitHub Pages (`mrosen.github.io`), `fetch('/api/projects/.../sync-status')` returns 404 because no Python backend runs on GitHub Pages. The `catch` block executed `actionsEl.innerHTML = ''`, erasing the **`🚀 SPC Live Export`** and **`🧪 SPC Dry Run`** buttons.
2. **Maintainer Toolbar Buttons Hidden on GitHub Pages**:
   - In `index.html`, `btn-spc-dry` and `btn-spc-live` had class `local-only-btn`. On GitHub Pages, `applyMaintenanceModeUI` hid them with `display: none`.
3. **No Direct Export Button in Detail View**:
   - In `showDetail`, the project header only displayed `🌐 View on SPC` if already exported. Unexported projects had no direct export button in maintainer mode.
4. **Local Daemon Reloader Exit**:
   - The background Python orchestrator process had stopped earlier due to a reloader reload.

---

## 2. Changes Made

### A. Robust SPC URL Extraction & Normalization ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))
- **`normalizeSpcUrl(url, guid)`**: Updated to handle bare GUIDs (e.g. `80ec1aaa-cb0d-4735-8762-b6a3102f3291`) and format them correctly into `https://spc.rotary.org/project?guid={guid}`.
- **`getProjectSpcUrl(project)`**: New helper that resolves SPC links from `project.sync_status.spc.spc_url`, `project.sync_status.spc.spc_project_id`, `project.spc_url`, `project.spc_id`, or any item in `project.project_links`.

### B. Project Detail View Header Actions ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))
- If project has an SPC link: renders **`🌐 View on SPC ↗`**. In Maintainer Mode, also adds **`🚀 Export to SPC`** (re-export).
- If project is not yet exported: in Maintainer Mode, renders **`🚀 Export to SPC`** directly next to **`✏️ Edit Project`**.

### C. Edit Drawer Sync Actions ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))
- Added `renderSyncActions(projectId, spc)`:
  - Renders **`🌐 View on SPC ↗`** (if exported).
  - Renders **`📥 Re-check RI`**.
  - Renders **`🧪 SPC Dry Run`**.
  - Renders **`🚀 Re-export to SPC`** (if exported) or **`🚀 Export to SPC`** (if unexported).
- Optimistically renders `renderSyncActions` immediately in Step 1 upon opening the drawer.
- If backend daemon is offline or on GitHub Pages, the `catch` block preserves the optimistic action buttons instead of clearing them.

### D. Maintainer Toolbar Buttons ([`index.html`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/index.html))
- Removed `local-only-btn` restriction from **`SPC Export (Dry)`** and **`SPC Export (Live)`** so they are visible whenever Maintainer Mode is enabled.

### E. Static Hosting Guidance ([`main.js`](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js))
- In `triggerProjectSpcExport` and `triggerSpcExport`:
  - When invoked from static GitHub Pages (`mrosen.github.io`), displays a friendly modal explaining that live browser automation uses Playwright via the local Python orchestrator, and provides a 1-click button to open `http://localhost:8000/?project={id}&edit=true`.
  - When invoked from `localhost:8000`, executes the export via the orchestrator immediately.

---

## 3. Verification

1. **Syntax Check**:
   - `node -c main.js`: Passed with exit code 0.
2. **Git Status & Changes**:
   - Verified changes in `main.js` and `index.html`.
3. **Local Orchestrator Process**:
   - Started and verified responding at `http://127.0.0.1:8000/api/status` (200 OK) and `http://127.0.0.1:8000/api/projects/GG1633934/sync-status` (200 OK).
