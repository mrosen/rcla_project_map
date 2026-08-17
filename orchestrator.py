#!/usr/bin/env python3
import asyncio
import csv
import json
import os
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

# Load environment configuration
load_dotenv()

app = FastAPI(title="Rotary Grant Sync & Maintenance Orchestrator")

# Prevent static browser caching during development
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Enable CORS for local client connections
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

async def run_pipeline_task(dry_run: bool = True):
    STATE["status"] = "running"
    STATE["last_run"] = datetime.now().isoformat()
    try:
        STATE["current_step"] = "Discovering Portal Grants"
        await emit_log("Launching portal discovery & reconciliation check...")

        script_path = GRANTCENTER_DIR / "check_grant_sync.py"
        if not script_path.exists():
            await emit_log(f"Warning: Discovery script not found at {script_path}. Running mock audit...")
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

# --- Project CSV Update Endpoint ---

class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    amount: Optional[str] = None
    shepard: Optional[str] = None
    category: Optional[str] = None
    start_year: Optional[str] = None
    narrative: Optional[str] = None
    notes: Optional[str] = None
    position_lat: Optional[str] = None
    position_lng: Optional[str] = None

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, updates: ProjectUpdate):
    if STATE.get("status") == "running":
        raise HTTPException(status_code=423, detail="Cannot update CSV while sync is active.")

    if not CSV_PATH.exists():
        raise HTTPException(status_code=500, detail="CSV file not found.")

    with open(CSV_PATH, mode="r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))
        fieldnames = reader[0].keys() if reader else []

    updated = False
    new_rows = []
    clean_updates = {k: str(v) for k, v in updates.model_dump().items() if v is not None}

    # Match ID or grant_id
    for row in reader:
        row_id = (row.get("id") or row.get("grant_id") or "").strip()
        if row_id.upper() == project_id.strip().upper():
            for key, val in clean_updates.items():
                if key in row:
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

    await emit_log(f"Updated CSV metadata for project: {project_id}")
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

    await emit_log(f"Updated web links manifest for project: {project_id}")
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

    await emit_log(f"Uploaded asset '{file.filename}' to project {project_id}")
    return {"status": "success", "filename": file.filename}

# --- Git Publishing ---

class PublishPayload(BaseModel):
    branch: str = "main"
    message: str = "chore(sync): automated grant sync"

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

# Mount root directory for static serving
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
