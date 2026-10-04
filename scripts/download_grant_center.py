#!/usr/bin/env python3
"""
scripts/download_grant_center.py
--------------------------------
Downloads Grant Applications, Reports, and Attachments from the legacy Rotary
Grant Center (grants.rotary.org / spc.rotary.org/mygrants) via Playwright, and
synchronizes them directly to Supabase Storage ('project-media') and the
'project_assets' PostgreSQL table.

Supabase is the sole source of truth:
- Existing file checks query Supabase project_assets directly.
- Downloaded files upload to Supabase Storage bucket 'project-media'.
- Metadata records are upserted into 'project_assets'.
- No files are written or committed to git.

Usage:
    python scripts/download_grant_center.py --grant GG2684482 --headless
    python scripts/download_grant_center.py --headless
    python scripts/download_grant_center.py --grant GG2684482 --force
"""

import asyncio
import argparse
import html as html_module
import mimetypes
import os
import re
import sys
import tempfile
import shutil
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Locate repository root dynamically
REPO_ROOT = Path(__file__).resolve().parent.parent

# Load environment configuration
load_dotenv(REPO_ROOT / ".env")
load_dotenv(Path.home() / "grantcenter" / ".env")

SPC_LOGIN_URL = "https://my.rotary.org/login?destination=/en/secure/showcase"
MYGRANTS_URL  = "https://spc.rotary.org/mygrants"
GRANTS_BASE   = "https://grants.rotary.org"

# Grants to skip — personal / external to club
EXCLUDE_GRANTS = {
    "GG1528500",  # Sustainable Pediatric Care (personal)
}

PDF_MARGIN = {"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"}

def sanitize(s: str) -> str:
    return re.sub(r'[\/:*?"<>|]+', "_", s).strip()[:80]

def log(s: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {s}", flush=True)

async def dismiss_cookies(page):
    selectors = [
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept All')",
        "#onetrust-accept-btn-handler",
        "button[id*='onetrust']",
    ]
    for sel in selectors:
        try:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                await btn.click()
                await page.wait_for_timeout(800)
                return
        except Exception:
            pass

def get_existing_supabase_assets(project_id: str, supabase_url: str, supabase_key: str) -> set:
    """Queries Supabase project_assets for filenames that already exist for this project."""
    if not supabase_url or not supabase_key:
        return set()

    clean_pid = project_id.upper().replace("-", "").replace(" ", "")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    url = f"{supabase_url}/rest/v1/project_assets?project_id=eq.{clean_pid}&select=filename"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200 and isinstance(r.json(), list):
            return {row.get("filename", "").strip() for row in r.json() if row.get("filename")}
    except Exception as e:
        log(f"  Warning querying Supabase assets for {clean_pid}: {e}")
    return set()

def sync_file_to_supabase(project_id: str, file_path: Path, supabase_url: str, supabase_key: str):
    """Uploads file to Supabase Storage bucket 'project-media' and upserts into project_assets table."""
    if not supabase_url or not supabase_key:
        log("  Warning: Supabase credentials missing. Skipping cloud upload.")
        return False

    clean_pid = project_id.upper().replace("-", "").replace(" ", "")
    storage_path = f"{clean_pid}/{file_path.name}"
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    ext = file_path.suffix.lower()
    f_type = "document" if ext in (".pdf", ".xls", ".xlsx", ".doc", ".docx") else (
        "image" if ext in (".jpg", ".jpeg", ".png", ".webp") else "other"
    )

    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
    }

    try:
        # 1. Upload file blob to Supabase Storage
        up_url = f"{supabase_url}/storage/v1/object/project-media/{storage_path}"
        up_headers = {
            **headers,
            "Content-Type": mime_type,
            "x-upsert": "true",
        }
        with open(file_path, "rb") as bf:
            up_res = requests.post(up_url, headers=up_headers, data=bf.read(), timeout=60)
        if up_res.status_code not in (200, 201):
            log(f"  Storage upload returned HTTP {up_res.status_code} for {file_path.name}")
            return False

        # 2. Upsert metadata row in project_assets table
        pub_url = f"{supabase_url}/storage/v1/object/public/project-media/{storage_path}"
        asset_row = {
            "project_id": clean_pid,
            "filename": file_path.name,
            "file_type": f_type,
            "mime_type": mime_type,
            "storage_path": storage_path,
            "public_url": pub_url,
            "display_order": 1,
        }

        chk_url = f"{supabase_url}/rest/v1/project_assets?project_id=eq.{clean_pid}&filename=eq.{file_path.name}&select=id"
        chk = requests.get(chk_url, headers=headers, timeout=15)
        if chk.status_code == 200 and chk.json():
            existing_id = chk.json()[0]["id"]
            patch_url = f"{supabase_url}/rest/v1/project_assets?id=eq.{existing_id}"
            requests.patch(patch_url, headers=headers, json=asset_row, timeout=15)
        else:
            post_url = f"{supabase_url}/rest/v1/project_assets"
            requests.post(post_url, headers=headers, json=asset_row, timeout=15)

        log(f"  ✓ Synced to Supabase: {file_path.name} ({file_path.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        log(f"  Supabase sync error for {file_path.name}: {e}")
        return False

def extract_print_url(page_source: str) -> str:
    decoded = html_module.unescape(page_source)
    m = re.search(r'btnPrintApplication[^>]*onclick=\'window\.open\("([^"]+)"\)', decoded)
    if m:
        return m.group(1)
    m = re.search(r'window\.open\("(/s_viewpagefield\.jsp\?fieldid=(?:1330825|1331198)[^"]+)"', decoded)
    if m:
        return m.group(1)
    return ""

async def wait_for_pdfwriter_popup(context, timeout_s=30):
    for _ in range(timeout_s * 2):
        await asyncio.sleep(0.5)
        for pg in context.pages:
            if "pdfWriter" in pg.url or "pdfwriter" in pg.url.lower():
                return pg
    return None

async def save_grant_pdf(context, grant_page, path: Path, print_url_override: str = "") -> bool:
    """Open print URL, intercept form submission to pdfWriter, replay with requests."""
    if print_url_override:
        full_print_url = print_url_override
    else:
        page_source = await grant_page.content()
        print_path = extract_print_url(page_source)
        if not print_path:
            log("  No print URL in page source — skipping")
            return False
        full_print_url = print_path if print_path.startswith("http") else GRANTS_BASE + print_path

    log(f"  Opening print URL: {full_print_url[:80]}")

    tab = await context.new_page()
    popup = None
    post_body = None

    try:
        async def handle_new_page(new_page):
            nonlocal post_body
            try:
                cdp2 = await context.new_cdp_session(new_page)
                await cdp2.send("Network.enable")

                def on_request(params):
                    nonlocal post_body
                    url = params.get("request", {}).get("url", "")
                    method = params.get("request", {}).get("method", "")
                    if "pdfWriter" in url and method == "POST":
                        post_body = params.get("request", {}).get("postData", "")

                cdp2.on("Network.requestWillBeSent", on_request)
            except Exception as e:
                log(f"  handle_new_page error: {e}")

        context.on("page", handle_new_page)

        # Inject interceptor script in all frames
        interceptor_js = """
            (function() {
                var _origSubmit = HTMLFormElement.prototype.submit;
                HTMLFormElement.prototype.submit = function() {
                    var action = this.action || '';
                    if (action.indexOf('pdfWriter') !== -1) {
                        try {
                            var data = new URLSearchParams(new FormData(this)).toString();
                            window.top._pdfFormData = data;
                            window._pdfFormData = data;
                        } catch(e) {}
                    }
                    return _origSubmit.apply(this, arguments);
                };
                var _origOpen = window.open;
                window.open = function(url, name, features) {
                    if (url && url.indexOf('pdfWriter') !== -1) {
                        var forms = document.querySelectorAll('form');
                        for (var i = 0; i < forms.length; i++) {
                            try {
                                var data = new URLSearchParams(new FormData(forms[i])).toString();
                                if (data.length > 100) {
                                    window.top._pdfFormData = data;
                                    window._pdfFormData = data;
                                    break;
                                }
                            } catch(e) {}
                        }
                    }
                    return _origOpen.apply(this, arguments);
                };
            })();
        """
        await context.add_init_script(interceptor_js)

        direct_pdf_body = None
        async def on_response(response):
            nonlocal direct_pdf_body
            try:
                ct = response.headers.get("content-type", "")
                if "pdf" in ct and response.status == 200:
                    direct_pdf_body = await response.body()
                    log(f"  Direct PDF response: {len(direct_pdf_body)} bytes from {response.url[:80]}")
            except Exception:
                pass
        tab.on("response", on_response)

        await tab.goto(full_print_url, wait_until="domcontentloaded")
        await tab.wait_for_timeout(3000)

        if direct_pdf_body and direct_pdf_body[:4] == b'%PDF':
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(direct_pdf_body)
            log(f"  ✓ Downloaded {path.name} ({len(direct_pdf_body):,} bytes) [direct]")
            return True

        log("  Waiting for pdfWriter popup...")
        popup = await wait_for_pdfwriter_popup(context, timeout_s=30)
        if not popup:
            if "pdfWriter" in tab.url.lower():
                popup = tab
            else:
                log(f"  No popup appeared — tab url: {tab.url[:80]}")
                return False

        log(f"  Got popup: {popup.url[:80]}")
        await popup.wait_for_timeout(2000)

        if not post_body:
            post_body = await tab.evaluate("() => window._pdfFormData || ''")
            if not post_body:
                for frame in tab.frames:
                    try:
                        data = await frame.evaluate("() => window._pdfFormData || ''")
                        if data:
                            post_body = data
                            break
                    except Exception:
                        pass
            log(f"  Intercepted form data: {len(post_body or '')} chars")

        if not post_body:
            log("  No POST body captured — skipping")
            return False

        cookies = {c["name"]: c["value"] for c in await context.cookies(["https://grants.rotary.org"])}
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": full_print_url,
            "Origin": "https://grants.rotary.org",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
        }
        log(f"  Replaying POST ({len(post_body)} chars)...")
        resp = requests.post(
            "https://grants.rotary.org/pdfWriter",
            data=post_body,
            cookies=cookies,
            headers=headers,
            timeout=60
        )
        ct = resp.headers.get("content-type", "?")
        log(f"  Response: {resp.status_code} {ct} {len(resp.content)} bytes")

        if resp.content[:4] == b'%PDF':
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(resp.content)
            log(f"  ✓ Downloaded {path.name} ({len(resp.content):,} bytes)")
            return True

        log("  Response is not a valid PDF")
        return False
    finally:
        if popup:
            try: await popup.close()
            except Exception: pass
        try: await tab.close()
        except Exception: pass

async def save_reports_pdfs(context, grant_page, work_dir: Path, gn: str, existing_assets: set, force: bool = False) -> list:
    """Discover all Report Print links and save newly found ones."""
    m = re.search(r'codedid=([^&\s]+)', grant_page.url)
    if not m:
        log("  No codedid for reports — skipping")
        return []
    codedid = m.group(1)
    reports_url = f"{GRANTS_BASE}/s_viewpagefield.jsp?fieldid=1330864&codedid={codedid}"
    log(f"  Loading reports page...")

    reports_tab = await context.new_page()
    saved = []
    try:
        await reports_tab.goto(reports_url, wait_until="domcontentloaded")
        await reports_tab.wait_for_timeout(8000)

        print_links = await reports_tab.query_selector_all("a:has-text('Print')")
        if not print_links:
            for frame in reports_tab.frames:
                try:
                    links = await frame.query_selector_all("a:has-text('Print')")
                    if links:
                        print_links = links
                        break
                except Exception:
                    pass

        print_urls = []
        for link in print_links:
            try:
                onclick = await link.get_attribute("onclick")
                if onclick:
                    m = re.search(r"window\.open\('([^']+)'", onclick)
                    if m:
                        path_str = html_module.unescape(m.group(1))
                        full = path_str if path_str.startswith("http") else GRANTS_BASE + path_str
                        print_urls.append(full)
            except Exception:
                pass

        log(f"  Found {len(print_urls)} report print link(s)")

        for idx, print_url in enumerate(print_urls, 1):
            report_name = f"{gn}_Report_{idx:02d}.pdf"
            if report_name in existing_assets and not force:
                log(f"  Skipping report {idx} (already in Supabase: {report_name})")
                continue

            out_path = work_dir / report_name
            log(f"  Downloading Report {idx}: {print_url[:80]}")
            try:
                ok = await save_grant_pdf(context, reports_tab, out_path, print_url_override=print_url)
                if ok:
                    saved.append(out_path)
            except Exception as e:
                log(f"  Report {idx} error: {e}")
    finally:
        try: await reports_tab.close()
        except Exception: pass
    return saved

async def save_supporting_docs(context, grant_page, work_dir: Path, gn: str, existing_assets: set, force: bool = False) -> list:
    """Discover all attachment links in Supporting Documents and download them."""
    m = re.search(r'codedid=([^&\s]+)', grant_page.url)
    if not m:
        log("  No codedid for supporting docs — skipping")
        return []
    codedid = m.group(1)
    docs_url = f"{GRANTS_BASE}/s_viewpagefield.jsp?fieldid=1331466&codedid={codedid}"
    log("  Loading supporting documents page...")

    docs_tab = await context.new_page()
    downloaded = []
    try:
        await docs_tab.goto(docs_url, wait_until="domcontentloaded")
        await docs_tab.wait_for_timeout(6000)

        frames = [docs_tab] + docs_tab.frames
        found_links = []

        for frame in frames:
            try:
                anchors = await frame.query_selector_all("a")
                for a in anchors:
                    href = await a.get_attribute("href") or ""
                    onclick = await a.get_attribute("onclick") or ""
                    text = (await a.inner_text() or "").strip()

                    target = ""
                    if any(href.lower().endswith(ext) for ext in [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                        target = href
                    elif "viewfile" in href.lower() or "/files/" in href.lower():
                        target = href
                    elif onclick:
                        m_target = re.search(r"['\"](/files/[^'\"]+|s_viewfile\.jsp[^'\"]+)['\"]", onclick)
                        if m_target:
                            target = m_target.group(1)

                    if target:
                        full_url = target if target.startswith("http") else GRANTS_BASE + ("" if target.startswith("/") else "/") + target
                        found_links.append((full_url, text))
            except Exception:
                pass

        if found_links:
            cookies = {c["name"]: c["value"] for c in await context.cookies(["https://grants.rotary.org"])}
            for idx, (file_url, label) in enumerate(found_links, 1):
                raw_name = label if label and len(label) > 3 else Path(file_url.split("?")[0]).name
                clean_name = sanitize(raw_name)
                if not any(clean_name.lower().endswith(ext) for ext in [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                    clean_name += ".pdf"

                attachment_filename = f"{gn}_Attachment_{idx:02d}_{clean_name}"
                if attachment_filename in existing_assets and not force:
                    log(f"  Skipping attachment {idx} (already in Supabase: {attachment_filename})")
                    continue

                dest = work_dir / attachment_filename
                try:
                    r = requests.get(file_url, cookies=cookies, timeout=60)
                    if r.status_code == 200 and len(r.content) > 100:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(r.content)
                        log(f"  ✓ Downloaded Attachment {idx}: {dest.name} ({len(r.content):,} bytes)")
                        downloaded.append(dest)
                except Exception as de:
                    log(f"  Attachment {idx} download error: {de}")

        return downloaded
    except Exception as e:
        log(f"  Supporting docs error: {e}")
        return []
    finally:
        try: await docs_tab.close()
        except Exception: pass

async def save_dg_excel(context, grant_page, out_path: Path) -> bool:
    """Fetch DG Excel export directly via fieldid=1324761."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    m = re.search(r'codedid=([^&]+)', grant_page.url)
    if not m:
        log("  Could not extract codedid from URL")
        return False
    codedid = m.group(1)

    url = f"{GRANTS_BASE}/s_viewpagefield.jsp?fieldid=1324761&codedid={codedid}"
    log(f"  Fetching DG Excel: {url[:80]}")

    cookies = {c["name"]: c["value"] for c in await context.cookies(["https://grants.rotary.org"])}
    headers = {
        "Referer": grant_page.url,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }
    try:
        resp = requests.get(url, cookies=cookies, headers=headers, timeout=60)
        if resp.status_code == 200 and len(resp.content) > 100:
            out_path.write_bytes(resp.content)
            log(f"  ✓ Downloaded {out_path.name} ({len(resp.content):,} bytes)")
            return True
        return False
    except Exception as e:
        log(f"  Excel fetch error: {e}")
        return False

async def process_grant_page(grant_page, context, gn: str, force: bool = False, sb_url: str = "", sb_key: str = "", local_save_dir: Path = None):
    """Processes open grant tab: checks Supabase, downloads missing files to temp, and uploads straight to Supabase."""
    log(f"\nProcessing grant {gn}...")

    # Query Supabase for existing assets for this grant
    existing_assets = get_existing_supabase_assets(gn, sb_url, sb_key) if not force else set()
    log(f"  Existing Supabase assets for {gn}: {len(existing_assets)} file(s)")

    is_dg = gn.startswith("DG")
    work_dir = Path(tempfile.mkdtemp(prefix=f"grant_{gn}_"))
    downloaded_files = []

    try:
        if is_dg:
            excel_name = f"{gn}_Application.xls"
            if excel_name not in existing_assets or force:
                excel_path = work_dir / excel_name
                if await save_dg_excel(context, grant_page, excel_path):
                    downloaded_files.append(excel_path)
            else:
                log(f"  Skipping DG Excel (already in Supabase: {excel_name})")
        else:
            # 1. Application PDF
            app_name = f"{gn}_Application.pdf"
            if app_name not in existing_assets or force:
                app_path = work_dir / app_name
                if await save_grant_pdf(context, grant_page, app_path):
                    downloaded_files.append(app_path)
            else:
                log(f"  Skipping Application (already in Supabase: {app_name})")

            # 2. Report PDFs
            reports = await save_reports_pdfs(context, grant_page, work_dir, gn, existing_assets=existing_assets, force=force)
            downloaded_files.extend(reports)

            # 3. Supporting Documents
            attachments = await save_supporting_docs(context, grant_page, work_dir, gn, existing_assets=existing_assets, force=force)
            downloaded_files.extend(attachments)

        # Upload downloaded files directly to Supabase Storage & project_assets
        if downloaded_files and sb_url and sb_key:
            log(f"  Uploading {len(downloaded_files)} newly retrieved file(s) to Supabase Storage & project_assets...")
            for df in downloaded_files:
                sync_file_to_supabase(gn, df, sb_url, sb_key)

                # Optional local copy if explicitly requested
                if local_save_dir:
                    dest = local_save_dir / gn / df.name
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(df, dest)
        elif not downloaded_files:
            log(f"  All files for {gn} are already up-to-date in Supabase.")

    finally:
        # Clean up temporary scratch directory
        shutil.rmtree(work_dir, ignore_errors=True)

    return True

async def login(page, email, password):
    log("Logging in to My Rotary...")
    await page.goto(SPC_LOGIN_URL, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await dismiss_cookies(page)

    await page.wait_for_selector("#okta-signin-username, input[name='username']", timeout=30000)
    await page.fill("#okta-signin-username, input[name='username']", email)
    await page.fill("#okta-signin-password, input[type='password']", password)
    await page.click("#okta-signin-submit, input[type='submit']")

    for _ in range(60):
        await page.wait_for_timeout(1000)
        if "spc.rotary.org" in page.url and "frmTicket" not in page.url:
            break
    log("  Logged in successfully.")

async def load_mygrants(page):
    log("  Navigating to Grant Center...")
    await page.goto("https://my.rotary.org/en/domui", wait_until="domcontentloaded")
    await page.wait_for_timeout(2000)
    await dismiss_cookies(page)
    await page.goto("https://spc.rotary.org/grants", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    await dismiss_cookies(page)

    log("  Clicking View My Grants...")
    for _ in range(20):
        btn = await page.query_selector("a:has-text('View My Grants'), button:has-text('View My Grants')")
        if btn:
            await btn.scroll_into_view_if_needed()
            await btn.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(4000)
            break
        await page.wait_for_timeout(1000)
    else:
        log("  Navigating directly to mygrants...")
        await page.goto(MYGRANTS_URL, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)
    await dismiss_cookies(page)

    for _ in range(50):
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(100)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1500)
    await dismiss_cookies(page)

async def get_all_grants(page):
    all_grants = {}

    rows = await page.evaluate("""() => {
        const results = [];
        const trs = document.querySelectorAll('tr.rwc-table__default');
        for (const tr of trs) {
            const span = tr.querySelector('span[class*="rwc-button"]');
            if (!span) continue;
            const gn = span.textContent.trim().toUpperCase();
            if (!/^(GG|DG)[0-9]{5,}$/.test(gn)) continue;
            let title = '', year = '', status = '';
            tr.querySelectorAll('td').forEach(td => {
                const badge = td.querySelector('[data-slot="badge"]');
                if (badge) { status = badge.textContent.trim(); return; }
                const hdr = td.querySelector('.rwc-table__mobile-header');
                const text = hdr ? td.textContent.replace(hdr.textContent, '').trim() : td.textContent.trim();
                const dm = text.match(/^[0-9]{2}\\/[0-9]{2}\\/([0-9]{4})$/);
                if (dm && !year) { year = dm[1]; return; }
                if (/^(GG|DG)[0-9]{5,}$/.test(text)) return;
                if (text.length > 8 && !title) title = text.substring(0, 80);
            });
            results.push({ gn, title, year, status });
        }
        return results;
    }""")

    for r in rows:
        gn = r['gn']
        if gn in all_grants or gn in EXCLUDE_GRANTS:
            continue
        all_grants[gn] = (r['title'], r['year'])
        log(f"    + {gn} ({r['year']}): {r['title'][:50]}")

    return [(gn, t, y) for gn, (t, y) in all_grants.items()]

async def find_and_click_grant(page, context, gn: str):
    for attempt in range(120):
        spans = await page.query_selector_all("span[class*='rwc-button']")
        for span in spans:
            try:
                text = (await span.inner_text()).strip().upper()
                if text == gn:
                    await span.scroll_into_view_if_needed()
                    await page.wait_for_timeout(300)
                    await dismiss_cookies(page)
                    async with context.expect_page() as new_page_info:
                        await span.click()
                    grant_tab = await new_page_info.value
                    await grant_tab.wait_for_load_state("domcontentloaded")
                    return grant_tab
            except Exception:
                pass

        selects = await page.query_selector_all("select.pagination-select")
        advanced = False
        for sel in selects:
            try:
                opts = [await o.get_attribute("value") for o in await sel.query_selector_all("option")]
                cur = await sel.evaluate("el => el.value")
                idx = opts.index(cur) if cur in opts else -1
                if idx >= 0 and idx + 1 < len(opts):
                    await sel.select_option(value=opts[idx + 1])
                    await page.wait_for_timeout(2000)
                    advanced = True
                    break
            except Exception:
                pass
        if not advanced:
            break

    return None

async def main():
    parser = argparse.ArgumentParser(description="Rotary Grant Application & Report Downloader (Direct to Supabase)")
    parser.add_argument("--grant", type=str, default="", help="Specific Grant ID (e.g. GG2684482)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if already in Supabase")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser headless")
    parser.add_argument("--headful", action="store_true", default=False, help="Run browser with visible UI")
    parser.add_argument("--discover-only", action="store_true", help="Discover and list grants without downloading")
    parser.add_argument("--save-local", type=str, default="", help="Optional local directory to save backup copies")
    args = parser.parse_args()

    print("=" * 65)
    print("  Rotary Grant Center Downloader (Supabase Datastore Architecture)")
    print("=" * 65)

    email = os.environ.get("ROTARY_EMAIL", "")
    password = os.environ.get("ROTARY_PASSWORD", "")
    supabase_url = os.environ.get("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")

    if not email or not password:
        print("ERROR: ROTARY_EMAIL and ROTARY_PASSWORD environment variables are required.")
        sys.exit(1)

    local_save_dir = Path(args.save_local).resolve() if args.save_local else None
    target_grant = args.grant.strip().upper()
    is_headless = True if (args.headless or not args.headful) else False

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=is_headless,
            slow_mo=100,
            args=[
                "--disable-extensions",
                "--disable-plugins",
                "--disable-blink-features=AutomationControlled",
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            accept_downloads=True,
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        page = await context.new_page()
        await login(page, email, password)

        log("Loading mygrants for discovery...")
        await load_mygrants(page)

        if args.discover_only:
            grants = await get_all_grants(page)
            log(f"Discovered {len(grants)} grants.")
            await browser.close()
            return

        to_process = []
        if target_grant:
            clean_tg = target_grant.replace("-", "").replace(" ", "")
            log(f"Targeting single grant: {clean_tg}")
            to_process = [(clean_tg, clean_tg, "")]
        else:
            discovered = await get_all_grants(page)
            log(f"Found {len(discovered)} grants on MyGrants.")
            to_process = discovered

        log(f"Grants to evaluate: {len(to_process)}")

        for idx, (gn, title, year) in enumerate(to_process, 1):
            log(f"\n[{idx}/{len(to_process)}] Evaluating {gn} ({year})...")
            try:
                await load_mygrants(page)
                grant_tab = await find_and_click_grant(page, context, gn)
                if not grant_tab:
                    log(f"  Could not open tab for {gn} — skipping")
                    continue

                try:
                    await grant_tab.wait_for_timeout(3000)
                    await process_grant_page(
                        grant_tab,
                        context,
                        gn,
                        force=args.force,
                        sb_url=supabase_url,
                        sb_key=supabase_key,
                        local_save_dir=local_save_dir
                    )
                except Exception as pe:
                    log(f"  Error on {gn}: {pe}")
                finally:
                    await grant_tab.close()
            except Exception as e:
                log(f"  Encountered error on {gn}: {e}")

        log("\nDownload & Supabase synchronization completed successfully.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
