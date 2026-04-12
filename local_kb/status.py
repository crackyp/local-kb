"""Centralized status logic for local-kb.

Single source of truth for file counts, Ollama availability, model list,
and FAISS index state.  Used by both the API and CLI.
"""

import json
import urllib.request
from pathlib import Path
from typing import List

from .config import CFG
from .paths import RAW, RAW_ASSETS, WIKI, OUTPUTS, CORRECTIONS, ensure_dirs
from .index_state import status_label as faiss_status_label


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

def _count_files(directory: Path, pattern: str = "**/*", exclude: list[Path] | None = None) -> int:
    if not directory.exists():
        return 0
    excluded = [e.resolve() for e in (exclude or []) if e.exists()]
    return sum(
        1 for p in directory.glob(pattern)
        if p.is_file()
        and p.name != ".gitkeep"
        and not any(ex in p.resolve().parents for ex in excluded)
    )


# ---------------------------------------------------------------------------
# Combined status
# ---------------------------------------------------------------------------

def get_status() -> dict:
    """Return full system status dict (Ollama, file counts, FAISS)."""
    ensure_dirs()
    alive = ollama_is_running()
    models = ollama_models() if alive else []

    try:
        faiss = faiss_status_label()
    except Exception:
        faiss = "unavailable"

    return {
        "ollama": {"running": alive, "models": models},
        "files": {
            "raw": _count_files(RAW, exclude=[RAW_ASSETS]),
            "wiki": _count_files(WIKI, "*.md"),
            "outputs": _count_files(OUTPUTS, "*.md"),
            "corrections": _count_files(CORRECTIONS, "*.md"),
        },
        "faiss": faiss,
    }
