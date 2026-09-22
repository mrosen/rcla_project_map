#!/usr/bin/env python3
"""
orchestrator.py — Rotary Grant Sync & Integration Orchestrator
--------------------------------------------------------------
Provides backend services for the Rotary Club of Lake Atitlán Project Map:
- Static web server with development no-cache headers
- Supabase Cloud health and diagnostics
- Rotary Grant Center discovery & synchronization
- Rotary Service Project Center (SPC) export automation
- Real-time Server-Sent Events (SSE) log streaming
"""

import asyncio
from collections import deque
import json
import mimetypes
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, List, Optional

import fitz  # PyMuPDF
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# Load environment configuration
load_dotenv()

app = FastAPI(
    title="Rotary Grant Sync & Integration Orchestrator",
    description="Integration API for Supabase, Rotary Grant Center, and Service Project Center",
    version="2.0.0"
)

# Force no-cache headers in development so changes to assets reload instantly
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
GRANTCENTER_DIR = Path(os.getenv("GRANTCENTER_DIR", str(Path.home() / "grantcenter")))

# Global state, log buffer & subscribers
LOG_BUFFER: deque = deque(maxlen=500)
SUBSCRIBERS: set[asyncio.Queue] = set()
STATE = {
    "status": "idle",       # "idle", "running", "error"
    "task": None,           # "grantcenter_sync", "spc_export"
    "last_run": None,
    "current_step": "Ready"
}

async def emit_log(message: str):
    """Sends a timestamped message to console, memory buffer, and all SSE subscriber queues."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    LOG_BUFFER.append(formatted)
    for q in list(SUBSCRIBERS):
        try:
            await q.put(formatted)
        except Exception:
            pass

# ==========================================
# DIAGNOSTICS & STATUS
# ==========================================

@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "rcla-orchestrator",
        "version": "2.0.0"
    }

@app.get("/api/status")
async def get_status():
    return STATE

@app.get("/api/logs")
async def stream_logs(request: Request):
    q: asyncio.Queue = asyncio.Queue()
    SUBSCRIBERS.add(q)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Replay recent log buffer so newly opened or reconnected log consoles immediately see context
            for past_line in list(LOG_BUFFER):
                yield f"data: {past_line}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    log_line = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {log_line}\n\n"
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            SUBSCRIBERS.discard(q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@app.get("/api/logs/history")
async def get_log_history():
    """Returns the recent history of log lines as a JSON array."""
    return {"logs": list(LOG_BUFFER)}

@app.get("/api/supabase/status")
async def get_supabase_status():
    """Checks live connectivity and counts in Supabase Cloud."""
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if not key:
        return {"connected": False, "error": "No Supabase API key configured."}

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Prefer": "count=exact"
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Query projects count
            p_res = await client.get(
                f"{SUPABASE_URL}/rest/v1/projects?select=id",
                headers=headers
            )
            # Query assets count
            a_res = await client.get(
                f"{SUPABASE_URL}/rest/v1/project_assets?select=id",
                headers=headers
            )

        projects_count = len(p_res.json()) if p_res.status_code == 200 else None
        assets_count = len(a_res.json()) if a_res.status_code == 200 else None

        return {
            "connected": p_res.status_code == 200,
            "supabase_url": SUPABASE_URL,
            "projects_count": projects_count,
            "assets_count": assets_count,
            "status_code": p_res.status_code
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "supabase_url": SUPABASE_URL
        }

# ==========================================
# GRANT CENTER INTEGRATION
# ==========================================

class GrantCenterSyncPayload(BaseModel):
    dry_run: bool = True
    grant_ids: Optional[List[str]] = None
    import_attachments: bool = True

async def run_grantcenter_sync(payload: GrantCenterSyncPayload):
    STATE["status"] = "running"
    STATE["task"] = "grantcenter_sync"
    STATE["last_run"] = datetime.now().isoformat()
    STATE["current_step"] = "Checking Grant Center Source"
    dry_run = payload.dry_run

    try:
        await emit_log(f"Starting Grant Center sync (Dry Run: {dry_run})...")

        script_path = GRANTCENTER_DIR / "check_grant_sync.py"
        if not script_path.exists():
            await emit_log(f"Notice: Grant Center script not found at {script_path}.")
            await emit_log("Running Supabase catalog reconciliation check...")
            await asyncio.sleep(1)
            # Reconcile directly with Supabase
            key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
            headers = {"apikey": key, "Authorization": f"Bearer {key}"}
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{SUPABASE_URL}/rest/v1/projects?select=id,title,grant_id,status", headers=headers)
                if res.status_code == 200:
                    projects = res.json()
                    await emit_log(f"Supabase contains {len(projects)} registered projects.")
                    gg_count = sum(1 for p in projects if str(p.get('id', '')).startswith('GG'))
                    await emit_log(f"Found {gg_count} Global Grants in active catalog.")
                else:
                    await emit_log(f"Supabase response code: {res.status_code}")
        else:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-u",
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
                raise RuntimeError(f"check_grant_sync.py returned exit code {proc.returncode}")

        mode_text = "DRY RUN AUDIT COMPLETE" if dry_run else "GRANT CENTER SYNC COMPLETE"
        await emit_log(f"✓ {mode_text}.")
        STATE["status"] = "idle"
        STATE["task"] = None
        STATE["current_step"] = "Complete"
    except Exception as e:
        STATE["status"] = "error"
        STATE["current_step"] = f"Failed: {str(e)}"
        await emit_log(f"ERROR: {str(e)}")

@app.post("/api/grantcenter/sync")
@app.post("/api/sync")
async def trigger_grantcenter_sync(
    background_tasks: BackgroundTasks,
    dry_run: bool = True,
    payload: Optional[GrantCenterSyncPayload] = None
):
    if STATE["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Job already running: {STATE.get('task')}")

    if payload is None:
        payload = GrantCenterSyncPayload(dry_run=dry_run)

    background_tasks.add_task(run_grantcenter_sync, payload)
    return {"message": "Grant Center sync initiated", "dry_run": payload.dry_run}

# ==========================================
# SERVICE PROJECT CENTER (SPC) EXPORT
# ==========================================

class SPCExportPayload(BaseModel):
    dry_run: bool = True
    project_ids: Optional[List[str]] = None
    spc_username: Optional[str] = None
    spc_password: Optional[str] = None

async def run_spc_export(payload: SPCExportPayload):
    STATE["status"] = "running"
    STATE["task"] = "spc_export"
    STATE["last_run"] = datetime.now().isoformat()
    STATE["current_step"] = "Launching SPC Automation"
    dry_run = payload.dry_run

    try:
        await emit_log(f"Initiating SPC Export task (Dry Run: {dry_run})...")

        script_path = Path("scripts") / "migrate_to_spc.py"
        if not script_path.exists():
            raise FileNotFoundError(f"Migration script not found at {script_path}")

        env = os.environ.copy()
        if payload.spc_username:
            env["ROTARY_USERNAME"] = payload.spc_username
        if payload.spc_password:
            env["ROTARY_PASSWORD"] = payload.spc_password
        if dry_run:
            env["SPC_DRY_RUN"] = "true"

        cmd = [sys.executable, "-u", str(script_path)]
        if dry_run:
            cmd.append("--dry-run")
        if payload.project_ids:
            cmd.extend(payload.project_ids)

        await emit_log(f"Spawning SPC worker: {' '.join(cmd)}...")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
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
            raise RuntimeError(f"SPC migration script exited with code {proc.returncode}")

        await emit_log("✓ SPC export task finished successfully.")
        target_pid = payload.project_ids[0] if (payload.project_ids and len(payload.project_ids) == 1) else None
        await sync_spc_state_to_supabase(target_pid)
        await emit_log("✓ Synced SPC export state and archive record links to Supabase.")
        STATE["status"] = "idle"
        STATE["task"] = None
        STATE["current_step"] = "Complete"
    except Exception as e:
        STATE["status"] = "error"
        STATE["current_step"] = f"Failed: {str(e)}"
        await emit_log(f"ERROR: {str(e)}")

async def sync_spc_state_to_supabase(project_id: Optional[str] = None):
    """Syncs spc_migration_state.json records to Supabase projects.sync_status and project_links."""
    spc_state_file = Path("spc_migration_state.json")
    if not spc_state_file.exists():
        return
    try:
        with open(spc_state_file, "r", encoding="utf-8") as f:
            raw_spc = json.load(f)
            spc_data = raw_spc.get("projects", raw_spc)
    except Exception as e:
        print(f"Error reading spc_migration_state.json: {e}")
        return

    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    targets = {project_id: spc_data[project_id]} if (project_id and project_id in spc_data) else spc_data

    async with httpx.AsyncClient(timeout=15.0) as client:
        for pid, info in targets.items():
            spc_id = info.get("spc_id")
            if not spc_id:
                continue
            spc_url = info.get("spc_url") or f"https://spc.rotary.org/project?guid={spc_id}"
            if "/project/detail/" in spc_url:
                spc_url = spc_url.replace("/project/detail/", "/project?guid=")
            migrated_at = info.get("migrated_at")

            # 1. Update projects.sync_status
            try:
                r = await client.get(f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}&select=id,sync_status", headers=headers)
                if r.status_code == 200 and r.json():
                    row = r.json()[0]
                    sync_status = row.get("sync_status") or {}
                    spc_status = sync_status.get("spc") or {}
                    spc_status.update({
                        "exported": True,
                        "in_sync": True,
                        "spc_project_id": spc_id,
                        "spc_url": spc_url,
                        "last_exported": migrated_at
                    })
                    sync_status["spc"] = spc_status

                    await client.patch(
                        f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}",
                        headers=headers,
                        json={"sync_status": sync_status}
                    )

                # 2. Add or update link in project_links
                lr = await client.get(f"{SUPABASE_URL}/rest/v1/project_links?project_id=eq.{pid}", headers=headers)
                existing_links = lr.json() if lr.status_code == 200 else []
                spc_link = next((l for l in existing_links if "spc.rotary.org" in (l.get("url") or "") or l.get("label") == "Rotary Service Project Center (SPC)"), None)
                if spc_link:
                    await client.patch(
                        f"{SUPABASE_URL}/rest/v1/project_links?id=eq.{spc_link['id']}",
                        headers=headers,
                        json={"url": spc_url, "label": "Rotary Service Project Center (SPC)"}
                    )
                else:
                    await client.post(
                        f"{SUPABASE_URL}/rest/v1/project_links",
                        headers=headers,
                        json={
                            "project_id": pid,
                            "label": "Rotary Service Project Center (SPC)",
                            "url": spc_url,
                            "display_order": len(existing_links)
                        }
                    )
            except Exception as ex:
                print(f"Error syncing SPC to Supabase for {pid}: {ex}")

@app.post("/api/spc/export")
async def trigger_spc_export(
    background_tasks: BackgroundTasks,
    dry_run: bool = True,
    payload: Optional[SPCExportPayload] = None
):
    if STATE["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Job already running: {STATE.get('task')}")

    if payload is None:
        payload = SPCExportPayload(dry_run=dry_run)

    background_tasks.add_task(run_spc_export, payload)
    return {"message": "SPC export initiated", "dry_run": payload.dry_run}

# ==========================================
# INDIVIDUAL PROJECT INTEGRATION & AI ENDPOINTS
# ==========================================

class SynthesizePayload(BaseModel):
    source: str = "pdf"  # "pdf" or "notes"
    notes_text: Optional[str] = None
    api_key: Optional[str] = None
    project_type: Optional[str] = None
    model: Optional[str] = None

@app.get("/api/projects/{project_id}/sync-status")
async def get_project_sync_status(project_id: str):
    """Retrieves RI file presence and SPC export status for a given project."""
    pid = project_id.strip()
    key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}

    has_app_pdf = False
    app_pdf_name = None
    report_names = []
    total_assets = 0

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{SUPABASE_URL}/rest/v1/project_assets?project_id=eq.{pid}&select=filename,file_type",
                headers=headers
            )
            if res.status_code == 200:
                assets = res.json()
                total_assets = len(assets)
                for a in assets:
                    fn = (a.get("filename") or "").lower()
                    if "application" in fn and fn.endswith(".pdf"):
                        has_app_pdf = True
                        app_pdf_name = a.get("filename")
                    elif "report" in fn and fn.endswith(".pdf"):
                        report_names.append(a.get("filename"))
    except Exception as e:
        print(f"Error querying project_assets: {e}")

    # Check local grant folder
    local_folder_exists = False
    local_files = []
    if GRANTCENTER_DIR.exists():
        grants_dir = GRANTCENTER_DIR / "rotary_grants"
        if grants_dir.exists():
            for folder in grants_dir.iterdir():
                if folder.is_dir() and folder.name.upper().startswith(pid.upper()):
                    local_folder_exists = True
                    local_files = [f.name for f in folder.iterdir() if f.is_file() and not f.name.startswith(".") and ":Zone.Identifier" not in f.name]
                    for f in local_files:
                        fn_lower = f.lower()
                        if "application" in fn_lower and fn_lower.endswith(".pdf"):
                            if not has_app_pdf:
                                has_app_pdf = True
                                app_pdf_name = f
                        elif "report" in fn_lower and fn_lower.endswith(".pdf"):
                            if f not in report_names:
                                report_names.append(f)
                    break

    # Check local projects folder
    local_proj_dir = Path("projects") / pid
    if local_proj_dir.exists() and local_proj_dir.is_dir():
        for f in local_proj_dir.iterdir():
            if f.is_file() and not f.name.startswith(".") and ":Zone.Identifier" not in f.name:
                fn_lower = f.name.lower()
                if "application" in fn_lower and fn_lower.endswith(".pdf"):
                    if not has_app_pdf:
                        has_app_pdf = True
                        app_pdf_name = f.name
                elif "report" in fn_lower and fn_lower.endswith(".pdf"):
                    if f.name not in report_names:
                        report_names.append(f.name)

    # Check SPC state file
    spc_exported = False
    spc_id = None
    last_exported = None
    spc_url = None
    spc_state_file = Path("spc_migration_state.json")
    if spc_state_file.exists():
        try:
            with open(spc_state_file, "r", encoding="utf-8") as f:
                raw_spc = json.load(f)
                spc_data = raw_spc.get("projects", raw_spc)
                if pid in spc_data:
                    spc_info = spc_data[pid]
                    spc_id = spc_info.get("spc_id")
                    spc_exported = bool(spc_id)
                    last_exported = spc_info.get("migrated_at") or spc_info.get("created_at")
                    spc_url = spc_info.get("spc_url")
        except Exception:
            pass

    # Check Supabase projects.sync_status fallback
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            proj_res = await client.get(
                f"{SUPABASE_URL}/rest/v1/projects?id=eq.{pid}&select=sync_status",
                headers=headers
            )
            if proj_res.status_code == 200 and proj_res.json():
                ss = proj_res.json()[0].get("sync_status") or {}
                gc_ss = ss.get("grant_center") or {}
                if gc_ss.get("has_application_pdf") and not has_app_pdf:
                    has_app_pdf = True
                if gc_ss.get("report_count") and len(report_names) == 0:
                    report_names = [f"Report_{i+1}.pdf" for i in range(gc_ss.get("report_count"))]
                spc_ss = ss.get("spc") or {}
                if spc_ss.get("exported") and not spc_exported:
                    spc_exported = True
                    spc_id = spc_ss.get("spc_project_id") or spc_id
                    spc_url = spc_ss.get("spc_url") or spc_url
                    last_exported = spc_ss.get("last_exported") or last_exported
    except Exception:
        pass

    if spc_url:
        if "/project/detail/" in spc_url:
            spc_url = spc_url.replace("/project/detail/", "/project?guid=")
    elif spc_id:
        spc_url = f"https://spc.rotary.org/project?guid={spc_id}"

    return {
        "project_id": pid,
        "grant_center": {
            "has_application_pdf": has_app_pdf,
            "application_pdf_name": app_pdf_name,
            "report_count": len(report_names),
            "report_names": report_names,
            "total_assets": total_assets,
            "local_folder_exists": local_folder_exists,
            "local_files_count": len(local_files)
        },
        "spc": {
            "exported": spc_exported,
            "spc_project_id": spc_id,
            "spc_url": spc_url,
            "last_exported": last_exported,
            "in_sync": spc_exported
        }
    }

@app.post("/api/projects/{project_id}/synthesize")
async def synthesize_project_data(project_id: str, payload: SynthesizePayload):
    """Uses Google Gemini to synthesize structured project data from an Application PDF or notes."""
    pid = project_id.strip()
    api_key = payload.api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "GEMINI_API_KEY_REQUIRED",
                "message": "Gemini API key is required. Obtain a free key at https://aistudio.google.com/app/apikey and add GEMINI_API_KEY to .env or supply it in the dialog."
            }
        )

    if genai is None:
        raise HTTPException(status_code=500, detail="google-genai library is not installed on the server.")

    is_global_grant = pid.upper().startswith("GG") or (payload.project_type and "global" in payload.project_type.lower())
    text_content = ""

    if payload.source == "pdf":
        pdf_path = None
        # 1. Check local projects folder
        local_repo_proj = Path("projects") / pid
        if not local_repo_proj.exists():
            for p_dir in Path("projects").iterdir() if Path("projects").exists() else []:
                if p_dir.is_dir() and p_dir.name.upper() == pid.upper():
                    local_repo_proj = p_dir
                    break
        if local_repo_proj.exists() and local_repo_proj.is_dir():
            for f in local_repo_proj.iterdir():
                if "application" in f.name.lower() and f.name.lower().endswith(".pdf"):
                    pdf_path = f
                    break

        # 2. Check local GrantCenter directory
        if not pdf_path and GRANTCENTER_DIR.exists():
            grants_dir = GRANTCENTER_DIR / "rotary_grants"
            if grants_dir.exists():
                for folder in grants_dir.iterdir():
                    if folder.is_dir() and folder.name.upper().startswith(pid.upper()):
                        for f in folder.iterdir():
                            if "application" in f.name.lower() and f.name.lower().endswith(".pdf"):
                                pdf_path = f
                                break
                    if pdf_path:
                        break

        # 3. Fallback to Supabase Storage if not local
        if not pdf_path or not pdf_path.exists():
            key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
            headers = {"apikey": key, "Authorization": f"Bearer {key}"}
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(
                    f"{SUPABASE_URL}/rest/v1/project_assets?project_id=eq.{pid}&filename=ilike.*application*.pdf&select=filename,storage_path,public_url",
                    headers=headers
                )
                if res.status_code == 200 and res.json():
                    asset = res.json()[0]
                    file_url = asset.get("public_url") or f"{SUPABASE_URL}/storage/v1/object/public/project-media/{asset.get('storage_path')}"
                    down_res = await client.get(file_url)
                    if down_res.status_code == 200:
                        temp_pdf = Path(f"/tmp/{pid}_Application.pdf")
                        temp_pdf.write_bytes(down_res.content)
                        pdf_path = temp_pdf

        if not pdf_path or not pdf_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Application PDF not found for {pid}. Please use 'AI Draft from Notes' or fetch the PDF first."
            )

        try:
            doc = fitz.open(str(pdf_path))
            if len(doc) > 6:
                # Smart filter: focus on key grant application sections and omit legal boilerplate
                pages_text = []
                for i, page in enumerate(doc):
                    t = page.get_text()
                    tl = t.lower()
                    if i < 2:  # Cover, basic info, primary contacts, committees
                        pages_text.append(f"--- Page {i+1} ---\n" + t.strip())
                    elif any(k in tl for k in ["total budget", "funding", "cash from club", "world fund", "ddf"]):
                        pages_text.append(f"--- Page {i+1} (Budget/Funding) ---\n" + t.strip())
                    elif any(k in tl for k in ["community need", "project description", "project planning", "sustainability"]):
                        pages_text.append(f"--- Page {i+1} (Project Info) ---\n" + t.strip()[:1800])
                text_content = "\n\n".join(pages_text)
            else:
                pages_text = []
                for i, page in enumerate(doc):
                    pages_text.append(f"--- Page {i+1} ---\n" + page.get_text())
                text_content = "\n".join(pages_text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed reading PDF: {str(e)}")

    elif payload.source == "notes":
        text_content = (payload.notes_text or "").strip()
        if not text_content:
            raise HTTPException(status_code=400, detail="No notes provided for AI synthesis.")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {payload.source}")

    prompt = f"""
You are an expert archivist and project manager for the Rotary Club of Lake Atitlán (RCLA) in Guatemala.
Analyze the following {'Rotary Foundation Grant Application' if payload.source == 'pdf' else 'project notes'} for project '{pid}'.

Extract and generate a clean, strictly formatted JSON response meeting these EXACT criteria:

CRITICAL CONSTRAINTS:
1. "brief_overview": A punchy, compelling summary of what the project accomplished.
   STRICT MAXIMUM LENGTH: 100 CHARACTERS. Count every character carefully. Do not exceed 100 characters.
2. "complete_overview": A comprehensive description of the project purpose, community need, activities, and lasting impact.
   STRICT MAXIMUM LENGTH: 1,000 CHARACTERS. Count every character carefully. Do not exceed 1,000 characters.
3. "start_date": ISO date format (YYYY-MM-DD or YYYY-MM) for when the project was initiated or planned.
4. "end_date": ISO date format (YYYY-MM-DD or YYYY-MM) for when the project was completed (or null if ongoing).
5. "timeline":
   - "backstory": 1-2 paragraphs detailing the background, community relationship, and how the initiative started.
   - "milestones": A chronological list of milestones. Each milestone object must have:
     - "name": Milestone name
     - "date": ISO date (YYYY-MM-DD or YYYY-MM)
     - "notes": Brief note or context
     {'CRITICAL: Since this is a Global Grant, you MUST include a milestone named "Submitted" and a milestone named "Approved", using dates extracted from the document.' if is_global_grant else 'Include natural milestones such as Initiated, Fundraising, Distribution, Completed. Do NOT include formal RI approval steps unless stated.'}
6. "details":
   - "budget": Total numeric project budget in USD (numeric)
   - "world_fund": Rotary Foundation World Fund match in USD (numeric or 0)
   - "district_ddf": District Designated Fund (DDF) in USD (numeric or 0)
   - "club_contributions": Total club cash contributions in USD (numeric or 0)
   - "host_club": Name of the host Rotary club (e.g., "Club Rotario de Lake Atitlán")
   - "host_district": Host district number (e.g., "4250")
   - "international_club": International sponsor Rotary club name
   - "international_district": International district number
   - "partner_clubs": Array of strings of ALL contributing/partner Rotary clubs mentioned anywhere in the application or funding lists (e.g. ["Baltimore", "Carroll Creek", "Petaluma Valley", "Rockville"]). Do NOT break out individual amounts; just list all club names.
   - "partner_districts": Array of strings of ALL contributing/partner districts (e.g. ["7620", "6690"]). Do NOT break out individual amounts; just list all district numbers.
   - "cooperating_organizations": Array of strings of ALL partner NGOs, cooperating organizations, government entities, and community groups (e.g. ["Mayan Families", "AdP", "Hospitalito Atitlán"]).
   - "key_personnel": Array of objects: [{{"name": "...", "role": "..."}}]

DOCUMENT CONTENT:
\"\"\"
{text_content[:18000]}
\"\"\"

Return ONLY valid JSON matching this schema.
"""

    try:
        target_model = payload.model or os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite-preview"
        
        # Candidate models verified available on current key
        candidate_models = []
        for candidate in [
            target_model,
            "gemini-3.1-flash-lite-preview",
            "gemini-3-flash-preview",
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.5-flash-lite"
        ]:
            if candidate and candidate not in candidate_models:
                candidate_models.append(candidate)

        response_text = None
        last_error = None
        used_model = None

        async with httpx.AsyncClient(timeout=45.0) as http_client:
            for m_name in candidate_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m_name}:generateContent?key={api_key}"
                req_body = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": 0.2
                    }
                }
                if "lite" not in m_name.lower() and "gemma" not in m_name.lower():
                    req_body["generationConfig"]["thinkingConfig"] = {
                        "thinkingBudget": 0
                    }
                try:
                    await emit_log(f"Synthesizing with Gemini model: {m_name}...")
                    r = await http_client.post(url, json=req_body)
                    if r.status_code == 200:
                        res_json = r.json()
                        response_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                        used_model = m_name
                        await emit_log(f"✓ AI synthesis completed successfully using {m_name}.")
                        break
                    else:
                        err_msg = r.text
                        try:
                            err_msg = r.json().get("error", {}).get("message", r.text)
                        except Exception:
                            pass
                        last_error = RuntimeError(f"Model {m_name} returned {r.status_code}: {err_msg}")
                        await emit_log(f"Notice: {m_name} returned {r.status_code} ({err_msg[:60]}...). Trying fallback model...")
                except Exception as me:
                    last_error = me
                    await emit_log(f"Notice: {m_name} encountered {type(me).__name__}. Trying fallback model...")

        if response_text is None:
            err_text = str(last_error)
            is_invalid_key = any(k in err_text.lower() for k in ["api key not valid", "invalid api key", "api_key_invalid", "api_key not found"])
            is_quota = "quota" in err_text.lower() or "429" in err_text or "resource_exhausted" in err_text.lower()

            if is_invalid_key:
                err_code = "INVALID_API_KEY"
                status_code = 401
                msg = "The provided Gemini API key is invalid. Please verify or re-generate your key at https://aistudio.google.com/app/apikey."
            elif is_quota:
                err_code = "QUOTA_EXCEEDED"
                status_code = 429
                msg = (
                    "Gemini API free-tier quota (20 requests/day per model) exceeded for today. "
                    "Please provide a fresh Gemini API key or enable billing (Pay-As-You-Go) in Google AI Studio (https://aistudio.google.com/app/apikey)."
                )
            else:
                err_code = "GEMINI_CAPACITY_LIMIT"
                status_code = 503
                msg = (
                    "Google Gemini servers are currently experiencing high demand and shedding free-tier traffic. "
                    "Please try again in a few moments, enter a fresh Gemini API key, or enable Pay-As-You-Go in Google AI Studio (https://aistudio.google.com/app/apikey)."
                )

            raise HTTPException(
                status_code=status_code,
                detail={
                    "error": err_code,
                    "message": msg,
                    "raw_error": err_text
                }
            )

        # If custom key was provided and succeeded, persist it to .env
        if payload.api_key and payload.api_key != os.getenv("GEMINI_API_KEY"):
            try:
                env_path = Path(".env")
                if env_path.exists():
                    lines = []
                    replaced = False
                    for eline in env_path.read_text().splitlines():
                        if eline.startswith("GEMINI_API_KEY="):
                            lines.append(f"GEMINI_API_KEY={payload.api_key}")
                            replaced = True
                        else:
                            lines.append(eline)
                    if not replaced:
                        lines.append(f"GEMINI_API_KEY={payload.api_key}")
                    env_path.write_text("\n".join(lines) + "\n")
                    os.environ["GEMINI_API_KEY"] = payload.api_key
            except Exception:
                pass

        parsed = json.loads(response_text)

        # Enforce character limits strictly as safety net
        if "brief_overview" in parsed and len(parsed["brief_overview"]) > 100:
            parsed["brief_overview"] = parsed["brief_overview"][:97].rsplit(' ', 1)[0] + "..."
        if "complete_overview" in parsed and len(parsed["complete_overview"]) > 1000:
            parsed["complete_overview"] = parsed["complete_overview"][:997].rsplit(' ', 1)[0] + "..."

        return {
            "success": True,
            "project_id": pid,
            "source": payload.source,
            "model_used": used_model,
            "draft": parsed
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini generation error: {str(e)}")

async def run_fetch_ri_files(project_id: str):
    STATE["status"] = "running"
    STATE["task"] = f"fetch_ri_files_{project_id}"
    STATE["last_run"] = datetime.now().isoformat()
    STATE["current_step"] = f"Fetching files from Grant Center for {project_id}"

    try:
        clean_pid = project_id.upper().replace("-", "").replace(" ", "")
        is_ri_grant = clean_pid.startswith("GG") or clean_pid.startswith("DG")
        await emit_log(f"Starting Grant Center sync for {project_id} (normalized: {clean_pid})...")

        # 1. Run live Grant Center downloader via Playwright for RI grants
        downloader_script = GRANTCENTER_DIR / "rotary_grant_downloader.py"
        if is_ri_grant and downloader_script.exists():
            await emit_log(f"Connecting to Rotary Grant Center via Playwright for {project_id}...")
            env = os.environ.copy()
            gc_env = GRANTCENTER_DIR / ".env"
            if gc_env.exists():
                for eline in gc_env.read_text().splitlines():
                    if "=" in eline and not eline.startswith("#"):
                        ek, ev = eline.split("=", 1)
                        env.setdefault(ek.strip(), ev.strip())

            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(downloader_script),
                "--grant", clean_pid,
                "--headless",
                "--force",
                cwd=str(GRANTCENTER_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=env
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
                await emit_log(f"Grant Center downloader exited with status {proc.returncode}")
        elif not is_ri_grant:
            await emit_log(f"Notice: {project_id} is a local/club-direct project (not a Global Grant or District Grant). Skipping RI Grant Center scraper.")
        else:
            await emit_log(f"Notice: Downloader script not found at {downloader_script}.")

        # 2. Reconcile downloaded files into Supabase Storage & project_assets
        key = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}

        local_files_found = []
        grants_dir = GRANTCENTER_DIR / "rotary_grants"
        if grants_dir.exists():
            for folder in grants_dir.iterdir():
                if folder.is_dir() and folder.name.upper().startswith(clean_pid):
                    for f in folder.iterdir():
                        if f.is_file() and not f.name.startswith(".") and ":Zone.Identifier" not in f.name:
                            local_files_found.append(f)
                    break

        if local_files_found:
            await emit_log(f"Staging {len(local_files_found)} downloaded files into Supabase Storage...")
            uploaded_count = 0
            for f in local_files_found:
                storage_path = f"{project_id}/{f.name}"
                mime_type, _ = mimetypes.guess_type(str(f))
                if not mime_type:
                    mime_type = "application/octet-stream"
                ext = f.suffix.lower()
                f_type = "document" if ext == ".pdf" else ("image" if ext in (".jpg", ".jpeg", ".png", ".webp") else "other")

                up_url = f"{SUPABASE_URL}/storage/v1/object/project-media/{storage_path}"
                up_headers = {
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": mime_type,
                    "x-upsert": "true"
                }
                async with httpx.AsyncClient(timeout=30.0) as client:
                    with open(f, "rb") as bf:
                        up_res = await client.post(up_url, headers=up_headers, content=bf.read())
                    if up_res.status_code in (200, 201):
                        pub_url = f"{SUPABASE_URL}/storage/v1/object/public/project-media/{storage_path}"
                        asset_row = {
                            "project_id": project_id,
                            "filename": f.name,
                            "file_type": f_type,
                            "mime_type": mime_type,
                            "storage_path": storage_path,
                            "public_url": pub_url,
                            "display_order": 1
                        }
                        # Safe deduplicated upsert into project_assets
                        chk = await client.get(
                            f"{SUPABASE_URL}/rest/v1/project_assets?project_id=eq.{project_id}&filename=eq.{f.name}&select=id",
                            headers=headers
                        )
                        if chk.status_code == 200 and chk.json():
                            existing_id = chk.json()[0]["id"]
                            await client.patch(
                                f"{SUPABASE_URL}/rest/v1/project_assets?id=eq.{existing_id}",
                                headers=headers,
                                json=asset_row
                            )
                        else:
                            await client.post(
                                f"{SUPABASE_URL}/rest/v1/project_assets",
                                headers=headers,
                                json=asset_row
                            )
                        uploaded_count += 1
                        await emit_log(f"  ✓ Synced to Supabase: {f.name}")
                    else:
                        await emit_log(f"  Upload notice on {f.name}: HTTP {up_res.status_code}")

            await emit_log(f"✓ Successfully synced {uploaded_count} Grant Center files into Supabase Storage.")
        else:
            await emit_log(f"Notice: No files retrieved for {project_id}.")

        STATE["status"] = "idle"
        STATE["task"] = None
        STATE["current_step"] = "Complete"
    except Exception as e:
        STATE["status"] = "error"
        STATE["current_step"] = f"Failed: {str(e)}"
        await emit_log(f"ERROR: {str(e)}")

@app.post("/api/projects/{project_id}/fetch-ri-files")
async def trigger_fetch_ri_files(project_id: str, background_tasks: BackgroundTasks):
    if STATE["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Job already running: {STATE.get('task')}")
    background_tasks.add_task(run_fetch_ri_files, project_id)
    return {"message": f"Fetching RI files for {project_id} initiated"}

@app.post("/api/projects/{project_id}/export-spc")
async def trigger_single_spc_export(
    project_id: str,
    background_tasks: BackgroundTasks,
    dry_run: bool = True
):
    if STATE["status"] == "running":
        raise HTTPException(status_code=409, detail=f"Job already running: {STATE.get('task')}")
    payload = SPCExportPayload(dry_run=dry_run, project_ids=[project_id])
    background_tasks.add_task(run_spc_export, payload)
    return {"message": f"SPC export for {project_id} initiated", "dry_run": dry_run}

# Static file serving
app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_flag = os.getenv("RELOAD", "false").lower() == "true"
    uvicorn_kwargs = {
        "host": host,
        "port": port,
        "reload": reload_flag,
        "timeout_graceful_shutdown": 2
    }
    if reload_flag:
        uvicorn_kwargs["reload_includes"] = ["orchestrator.py"]
    uvicorn.run("orchestrator:app", **uvicorn_kwargs)


