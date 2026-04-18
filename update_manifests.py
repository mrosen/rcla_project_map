#!/usr/bin/env python3
"""
update_manifests.py
-------------------
Scans every folder under projects/ and updates files.json to reflect
the actual files present on disk.

Rules:
- 'files' list is always regenerated from disk contents
- 'links' list is NEVER touched (preserves manually added links)
- files.json itself and Zone.Identifier files are excluded
- Run from the root of your rcla_project_map directory

Usage:
    cd ~/rcla_project_map
    python3 update_manifests.py

Options:
    --dry-run    Show what would change without writing anything
    --verbose    Show every file found in every folder
"""

import os
import json
import argparse

# Files to always exclude from the manifest
EXCLUDE = {
    'files.json',
}

# Extensions to exclude (Windows metadata etc.)
EXCLUDE_SUFFIXES = (
    ':Zone.Identifier',
    '.Identifier',
)

def scan_folder(folder_path, verbose=False):
    """Return sorted list of files in folder, excluding noise."""
    files = []
    try:
        entries = os.listdir(folder_path)
    except PermissionError:
        print(f"  WARNING: Cannot read {folder_path}")
        return files

    for entry in sorted(entries):
        # Skip directories
        if os.path.isdir(os.path.join(folder_path, entry)):
            continue
        # Skip excluded filenames
        if entry in EXCLUDE:
            continue
        # Skip Windows Zone.Identifier and similar
        if any(entry.endswith(s) for s in EXCLUDE_SUFFIXES):
            continue
        # Skip hidden files
        if entry.startswith('.'):
            continue
        files.append(entry)
        if verbose:
            print(f"    + {entry}")

    return files

def load_manifest(json_path):
    """Load existing files.json, returning defaults if missing or corrupt."""
    if not os.path.exists(json_path):
        return {'files': [], 'links': []}
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # Ensure both keys exist
        if 'files' not in data:
            data['files'] = []
        if 'links' not in data:
            data['links'] = []
        return data
    except json.JSONDecodeError as e:
        print(f"  WARNING: Corrupt files.json ({e}) — preserving links if recoverable")
        # Try to salvage links from raw text
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = f.read()
            # If we can find a links array, try to preserve it
            import re
            match = re.search(r'"links"\s*:\s*(\[.*?\])', raw, re.DOTALL)
            if match:
                links = json.loads(match.group(1))
                print(f"  Salvaged {len(links)} link(s) from corrupt file")
                return {'files': [], 'links': links}
        except Exception:
            pass
        return {'files': [], 'links': []}

def update_manifests(projects_dir, dry_run=False, verbose=False):
    if not os.path.isdir(projects_dir):
        print(f"ERROR: projects directory not found: {projects_dir}")
        return

    project_folders = sorted([
        d for d in os.listdir(projects_dir)
        if os.path.isdir(os.path.join(projects_dir, d))
    ])

    if not project_folders:
        print("No project folders found.")
        return

    print(f"Scanning {len(project_folders)} project folders...\n")

    changed = 0
    unchanged = 0

    for folder_name in project_folders:
        folder_path = os.path.join(projects_dir, folder_name)
        json_path   = os.path.join(folder_path, 'files.json')

        if verbose:
            print(f"{folder_name}/")

        existing   = load_manifest(json_path)
        disk_files = scan_folder(folder_path, verbose=verbose)

        # Compare — only update if files list changed
        if disk_files == existing['files']:
            if verbose:
                print(f"  (no change)\n")
            unchanged += 1
            continue

        # Show diff
        added   = [f for f in disk_files      if f not in existing['files']]
        removed = [f for f in existing['files'] if f not in disk_files]

        print(f"{folder_name}/")
        for f in added:
            print(f"  + {f}")
        for f in removed:
            print(f"  - {f}")
        if existing['links']:
            print(f"  links preserved: {len(existing['links'])}")

        if not dry_run:
            new_manifest = {
                'files': disk_files,
                'links': existing['links'],   # always preserve
            }
            with open(json_path, 'w', encoding='utf-8') as out:
                json.dump(new_manifest, out, indent=2, ensure_ascii=False)
            print(f"  ✓ updated\n")
        else:
            print(f"  (dry run — not written)\n")

        changed += 1

    print(f"Done. {changed} updated, {unchanged} unchanged.")
    if dry_run:
        print("(dry run — no files were written)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update files.json manifests from disk contents')
    parser.add_argument('--dry-run',  action='store_true', help='Show changes without writing')
    parser.add_argument('--verbose',  action='store_true', help='Show all files found')
    parser.add_argument('--projects', default='projects',  help='Path to projects directory (default: projects/)')
    args = parser.parse_args()

    update_manifests(
        projects_dir=args.projects,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
