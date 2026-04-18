#!/usr/bin/env python3
"""
sync_narratives.py
------------------
Reads SUMMARY.md files from ~/grantcenter/rotary_grants/ and writes
their content into the 'narrative' column of RCLA_Projects_v2.csv.

Rules:
- Only populates rows where narrative is currently empty
- Use --overwrite to replace existing narratives
- Use --id GG1234567 to sync a single grant
- Reports which grants have no matching SUMMARY.md

Usage:
    cd ~/rcla_project_map
    python3 sync_narratives.py
    python3 sync_narratives.py --dry-run
    python3 sync_narratives.py --overwrite
    python3 sync_narratives.py --id GG2091778
"""

import os
import csv
import argparse

SOURCE_DIR = os.path.expanduser('~/grantcenter/rotary_grants')
CSV_PATH   = 'RCLA_Projects_v2.csv'

def find_summary(grant_id):
    """Find SUMMARY.md for a given grant ID by scanning source folders."""
    try:
        folders = os.listdir(SOURCE_DIR)
    except FileNotFoundError:
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        return None

    for folder in folders:
        if folder.startswith(grant_id + '_') or folder == grant_id:
            summary_path = os.path.join(SOURCE_DIR, folder, 'SUMMARY.md')
            if os.path.exists(summary_path):
                return summary_path
    return None

def read_summary(path):
    """Read and return SUMMARY.md content, stripping trailing whitespace."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()

def sync(dry_run=False, overwrite=False, only_id=None):
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: {CSV_PATH} not found. Run from ~/rcla_project_map/")
        return

    # Read CSV
    with open(CSV_PATH, 'r', encoding='utf-8', newline='') as f:
        reader    = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows      = list(reader)

    if 'narrative' not in fieldnames:
        print("ERROR: 'narrative' column not found in CSV.")
        return

    updated   = 0
    skipped   = 0
    not_found = []
    no_pdf    = []

    for row in rows:
        grant_id = row['id']

        # Filter to single ID if requested
        if only_id and grant_id != only_id:
            continue

        # Skip non-GG grants — no SUMMARY.md exists for these
        if not grant_id.startswith('GG'):
            no_pdf.append(grant_id)
            continue

        # Skip if already has narrative and not overwriting
        if row['narrative'] and row['narrative'].strip() and not overwrite:
            print(f"  skip (has narrative): {grant_id}")
            skipped += 1
            continue

        # Find the SUMMARY.md
        summary_path = find_summary(grant_id)
        if not summary_path:
            print(f"  NOT FOUND: {grant_id} — no SUMMARY.md in rotary_grants/")
            not_found.append(grant_id)
            continue

        content = read_summary(summary_path)

        if dry_run:
            action = 'overwrite' if row['narrative'] else 'populate'
            print(f"  {action} (dry run): {grant_id} — {len(content)} chars from {os.path.basename(os.path.dirname(summary_path))}")
        else:
            row['narrative'] = content
            action = 'overwrote' if row.get('narrative') else 'populated'
            print(f"  ✓ {grant_id} — {len(content)} chars")
            updated += 1

    # Write CSV back
    if not dry_run and updated > 0:
        with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n✓ Wrote {CSV_PATH}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Updated:  {updated}")
    print(f"Skipped:  {skipped} (already have narratives — use --overwrite to replace)")
    if not_found:
        print(f"\nNo SUMMARY.md found for:")
        for gid in not_found:
            print(f"  {gid}")
    if no_pdf:
        print(f"\nNon-GG grants (no pipeline summaries — edit narrative manually):")
        for gid in no_pdf:
            print(f"  {gid}")
    if dry_run:
        print("\n(dry run — CSV was not modified)")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sync SUMMARY.md files into CSV narrative column')
    parser.add_argument('--dry-run',   action='store_true', help='Show what would change without writing')
    parser.add_argument('--overwrite', action='store_true', help='Replace existing narratives')
    parser.add_argument('--id',        metavar='GRANT_ID',  help='Sync a single grant ID only')
    args = parser.parse_args()

    sync(dry_run=args.dry_run, overwrite=args.overwrite, only_id=args.id)
