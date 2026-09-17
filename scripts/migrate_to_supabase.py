#!/usr/bin/env python3
"""
scripts/migrate_to_supabase.py
------------------------------
Automated migration script to ingest RCLA_Projects_v2.csv and all local media
from projects/ into Supabase PostgreSQL and Storage.
"""

import os
import csv
import json
import mimetypes
import re
from pathlib import Path
import requests

# Load environment variables
ENV_PATH = Path(".env")
env_vars = {}
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

SUPABASE_URL = env_vars.get("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
SERVICE_KEY = env_vars.get("SUPABASE_SERVICE_KEY", "")

if not SERVICE_KEY:
    raise RuntimeError("SUPABASE_SERVICE_KEY not found in .env!")

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json"
}

def infer_project_type(proj_id, p_type):
    if p_type and str(p_type).strip():
        return str(p_type).strip()
    pid = (proj_id or "").upper()
    if pid.startswith("GG"):
        return "Global Grant"
    if pid.startswith("DG"):
        return "District Grant"
    if pid.startswith("C2C") or pid.startswith("CLUB-TO-CLUB"):
        return "Club-to-Club Grant"
    return "Club Direct / Donation"

def parse_int(val):
    if not val:
        return None
    val_str = re.sub(r"[^\d]", "", str(val))
    return int(val_str) if val_str else None

def parse_numeric(val):
    if not val:
        return 0
    val_str = re.sub(r"[^\d.]", "", str(val))
    try:
        return float(val_str) if val_str else 0
    except ValueError:
        return 0

def ensure_bucket_exists(bucket_name="project-media"):
    print(f"Checking storage bucket '{bucket_name}'...")
    check_url = f"{SUPABASE_URL}/storage/v1/bucket/{bucket_name}"
    res = requests.get(check_url, headers=HEADERS)
    if res.status_code == 200:
        print(f"Bucket '{bucket_name}' already exists.")
        return

    print(f"Creating public bucket '{bucket_name}'...")
    create_url = f"{SUPABASE_URL}/storage/v1/bucket"
    payload = {"id": bucket_name, "name": bucket_name, "public": True}
    create_res = requests.post(create_url, headers=HEADERS, json=payload)
    if create_res.status_code not in (200, 201):
        print(f"Warning creating bucket: {create_res.status_code} {create_res.text}")
    else:
        print(f"Bucket '{bucket_name}' created successfully.")

def migrate_csv():
    csv_file = Path("RCLA_Projects_v2.csv")
    if not csv_file.exists():
        csv_file = Path("RCLA_Projects.csv")
    print(f"Reading project data from {csv_file}...")

    with open(csv_file, mode="r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    print(f"Found {len(rows)} projects to migrate.")

    projects_to_insert = []
    for r in rows:
        proj_id = (r.get("id") or r.get("grant_id") or "").strip()
        if not proj_id:
            continue

        lat_val = r.get("position_lat") or ""
        lng_val = r.get("position_lng") or ""

        # Handle combined comma coordinates
        if "," in str(lat_val):
            parts = str(lat_val).split(",")
            lat_val = parts[0].strip()
            lng_val = parts[1].strip()

        try:
            lat = float(lat_val) if lat_val else None
        except ValueError:
            lat = None

        try:
            lng = float(lng_val) if lng_val else None
        except ValueError:
            lng = None

        amount = parse_numeric(r.get("amount") or r.get("budget") or 0)
        p_type = infer_project_type(proj_id, r.get("project_type"))

        record = {
            "id": proj_id,
            "title": (r.get("title") or "Untitled").strip(),
            "project_type": p_type,
            "category": (r.get("category") or "").strip() or "Community Service",
            "status": (r.get("status") or "approved").strip().lower(),
            "start_year": parse_int(r.get("start_year")),
            "end_year": parse_int(r.get("end_year")),
            "budget": amount,
            "position_lat": lat,
            "position_lng": lng,
            "shepherd": (r.get("shepard") or r.get("shepherd") or "").strip(),
            "partner": (r.get("partner") or "").strip(),
            "international_club_name": (r.get("internationalClub_name") or "").strip(),
            "international_club_district": (r.get("internationalClub_district") or "").strip(),
            "beneficiaries": (r.get("beneficiaries") or "").strip(),
            "description": (r.get("description") or "").strip(),
            "narrative": (r.get("narrative") or "").strip()
        }
        projects_to_insert.append(record)

    # Upsert projects into Supabase
    url = f"{SUPABASE_URL}/rest/v1/projects"
    upsert_headers = {
        **HEADERS,
        "Prefer": "resolution=merge-duplicates"
    }

    # Batch in groups of 25
    batch_size = 25
    for i in range(0, len(projects_to_insert), batch_size):
        chunk = projects_to_insert[i:i + batch_size]
        res = requests.post(url, headers=upsert_headers, json=chunk)
        if res.status_code in (200, 201):
            print(f"  Synced projects {i+1} to {min(i+batch_size, len(projects_to_insert))} of {len(projects_to_insert)}")
        else:
            print(f"  Error syncing projects chunk {i}: {res.status_code} {res.text}")

def migrate_links_and_media():
    projects_dir = Path("projects")
    if not projects_dir.exists():
        print("No projects/ directory found, skipping asset migration.")
        return

    print("Scanning projects/ folder for media and links...")
    total_uploaded = 0
    total_links = 0

    for proj_folder in sorted(projects_dir.iterdir()):
        if not proj_folder.is_dir():
            continue
        proj_id = proj_folder.name

        # 1. Read files.json if present
        manifest_path = proj_folder / "files.json"
        manifest = {"files": [], "links": []}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  Warning reading {manifest_path}: {e}")

        # Sync web links
        links = manifest.get("links", [])
        if links:
            # Delete existing links for this project first to avoid duplicates
            requests.delete(f"{SUPABASE_URL}/rest/v1/project_links?project_id=eq.{proj_id}", headers=HEADERS)
            links_payload = []
            for idx, l in enumerate(links):
                if isinstance(l, dict) and l.get("url"):
                    links_payload.append({
                        "project_id": proj_id,
                        "label": l.get("label") or l.get("url"),
                        "url": l.get("url"),
                        "display_order": idx
                    })
            if links_payload:
                res = requests.post(f"{SUPABASE_URL}/rest/v1/project_links", headers=HEADERS, json=links_payload)
                if res.status_code in (200, 201):
                    total_links += len(links_payload)

        # 2. Upload actual files to Supabase Storage
        for file_path in proj_folder.iterdir():
            if not file_path.is_file():
                continue
            if file_path.name in ("files.json", ".DS_Store") or ":Zone.Identifier" in file_path.name:
                continue

            filename = file_path.name
            storage_path = f"{proj_id}/{filename}"

            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"

            ext = file_path.suffix.lower()
            if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
                file_type = "image"
            elif ext in (".mp4", ".mov", ".webm"):
                file_type = "video"
            elif ext in (".pdf", ".doc", ".docx", ".txt"):
                file_type = "document"
            else:
                file_type = "other"

            # Upload binary to Supabase Storage
            upload_url = f"{SUPABASE_URL}/storage/v1/object/project-media/{storage_path}"
            upload_headers = {
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type": mime_type,
                "x-upsert": "true"
            }

            with open(file_path, "rb") as bf:
                file_bytes = bf.read()

            up_res = requests.post(upload_url, headers=upload_headers, data=file_bytes)
            if up_res.status_code in (200, 201):
                public_url = f"{SUPABASE_URL}/storage/v1/object/public/project-media/{storage_path}"
                file_size = len(file_bytes)

                # Upsert into project_assets table
                asset_payload = {
                    "project_id": proj_id,
                    "filename": filename,
                    "file_type": file_type,
                    "mime_type": mime_type,
                    "storage_path": storage_path,
                    "public_url": public_url
                }
                # Check if asset already exists
                del_url = f"{SUPABASE_URL}/rest/v1/project_assets?project_id=eq.{proj_id}&filename=eq.{filename}"
                requests.delete(del_url, headers=HEADERS)

                ins_url = f"{SUPABASE_URL}/rest/v1/project_assets"
                ins_res = requests.post(ins_url, headers=HEADERS, json=asset_payload)
                if ins_res.status_code in (200, 201):
                    total_uploaded += 1
                    print(f"  Uploaded & indexed: {storage_path} ({file_size / 1024:.1f} KB)")
                else:
                    print(f"  Error indexing {storage_path}: {ins_res.status_code} {ins_res.text}")
            else:
                print(f"  Failed upload {storage_path}: {up_res.status_code} {up_res.text}")

    print(f"Asset Migration Complete: Uploaded {total_uploaded} files, Synced {total_links} links.")

if __name__ == "__main__":
    print("=== STARTING SUPABASE MIGRATION ===")
    ensure_bucket_exists("project-media")
    migrate_csv()
    migrate_links_and_media()
    print("=== MIGRATION FINISHED SUCCESSFULLY ===")

