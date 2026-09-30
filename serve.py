#!/usr/bin/env python3
"""Headless launcher for the Local KB backend, for when another app is the UI.

Mission Control's Knowledge Base tab is that UI: it proxies /api/kb/* to this
server from the Pi, so the API binds to the LAN and answers only the hosts in
KB_ALLOW_CLIENTS. Run by the "kb-server" scheduled task under pythonw, hence
the log file instead of a console.

Environment variables (all optional):
    KB_HOST           Bind address (default 0.0.0.0)
    KB_API_PORT       Port (default 8765)
    KB_ALLOW_CLIENTS  Comma-separated client IPs (default: this PC and the Pi)
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if sys.stdout is None:  # pythonw has no console
    log_dir = ROOT / ".tmp_uploads"
    log_dir.mkdir(exist_ok=True)
    sys.stdout = sys.stderr = open(log_dir / "kb-server.log", "a", buffering=1, encoding="utf-8")

os.environ.setdefault("KB_ALLOW_CLIENTS", "127.0.0.1,192.168.7.111")

import uvicorn

uvicorn.run(
    "backend.app:app",
    host=os.environ.get("KB_HOST", "0.0.0.0"),
    port=int(os.environ.get("KB_API_PORT", "8765")),
    # The UI polls /api/status every 10 s; keep that out of the log.
    access_log=False,
)
