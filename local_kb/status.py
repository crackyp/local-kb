"""Centralized status logic for local-kb.

Single source of truth for file counts, Ollama availability, model list,
and FAISS index state.  Used by both the API and CLI.
"""

import json
import sys
import urllib.request
from pathlib import Path
from typing import List

from .config import CFG
from .paths import RAW, WIKI, OUTPUTS, SCRIPTS_DIR, ensure_dirs


# ---------------------------------------------------------------------------
# Ollama
# ---------------------------------------------------------------------------

def ollama_is_running() -> bool:
    try:
        req = urllib.request.Request(CFG["ollama"]["url"] + "/", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def ollama_models() -> List[str]:
    try:
        req = urllib.request.Request(
            CFG["ollama"]["url"] + "/api/tags", method="GET"
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# File counts
# ---------------------------------------------------------------------------

def _count_files(directory: Path, pattern: str = "**/*") -> int:
    if not directory.exists():
        return 0
    return sum(
        1 for p in directory.glob(pattern)
        if p.is_file() and p.name != ".gitkeep"
    )


# ---------------------------------------------------------------------------
# FAISS state
# ---------------------------------------------------------------------------

def faiss_status() -> str:
    """Return one of: ready, stale, not_built, not_installed, unavailable."""
    try:
        if str(SCRIPTS_DIR) not in sys.path:
            sys.path.insert(0, str(SCRIPTS_DIR))
        from faiss_index import faiss_available, is_index_stale, FAISS_INDEX_FILE

        if not faiss_available():
            return "not_installed"
        if not FAISS_INDEX_FILE.exists():
            return "not_built"
        return "stale" if is_index_stale() else "ready"
    except Exception:
        return "unavailable"


# ---------------------------------------------------------------------------
# Combined status
# ---------------------------------------------------------------------------

def get_status() -> dict:
    """Return full system status dict (Ollama, file counts, FAISS)."""
    ensure_dirs()
    alive = ollama_is_running()
    models = ollama_models() if alive else []

    return {
        "ollama": {"running": alive, "models": models},
        "files": {
            "raw": _count_files(RAW),
            "wiki": _count_files(WIKI, "*.md"),
            "outputs": _count_files(OUTPUTS, "*.md"),
        },
        "faiss": faiss_status(),
    }
