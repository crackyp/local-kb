#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run_server():
    print("Starting FastAPI backend on http://127.0.0.1:8000 ...")
    subprocess.run([sys.executable, "-m", "uvicorn", "api:app", "--reload", "--port", "8000"], cwd=ROOT / "frontend")

if __name__ == "__main__":
    run_server()
