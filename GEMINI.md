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

