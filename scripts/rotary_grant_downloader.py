#!/usr/bin/env python3
"""
scripts/rotary_grant_downloader.py
----------------------------------
Backward-compatibility wrapper pointing to scripts/download_grant_center.py.
"""
import sys
from pathlib import Path
import runpy

target = Path(__file__).resolve().parent / "download_grant_center.py"
runpy.run_path(str(target), run_name="__main__")
