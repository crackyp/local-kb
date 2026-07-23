"""Centralized status logic for local-kb.

Single source of truth for file counts, llama.cpp availability, model list,
and FAISS index state.  Used by both the API and CLI.
"""

from pathlib import Path
from typing import List

from .paths import RAW, RAW_ASSETS, WIKI, OUTPUTS, CORRECTIONS, ensure_dirs
from .index_state import status_label as faiss_status_label
from . import llamacpp
from .config import CFG


# ---------------------------------------------------------------------------
# llama.cpp
# ---------------------------------------------------------------------------

def llamacpp_is_running() -> bool:
    return llamacpp.ping_any()


def llamacpp_providers() -> list[dict]:
    """Return a list of provider statuses."""
    providers = []
    for key, value in CFG.items():
        if not isinstance(value, dict):
            continue
        if key == "llamacpp" or (key.startswith("llamacpp_") and value.get("models")):
            display_name = key.replace("llamacpp", "llama-swap").replace("_", "-")
            host = value.get("host", "127.0.0.1")
            port = int(value.get("chat_port", 8080))
            try:
                mgr = llamacpp.get_chat_manager(key)
                alive = mgr.is_alive()
                loaded = llamacpp.loaded_model(key) if alive else None
            except Exception:
                alive = False
                loaded = None
            providers.append({
                "name": key,
                "display_name": display_name,
                "host": f"http://{host}:{port}",
                "running": alive,
                "loaded": loaded,
                "models": [str(m) for m in value.get("models", [])],
            })
    return providers


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
    """Return full system status dict (llama.cpp providers, file counts, FAISS)."""
    ensure_dirs()
    providers = llamacpp_providers()
    models = llamacpp_models()
    # Primary loaded model (backward compat)
    primary = next((p for p in providers if p["name"] == "llamacpp"), None)
    loaded = primary["loaded"] if primary else None

    try:
        faiss = faiss_status_label()
    except Exception:
        faiss = "unavailable"

    return {
        "llamacpp": {"running": llamacpp_is_running(), "models": models, "loaded": loaded, "default_model": CFG["model"]["default"]},
        "providers": providers,
        "files": {
            "raw": _count_files(RAW, exclude=[RAW_ASSETS]),
            "wiki": _count_files(WIKI, "*.md"),
            "outputs": _count_files(OUTPUTS, "*.md"),
            "corrections": _count_files(CORRECTIONS, "*.md"),
        },
        "faiss": faiss,
    }
