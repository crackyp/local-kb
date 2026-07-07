"""Compile pipeline: raw sources -> wiki pages (iterative-incremental).

For each changed raw file we:
  1. Find the most-similar existing wiki pages via FAISS.
  2. Send the new source + those pages to the LLM and ask it to decide
     whether to update an existing page, merge several, or create a new one.
  3. Apply the resulting writes (and soft-delete any redundant pages).

The LLM never sees the whole corpus, so the flow scales regardless of how
big kb/raw/ or kb/wiki/ grow. Periodic global reorganization is handled
out-of-band (chat agent or a future `reconcile` command).
"""

import datetime as dt
import json
import re
from pathlib import Path

from .config import CFG
from .paths import RAW, WIKI, STATE_FILE, DOC_INDEX_FILE, WIKI_INDEX_FILE, ensure_dirs
from .utils import (
    load_json, save_json, slugify, read_text, sha256_text,
    extract_links, truncate_at_sentence, should_compile_file,
)
from .llamacpp import ping as ping_llamacpp, generate as llamacpp_generate
from .extract import extract_pdf_text, extract_docx_text, extract_pptx_text
from .safe_ops import soft_delete


# ---------------------------------------------------------------------------
# Wiki index (filesystem -> wiki_index.json + INDEX.md)
# ---------------------------------------------------------------------------


def _index_wiki_page(path: Path) -> dict:
    text = read_text(path)
    links = extract_links(text)
    first = ""
    for ln in text.splitlines():
        if ln.strip():
            first = ln.strip()
            break
    title = first.lstrip("# ").strip() if first else path.stem
    return {
        "title": title,
        "links_to": [l[1] for l in links],
        "words": len(text.split()),
    }


def _write_index_md(index: dict):
    if not index:
        idx_path = WIKI / "INDEX.md"
        if idx_path.exists():
            idx_path.unlink()
        return
    lines = ["# Wiki Index", f"\n{len(index)} topics\n"]
    for fname in sorted(index):
        title = index[fname]["title"]
        lines.append(f"- [{title}]({fname})")
    (WIKI / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_wiki_index(changed_pages: set | None = None):
    """Build or incrementally update the wiki index from the filesystem."""
    index = load_json(WIKI_INDEX_FILE, {}) if changed_pages is not None else {}

    if changed_pages is None:
        for path in sorted(WIKI.glob("*.md")):
            if path.name == "INDEX.md":
                continue
            index[path.name] = _index_wiki_page(path)
    else:
        for page_name in changed_pages:
            path = WIKI / page_name
            if path.exists():
                index[page_name] = _index_wiki_page(path)

        existing = {p.name for p in WIKI.glob("*.md") if p.name != "INDEX.md"}
        for stale in list(index):
            if stale not in existing:
                del index[stale]

    save_json(WIKI_INDEX_FILE, index)
    _write_index_md(index)
    return index


# ---------------------------------------------------------------------------
# docs.json (raw -> sha tracking only; no longer 1:1 wiki mapping)
# ---------------------------------------------------------------------------


def validate_docs_index() -> dict:
    """Drop docs.json entries whose raw source no longer exists."""
    docs_index = load_json(DOC_INDEX_FILE, {})
    state = load_json(STATE_FILE, {"compiled": {}})
    removed_sources = []

    for rel_name in list(docs_index):
        if not (RAW / rel_name).exists():
            removed_sources.append(rel_name)
            del docs_index[rel_name]
            state["compiled"].pop(rel_name, None)

    save_json(DOC_INDEX_FILE, docs_index)
    save_json(STATE_FILE, state)
    return {"removed_sources": removed_sources, "valid": len(docs_index)}


# ---------------------------------------------------------------------------
# Retrieval: find related wiki pages for a new/updated source
# ---------------------------------------------------------------------------


def _find_related_pages(text: str, top_k: int) -> list[Path]:
    """Return up to top_k existing wiki pages most semantically similar to text."""
    if not CFG["faiss"].get("enabled", True):
        return []
    try:
        import sys
        scripts_dir = str((WIKI.parent.parent / "scripts").resolve())
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from faiss_index import faiss_available, search_chunks, FAISS_INDEX_FILE
    except Exception as e:
        print(f"  ! related-page search disabled (FAISS import failed): {e}")
        return []
    if not faiss_available() or not FAISS_INDEX_FILE.exists():
        return []

    # Sample several windows so very long documents don't get judged only by
    # their cover page or TOC. Each window embeds independently via separate
    # search calls is too costly; instead concatenate windows into one query.
    windows: list[str] = [text[:2000]]
    if len(text) > 6000:
        mid = len(text) // 2
        windows.append(text[mid : mid + 2000])
    if len(text) > 4000:
        windows.append(text[-2000:])
    query = "\n\n".join(windows)

    cfg = dict(CFG)
    cfg["faiss"] = dict(cfg["faiss"])
    cfg["faiss"]["top_k"] = max(top_k * 4, 20)
    try:
        results = search_chunks(query, cfg)
    except Exception as e:
        print(f"  ! related-page search failed: {e}")
        return []
    if not results:
        return []

    page_scores: dict[str, float] = {}
    for r in results:
        page = r.get("page")
        if not page:
            continue
        page_scores[page] = page_scores.get(page, 0.0) + float(r.get("score", 0.0))

    ranked = sorted(page_scores.items(), key=lambda kv: kv[1], reverse=True)
    out: list[Path] = []
    for page_name, _score in ranked[:top_k]:
        p = WIKI / page_name
        if p.exists():
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# LLM call: decide writes + deletes for one source
# ---------------------------------------------------------------------------


_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


def _parse_decision(raw: str) -> dict | None:
    """Extract a JSON decision object from the LLM response. Returns None on failure."""
    if not raw:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        m = _JSON_BLOCK.search(raw)
        candidate = m.group(0) if m else None
    if candidate is None:
        return None
    try:
        obj = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


_SAFE_FILENAME = re.compile(r"^[a-z0-9][a-z0-9._-]*\.md$")


def _safe_wiki_filename(name: str) -> str | None:
    """Validate and normalize an LLM-proposed wiki filename. None if unsafe."""
    if not isinstance(name, str):
        return None
    n = Path(name).name.strip().lower()
    if not n.endswith(".md"):
        n = slugify(n) + ".md"
    if n == "index.md":
        return None
    if not _SAFE_FILENAME.match(n):
        n = slugify(n[:-3]) + ".md"
        if not _SAFE_FILENAME.match(n):
            return None
    return n


def _build_prompt(rel_name: str, source_text: str, related: list[Path]) -> str:
    max_source = int(CFG["compile"]["max_source_chars"])
    truncated_source = truncate_at_sentence(source_text, max_source)

    # Budget the related-pages context to leave headroom for the source + output.
    # max_source already controls source size; cap related context to ~2x that
    # by default, scaled by how many pages we include.
    per_page_budget = max(2000, max_source // max(1, len(related))) if related else 0

    parts: list[str] = []
    for p in related:
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        parts.append(
            f"=== kb/wiki/{p.name} ===\n"
            f"{truncate_at_sentence(body, per_page_budget)}"
        )
    related_block = "\n\n".join(parts) if parts else "(no related pages found)"

    return f"""You maintain a personal research wiki. A new or updated source has been added to kb/raw/. Decide how to incorporate it into the existing wiki and return ONLY a JSON object.

EXISTING RELATED WIKI PAGES (most-similar first, full or truncated content shown):

{related_block}

NEW/UPDATED SOURCE
Filename: {rel_name}

{truncated_source}

INSTRUCTIONS
- If the source supersedes an existing page (e.g. a later draft of the same document), rewrite that page in place by listing it in "writes" with the same filename and the updated content.
- If the source extends an existing page (e.g. meeting notes about a draft already in the wiki), update that page in place — fold the new information in without losing prior content.
- If multiple existing pages overlap with the new source and should be merged, write the consolidated result and list the redundant filenames in "deletes".
- If the source is genuinely about a new topic not covered above, create a new page with a kebab-case .md filename derived from its title.
- Only list filenames in "deletes" that appear in the EXISTING RELATED WIKI PAGES section above. Never delete a page you also list in "writes".

PAGE FORMAT REQUIREMENTS (apply to every page in "writes")
- First line: `# <Title>` where <Title> is a short descriptive phrase (3-7 words). Not the filename.
- Then a `## Summary` section with a single-paragraph overview.
- Then sections preserving the important detail (procedures, requirements, definitions, timelines, quotes). Use ### subheadings and bullet lists for dense material.
- Cross-link related pages with markdown links: `[Title](slug.md)`.
- Do not invent facts that are not in the provided sources.

OUTPUT FORMAT (return ONLY this JSON object, no prose, no markdown fences):
{{
  "reasoning": "one short paragraph describing the decision",
  "writes": [
    {{"filename": "kebab-case-slug.md", "content": "# Title\\n\\n## Summary\\n..."}}
  ],
  "deletes": ["redundant-page.md"]
}}
"""


# ---------------------------------------------------------------------------
# Fallback article (used when the LLM returns no parseable decision)
# ---------------------------------------------------------------------------


def fallback_article(path: Path, text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    excerpt = "\n".join(lines[:8]) if lines else "(no readable content extracted)"
    key_points = []
    for ln in lines[:5]:
        if len(ln) > 140:
            ln = ln[:137] + "..."
        key_points.append(f"- {ln}")
    if not key_points:
        key_points = ["- Source had little readable text; keep for manual review."]

    return f"""# {path.stem}

## Summary
Auto-generated fallback page because the model returned no parseable decision.

## Key Points
{chr(10).join(key_points)}

## Notable Quotes
> {excerpt[:400]}

## Open Questions
- What are the main concepts in this source?
- Which existing pages should link here?

## Related Concepts
- [Inbox](inbox.md)
"""


# ---------------------------------------------------------------------------
# Apply decisions to disk
# ---------------------------------------------------------------------------


def _append_source_footer(content: str, rel_name: str) -> str:
    return content.rstrip() + (
        f"\n\n---\nLast updated from: `{rel_name}`\n"
        f"Compiled: {dt.datetime.now().isoformat()}\n"
    )


def _apply_decision(
    rel_name: str,
    decision: dict,
    related: list[Path],
) -> tuple[set[str], list[str]]:
    """Apply a parsed decision. Returns (changed_pages, deleted_pages)."""
    changed: set[str] = set()
    deleted: list[str] = []
    related_names = {p.name for p in related}

    writes = decision.get("writes") or []
    deletes = decision.get("deletes") or []
    write_targets: set[str] = set()

    if isinstance(writes, list):
        for entry in writes:
            if not isinstance(entry, dict):
                continue
            fname = _safe_wiki_filename(entry.get("filename", ""))
            content = entry.get("content")
            if not fname or not isinstance(content, str) or not content.strip():
                continue
            if not content.lstrip().startswith("#"):
                content = f"# {Path(fname).stem}\n\n" + content.strip()
            content = _append_source_footer(content, rel_name)
            out_path = WIKI / fname
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")
            changed.add(fname)
            write_targets.add(fname)

    if isinstance(deletes, list):
        for d in deletes:
            fname = _safe_wiki_filename(d) if isinstance(d, str) else None
            if not fname:
                continue
            # Only allow deleting pages that were in the related context AND
            # are not being (re)written this same turn.
            if fname not in related_names or fname in write_targets:
                continue
            target = WIKI / fname
            if not target.is_file():
                continue
            try:
                soft_delete(target, "wiki")
                deleted.append(fname)
            except Exception as e:
                print(f"  ! failed to soft-delete {fname}: {e}")

    return changed, deleted


# ---------------------------------------------------------------------------
# Per-source compile
# ---------------------------------------------------------------------------


def _read_source_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return extract_docx_text(path)
    if suffix == ".pdf":
        return extract_pdf_text(path)
    if suffix == ".pptx":
        return extract_pptx_text(path)
    return read_text(path)


def compile_one_source(path: Path, model: str) -> dict:
    """Compile a single raw file. Returns dict with keys:
    rel_name, changed_pages, deleted_pages, fallback (bool), reasoning (str).
    """
    rel_name = str(path.relative_to(RAW))
    text = _read_source_text(path)
    if not text.strip():
        return {
            "rel_name": rel_name,
            "changed_pages": set(),
            "deleted_pages": [],
            "fallback": False,
            "reasoning": "(source has no readable text)",
        }

    top_k = int(CFG["compile"].get("related_pages_top_k", 5))
    related = _find_related_pages(text, top_k=top_k)
    print(f"Compiling: {rel_name}  (related: {[p.name for p in related] or 'none'})")

    prompt = _build_prompt(rel_name, text, related)
    response = llamacpp_generate(prompt, model=model)
    decision = _parse_decision(response)

    if decision is None:
        # Fallback: write a single page for this source so the run still produces something.
        fname = slugify(path.stem) + ".md"
        article = response.strip() if response.strip() else fallback_article(path, text)
        if not article.lstrip().startswith("#"):
            article = f"# {path.stem}\n\n" + article.strip()
        article = _append_source_footer(article, rel_name)
        (WIKI / fname).write_text(article, encoding="utf-8")
        return {
            "rel_name": rel_name,
            "changed_pages": {fname},
            "deleted_pages": [],
            "fallback": True,
            "reasoning": "(model did not return parseable JSON; wrote a single page as fallback)",
        }

    changed, deleted = _apply_decision(rel_name, decision, related)
    if not changed and not deleted:
        # Decision parsed but did nothing — fall back rather than silently no-op.
        fname = slugify(path.stem) + ".md"
        article = fallback_article(path, text)
        article = _append_source_footer(article, rel_name)
        (WIKI / fname).write_text(article, encoding="utf-8")
        changed = {fname}

    return {
        "rel_name": rel_name,
        "changed_pages": changed,
        "deleted_pages": deleted,
        "fallback": False,
        "reasoning": str(decision.get("reasoning", "") or "")[:500],
    }


# ---------------------------------------------------------------------------
# Mid-loop FAISS refresh so the next source can find pages just written
# ---------------------------------------------------------------------------


def _refresh_faiss_incremental() -> None:
    """Incrementally bring FAISS up to date with the current wiki contents.

    Called between sources in compile_documents so that file N+1 can find
    pages produced by file N. Relies on the FAISS module's own incremental
    update path (which diffs page hashes and only embeds what changed).
    Errors are logged but never raised — a stale FAISS shouldn't abort compile.
    """
    if not CFG["faiss"].get("enabled", True):
        return
    try:
        import sys
        scripts_dir = str((WIKI.parent.parent / "scripts").resolve())
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from faiss_index import faiss_available, build_faiss_index
        if faiss_available():
            build_faiss_index(CFG)
    except Exception as e:
        print(f"  ! FAISS incremental refresh failed: {e}")


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


def compile_documents(
    model: str,
    force: bool = False,
    max_source_chars: int | None = None,
    **_unused,
) -> dict:
    """Iteratively compile changed raw documents into the wiki.

    Returns dict with: compiled (int), skipped (list of (name, error)),
    changed_pages (set), deleted_pages (list).
    """
    ensure_dirs()
    if not ping_llamacpp():
        raise RuntimeError(
            f"llama-swap is not reachable at "
            f"{CFG['llamacpp']['host']}:{CFG['llamacpp']['chat_port']}. "
            "Start it and try again."
        )

    if max_source_chars is not None:
        CFG["compile"]["max_source_chars"] = max_source_chars

    cleanup = validate_docs_index()
    if cleanup["removed_sources"]:
        print(
            f"Cleaned docs.json: {len(cleanup['removed_sources'])} orphaned source(s) removed"
        )

    state = load_json(STATE_FILE, {"compiled": {}})
    docs_index = load_json(DOC_INDEX_FILE, {})

    raw_files = sorted([p for p in RAW.glob("**/*") if should_compile_file(p)])

    # Build content-hash -> path reverse lookup so we can detect moved files.
    # If two old entries share the same hash (duplicates), the first one wins.
    hash_to_old_path: dict[str, str] = {}
    for old_rel, old_hash in state["compiled"].items():
        if old_hash not in hash_to_old_path:
            hash_to_old_path[old_hash] = old_rel

    compiled_now = 0
    changed_wiki_pages: set[str] = set()
    deleted_wiki_pages: list[str] = []
    skipped: list[tuple[str, str]] = []

    try:
        for path in raw_files:
            rel_name = str(path.relative_to(RAW))
            try:
                text = _read_source_text(path)
            except Exception as e:
                print(f"! Skipping {rel_name}: {e}")
                skipped.append((rel_name, str(e)))
                continue
            if not text.strip():
                continue

            digest = sha256_text(text)

            # Content-addressable skip: already compiled under this or another path?
            old_path = hash_to_old_path.get(digest)
            if old_path is not None and not force:
                if old_path != rel_name:
                    # File was moved — update state to the new path, remove the old.
                    old_hash = state["compiled"].pop(old_path, None)
                    state["compiled"][rel_name] = old_hash
                    if old_path in docs_index:
                        docs_index[rel_name] = docs_index.pop(old_path)
                    hash_to_old_path[digest] = rel_name
                    print(f"  (moved) {old_path} -> {rel_name}  (already compiled, skipping)")
                else:
                    print(f"  (skipped) {rel_name}  (unchanged)")
                continue

            try:
                result = compile_one_source(path, model=model)
            except Exception as e:
                print(f"! Compile failed for {rel_name}: {e}")
                skipped.append((rel_name, str(e)))
                continue

            if result["reasoning"]:
                print(f"  -> {result['reasoning']}")
            if result["deleted_pages"]:
                print(f"  -> soft-deleted: {', '.join(result['deleted_pages'])}")

            changed_wiki_pages |= result["changed_pages"]
            deleted_wiki_pages.extend(result["deleted_pages"])

            state["compiled"][rel_name] = digest
            hash_to_old_path[digest] = rel_name
            docs_index[rel_name] = {
                "sha256": digest,
                "updated_at": dt.datetime.now().isoformat(),
            }
            compiled_now += 1

            save_json(STATE_FILE, state)
            save_json(DOC_INDEX_FILE, docs_index)

            # Refresh FAISS so the NEXT source's related-page search can see
            # the pages we just wrote. Without this, batch runs treat every
            # source as a fresh topic because FAISS is frozen at the start.
            if result["changed_pages"] or result["deleted_pages"]:
                _refresh_faiss_incremental()
    finally:
        # Always flush wiki-index + FAISS, even if compile was cancelled or
        # an exception escaped, so subsequent runs don't start from a stale
        # FAISS that omits pages already written to disk.
        if changed_wiki_pages or deleted_wiki_pages:
            from .links import resolve_page_file
            for page_name in changed_wiki_pages:
                page_path = WIKI / page_name
                if page_path.exists():
                    resolve_page_file(page_path)

            # If anything was deleted we touch the full index so removed pages drop out.
            if deleted_wiki_pages:
                build_wiki_index(None)
            else:
                build_wiki_index(None if force else changed_wiki_pages)

            # Final FAISS sweep — usually a no-op because the in-loop refresh
            # kept things current, but cheap insurance against missed updates.
            _refresh_faiss_incremental()

    return {
        "compiled": compiled_now,
        "skipped": skipped,
        "changed_pages": changed_wiki_pages,
        "deleted_pages": deleted_wiki_pages,
    }
