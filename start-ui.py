#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"

def start_api():
    print("\n[1/2] Starting FastAPI backend on http://127.0.0.1:8000 ...")
    subprocess.run([sys.executable, "-m", "uvicorn", "api:app", "--reload", "--port", "8000"], cwd=FRONTEND)

def start_next():
    print("\n[2/2] Starting Next.js dev server on http://localhost:3000 ...")
    subprocess.run(["npm", "run", "dev"], cwd=FRONTEND)

if __name__ == "__main__":
    import threading

    api_thread = threading.Thread(target=start_api)
    api_thread.start()

    next_thread = threading.Thread(target=start_next)
    next_thread.start()

    next_thread.join()
