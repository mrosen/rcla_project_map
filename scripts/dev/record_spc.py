#!/usr/bin/env python3
"""
record_spc.py — Interactive recorder for Rotary Service Project Center (SPC)
Launches a browser, auto-fills login from .env if present, and captures
Playwright trace + network HAR for migration automation.
"""
import asyncio
import os
from pathlib import Path
from playwright.async_api import async_playwright

ENV_PATH = Path("/home/msr/grantcenter/.env")
if not ENV_PATH.exists():
    ENV_PATH = Path(".env")

if ENV_PATH.exists():
    for line in ENV_PATH.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

async def main():
    print("=" * 60)
    print("  LAUNCHING PLAYWRIGHT FOR SERVICE PROJECT CENTER")
    print("=" * 60)
    print("1. A browser window and the Playwright Inspector will open.")
    print("2. Log into My Rotary (credentials from .env are auto-filled).")
    print("3. Navigate to Service Project Center (SPC).")
    print("4. Click 'Add Project' and enter a sample project.")
    print("5. When you finish, simply close the browser window.")
    print("=" * 60 + "\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context(
            record_har_path="spc_traffic.har",
            record_har_mode="minimal"
        )
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)

        page = await context.new_page()

        # Navigate to login
        await page.goto("https://my.rotary.org/en/login", wait_until="domcontentloaded")

        email = os.getenv("ROTARY_EMAIL", "")
        password = os.getenv("ROTARY_PASSWORD", "")

        if email and password:
            try:
                await page.wait_for_selector("#okta-signin-username", timeout=8000)
                await page.fill("#okta-signin-username", email)
                await page.fill("#okta-signin-password", password)
                print("✓ Auto-filled credentials from .env. Click Sign In.")
            except Exception:
                pass

        # Opens the Playwright Inspector window and pauses for user interaction
        await page.pause()

        # Stop tracing and save artifacts
        await context.tracing.stop(path="spc_trace.zip")
        await browser.close()
        print("\n✓ Recording complete! Saved 'spc_trace.zip' and 'spc_traffic.har'.")

if __name__ == "__main__":
    asyncio.run(main())

