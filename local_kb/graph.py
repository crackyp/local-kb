"""The wiki knowledge graph: explicit links plus semantic similarity.

Two kinds of edge, built from two different sources:

``link``
    A markdown link one page makes to another. Authored by the compile LLM, so
    it says "someone wrote a cross-reference here" — reliable, but its density
    reflects prose habits, and overview pages accumulate far more of them than
    their actual importance warrants.

``similar``
    Two pages whose content embeds close together. Derived from the vectors
    already sitting in the FAISS index, so it costs no embedding calls. Edges
    are *mutual* k-nearest-neighbour matches: a page that reads as vaguely
    close to everything still only gets k slots of its own, which keeps generic
    pages from turning into hubs the way they do in the link layer.

Nothing is cached. The link layer is read from ``wiki_index.json`` (refreshed
against disk first) and the similarity layer is a matmul over vectors already
on disk, so the graph cannot drift out of sync with the wiki.
"""

from .compile import refresh_wiki_index
from .config import CFG
from .index_state import (
    FAISS_INDEX_FILE,
    FAISS_META_FILE,
    faiss_available,
    index_exists,
    is_stale,
)
from .utils import load_json


def _link_edges(index: dict) -> list[dict]:
    """Undirected link edges, with direction recorded on each one."""
    edges: dict[tuple[str, str], dict] = {}

    for name, entry in index.items():
        for target in entry.get("links_to", []):
            # Both endpoints must be real pages; dead links belong to lint, not
            # to the graph, and inventing a node for one would be a lie.
            if target == name or target not in index:
                continue
            key = (name, target) if name < target else (target, name)
            forward = key[0] == name
            edge = edges.get(key)
            if edge is None:
                edges[key] = {
                    "a": key[0],
                    "b": key[1],
                    "type": "link",
                    "ab": forward,
                    "ba": not forward,
                }
            elif forward:
                edge["ab"] = True
            else:
                edge["ba"] = True

    return list(edges.values())


def _page_vectors():
    """Mean-pool each page's chunk vectors out of the existing FAISS index.

    Returns ``(page_names, matrix)`` with one L2-normalized row per page, or
    ``(None, None)`` if the index can't be read in the expected layout.
    """
    import faiss
    import numpy as np

    index = faiss.read_index(str(FAISS_INDEX_FILE))
    if index.ntotal == 0:
        return None, None

    meta = load_json(FAISS_META_FILE, {})
    if isinstance(meta, list):  # legacy format: list positional by id
        meta = {str(i): m for i, m in enumerate(meta)}

    try:
        # IndexIDMap keeps the vectors in a flat sub-index and the ids beside
        # them, so both come back without re-embedding anything.
        ids = faiss.vector_to_array(index.id_map)
        vectors = index.index.reconstruct_n(0, index.index.ntotal)
    except AttributeError:
        return None, None

    rows: dict[str, list[int]] = {}
    for position, chunk_id in enumerate(ids):
        entry = meta.get(str(int(chunk_id)))
        if entry:
            rows.setdefault(entry["page"], []).append(position)

    if not rows:
        return None, None

    names = sorted(rows)
    matrix = np.vstack([vectors[rows[n]].mean(axis=0) for n in names]).astype("float32")
    faiss.normalize_L2(matrix)
    return names, matrix


def _similar_edges(index: dict, top_k: int, min_score: float) -> list[dict]:
    """Mutual k-nearest-neighbour edges between pages."""
    import faiss

    names, matrix = _page_vectors()
    if names is None or len(names) < 2:
        return []

    # Search the page matrix against itself. k+1 because the first hit for
    # every row is the row itself.
    flat = faiss.IndexFlatIP(matrix.shape[1])
    flat.add(matrix)
    k = min(top_k + 1, len(names))
    scores, neighbor_ids = flat.search(matrix, k)

    neighbors: list[set[int]] = []
    scored: dict[tuple[int, int], float] = {}
    for i, (row_ids, row_scores) in enumerate(zip(neighbor_ids, scores)):
        row: set[int] = set()
        for raw_j, score in zip(row_ids, row_scores):
            j = int(raw_j)
            if j < 0 or j == i:
                continue
            row.add(j)
            scored[(i, j)] = float(score)
        neighbors.append(row)

    edges: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for i, row in enumerate(neighbors):
        for j in row:
            # Mutual only: both pages must rank the other in their own top k.
            if i not in neighbors[j]:
                continue
            key = (i, j) if i < j else (j, i)
            if key in seen:
                continue
            seen.add(key)

            a, b = names[key[0]], names[key[1]]
            # A page deleted since the last reindex can still be in FAISS.
            if a not in index or b not in index:
                continue
            score = scored[(i, j)]
            if score < min_score:
                continue
            edges.append({"a": a, "b": b, "type": "similar", "weight": round(score, 4)})

    return edges


def _similarity_status() -> str:
    """Why the similarity layer is (or isn't) usable, for the UI to explain."""
    if not CFG["faiss"].get("enabled", True):
        return "disabled"
    if not faiss_available():
        return "not_installed"
    if not index_exists():
        return "not_built"
    return "stale" if is_stale() else "ready"


def build_graph() -> dict:
    """Build the current knowledge graph.

    Returns ``{"edges": [...], "counts": {...}, "similarity": str}``. Nodes are
    not included — the caller already has the page list from ``/api/files/wiki``
    and joins on the ``a``/``b`` filenames.
    """
    index = refresh_wiki_index()

    edges = _link_edges(index)
    similarity = _similarity_status()

    if similarity in ("ready", "stale"):
        gcfg = CFG["graph"]
        try:
            edges += _similar_edges(
                index,
                top_k=int(gcfg["similar_top_k"]),
                min_score=float(gcfg["similar_min_score"]),
            )
        except Exception as e:
            print(f"  ! similarity edges unavailable: {e}")
            similarity = "error"

    counts = {"link": 0, "similar": 0}
    for edge in edges:
        counts[edge["type"]] += 1

    return {"edges": edges, "counts": counts, "similarity": similarity}
