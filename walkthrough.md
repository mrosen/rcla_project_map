# Walkthrough: Gemini Key Persistence, Live SPC Export Updates & Funding Cleanups

We have addressed and verified all issues raised:
1. **Gemini API Key Persistence**: The Gemini API key now persists permanently in both the browser's `localStorage` and the local `.env` configuration, eliminating repeated key prompts when clicking "Auto-fill from App PDF".
2. **Removed $0 Funding Lines from Rotary SPC**: All 4 zero-dollar funding lines on project `GG2578692` (`https://spc.rotary.org/project?guid=0c101fff-43ee-41ea-97bc-22fd018d4cff`) have been cleanly removed from Rotary SPC.
3. **Detailed Description Sync**: Ensured the complete AI-synthesized narrative starting with *"This project addresses critical sanitation needs in Vista Hermosa, Guatemala, by installing 49 decentralized modular wastewater treatment systems (MWWTPs)..."* is active on Rotary SPC.
4. **Real-time "Open SPC View" Link Updates**: Fixed the UI link behavior so that immediately upon export completion, the button links directly to the project's unique Rotary SPC URL without requiring a page refresh.

---

## 1. Root Cause Analysis & Resolutions

### A. Gemini API Key Persistence
- **Root Cause**:
  1. In [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js), `synthesizeFromAi` only checked `if (customApiKey)` before attaching `payload.api_key`. When called from the "Auto-fill from App PDF" button, `customApiKey` was undefined, so it never loaded from `localStorage.getItem('gemini_api_key')`.
  2. The prompt modal handlers previously saved only to `sessionStorage`, causing the key to be lost whenever a tab or session closed.
  3. The local orchestrator had no dedicated endpoint for the browser to persist the API key to `.env`, and only saved keys inside `synthesize_project_data` if the request succeeded.
  4. Deprecated models in the client candidate fallback list occasionally returned unexpected non-JSON responses, triggering the `Unexpected token '<'` error dialog.
- **Fix**:
  - Added dedicated endpoint `POST /api/config/gemini-key` in [orchestrator.py](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/orchestrator.py) that saves the key directly to `.env` and updates `os.environ["GEMINI_API_KEY"]`.
  - Updated `synthesizeFromAi`, `promptChangeGeminiKey`, and API prompt dialogs in [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js) to store the key in `localStorage` and immediately `POST` it to `/api/config/gemini-key`.
  - Prioritized the verified active models (`gemini-3-flash-preview`, `gemini-2.5-flash`, etc.) and added robust response parsing that strips markdown fences and unwraps single-item array drafts.

---

### B. Removal of $0 Funding Lines on Rotary SPC (`GG2578692`)
- **Root Cause**:
  - Rotary SPC backend (`PUT /api/Project/UpdateProject`) is an ASP.NET Core API.
  - When attempting to delete zero-dollar funding lines, passing club keys for non-Rotary partner lines caused the Rotary API to reject the update (returning string `'false'`).
  - Sending `"rotaryFoundationGrantFlag": "1"` as a string caused .NET deserialization errors (`System.Text.Json: The JSON value could not be converted to System.Boolean`).
- **Fix**:
  - In [migrate_to_spc.py](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/migrate_to_spc.py) and [scripts/migrate_to_spc.py](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/scripts/migrate_to_spc.py):
    - Ensured `rotaryFoundationGrantFlag` is sent as boolean `True`.
    - When deleting existing zero-dollar funding lines, `fundingClubKey` is explicitly set to `""`.
    - Existing creator contacts in `joiners` are preserved with `isDeleted: False` to avoid creator constraints.
    - Verified live on Rotary SPC: All 4 zero-dollar lines (AdP, Municipality of Santa Lucia Utatlan, Education Dept, COCODE) have been deleted, and total funding sources went from 16 to 12.

---

### C. Detailed Description on Rotary SPC
- **Verification**:
  - The project payload now maps `complete_overview` directly into `projectDescription.projectDetail`.
  - Checked live endpoint `GET https://spc.rotary.org/api/Project/ProjectDetail/en/0c101fff-43ee-41ea-97bc-22fd018d4cff`:
    The live text starts with:
    > *"This project addresses critical sanitation needs in Vista Hermosa, Guatemala, by installing 49 decentralized modular wastewater treatment systems (MWWTPs)..."*

---

### D. Instant "Open SPC View" Link Update
- **Fix**:
  - In [main.js](file:///wsl.localhost/Ubuntu/home/msr/rcla_project_map/main.js), `applyExportedSpcGuid` and `loadProjectSyncStatus` now directly query `#detail-spc-badge` and `#detail-spc-view-btn` in the DOM and set their `href` to `https://spc.rotary.org/project?guid={guid}`.
  - As soon as the export automation outputs the success GUID, the button updates to blue with the direct project link without requiring a page reload.

---

## 2. Verification Results

1. **Gemini Config Endpoint**:
   - `curl -X POST http://localhost:8000/api/config/gemini-key -d '{"api_key": "..."}'` -> `{"success": true, "message": "Gemini API key saved to .env."}`.
2. **AI Synthesis Test (`GG2578692`)**:
   - `curl -X POST http://localhost:8000/api/projects/GG2578692/synthesize -d '{"source": "pdf"}'` -> Returned valid structured JSON draft using `gemini-3-flash-preview` in ~6 seconds with unwrapped dictionary format.
3. **Live Rotary SPC Project (`0c101fff-43ee-41ea-97bc-22fd018d4cff`)**:
   - Zero-dollar funding lines: 0 present (cleanly deleted).
   - Detailed Description: Matches the full narrative.
4. **Git Repository**:
   - Changes committed and pushed to `origin/main`.
