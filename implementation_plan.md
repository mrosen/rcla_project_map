# Implementation Plan: Streamline Public View & Restrict Maintenance Mode

Make Maintenance Mode strictly opt-in and hidden from standard public visitors, remove the "Edit Project" and "Export to SPC" action buttons from the default view, relocate the SPC link into the project's web links section, and display a clean sync indicator badge in the header metadata.

## User Review Required

> [!IMPORTANT]
> - **Default View for Public Users**: Maintenance Mode will be **OFF** by default for all visitors (both local and on GitHub Pages). Standard visitors will see a clean public interface with **no** "Maintainer Mode" button, **no** database status pill, **no** "Edit Project" button, and **no** "Export to SPC" button.
> - **Accessing Maintenance Mode**: Maintainers can activate Maintenance Mode at any time using:
>   1. Keyboard shortcut: `Ctrl+Shift+M` (or `Cmd+Shift+M` on Mac).
>   2. URL query parameter: appending `?maint=true`, `?admin=true`, or `?edit=true` to the URL.
>   3. Discreet trigger: double-clicking the club name in the top navigation bar.
> - **SPC Link for Public Users**: When a project has been synced to Rotary SPC:
>   1. A subtle, elegant metadata badge `✓ Synced to Rotary SPC ↗` appears alongside the project status/type badges in the header.
>   2. The project's Rotary Service Project Center entry appears as one of the web links in the **"Attached Documents & Web Links"** section.

---

## Proposed Changes

### Top Navigation & Maintenance Mode Defaults

#### [MODIFY] [index.html](./index.html)
- Set `#btn-maint-toggle` and `#backend-status-indicator` to `display: none;` by default in HTML so they never flash or appear for regular visitors.
- Add `ondblclick="toggleMaintenanceMode()"` to the navbar club title as a discreet maintainer fallback on devices without a keyboard.

#### [MODIFY] [main.js](./main.js)
- In `checkMaintenanceMode()`: Default to `false` (remove the `hostname === 'localhost'` override so local and production behave identically for clean public preview).
- In `applyMaintenanceModeUI()`:
  - When `isMaintenanceMode` is `false`: Hide `#maintainer-panel`, hide `#btn-maint-toggle`, and hide `#backend-status-indicator`.
  - When `isMaintenanceMode` is `true`: Show `#maintainer-panel`, show `#btn-maint-toggle` styled as `🛠️ Maint Mode ON (✕ Exit)`, and show `#backend-status-indicator`.

---

### Project Detail View & SPC Link Relocation

#### [MODIFY] [main.js](file:///home/msr/rcla_project_map/main.js)
- In `showDetail(idx)`:
  - Make `editBtn` (`✏️ Edit Project`) visible **only** when `isMaintenanceMode` is `true`.
  - Make `spcBadge` (`🚀 Export to SPC` / `🌐 Open SPC View ↗` maintainer action cluster) visible **only** when `isMaintenanceMode` is `true`.
  - In the project meta badge row (next to Project Type and Status):
    - If project has an SPC link (`getProjectSpcUrl(project)`): display a tasteful link badge:
      `✓ Synced to Rotary SPC ↗`
  - In `renderFilesAndLinksFromProject` and `renderFilesAndLinks`:
    - Ensure that if `getProjectSpcUrl(project)` exists, the link `🌐 Rotary Service Project Center (SPC) ↗` is included in the project's **Attached Documents & Web Links** list as one of the standard web links.

---

## Verification Plan

### Automated / Syntax Verification
- Run `node -c main.js` to ensure 0 syntax errors.
- Test endpoint responses and build files.

### Manual Verification
1. **Public View (Default)**:
   - Load `http://localhost:8000/` without any query parameters or session state.
   - Verify `#nav`: Shows only `Overview` and `Projects`. No maintainer button, no database indicator, no maintainer panel.
   - Click a project (e.g. `GG2578692`):
     - Confirm **NO** `✏️ Edit Project` button.
     - Confirm **NO** `🚀 Export to SPC` button.
     - Confirm `✓ Synced to Rotary SPC ↗` appears gracefully in the badge row.
     - Scroll down to "Attached Documents & Web Links" and confirm `🌐 Rotary Service Project Center (SPC) ↗` is present among the web links.
2. **Maintainer Mode Activation**:
   - Press `Ctrl+Shift+M` (or visit `http://localhost:8000/?maint=true`):
     - Confirm the maintainer panel opens at the top.
     - Confirm `#btn-maint-toggle` appears in the navbar with `🛠️ Maint Mode ON (✕ Exit)`.
     - Confirm `✏️ Edit Project` and `🚀 Re-export to SPC` / `🌐 Open SPC View ↗` appear in the detail header.
   - Click `✕ Exit Maint`:
     - Confirm UI seamlessly returns to the clean public view.
