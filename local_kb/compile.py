"""Compile pipeline: raw sources -> wiki pages."""

import datetime as dt
import re
from pathlib import Path

from .config import CFG
from .paths import RAW, WIKI, INDEX, STATE_FILE, DOC_INDEX_FILE, WIKI_INDEX_FILE, ensure_dirs
from .utils import (
    load_json, save_json, slugify, unique_path, read_text, sha256_text,
    extract_links, truncate_at_sentence, should_compile_file,
    ping_ollama, ollama_generate,
)
from .extract import extract_pdf_text, extract_docx_text


# ---------------------------------------------------------------------------
# Wiki index
# ---------------------------------------------------------------------------


def _index_wiki_page(path: Path) -> dict:
    """Extract index metadata for a single wiki page."""
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
    """Write wiki/INDEX.md from the index dict."""
    if not index:
        idx_path = WIKI / "INDEX.md"
        if idx_path.exists():
            idx_path.unlink()
        return
    lines = ["# Wiki Index", f"\n{len(index)} topics\n"]
    for fname in sorted(index):
        title = index[fname]["title"]
        lines.append(f"- [[{fname}]] — {title}")
    (WIKI / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_wiki_index(changed_pages: set | None = None):
    """Build or incrementally update the wiki index.

    If *changed_pages* is provided (set of wiki filenames), only those pages
    are re-read.  Pages in the index that no longer exist on disk are pruned.
    If *changed_pages* is None, a full rebuild is performed.
    """
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
# Matching / merging
# ---------------------------------------------------------------------------


def find_matching_wiki_page(text: str, cfg: dict):
    """Return (wiki_path, existing_content) if a raw doc matches an existing wiki page, else None."""
    from .retrieval import relevant_pages

    query = text[:500]
    threshold = cfg["compile"]["merge_threshold"]

    if cfg["faiss"]["enabled"]:
        try:
            from faiss_index import faiss_available, search_chunks, FAISS_INDEX_FILE
            if faiss_available() and FAISS_INDEX_FILE.exists():
                results = search_chunks(query, cfg)
                if results:
                    page_scores = {}
                    for r in results:
                        page_scores[r["page"]] = page_scores.get(r["page"], 0) + r["score"]
                    best_page = max(page_scores, key=page_scores.get)
                    if page_scores[best_page] >= threshold:
                        wiki_path = WIKI / best_page
                        if wiki_path.exists():
                            return (wiki_path, read_text(wiki_path))
        except Exception as e:
            print(f"FAISS match lookup failed, trying TF-IDF: {e}")

    pages = relevant_pages(query, limit=1)
    if pages:
        page_text = read_text(pages[0])
        raw_terms = set(re.findall(r"[a-zA-Z0-9]{3,}", query.lower()))
        page_terms = set(re.findall(r"[a-zA-Z0-9]{3,}", page_text[:2000].lower()))
        if raw_terms and page_terms:
            overlap = len(raw_terms & page_terms) / len(raw_terms)
            if overlap >= threshold:
                return (pages[0], page_text)

    return None


def update_doc(filename: str, text: str, existing_wiki: str, model: str) -> str:
    """Merge new source material into an existing wiki article."""
    max_wiki = CFG["compile"]["max_wiki_chars"]
    max_source = CFG["compile"]["max_source_chars"]

    prompt = f"""You are updating a personal research wiki article with new source material.
Merge the new information into the existing article. Preserve the existing structure and content.
Add new facts, quotes, and points. Do not remove existing content unless it's contradicted.
Preserve specific details: procedures, methods, requirements, timelines, definitions, and conditions.
Keep the same markdown section structure. Add new sections if the new source covers topics not in the existing article.
Add 3-8 wiki style links in markdown form like [Concept](concept.md) when relevant.

EXISTING ARTICLE:
{truncate_at_sentence(existing_wiki, max_wiki)}

NEW SOURCE ({filename}):
{truncate_at_sentence(text, max_source)}
"""
    return ollama_generate(prompt, model=model)


# ---------------------------------------------------------------------------
# Summarization
# ---------------------------------------------------------------------------


def _summarize_single(filename: str, text: str, model: str) -> str:
    """Single-pass summarization (truncates if needed)."""
    source_text = truncate_at_sentence(text, CFG["compile"]["max_source_chars"])
    prompt = f"""You are compiling a personal research wiki.
Create a comprehensive markdown article from this source document.
Your article should preserve the important detail from the source — do NOT over-summarize.

Requirements:
- Start with '# <Title>' where <Title> is a short, descriptive phrase (3-7 words) that captures the MAIN TOPIC or CONCEPT of the content — NOT the filename. Examples: "# Attention Mechanisms in Transformers", "# Notes on Stoic Philosophy", "# 2024 Q3 Budget Analysis".
- Start with a ## Summary section (one paragraph overview).
- Then use ## sections that mirror the source document's own structure (e.g., if the source has Rule 1, Rule 2, etc., create sections for each; if it has chapters, use those).
- Within each section, preserve specific details: procedures, methods, requirements, timelines, numbered lists, definitions, and conditions. Use sub-headings (###) and bullet points to organize dense content.
- If the source is a legal document, regulation, or technical specification, preserve the specific rules, requirements, and procedures — these details ARE the knowledge.
- End with: ## Notable Quotes (2-5 key quotes), ## Open Questions, ## Related Concepts (3-8 wiki links in markdown form like [Concept](concept.md)).
- Keep it factual and grounded in the source. Do not invent information.
- The article length should be proportional to the source detail. A detailed source should produce a detailed article.

Source file: {filename}

SOURCE:
{source_text}
"""
    return ollama_generate(prompt, model=model)


def _summarize_chunked(filename: str, text: str, model: str) -> str:
    """Multi-pass chunked summarization for long documents."""
    max_chars = CFG["compile"]["max_source_chars"]
    chunks = []
    pos = 0
    while pos < len(text):
        chunk = truncate_at_sentence(text[pos:], max_chars)
        if not chunk:
            pos += max_chars
            continue
        chunks.append(chunk)
        pos += len(chunk)

    print(f"  Chunking: {len(text)} chars -> {len(chunks)} chunks")
    summaries = []
    for i, chunk in enumerate(chunks, 1):
        print(f"  Summarizing chunk {i}/{len(chunks)}...")
        label = f"(part {i}/{len(chunks)})"
        prompt = f"""You are compiling a personal research wiki.
Extract the key facts, points, and quotes from this source document {label}.
Return a concise bullet-point summary. Be thorough — do not omit details.

Source file: {filename}

SOURCE:
{chunk}
"""
        summary = ollama_generate(prompt, model=model)
        if summary.strip():
            summaries.append(summary.strip())

    if not summaries:
        return ""
    if len(summaries) == 1:
        return summaries[0]

    print(f"  Merging {len(summaries)} chunk summaries...")
    combined = "\n\n---\n\n".join(
        f"Part {i+1}:\n{s}" for i, s in enumerate(summaries)
    )
    prompt = f"""You are compiling a personal research wiki.
Below are summaries extracted from different parts of the same source document.
Merge them into a single, comprehensive markdown article. Remove duplicates and organize logically.

Requirements:
- Start with '# <Title>' where <Title> is a short, descriptive phrase (3-7 words) that captures the MAIN TOPIC or CONCEPT of the content — NOT the filename.
- Start with a ## Summary section (one paragraph overview).
- Then use ## sections that mirror the source document's structure. Preserve specific details: procedures, methods, requirements, timelines, definitions, and conditions.
- Use ### sub-headings and bullet points to organize dense content.
- End with: ## Notable Quotes, ## Open Questions, ## Related Concepts (3-8 wiki links like [Concept](concept.md)).
- Keep it factual. Do not omit important details just to be brief — the article length should be proportional to the source detail.

Source file: {filename}

PART SUMMARIES:
{truncate_at_sentence(combined, max_chars * 2)}
"""
    return ollama_generate(prompt, model=model)


def summarize_doc(filename: str, text: str, model: str) -> str:
    max_chars = CFG["compile"]["max_source_chars"]
    use_chunking = CFG["compile"].get("chunking", False)

    if use_chunking and len(text) > max_chars:
        return _summarize_chunked(filename, text, model)
    return _summarize_single(filename, text, model)


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
Auto-generated fallback page because the model returned an empty response.

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
# Compile orchestration
# ---------------------------------------------------------------------------


def compile_documents(
    model: str,
    force: bool = False,
    max_source_chars: int | None = None,
    chunking: bool = False,
) -> dict:
    """Compile raw documents into wiki pages.

    Returns a dict with keys: compiled (int), skipped (list of tuples),
    changed_pages (set of wiki filenames).
    """
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")

    if max_source_chars is not None:
        CFG["compile"]["max_source_chars"] = max_source_chars
    if chunking:
        CFG["compile"]["chunking"] = True

    state = load_json(STATE_FILE, {"compiled": {}})
    docs_index = load_json(DOC_INDEX_FILE, {})

    raw_files = sorted([p for p in RAW.glob("**/*") if should_compile_file(p)])
    compiled_now = 0
    changed_wiki_pages: set = set()
    skipped = []

    for path in raw_files:
        suffix = path.suffix.lower()
        if suffix == ".docx":
            try:
                text = extract_docx_text(path)
            except Exception as e:
                print(f"! Skipping {path.name}: {e}")
                skipped.append((path.name, str(e)))
                continue
        elif suffix == ".pdf":
            try:
                text = extract_pdf_text(path)
            except Exception as e:
                print(f"! Skipping {path.name}: {e}")
                skipped.append((path.name, str(e)))
                continue
        else:
            text = read_text(path)
        if not text.strip():
            continue

        digest = sha256_text(text)
        rel_name = str(path.relative_to(RAW))
        prev = state["compiled"].get(rel_name)
        wiki_page = docs_index.get(rel_name, {}).get("wiki_page")
        wiki_exists = (WIKI / wiki_page).exists() if wiki_page else False
        if prev == digest and wiki_exists and not force:
            continue

        merge_match = None
        if not docs_index.get(rel_name) and CFG["compile"].get("merge_into_existing", False):
            merge_match = find_matching_wiki_page(text, CFG)

        if merge_match:
            wiki_path, existing_content = merge_match
            print(f"Merging: {rel_name} -> {wiki_path.name}")
            article = update_doc(rel_name, text, existing_content, model=model)
            if not article.strip():
                article = fallback_article(path, text)
            elif not article.lstrip().startswith("#"):
                article = f"# {path.stem}\n\n" + article.strip()
            out_path = wiki_path
        else:
            print(f"Compiling: {rel_name}")
            article = summarize_doc(rel_name, text, model=model)
            if not article.strip():
                article = fallback_article(path, text)
            elif not article.lstrip().startswith("#"):
                article = f"# {path.stem}\n\n" + article.strip()

            title_line = article.splitlines()[0] if article.strip() else f"# {path.stem}"
            title = title_line.lstrip("# ").strip() or path.stem
            out_name = slugify(title) + ".md"
            prev_page = docs_index.get(rel_name, {}).get("wiki_page")
            if prev_page:
                out_path = WIKI / prev_page
            else:
                out_path = WIKI / out_name
                claimed_pages = {
                    v["wiki_page"]
                    for k, v in docs_index.items()
                    if isinstance(v, dict) and "wiki_page" in v and k != rel_name
                }
                if out_path.exists() or out_name in claimed_pages:
                    out_path = unique_path(out_path)

        source_note = f"\n\n---\nSource: `{rel_name}`\nCompiled: {dt.datetime.now().isoformat()}\n"
        out_path.write_text(article.strip() + source_note, encoding="utf-8")

        state["compiled"][rel_name] = digest
        docs_index[rel_name] = {
            "wiki_page": out_path.name,
            "sha256": digest,
            "updated_at": dt.datetime.now().isoformat(),
        }
        changed_wiki_pages.add(out_path.name)
        compiled_now += 1

    save_json(STATE_FILE, state)
    save_json(DOC_INDEX_FILE, docs_index)

    if compiled_now > 0:
        build_wiki_index(None if force else changed_wiki_pages)
        if CFG["faiss"]["enabled"]:
            try:
                from faiss_index import faiss_available, build_faiss_index
                if faiss_available():
                    print("Updating FAISS index...")
                    build_faiss_index(CFG)
            except Exception as e:
                print(f"FAISS auto-index skipped: {e}")

    return {
        "compiled": compiled_now,
        "skipped": skipped,
        "changed_pages": changed_wiki_pages,
    }
