#!/usr/bin/env python3
"""Pre-startup checks for Local KB.

Run standalone (``python preflight.py``) or import and call ``run_checks()``.
Returns True if everything looks good, False (with printed warnings) otherwise.
"""

import importlib
import json
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
    ("pptx", "python-pptx"),
    ("pydantic", "pydantic"),
    ("bs4", "beautifulsoup4"),
]

# Optional capabilities. FAISS improves retrieval. OCR is only needed for scanned/image PDFs.
OPTIONAL_PYTHON_PACKAGES = [
    ("faiss", "faiss-cpu"),
    ("fitz", "PyMuPDF (OCR extra)"),
    ("easyocr", "easyocr (OCR extra)"),
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
            if "OCR extra" in pip_name:
                _warn(
                    f"{pip_name} not installed (optional)  ->  "
                    "python -m pip install -r requirements-ocr.txt"
                )
            else:
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
    """Check that nothing is already listening on *port*.

    Probes with connect() rather than bind(). On Windows SO_REUSEADDR lets a
    socket bind a port that another socket is already actively listening on, so
    a bind probe reports "free" while a server is running — that is how several
    uvicorn instances used to stack on the same port, each serving a different
    snapshot of kb.toml. A refused connection also correctly reports a lingering
    TIME_WAIT socket as free.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        in_use = s.connect_ex(("127.0.0.1", port)) == 0
    if in_use:
        _fail(f"Port {port} ({label}) is already in use — stop whatever is "
              f"listening on it, or set "
              f"KB_{label.upper().replace(' ', '_')}_PORT to a free port")
        return False
    _ok(f"Port {port} ({label}) is free")
    return True


def api_is_running(port: int) -> bool:
    """Return True if a Local KB backend is already answering on *port*.

    Probes /api/status so the launcher can reuse an instance left running by
    a previous launch instead of failing on a port conflict (or stacking a
    second uvicorn on top, which Windows SO_REUSEADDR allows).
    """
    url = f"http://127.0.0.1:{port}/api/status"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            if resp.status != 200:
                return False
            data = json.loads(resp.read())
            return isinstance(data, dict) and "faiss" in data
    except Exception:
        return False


def check_api_port() -> bool:
    """Check the backend port; a running Local KB backend counts as OK."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        in_use = s.connect_ex(("127.0.0.1", API_PORT)) == 0
    if not in_use:
        _ok(f"Port {API_PORT} (api) is free")
        return True
    if api_is_running(API_PORT):
        _ok(f"Port {API_PORT} (api) is served by a running Local KB backend - reusing it")
        return True
    _fail(f"Port {API_PORT} (api) is in use by something else — stop whatever is "
          f"listening on it, or set KB_API_PORT to a free port")
    return False


def check_llamacpp() -> bool:
    """Check that the local chat server is reachable on the configured port."""
    sys.path.insert(0, str(ROOT))
    try:
        from local_kb.config import CFG
    except Exception as e:
        _warn(f"could not import local_kb.config: {e}")
        return False

    cfg = CFG["llamacpp"]
    chat_url = f"http://{cfg['host']}:{cfg['chat_port']}/health"
    try:
        with urllib.request.urlopen(chat_url, timeout=3):
            _ok(f"local chat server reachable at http://{cfg['host']}:{cfg['chat_port']}")
            return True
    except Exception:
        _warn(
            f"local chat server not reachable at http://{cfg['host']}:{cfg['chat_port']} — "
            "start `python start-llm.py` or llama-swap before launching the UI."
        )
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
    api_ok = check_api_port()
    fe_ok = check_port_free(FRONTEND_PORT, "frontend")
    print()

    print("  Services:")
    check_llamacpp()
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
