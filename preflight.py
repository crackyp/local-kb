#!/usr/bin/env python3
"""Pre-startup checks for Local KB.

Run standalone (``python preflight.py``) or import and call ``run_checks()``.
Returns True if everything looks good, False (with printed warnings) otherwise.
"""

import importlib
import os
import socket
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"

API_PORT = int(os.environ.get("KB_API_PORT", "8765"))
FRONTEND_PORT = int(os.environ.get("KB_FRONTEND_PORT", "3737"))

# Python packages required by the backend
REQUIRED_PYTHON_PACKAGES = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn"),
    ("pypdf", "pypdf"),
    ("docx", "python-docx"),
    ("pydantic", "pydantic"),
]

# Optional but recommended
OPTIONAL_PYTHON_PACKAGES = [
    ("faiss", "faiss-cpu"),
    ("easyocr", "easyocr"),
]


def _ok(msg: str):
    print(f"  [OK]   {msg}")


def _warn(msg: str):
    print(f"  [WARN] {msg}")


def _fail(msg: str):
    print(f"  [FAIL] {msg}")


def check_python_deps() -> bool:
    """Check that required Python packages are importable."""
    all_good = True
    for module_name, pip_name in REQUIRED_PYTHON_PACKAGES:
        try:
            importlib.import_module(module_name)
            _ok(f"{pip_name}")
        except ImportError:
            _fail(f"{pip_name} not installed  ->  pip install {pip_name}")
            all_good = False

    for module_name, pip_name in OPTIONAL_PYTHON_PACKAGES:
        try:
            importlib.import_module(module_name)
            _ok(f"{pip_name} (optional)")
        except ImportError:
            _warn(f"{pip_name} not installed (optional)  ->  pip install {pip_name}")

    return all_good


def check_node_modules() -> bool:
    """Check that frontend/node_modules exists."""
    nm = FRONTEND / "node_modules"
    if nm.is_dir():
        _ok("frontend/node_modules")
        return True
    _fail("frontend/node_modules missing  ->  cd frontend && npm install")
    return False


def check_port_free(port: int, label: str) -> bool:
    """Check that a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
        _ok(f"Port {port} ({label}) is free")
        return True
    except OSError:
        _fail(f"Port {port} ({label}) is already in use — "
              f"set KB_{label.upper().replace(' ', '_')}_PORT to a free port")
        return False


def check_ollama() -> bool:
    """Check that Ollama is reachable."""
    url = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    try:
        req = urllib.request.Request(url + "/", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            pass
        _ok(f"Ollama reachable at {url}")
        return True
    except Exception:
        _warn(f"Ollama not reachable at {url} — LLM features will not work until Ollama is running")
        return False


def run_checks() -> bool:
    """Run all preflight checks. Returns True if no hard failures."""
    print("Preflight checks:")
    print()

    print("  Python packages:")
    deps_ok = check_python_deps()
    print()

    print("  Frontend:")
    node_ok = check_node_modules()
    print()

    print("  Ports:")
    api_ok = check_port_free(API_PORT, "api")
    fe_ok = check_port_free(FRONTEND_PORT, "frontend")
    print()

    print("  Services:")
    check_ollama()
    print()

    all_ok = deps_ok and node_ok and api_ok and fe_ok
    if all_ok:
        print("All critical checks passed.")
    else:
        print("Some checks failed — see above. Fix the [FAIL] items before starting.")

    return all_ok


if __name__ == "__main__":
    ok = run_checks()
    sys.exit(0 if ok else 1)
