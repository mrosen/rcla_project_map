# Multi-Club Rotary Project Map — Implementation Plan (v2)

This plan outlines the agreed implementation to evolve the **Rotary Club of Lake Atitlán Project Map** into a **Multi-Club Rotary Project Map Platform** where multiple Rotary clubs share the same canonical Supabase PostgreSQL database and authenticate dynamically with their own **MyRotary.org** credentials for Grant Center imports and Service Project Center (SPC) exports.

---

## ✅ Agreed Scope & Design Decisions
1. **Shared Supabase Database with Multi-Club Support**:
   - New `clubs` registry table + `club_id` column on `projects` (defaulting to `'lake-atitlan'`).
   - Shared Global Grants (`GGxxxxxxx`) remain single canonical records visible to any participating club (Host, International Sponsor, or Partner Club).
   - Default landing view without `?club=...` remains **Rotary Club of Lake Atitlán** for full backward compatibility, with a **Club Switcher** in the top navigation bar (including an **"All Clubs"** option).
2. **Lightweight Maintainer Management (Option A)**:
   - Keep Maintainer Mode lightweight (`Ctrl+Shift+M` / `?maint=1`), scoped by default to the currently active club (or the club auto-detected from the user's MyRotary login).
3. **Dynamic Per-User MyRotary.org Credentials**:
   - Prompt the user for their MyRotary Email & Password in a Maintainer Mode modal (cached only in browser `sessionStorage` for the active tab, with local `.env` fallback).
   - Auto-detect the signed-in member's identity (`individualkey`, `memberId`, `userName`, `userLoginEmail`) and club metadata (`clubKey`, `clubId`, `clubName`, `district`, `country`) from Rotary's live session (`window.store.getState().user.userDeatils` / `/api/Auth`).
   - Support an interactive 6-digit MFA code prompt if a user's MyRotary Okta account challenges for MFA.
4. **Deferred / Out of Scope for Now**:
   - Deep Grant Center attachment crawling enhancements (existing Application & Report PDF download flow remains as-is).
   - Multi-job backend concurrency queues (existing single-job `STATE` and SSE `LOG_BUFFER` in `./orchestrator.py` remain as-is).

---

## Phase 1: Database Schema Migration (`./schema_migration.sql`)

1. **Create `clubs` Table in Supabase**:
   ```sql
   CREATE TABLE IF NOT EXISTS clubs (
     id text PRIMARY KEY,                      -- slug, e.g. 'lake-atitlan', 'annapolis'
     name text NOT NULL,                       -- e.g. 'Rotary Club of Lake Atitlán'
     short_name text,                          -- e.g. 'Lake Atitlán'
     rotary_club_id text,                      -- e.g. '84633'
     spc_club_key text,                        -- e.g. '7de94f72-4330-4015-9ba9-5fac50225049'
     district text,                            -- e.g. '4250'
     country text DEFAULT 'Guatemala',
     default_city text DEFAULT 'Panajachel',
     default_state text DEFAULT 'Sololá Department',
     default_language text DEFAULT 'Spanish',
     default_lat numeric DEFAULT 14.703454,
     default_lng numeric DEFAULT -91.191623,
     default_zoom integer DEFAULT 11,
     created_at timestamptz DEFAULT now()
   );
   ```
2. **Seed Initial Club (`lake-atitlan`) & Link `projects`**:
   - Insert Rotary Club of Lake Atitlán (`id = 'lake-atitlan'`, `rotary_club_id = '84633'`, `spc_club_key = '7de94f72-4330-4015-9ba9-5fac50225049'`, `district = '4250'`).
   - Add `club_id text REFERENCES clubs(id) DEFAULT 'lake-atitlan'` to `projects` and backfill all existing rows to `'lake-atitlan'`.
   - Enable public read/write policies on `clubs` matching `projects` so Maintainer Mode can register a new club automatically when a member from another club signs in or creates a club profile.

---

## Phase 2: Dynamic MyRotary Credentials & Auto-Discovery (`./orchestrator.py`, `./scripts/migrate_to_spc.py`, `./scripts/download_grant_center.py`)

### 2.1 Backend API Payloads (`./orchestrator.py`)
- Update `GrantCenterSyncPayload`, `SPCExportPayload`, and `/api/projects/{project_id}/fetch-ri-files` + `/api/projects/{project_id}/export-spc` to accept optional per-request fields:
  - `rotary_email: Optional[str]`
  - `rotary_password: Optional[str]`
  - `club_id: Optional[str]` (active club slug, e.g. `'lake-atitlan'`)
- Pass `ROTARY_EMAIL`, `ROTARY_PASSWORD`, and `ACTIVE_CLUB_ID` in the subprocess `env` dictionary for each Playwright worker run (falling back to `.env` if omitted locally).
- Add a lightweight MFA relay endpoint (`POST /api/rotary/mfa-code`) and state flag (`STATE["waiting_for_mfa"] = True`) so if Okta presents an MFA code input during headless login, the UI can prompt the user and pass the code to the waiting Playwright process.

### 2.2 Dynamic User & Club Context in SPC Export (`./scripts/migrate_to_spc.py`)
- Replace hardcoded constants (`ROTARY_LAKE_ATITLAN_CLUB_KEY`, `MEMBER_KEY`, `MEMBER_ID`, `MEMBER_NAME`, `MEMBER_EMAIL`, `"Guatemala"`, `"Panajachel"`, `"Sololá Department"`) with a dynamic `ClubAndUserContext` resolved at runtime:
  1. Look up the active club in Supabase `clubs` (by `ACTIVE_CLUB_ID` or the project's `club_id`).
  2. Upon Playwright login to `spc.rotary.org`, extract `individualkey`, `memberId`, `userName`, `userLoginEmail`, and any club identifiers from `window.store.getState().user.userDeatils` / `/api/Auth`.
  3. If the active club in `clubs` does not yet have an `spc_club_key`, resolve it automatically via `https://spc.rotary.org/apiNew/Search/Organization` and update the `clubs` row in Supabase.
  4. Build `construct_spc_payload(p, club_ctx, user_ctx)` using the active club's `spc_club_key`, `country`, `default_city`, `default_state`, `default_language`, and the signed-in user's `individualkey` / `memberId` / `userLoginEmail`.
  5. Update the archive deep-link (`relLinkType: "5"`) to include `?club={club_slug}&project={gid}`.

### 2.3 Supabase-Native Grant Center Discovery & Sync (`./scripts/download_grant_center.py` & `./orchestrator.py`)
- Update `./orchestrator.py`'s `run_grantcenter_sync()` to invoke `./scripts/download_grant_center.py` directly (retiring the legacy CSV-based `check_grant_sync.py`):
  - **Dry Run Mode (`--discover-only` / `--audit`)**: Logs into `spc.rotary.org/mygrants` using the user's MyRotary credentials, lists all `GG` and `DG` grants associated with their account, and compares them against Supabase `projects` (reporting new grants and status changes in the log console).
  - **Live Sync Mode (`--sync-new`)**: For any newly discovered grant on `mygrants` not yet in Supabase:
    1. Creates the project record in Supabase `projects` linked to the active `club_id`.
    2. Downloads the Application PDF and Report PDFs to Supabase Storage (`project-media`) and `project_assets`.
    3. Automatically runs Gemini AI synthesis + geocoding on the Application PDF so the new grant gets its title, 100-char brief overview, 1,000-char complete overview, budget, host/international partner clubs, milestones, and community map coordinates.

---

## Phase 3: Multi-Club Frontend & MyRotary Session UI (`./index.html` & `./main.js`)

1. **Top Navigation Club Switcher (`#nav`)**:
   - Add a `<select id="club-selector">` in `#nav` next to the dynamic club title:
     - Populated from Supabase `clubs` table (plus `"🌎 All Rotary Clubs"`).
     - Defaults to `lake-atitlan` unless `?club=<slug>` is in the URL.
     - Selecting a club updates `?club=<slug>` in the URL, updates the header title (`<Club Name> — Projects`), filters `allProjects` to show projects owned by **or** partnered with that club (via `club_id`, `host_club`, `international_club`, or `details.partner_clubs`), and smoothly re-centers the map to fit those projects.
   - In Maintainer Mode, include a **`➕ Add Club`** option in the club selector to register a new Rotary club (Name, District, Country, Default City/Coordinates).
2. **MyRotary Credentials Modal in Maintainer Mode**:
   - Add a **`🔐 MyRotary Login`** button in `#maintainer-panel` (and automatically open the modal when a user clicks **Grant Sync**, **Fetch RI Files**, or **SPC Export** if no session credentials are set and they aren't using local `.env`).
   - Stores email/password only in `sessionStorage` (`rcla_rotary_email`, `rcla_rotary_password`) for the current browser tab session and attaches them to `/api/grantcenter/sync`, `/api/spc/export`, `/api/projects/{id}/fetch-ri-files`, and `/api/projects/{id}/export-spc`.
3. **AI Geocoding for Non-Atitlán Grants (`./orchestrator.py`)**:
   - Enhance the Gemini synthesis prompt in `synthesize_project_data()` to also return `community_location` (`city`, `state_or_department`, `country`, and approximate `latitude` / `longitude`) extracted from the Grant Application PDF so grants imported by any club worldwide land accurately on the map.
