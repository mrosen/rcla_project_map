# Learning Proposal: WSL UNC File Link Rule for VS Code on Windows

## 1. Classification & Scope
* **Type**: Workspace Rule (`GEMINI.md`)
* **Target Location**: `/home/msr/rcla_project_map/GEMINI.md` (or `\\wsl.localhost\Ubuntu\home\msr\rcla_project_map\GEMINI.md`)
* **Scope**: All conversations and agent operations within the `rcla_project_map` workspace.

---

## 2. Background & Root Cause Analysis
When VS Code runs on Windows with a project opened via the WSL network share (`\\wsl.localhost\Ubuntu\home\msr\rcla_project_map`):
1. **Double-hostname failure (`file:///wsl.localhost/...`)**:
   Three slashes indicate an empty host. VS Code on Windows treats the path as root-relative to the workspace's network authority (`wsl.localhost`), prepending `\\wsl.localhost\` to create `\\wsl.localhost\wsl.localhost\Ubuntu\...`, causing a file system error (`stat UNKNOWN`).
2. **Missing distribution failure (`file:///home/msr/...`)**:
   Omits the WSL distribution name (`Ubuntu`). When VS Code prepends `\\wsl.localhost\`, it becomes `\\wsl.localhost\home\...`, which does not exist on the Windows network provider.
3. **Relative links in chat**:
   The chat interface runs in an isolated webview context with no local filesystem base, so relative markdown links (`./...`) cannot be resolved. (However, within repo markdown files like `walkthrough.md`, document-relative links work as expected).

---

## 3. Verified Working Link Formats
The user confirmed that both of the following formats open cleanly in VS Code:
1. **RFC 8089 2-slash UNC File URI** *(Recommended default)*:
   `file://wsl.localhost/Ubuntu/home/msr/rcla_project_map/<relative-path>`
2. **Distro-Root 3-slash File URI**:
   `file:///Ubuntu/home/msr/rcla_project_map/<relative-path>`

---

## 4. Proposed Content for `GEMINI.md`

```markdown
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
```

---

## 5. Next Steps Upon Approval
Once approved:
1. Create `/home/msr/rcla_project_map/GEMINI.md` with the rule text above.
2. Commit and push to `origin/main`.
3. The rule will automatically be loaded and enforced across all future Antigravity conversations in this workspace.

