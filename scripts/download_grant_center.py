#!/usr/bin/env python3
"""
scripts/download_grant_center.py
--------------------------------
Downloads Grant Applications, Reports, and Attachments from the legacy Rotary
Grant Center (grants.rotary.org / spc.rotary.org/mygrants) via Playwright.

Saves documents directly into projects/<grant_id>/, updates files.json manifests,
and syncs assets into Supabase Storage ('project-media') and the 'project_assets' table.

Usage:
    python scripts/download_grant_center.py --grant GG2684482 --headless
    python scripts/download_grant_center.py --headless
    python scripts/download_grant_center.py --grant GG2684482 --force
"""

import asyncio
import argparse
import html as html_module
import json
import mimetypes
import os
import re
import sys
from datetime import datetime
from pathlib import Path
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Locate repository root dynamically
REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = REPO_ROOT / "projects"

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

def update_project_manifest(project_folder: Path):
    """Scans project folder and updates files.json while preserving links."""
    manifest_path = project_folder / "files.json"
    existing_links = []
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                existing_links = data.get("links", [])
        except Exception:
            pass

    exclude = {"files.json"}
    files = []
    for entry in sorted(project_folder.iterdir()):
        if entry.is_file() and entry.name not in exclude and not entry.name.startswith(".") and ":Zone.Identifier" not in entry.name:
            files.append(entry.name)

    manifest_data = {
        "files": files,
        "links": existing_links
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2)
    log(f"  ✓ Updated manifest: {manifest_path.name} ({len(files)} files)")

def sync_file_to_supabase(project_id: str, file_path: Path, supabase_url: str, supabase_key: str):
    """Uploads file to Supabase Storage bucket 'project-media' and upserts into project_assets table."""
    if not supabase_url or not supabase_key:
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
        # 1. Upload to storage bucket
        up_url = f"{supabase_url}/storage/v1/object/project-media/{storage_path}"
        up_headers = {
            **headers,
            "Content-Type": mime_type,
            "x-upsert": "true",
        }
        with open(file_path, "rb") as bf:
            up_res = requests.post(up_url, headers=up_headers, data=bf.read(), timeout=40)
        if up_res.status_code not in (200, 201):
            log(f"  Notice: Supabase storage upload HTTP {up_res.status_code} for {file_path.name}")

        # 2. Upsert row in project_assets table
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

        log(f"  ✓ Synced to Supabase: {file_path.name}")
        return True
    except Exception as e:
        log(f"  Supabase sync warning for {file_path.name}: {e}")
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

        # Watch for direct PDF response
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
            log(f"  ✓ {path.name} ({len(direct_pdf_body):,} bytes) [direct]")
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

        # Replay POST using requests with browser session cookies
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
            log(f"  ✓ {path.name} ({len(resp.content):,} bytes)")
            return True

        log("  Response is not a valid PDF")
        return False
    finally:
        if popup:
            try: await popup.close()
            except Exception: pass
        try: await tab.close()
        except Exception: pass

async def save_reports_pdfs(context, grant_page, folder: Path, gn: str, force: bool = False) -> list:
    """Navigate to Reports page (fieldid=1330864), discover all Print links, save each as PDF."""
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
                        log(f"  Found Print links in frame: {frame.url[:60]}")
                        print_links = links
                        break
                except Exception:
                    pass

        log(f"  Print link elements found: {len(print_links)}")
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
            out_path = folder / f"{gn}_Report_{idx:02d}.pdf"
            if out_path.exists() and out_path.stat().st_size > 10000 and not force:
                log(f"  Skipping report {idx} (already exists)")
                continue
            log(f"  Report {idx}: {print_url[:80]}")
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

async def save_supporting_docs(context, grant_page, folder: Path, gn: str) -> list:
    """Navigate to Supporting Documents page (fieldid=1331466), download all attachments."""
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

        log(f"  Found {len(found_links)} supporting document link(s)")
        if found_links:
            cookies = {c["name"]: c["value"] for c in await context.cookies(["https://grants.rotary.org"])}
            for idx, (file_url, label) in enumerate(found_links, 1):
                raw_name = label if label and len(label) > 3 else Path(file_url.split("?")[0]).name
                clean_name = sanitize(raw_name)
                if not any(clean_name.lower().endswith(ext) for ext in [".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".zip"]):
                    clean_name += ".pdf"

                dest = folder / f"{gn}_Attachment_{idx:02d}_{clean_name}"
                if dest.exists() and dest.stat().st_size > 500:
                    continue

                try:
                    r = requests.get(file_url, cookies=cookies, timeout=60)
                    if r.status_code == 200 and len(r.content) > 100:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        dest.write_bytes(r.content)
                        log(f"  ✓ Attachment {idx}: {dest.name} ({len(r.content):,} bytes)")
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
    if out_path.exists() and out_path.stat().st_size > 1000:
        log("  Skipping Excel (already exists)")
        return True

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
            log(f"  ✓ {out_path.name} ({len(resp.content):,} bytes)")
            return True
        return False
    except Exception as e:
        log(f"  Excel fetch error: {e}")
        return False

async def process_grant_page(grant_page, context, gn: str, dest_dir: Path, force: bool = False, sync_supabase: bool = True, sb_url: str = "", sb_key: str = ""):
    """Processes open grant tab: downloads application, reports, attachments, and updates manifests."""
    log(f"\nProcessing grant {gn} -> {dest_dir.name}...")
    dest_dir.mkdir(parents=True, exist_ok=True)
    is_dg = gn.startswith("DG")
    downloaded_files = []

    if is_dg:
        excel_path = dest_dir / f"{gn}_Application.xls"
        if not excel_path.exists() or force:
            if await save_dg_excel(context, grant_page, excel_path):
                downloaded_files.append(excel_path)
    else:
        # 1. Application PDF
        app_path = dest_dir / f"{gn}_Application.pdf"
        if not app_path.exists() or force or app_path.stat().st_size < 10000:
            if await save_grant_pdf(context, grant_page, app_path):
                downloaded_files.append(app_path)
        else:
            log(f"  Skipping Application (already downloaded: {app_path.name})")

        # 2. Report PDFs
        reports = await save_reports_pdfs(context, grant_page, dest_dir, gn, force=force)
        downloaded_files.extend(reports)

        # 3. Supporting Documents
        attachments = await save_supporting_docs(context, grant_page, dest_dir, gn)
        downloaded_files.extend(attachments)

    # Update manifest files.json
    update_project_manifest(dest_dir)

    # Sync to Supabase if configured
    if sync_supabase and sb_url and sb_key and downloaded_files:
        log(f"  Syncing {len(downloaded_files)} newly acquired files to Supabase...")
        for df in downloaded_files:
            sync_file_to_supabase(gn, df, sb_url, sb_key)

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

    # Scroll page to trigger lazy loading
    for _ in range(50):
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(100)
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(1500)
    await dismiss_cookies(page)

async def get_all_grants(page):
    all_grants = {}
    sections = ['Authorization Required', 'Submitted', 'Approved', 'Past Applications']

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
    """Finds grant button matching gn on mygrants and clicks it to open grant tab."""
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

        # Try next page
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
    parser = argparse.ArgumentParser(description="Rotary Grant Application & Report Downloader")
    parser.add_argument("--grant", type=str, default="", help="Specific Grant ID (e.g. GG2684482)")
    parser.add_argument("--force", action="store_true", help="Force re-download even if files exist")
    parser.add_argument("--headless", action="store_true", default=False, help="Run browser headless")
    parser.add_argument("--headful", action="store_true", default=False, help="Run browser with visible UI")
    parser.add_argument("--discover-only", action="store_true", help="Discover and list grants without downloading")
    parser.add_argument("--no-supabase", action="store_true", help="Skip syncing files to Supabase")
    parser.add_argument("--output-dir", type=str, default=str(PROJECTS_DIR), help="Output projects directory")
    args = parser.parse_args()

    print("=" * 65)
    print("  Rotary Grant Center Downloader (Applications & Reports)")
    print("=" * 65)

    email = os.environ.get("ROTARY_EMAIL", "")
    password = os.environ.get("ROTARY_PASSWORD", "")
    supabase_url = os.environ.get("SUPABASE_URL", "https://rqhmsincnmxrgtipvkif.supabase.co")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")

    if not email or not password:
        print("ERROR: ROTARY_EMAIL and ROTARY_PASSWORD environment variables are required.")
        sys.exit(1)

    out_base = Path(args.output_dir).resolve()
    out_base.mkdir(parents=True, exist_ok=True)

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
            for gn, title, year in discovered:
                dest_dir = out_base / gn
                app_file = dest_dir / f"{gn}_Application.pdf"
                if not args.force and app_file.exists() and app_file.stat().st_size > 10000:
                    log(f"  Skipping {gn} (already downloaded)")
                    continue
                to_process.append((gn, title, year))

        log(f"Grants to process: {len(to_process)}")

        for idx, (gn, title, year) in enumerate(to_process, 1):
            log(f"\n[{idx}/{len(to_process)}] Processing {gn} ({year})...")
            try:
                await load_mygrants(page)
                grant_tab = await find_and_click_grant(page, context, gn)
                if not grant_tab:
                    log(f"  Could not open tab for {gn} — skipping")
                    continue

                try:
                    dest_dir = out_base / gn
                    await grant_tab.wait_for_timeout(3000)
                    await process_grant_page(
                        grant_tab,
                        context,
                        gn,
                        dest_dir,
                        force=args.force,
                        sync_supabase=not args.no_supabase,
                        sb_url=supabase_url,
                        sb_key=supabase_key
                    )
                except Exception as pe:
                    log(f"  Error on {gn}: {pe}")
                finally:
                    await grant_tab.close()
            except Exception as e:
                log(f"  Encountered error on {gn}: {e}")

        log("\nDownload process completed.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
