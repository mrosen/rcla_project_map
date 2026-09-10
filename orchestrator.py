#!/usr/bin/env python3
import asyncio
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import git
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

app = FastAPI(title="Rotary Grant Sync & Maintenance Orchestrator")

# Prevent static caching during active development
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_PATH = Path("RCLA_Projects_v2.csv")
if not CSV_PATH.exists():
    CSV_PATH = Path("RCLA_Projects.csv")

GRANTCENTER_DIR = Path.home() / "grantcenter"
LOG_QUEUE: asyncio.Queue = asyncio.Queue()
STATE = {"status": "idle", "last_run": None, "current_step": ""}

async def emit_log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    await LOG_QUEUE.put(formatted)

def git_stage_path(path_to_stage: Path | str):
    """Safely stages a file or folder path in Git."""
    try:
        repo = git.Repo(os.getcwd())
        repo.git.add(str(path_to_stage))
    except Exception as e:
        print(f"Warning: Failed to git add {path_to_stage}: {e}")

def git_remove_path(path_to_remove: Path | str):
    """Safely removes and stages a deleted file path in Git."""
    try:
        repo = git.Repo(os.getcwd())
        repo.git.rm("-f", str(path_to_remove))
    except Exception:
        # Fallback if git wasn't actively tracking it
        if os.path.exists(path_to_remove):
            try:
                os.remove(path_to_remove)
            except Exception:
                pass

async def run_pipeline_task(dry_run: bool = True):
    STATE["status"] = "running"
    STATE["last_run"] = datetime.now().isoformat()
    try:
        STATE["current_step"] = "Discovering Portal Grants"
        await emit_log("Launching portal discovery & reconciliation check...")

        script_path = GRANTCENTER_DIR / "check_grant_sync.py"
        if not script_path.exists():
            await emit_log(f"Discovery script not found at {script_path}. Running mock audit...")
            await asyncio.sleep(2)
            await emit_log("Audit complete (mock).")
        else:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                cwd=str(GRANTCENTER_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=os.environ.copy()
            )
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                text = line.decode("utf-8", errors="replace").rstrip()
                if text:
                    await emit_log(text)
            await proc.wait()
            if proc.returncode != 0:
                raise RuntimeError(f"check_grant_sync.py failed with code {proc.returncode}")

        if dry_run:
            await emit_log("DRY-RUN AUDIT COMPLETE: Review logs above.")
        else:
            await emit_log("Full sync complete. Ready to publish to GitHub.")

        STATE["status"] = "idle"
        STATE["current_step"] = "Complete"
    except Exception as e:
        STATE["status"] = "error"
        STATE["current_step"] = f"Failed: {str(e)}"
        await emit_log(f"ERROR: {str(e)}")

# ==========================================
# API ENDPOINTS
# ==========================================

@app.get("/api/config")
async def get_config():
    return {"mapsApiKey": os.getenv("MAPS_API_KEY", "")}

@app.get("/api/status")
async def get_status():
    return STATE

@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks, dry_run: bool = True):
    if STATE["status"] == "running":
        raise HTTPException(status_code=409, detail="A sync job is already in progress.")
    background_tasks.add_task(run_pipeline_task, dry_run=dry_run)
    return {"message": "Sync initiated", "dry_run": dry_run}

@app.get("/api/logs")
async def stream_logs():
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            log_line = await LOG_QUEUE.get()
            yield f"data: {log_line}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.delete("/api/projects/{project_id}/files/{filename}")
async def delete_project_file(project_id: str, filename: str):
    pdir = Path("projects") / project_id
    target_file = pdir / filename
    manifest_file = pdir / "files.json"

    # 1. Remove file entry from files.json manifest first
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            if filename in data.get("files", []):
                data["files"].remove(filename)
                with open(manifest_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                git_stage_path(manifest_file)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update manifest: {e}")

    # 2. Remove file from disk and stage removal in git
    if target_file.exists():
        git_remove_path(target_file)
    else:
        # Fallback cleanup just in case
        try:
            target_file.unlink(missing_ok=True)
        except Exception:
            pass

    await emit_log(f"Deleted asset '{filename}' from project {project_id} and updated git")
    return {"status": "success", "filename": filename}

@app.get("/api/diff")
async def get_repo_diff():
    try:
        repo = git.Repo(os.getcwd())
        status = repo.git.status(porcelain=True)
        if not status:
            return {"status": "clean", "diff": "", "untracked": [], "summary": "Working tree clean."}

        # Diff modified tracked files against HEAD for CSV and projects/
        try:
            diff_text = repo.git.diff("HEAD", "--", str(CSV_PATH), "projects/")
        except Exception:
            diff_text = repo.git.diff("--", str(CSV_PATH), "projects/")

        # List newly added/untracked files
        untracked = [
            f for f in repo.untracked_files
            if f.startswith("projects/") or f == str(CSV_PATH)
        ]

        return {
            "status": "dirty",
            "diff": diff_text,
            "untracked": untracked,
            "summary": status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Project Creation and Update Models ---

class ProjectCreate(BaseModel):
    id: Optional[str] = None
    title: str
    project_type: Optional[str] = "Club Direct / Donation"
    category: Optional[str] = "Community Service"
    status: Optional[str] = "approved"
    start_year: Optional[str] = None
    amount: Optional[str] = "0"
    shepard: Optional[str] = ""
    partner: Optional[str] = ""
    beneficiaries: Optional[str] = ""
    narrative: Optional[str] = ""
    position_lat: Optional[str] = "14.703454"
    position_lng: Optional[str] = "-91.191623"

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    project_type: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[str] = None
    shepard: Optional[str] = None
    category: Optional[str] = None
    start_year: Optional[str] = None
    narrative: Optional[str] = None
    notes: Optional[str] = None
    partner: Optional[str] = None
    beneficiaries: Optional[str] = None
    position_lat: Optional[str] = None
    position_lng: Optional[str] = None

@app.post("/api/projects")
async def create_project(project: ProjectCreate):
    if not CSV_PATH.exists():
        raise HTTPException(status_code=500, detail="CSV file not found.")

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
        fieldnames = list(reader[0].keys()) if reader else []

    if "project_type" not in fieldnames:
        fieldnames.append("project_type")

    proj_id = (project.id or "").strip()
    if not proj_id:
        safe_title = re.sub(r'[^a-zA-Z0-9]', '', project.title.title())[:20]
        year = project.start_year or datetime.now().year
        proj_id = f"CLUB_{year}_{safe_title}"

    for row in reader:
        row_id = (row.get("id") or row.get("grant_id") or "").strip()
        if row_id.upper() == proj_id.upper():
            raise HTTPException(status_code=400, detail=f"Project ID '{proj_id}' already exists.")

    new_row = {fn: "" for fn in fieldnames}
    payload_dict = project.model_dump()
    payload_dict["id"] = proj_id
    if not payload_dict.get("start_year"):
        payload_dict["start_year"] = str(datetime.now().year)

    for k, v in payload_dict.items():
        if k in new_row:
            new_row[k] = str(v) if v is not None else ""
        elif k == "shepard" and "shepherd" in new_row:
            new_row["shepherd"] = str(v)
        elif k == "amount" and "budget" in new_row:
            new_row["budget"] = str(v)

    reader.append(new_row)

    with open(CSV_PATH, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reader)

    # Scaffolding asset directory & blank manifest, then git staging
    pdir = Path("projects") / proj_id
    pdir.mkdir(parents=True, exist_ok=True)
    manifest_file = pdir / "files.json"
    if not manifest_file.exists():
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump({"files": [], "links": []}, f, indent=2)

    git_stage_path(CSV_PATH)
    git_stage_path(pdir)

    await emit_log(f"Created new project [{project.project_type}]: {proj_id} ('{project.title}') and staged in git")
    return {"status": "success", "id": proj_id, "project": new_row}

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, updates: ProjectUpdate):
    if STATE.get("status") == "running":
        raise HTTPException(status_code=423, detail="Cannot update CSV while sync is active.")

    if not CSV_PATH.exists():
        raise HTTPException(status_code=500, detail="CSV file not found.")

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
        fieldnames = list(reader[0].keys()) if reader else []

    if "project_type" not in fieldnames:
        fieldnames.append("project_type")

    updated = False
    new_rows = []
    clean_updates = {k: str(v) for k, v in updates.model_dump().items() if v is not None}

    for row in reader:
        row_id = (row.get("id") or row.get("grant_id") or "").strip()
        if row_id.upper() == project_id.strip().upper():
            for key, val in clean_updates.items():
                if key in row or key in fieldnames:
                    row[key] = val
                elif key == "shepard" and "shepherd" in row:
                    row["shepherd"] = val
                elif key == "amount" and "budget" in row:
                    row["budget"] = val
            updated = True
        new_rows.append(row)

    if not updated:
        raise HTTPException(status_code=404, detail="Project ID not found in CSV.")

    with open(CSV_PATH, mode="w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(new_rows)

    git_stage_path(CSV_PATH)

    await emit_log(f"Updated CSV metadata for project: {project_id} and staged changes")
    return {"status": "success", "id": project_id, "updated": clean_updates}

# --- Manifest & Files Endpoints ---

class WebLink(BaseModel):
    label: str
    url: str

class LinksUpdate(BaseModel):
    links: List[WebLink]

@app.put("/api/projects/{project_id}/links")
async def update_project_links(project_id: str, payload: LinksUpdate):
    pdir = Path("projects") / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    manifest_file = pdir / "files.json"

    data = {"files": [], "links": []}
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    data["links"] = [link.model_dump() for link in payload.links]
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    git_stage_path(manifest_file)

    await emit_log(f"Updated web links manifest for project: {project_id} and staged in git")
    return {"status": "success", "links": data["links"]}

@app.post("/api/projects/{project_id}/upload")
async def upload_project_file(project_id: str, file: UploadFile = File(...)):
    pdir = Path("projects") / project_id
    pdir.mkdir(parents=True, exist_ok=True)
    dest_path = pdir / file.filename

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    manifest_file = pdir / "files.json"
    data = {"files": [], "links": []}
    if manifest_file.exists():
        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass

    if file.filename not in data.get("files", []):
        data.setdefault("files", []).append(file.filename)
        with open(manifest_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # Automatically stage both the uploaded asset file and the updated manifest file
    git_stage_path(dest_path)
    git_stage_path(manifest_file)

    await emit_log(f"Uploaded asset '{file.filename}' to project {project_id} and staged in git")
    return {"status": "success", "filename": file.filename}

# --- Git Publishing ---

class PublishPayload(BaseModel):
    branch: str = "main"
    message: str = "chore(sync): project and grant data updates"

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/publish")
async def git_publish(payload: PublishPayload):
    try:
        repo = git.Repo(os.getcwd())
        status = repo.git.status(porcelain=True)
        if not status:
            return {"status": "clean", "message": "No changes to commit."}

        current_branch = repo.active_branch.name
        await emit_log(f"Git: Staging changes on branch '{current_branch}'...")
        repo.git.add("projects/", str(CSV_PATH))
        repo.git.commit("-m", payload.message)

        await emit_log(f"Git: Committed: '{payload.message}' on {current_branch}")
        return {"status": "success", "branch": current_branch, "commit": payload.message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Static serving for app
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
