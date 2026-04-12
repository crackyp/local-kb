#!/usr/bin/env python3
"""Launch the Local KB backend (FastAPI) and frontend (Next.js) together.

Environment variables (all optional):
    KB_API_PORT       Backend port  (default 8765)
    KB_FRONTEND_PORT  Frontend port (default 3737)
    KB_FRONTEND_HOST  Frontend hostname for CORS (default localhost)
"""

import os
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"

# Defaults chosen to avoid colliding with common dev services (8000/3000).
API_PORT = os.environ.get("KB_API_PORT", "8765")
FRONTEND_PORT = os.environ.get("KB_FRONTEND_PORT", "3737")


def start_api():
    print(f"\n[1/2] Starting FastAPI backend on http://127.0.0.1:{API_PORT} ...")
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "api:app", "--reload", "--port", API_PORT],
        cwd=FRONTEND,
        env={**os.environ, "KB_API_PORT": API_PORT, "KB_FRONTEND_PORT": FRONTEND_PORT},
    )


def start_next():
    print(f"\n[2/2] Starting Next.js dev server on http://localhost:{FRONTEND_PORT} ...")
    subprocess.run(
        ["npm", "run", "dev", "--", "--port", FRONTEND_PORT],
        cwd=FRONTEND,
        env={**os.environ, "NEXT_PUBLIC_API_BASE": f"http://127.0.0.1:{API_PORT}"},
    )


if __name__ == "__main__":
    from preflight import run_checks

    if not run_checks():
        print("\nFix the issues above before starting, or press Enter to continue anyway.")
        input()
    print()

    # Non-daemon threads so Ctrl+C propagates and uvicorn/next get a chance to
    # release their listening sockets. Daemon threads get torn down hard on
    # Windows and leave orphaned processes still bound to the port.
    api_thread = threading.Thread(target=start_api)
    api_thread.start()

    next_thread = threading.Thread(target=start_next)
    next_thread.start()

    try:
        next_thread.join()
    except KeyboardInterrupt:
        print("\nShutting down...")
