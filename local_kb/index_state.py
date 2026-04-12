"""Centralized FAISS index state management.

Single source of truth for what constitutes a valid, stale, or missing index.

Index files (all in kb/index/):
    faiss.index       — The FAISS vector index (IndexIDMap wrapping IndexFlatIP).
    faiss_meta.json   — Chunk metadata keyed by vector ID: {page, text, start, end}.
    faiss_state.json  — Page hashes + settings for staleness detection:
                        {pages: {name: sha256}, embed_model, chunk_size, chunk_overlap,
                         dimensions, next_id}.

INDEX.md is auto-generated from wiki_index.json and is NOT part of the FAISS
index.  It is excluded from hashing and indexing.

Staleness rules:
    - Any of the three FAISS files missing → not_built.
    - Page hashes differ from current wiki contents → stale.
    - Embedding settings (model, chunk_size, chunk_overlap) changed → stale.
    - Wiki pages deleted but still present in FAISS state → stale.

Wiki page deletion:
    When a wiki page is deleted, its chunks remain in the FAISS index until the
    next rebuild.  ``remove_page_from_index()`` allows immediate cleanup.
"""

import sys
from pathlib import Path

from .config import CFG
from .paths import INDEX, WIKI, SCRIPTS_DIR
from .utils import load_json, save_json, read_text, sha256_text


# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

FAISS_INDEX_FILE = INDEX / "faiss.index"
FAISS_META_FILE = INDEX / "faiss_meta.json"
FAISS_STATE_FILE = INDEX / "faiss_state.json"
WIKI_INDEX_FILE = INDEX / "wiki_index.json"


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def faiss_available() -> bool:
    """Return True if the faiss-cpu package is installed."""
    try:
        import faiss  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# State queries
# ---------------------------------------------------------------------------

def index_exists() -> bool:
    """Return True if all three FAISS index files are present."""
    return (
        FAISS_INDEX_FILE.exists()
        and FAISS_META_FILE.exists()
        and FAISS_STATE_FILE.exists()
    )


def wiki_page_hashes() -> dict:
    """Return ``{page_name: sha256}`` for every wiki .md file, excluding INDEX.md."""
    hashes = {}
    for p in sorted(WIKI.glob("*.md")):
        if p.name == "INDEX.md":
            continue
        hashes[p.name] = sha256_text(read_text(p))
    return hashes


def is_stale() -> bool:
    """Return True if the FAISS index is missing or out of date."""
    if not index_exists():
        return True

    state = load_json(FAISS_STATE_FILE, {})
    current = wiki_page_hashes()
    fcfg = CFG["faiss"]

    if state.get("pages", {}) != current:
        return True
    if state.get("embed_model") != fcfg["embed_model"]:
        return True
    if state.get("chunk_size") != fcfg["chunk_size"]:
        return True
    if state.get("chunk_overlap") != fcfg["chunk_overlap"]:
        return True
    return False


def status_label() -> str:
    """Return a human-readable status: ready, stale, not_built, not_installed."""
    if not faiss_available():
        return "not_installed"
    if not index_exists():
        return "not_built"
    return "stale" if is_stale() else "ready"


# ---------------------------------------------------------------------------
# Wiki page deletion cleanup
# ---------------------------------------------------------------------------

def remove_page_from_index(page_name: str) -> int:
    """Remove all chunks for *page_name* from the FAISS index.

    Returns the number of vectors removed.  No-op if FAISS is not installed
    or the index doesn't exist.
    """
    if not faiss_available() or not index_exists():
        return 0

    import faiss
    import numpy as np

    meta = load_json(FAISS_META_FILE, {})
    ids_to_remove = [int(cid) for cid, m in meta.items() if m["page"] == page_name]

    if not ids_to_remove:
        return 0

    index = faiss.read_index(str(FAISS_INDEX_FILE))
    index.remove_ids(np.array(ids_to_remove, dtype=np.int64))
    faiss.write_index(index, str(FAISS_INDEX_FILE))

    for cid in ids_to_remove:
        del meta[str(cid)]
    save_json(FAISS_META_FILE, meta)

    # Update state: remove the page from tracked hashes
    state = load_json(FAISS_STATE_FILE, {})
    state.get("pages", {}).pop(page_name, None)
    save_json(FAISS_STATE_FILE, state)

    return len(ids_to_remove)


def remove_page_from_wiki_index(page_name: str):
    """Remove a page from wiki_index.json and regenerate INDEX.md."""
    from .compile import build_wiki_index

    wiki_index = load_json(WIKI_INDEX_FILE, {})
    if page_name in wiki_index:
        del wiki_index[page_name]
        save_json(WIKI_INDEX_FILE, wiki_index)

    # Regenerate INDEX.md from the updated index
    build_wiki_index(changed_pages=set())
