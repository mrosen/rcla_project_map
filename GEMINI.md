# Workspace Rules for Rotary Club of Lake Atitlán Project Map

## Markdown File Links & URI Formatting
When running with VS Code on Windows accessing this workspace via WSL UNC (`\\wsl.localhost\Ubuntu\home\msr\rcla_project_map`):

1. **Clickable Links in Chat Responses**:
   Always format file links using the 2-slash UNC authority URI:
   `[<filename>](file://wsl.localhost/Ubuntu/home/msr/rcla_project_map/<path-from-root>)`
   *(Alternative accepted format: `file:///Ubuntu/home/msr/rcla_project_map/<path-from-root>`)*

2. **Prohibited Formats in Chat**:
   - DO NOT use `file:///wsl.localhost/...` (VS Code prepends `\\wsl.localhost\`, causing `\\wsl.localhost\wsl.localhost\...`).
   - DO NOT use `file:///home/msr/...` (omits the `Ubuntu` distribution share name, causing `\\wsl.localhost\home\...`).
   - DO NOT use relative links (`./file.ext`) in chat messages (chat webviews cannot resolve relative filesystem paths).

3. **Links Inside Workspace Markdown Files**:
   Inside markdown files committed to the repository (e.g. `walkthrough.md`, `implementation_plan.md`), use document-relative paths (`./<file>`) so they can be browsed seamlessly in both VS Code Markdown Preview and on GitHub.

## Canonical Datastore Architecture (Supabase Single Source of Truth)
- **Supabase PostgreSQL is the Sole Source of Truth**:
  All project definitions, financials, details, narratives, coordinates, timelines, media assets, and partner lists reside in Supabase (`projects`, `project_links`, `project_assets`).
- **No CSV Datastore Fallbacks or Ingestion**:
  Legacy CSV files (`RCLA_Projects_v2.csv`, `RCLA_Projects.csv`, etc.) are obsolete historical artifacts. Code, scripts, and reasoning must NEVER read, query, update, or fall back to CSV files for project data.
- **Source Documents Inform Supabase Directly**:
  Any grant applications, PDF reports, or external spreadsheets are source material used to update Supabase directly. All application logic, APIs, and export tools must read exclusively from Supabase.


