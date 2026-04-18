#!/usr/bin/env python3
"""
migrate_grants.py
-----------------
Copies PDFs and SUMMARY files from ~/grantcenter/rotary_grants/
into the matching projects/<id>/ folder in the web app.

For each GG* folder in rotary_grants it:
  - Extracts the grant ID (e.g. GG2091778) from the folder name
  - Finds the matching projects/<id>/ folder
  - Copies: GG*_Application.pdf, GG*_Report_*.pdf, SUMMARY.md, SUMMARY.pdf
  - Skips DG* folders (district grants, not in web app)
  - Never overwrites existing files unless --overwrite is passed
  - Runs update_manifests.py at the end to refresh all files.json

Usage:
    cd ~/rcla_project_map
    python3 migrate_grants.py
    python3 migrate_grants.py --dry-run
    python3 migrate_grants.py --overwrite
"""

import os
import shutil
import argparse
import subprocess

SOURCE_DIR  = os.path.expanduser('~/grantcenter/rotary_grants')
PROJECTS_DIR = 'projects'

# Files to copy — matched by these patterns
COPY_SUFFIXES = (
    '_Application.pdf',
    '_Report_',
)

def should_copy(filename):
    """Return True if this file should be migrated."""
    for suffix in COPY_SUFFIXES:
        if suffix in filename:
            return True
    return False

def extract_grant_id(folder_name):
    """Extract GG1234567 from folder name like GG1234567_Some Title_2019."""
    parts = folder_name.split('_')
    if parts:
        return parts[0]
    return None

def migrate(dry_run=False, overwrite=False):
    if not os.path.isdir(SOURCE_DIR):
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        return

    if not os.path.isdir(PROJECTS_DIR):
        print(f"ERROR: projects/ directory not found. Run from ~/rcla_project_map/")
        return

    source_folders = sorted(os.listdir(SOURCE_DIR))
    gg_folders     = [f for f in source_folders if f.startswith('GG')]
    skipped_dg     = [f for f in source_folders if f.startswith('DG')]

    print(f"Found {len(gg_folders)} GG grant folders, skipping {len(skipped_dg)} DG folders.\n")

    total_copied  = 0
    total_skipped = 0
    unmatched     = []

    for folder_name in gg_folders:
        grant_id    = extract_grant_id(folder_name)
        source_path = os.path.join(SOURCE_DIR, folder_name)
        dest_path   = os.path.join(PROJECTS_DIR, grant_id)

        # Check destination folder exists
        if not os.path.isdir(dest_path):
            print(f"  UNMATCHED: {grant_id} — no projects/{grant_id}/ folder found")
            unmatched.append(grant_id)
            continue

        # Find files to copy
        try:
            files = sorted(os.listdir(source_path))
        except PermissionError:
            print(f"  ERROR: Cannot read {source_path}")
            continue

        to_copy = [f for f in files if should_copy(f)]

        if not to_copy:
            print(f"{grant_id}/ — no files to copy")
            continue

        print(f"{grant_id}/")
        for filename in to_copy:
            src  = os.path.join(source_path, filename)
            dest = os.path.join(dest_path, filename)

            if os.path.exists(dest) and not overwrite:
                print(f"  skip (exists): {filename}")
                total_skipped += 1
                continue

            if dry_run:
                action = 'overwrite' if os.path.exists(dest) else 'copy'
                print(f"  {action} (dry run): {filename}")
            else:
                shutil.copy2(src, dest)
                action = 'overwrote' if os.path.exists(dest) else 'copied'
                print(f"  ✓ {filename}")
                total_copied += 1

    # Summary
    print(f"\n{'='*50}")
    print(f"Copied:  {total_copied} files")
    print(f"Skipped: {total_skipped} files (already exist — use --overwrite to replace)")
    if unmatched:
        print(f"\nUnmatched grant IDs (not in projects/ folder):")
        for uid in unmatched:
            print(f"  {uid}")
        print(f"  These may be grants not yet in RCLA_Projects_v2.csv")

    if dry_run:
        print("\n(dry run — no files were copied)")
        return

    # Run update_manifests to refresh files.json for everything
    print("\nUpdating files.json manifests...")
    try:
        result = subprocess.run(
            ['python3', 'update_manifests.py'],
            capture_output=True, text=True
        )
        print(result.stdout)
        if result.returncode != 0:
            print(f"WARNING: update_manifests.py returned error:\n{result.stderr}")
    except FileNotFoundError:
        print("NOTE: update_manifests.py not found — run it manually to refresh files.json")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migrate grant files to projects/ folder')
    parser.add_argument('--dry-run',   action='store_true', help='Show what would be copied without doing it')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing files')
    args = parser.parse_args()

    migrate(dry_run=args.dry_run, overwrite=args.overwrite)
