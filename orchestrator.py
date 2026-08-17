import asyncio
import os
import shutil
from datetime import datetime
from typing import AsyncGenerator
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import git

# Load local environment variables from .env
load_dotenv()

app = FastAPI(title="Rotary Grant Sync Orchestrator")

# Prevent static file caching during local iteration
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Enable CORS for local cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_QUEUE: asyncio.Queue = asyncio.Queue()
STATE = {"status": "idle", "last_run": None, "current_step": ""}

async def emit_log(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    await LOG_QUEUE.put(formatted)

import sys

import sys
import os
import asyncio
from pathlib import Path

GRANTCENTER_DIR = Path.home() / "grantcenter"

async def run_pipeline_task(dry_run: bool = False):
    STATE["status"] = "running"
    STATE["last_run"] = datetime.now().isoformat()
    try:
        STATE["current_step"] = "Discovering Portal Grants"
        await emit_log("Launching portal discovery & reconciliation check...")

        script_path = GRANTCENTER_DIR / "check_grant_sync.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Script not found at {script_path}")

        # Launch child process with active environment (for ROTARY_EMAIL / ROTARY_PASSWORD)
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
            raise RuntimeError(f"check_grant_sync.py exited with code {proc.returncode}")

        if dry_run:
            await emit_log("DRY-RUN AUDIT COMPLETE: Review log output above.")
        else:
            await emit_log("Full sync routine completed.")

        STATE["status"] = "idle"
        STATE["current_step"] = "Complete"
    except Exception as e:
        STATE["status"] = "error"
        STATE["current_step"] = f"Failed: {str(e)}"
        await emit_log(f"ERROR: {str(e)}")

# --- API Endpoints ---

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
    return {"message": "Sync job initiated", "dry_run": dry_run}

@app.get("/api/logs")
async def stream_logs():
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            log_line = await LOG_QUEUE.get()
            yield f"data: {log_line}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

class PublishPayload(BaseModel):
    branch: str = "main"
    message: str = "chore(sync): automated grant sync"

@app.post("/api/publish")
async def git_publish(payload: PublishPayload):
    try:
        repo = git.Repo(os.getcwd())
        status = repo.git.status(porcelain=True)
        if not status:
            return {"status": "clean", "message": "No staged or unstaged changes to commit."}

        current_branch = repo.active_branch.name
        await emit_log(f"Git: Staging changes on branch '{current_branch}'...")
        repo.git.add("projects/", "RCLA_Projects_v2.csv")
        repo.git.commit("-m", payload.message)
        
        await emit_log(f"Git: Changes committed locally on '{current_branch}'.")
        return {"status": "success", "branch": current_branch, "commit": payload.message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount root directory for static serving
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
