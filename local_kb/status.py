"""Centralized status logic for local-kb.

Single source of truth for file counts, llama.cpp availability, model list,
and FAISS index state.  Used by both the API and CLI.
"""

from pathlib import Path
from typing import List

from .paths import RAW, RAW_ASSETS, WIKI, OUTPUTS, CORRECTIONS, ensure_dirs
from .index_state import status_label as faiss_status_label
from . import llamacpp


# ---------------------------------------------------------------------------
# llama.cpp
# ---------------------------------------------------------------------------

def llamacpp_is_running() -> bool:
    return llamacpp.is_ready()


def llamacpp_models() -> List[str]:
    return llamacpp.list_models()


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
    """Return full system status dict (llama.cpp, file counts, FAISS)."""
    ensure_dirs()
    alive = llamacpp_is_running()
    models = llamacpp_models()
    loaded = llamacpp.loaded_model() if alive else None

    try:
        faiss = faiss_status_label()
    except Exception:
        faiss = "unavailable"

    return {
        "llamacpp": {"running": alive, "models": models, "loaded": loaded},
        "files": {
            "raw": _count_files(RAW, exclude=[RAW_ASSETS]),
            "wiki": _count_files(WIKI, "*.md"),
            "outputs": _count_files(OUTPUTS, "*.md"),
            "corrections": _count_files(CORRECTIONS, "*.md"),
        },
        "faiss": faiss,
    }
