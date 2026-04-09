"""FAISS semantic index for local-kb.

Provides chunking, embedding (via Ollama), and vector search so that
``cmd_ask`` can retrieve only the most relevant text fragments instead of
full wiki pages, dramatically reducing context-window usage.
"""

import json
import math
import urllib.error
import urllib.request
from pathlib import Path

# Re-use paths and helpers from the main CLI module.
from kb import INDEX, WIKI, CFG, read_text, sha256_text, load_json, save_json

# ---------------------------------------------------------------------------
# Index file paths
# ---------------------------------------------------------------------------

FAISS_INDEX_FILE = INDEX / "faiss.index"
FAISS_META_FILE = INDEX / "faiss_meta.json"
FAISS_STATE_FILE = INDEX / "faiss_state.json"

# ---------------------------------------------------------------------------
# FAISS availability check
# ---------------------------------------------------------------------------

def faiss_available() -> bool:
    try:
        import faiss  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Ollama embedding helper
# ---------------------------------------------------------------------------

_BATCH_SIZE = 32


def ollama_embed(texts: list, model: str, ollama_url: str, timeout: int) -> list:
    """Embed *texts* via the Ollama ``/api/embed`` endpoint.

    Returns a list of float-lists, one per input text.  Batches requests to
    avoid oversized payloads.
    """
    all_embeddings: list = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        payload = {"model": model, "input": batch}
        req = urllib.request.Request(
            ollama_url + "/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                embeddings = body.get("embeddings", [])
                if len(embeddings) != len(batch):
                    raise RuntimeError(
                        f"Ollama returned {len(embeddings)} embeddings for {len(batch)} inputs"
                    )
                all_embeddings.extend(embeddings)
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = e.read().decode("utf-8", errors="ignore")[:300]
            except Exception:
                pass
            raise RuntimeError(f"Ollama embed failed: HTTP {e.code} - {detail}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Ollama embed failed: {e}")
    return all_embeddings


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_page(text: str, chunk_size: int = 800, overlap: int = 100) -> list:
    """Split *text* into paragraph-aware chunks.

    Returns a list of dicts ``{"text": str, "start": int, "end": int}``.
    """
    if not text.strip():
        return []

    paragraphs = text.split("\n\n")
    chunks: list = []
    current_text = ""
    current_start = 0
    pos = 0  # character position in original text

    for i, para in enumerate(paragraphs):
        # Account for the \n\n separator (except before the first paragraph)
        if i > 0:
            pos += 2  # the \n\n we split on

        para_text = para
        if not current_text:
            current_start = pos

        candidate = (current_text + "\n\n" + para_text).strip() if current_text else para_text

        if len(candidate) <= chunk_size:
            current_text = candidate
        else:
            # Flush current chunk if it has content
            if current_text:
                chunks.append({
                    "text": current_text,
                    "start": current_start,
                    "end": current_start + len(current_text),
                })
                # Start next chunk with overlap from tail of current
                if overlap > 0 and len(current_text) > overlap:
                    overlap_text = current_text[-overlap:]
                    current_text = overlap_text + "\n\n" + para_text
                    current_start = current_start + len(chunks[-1]["text"]) - overlap
                else:
                    current_text = para_text
                    current_start = pos
            else:
                current_text = para_text
                current_start = pos

            # If a single paragraph exceeds chunk_size, hard-split it
            while len(current_text) > chunk_size:
                split_at = chunk_size
                # Try to split at sentence boundary
                dot_pos = current_text.rfind(". ", 0, chunk_size)
                if dot_pos > chunk_size // 2:
                    split_at = dot_pos + 2
                chunks.append({
                    "text": current_text[:split_at],
                    "start": current_start,
                    "end": current_start + split_at,
                })
                if overlap > 0:
                    overlap_start = max(0, split_at - overlap)
                    current_text = current_text[overlap_start:]
                    current_start = current_start + overlap_start
                else:
                    current_text = current_text[split_at:]
                    current_start = current_start + split_at

        pos += len(para)

    # Flush remaining
    if current_text.strip():
        chunks.append({
            "text": current_text,
            "start": current_start,
            "end": current_start + len(current_text),
        })

    return chunks


# ---------------------------------------------------------------------------
# Build / rebuild FAISS index
# ---------------------------------------------------------------------------

def _wiki_page_hashes() -> dict:
    """Return ``{page_name: sha256}`` for every wiki markdown file."""
    hashes = {}
    for p in sorted(WIKI.glob("*.md")):
        hashes[p.name] = sha256_text(read_text(p))
    return hashes


def build_faiss_index(cfg: dict, force: bool = False) -> dict:
    """Build (or rebuild) the FAISS index from wiki pages.

    Returns ``{"pages": int, "chunks": int, "dimensions": int}``.
    """
    import faiss
    import numpy as np

    fcfg = cfg["faiss"]
    current_hashes = _wiki_page_hashes()

    # Check if rebuild is needed
    if not force and FAISS_INDEX_FILE.exists() and FAISS_STATE_FILE.exists():
        state = load_json(FAISS_STATE_FILE, {})
        stored_pages = state.get("pages", {})
        if (
            stored_pages == current_hashes
            and state.get("embed_model") == fcfg["embed_model"]
            and state.get("chunk_size") == fcfg["chunk_size"]
            and state.get("chunk_overlap") == fcfg["chunk_overlap"]
        ):
            n_chunks = len(load_json(FAISS_META_FILE, []))
            print("FAISS index is up to date.")
            return {"pages": len(current_hashes), "chunks": n_chunks, "dimensions": state.get("dimensions", 0)}

    if not current_hashes:
        print("No wiki pages to index.")
        return {"pages": 0, "chunks": 0, "dimensions": 0}

    # Chunk all pages
    all_chunks: list = []  # list of {"page", "text", "start", "end"}
    for page_name in sorted(current_hashes):
        text = read_text(WIKI / page_name)
        page_chunks = chunk_page(text, fcfg["chunk_size"], fcfg["chunk_overlap"])
        for c in page_chunks:
            all_chunks.append({
                "page": page_name,
                "text": c["text"],
                "start": c["start"],
                "end": c["end"],
            })

    if not all_chunks:
        print("No chunks generated.")
        return {"pages": len(current_hashes), "chunks": 0, "dimensions": 0}

    print(f"Embedding {len(all_chunks)} chunks from {len(current_hashes)} pages...")

    # Embed all chunks
    texts = [c["text"] for c in all_chunks]
    embeddings = ollama_embed(
        texts,
        model=fcfg["embed_model"],
        ollama_url=cfg["ollama"]["url"],
        timeout=cfg["ollama"]["timeout"],
    )

    # Build numpy matrix and L2-normalise for cosine similarity via inner product
    matrix = np.array(embeddings, dtype=np.float32)
    faiss.normalize_L2(matrix)

    dim = matrix.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(matrix)

    # Save everything
    faiss.write_index(index, str(FAISS_INDEX_FILE))

    # Metadata: store text alongside page/offsets for context assembly
    meta = []
    for c in all_chunks:
        meta.append({
            "page": c["page"],
            "start": c["start"],
            "end": c["end"],
            "text": c["text"],
        })
    save_json(FAISS_META_FILE, meta)

    save_json(FAISS_STATE_FILE, {
        "pages": current_hashes,
        "embed_model": fcfg["embed_model"],
        "chunk_size": fcfg["chunk_size"],
        "chunk_overlap": fcfg["chunk_overlap"],
        "dimensions": dim,
    })

    print(f"FAISS index built: {dim}-dimensional, {len(all_chunks)} vectors.")
    return {"pages": len(current_hashes), "chunks": len(all_chunks), "dimensions": dim}


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def search_chunks(question: str, cfg: dict) -> list:
    """Search the FAISS index for chunks relevant to *question*.

    Returns a list of dicts ``{"page", "text", "start", "end", "score"}``,
    sorted by descending score.
    """
    import faiss
    import numpy as np

    fcfg = cfg["faiss"]

    if not FAISS_INDEX_FILE.exists() or not FAISS_META_FILE.exists():
        return []

    index = faiss.read_index(str(FAISS_INDEX_FILE))
    meta = load_json(FAISS_META_FILE, [])

    # Embed the question
    q_emb = ollama_embed(
        [question],
        model=fcfg["embed_model"],
        ollama_url=cfg["ollama"]["url"],
        timeout=cfg["ollama"]["timeout"],
    )
    q_vec = np.array(q_emb, dtype=np.float32)
    faiss.normalize_L2(q_vec)

    top_k = min(fcfg["top_k"], index.ntotal)
    if top_k == 0:
        return []

    scores, ids = index.search(q_vec, top_k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or idx >= len(meta):
            continue
        m = meta[idx]
        results.append({
            "page": m["page"],
            "text": m["text"],
            "start": m["start"],
            "end": m["end"],
            "score": float(score),
        })
    return results


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------

def assemble_context(question: str, cfg: dict):
    """Retrieve relevant chunks and assemble context within the budget.

    Returns ``(context_string, list_of_page_names)`` or ``(None, [])`` if
    retrieval fails or yields nothing.
    """
    fcfg = cfg["faiss"]
    chunks = search_chunks(question, cfg)
    if not chunks:
        return None, []

    budget = fcfg["context_budget"]
    used = 0
    selected: list = []  # list of (page, text, score)

    # Group by page to merge overlapping chunks
    page_chunks: dict = {}
    for c in chunks:
        page_chunks.setdefault(c["page"], []).append(c)

    # Merge overlapping/adjacent chunks within each page
    merged: list = []
    for page, pchunks in page_chunks.items():
        pchunks.sort(key=lambda x: x["start"])
        spans: list = []
        for c in pchunks:
            if spans and c["start"] <= spans[-1]["end"]:
                # Overlap: extend the span
                spans[-1]["end"] = max(spans[-1]["end"], c["end"])
                spans[-1]["text"] = spans[-1]["text"] + c["text"][spans[-1]["end"] - c["start"]:]
                spans[-1]["score"] = max(spans[-1]["score"], c["score"])
            else:
                spans.append(dict(c))
        for s in spans:
            merged.append(s)

    # Sort by score descending, greedily fill budget
    merged.sort(key=lambda x: x["score"], reverse=True)

    for chunk in merged:
        text = chunk["text"]
        cost = len(text) + len(chunk["page"]) + 10  # header overhead
        if used + cost > budget and selected:
            break
        selected.append((chunk["page"], text, chunk["score"]))
        used += cost

    if not selected:
        return None, []

    # Group selected chunks by page for coherent output
    page_order: list = []
    page_texts: dict = {}
    for page, text, _score in selected:
        if page not in page_texts:
            page_order.append(page)
            page_texts[page] = []
        page_texts[page].append(text)

    parts: list = []
    for page in page_order:
        header = f"## {page}"
        body = "\n\n".join(page_texts[page])
        parts.append(f"{header}\n{body}")

    context = "\n\n".join(parts)
    return context, page_order


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------

def is_index_stale() -> bool:
    """Return True if the FAISS index is missing or out of date."""
    if not FAISS_INDEX_FILE.exists() or not FAISS_STATE_FILE.exists():
        return True

    state = load_json(FAISS_STATE_FILE, {})
    current = _wiki_page_hashes()
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
