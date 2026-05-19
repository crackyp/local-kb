"""Resolve LLM-generated wiki links to real wiki pages.

The compile prompts ask the model to emit links like ``[Concept](concept.md)``.
The model invents the slug, so it almost never matches the real filename
produced by ``slugify(title)``. This module rewrites those links to point at
existing pages (matching by slug or title) and strips links that cannot be
resolved, so the wiki has no dead links.
"""

import re
from pathlib import Path

from .paths import WIKI, WIKI_INDEX_FILE
from .utils import load_json

# Matches [Text](href.md). Only .md targets are considered wiki links.
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+\.md)\)")


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def _build_page_lookup() -> dict[str, str]:
    """Return ``{normalized_key: real_filename}`` for every wiki page.

    Keys come from each page's filename stem and (when available) its title in
    ``wiki_index.json``. The first key wins on collision so filenames take
    precedence over titles.
    """
    index = load_json(WIKI_INDEX_FILE, {})
    real = {p.name for p in WIKI.glob("*.md") if p.name != "INDEX.md"}
    lookup: dict[str, str] = {}

    for fname in real:
        key = _normalize(Path(fname).stem)
        if key:
            lookup.setdefault(key, fname)

    for fname, meta in index.items():
        if fname not in real or not isinstance(meta, dict):
            continue
        title = meta.get("title") or ""
        key = _normalize(title)
        if key:
            lookup.setdefault(key, fname)

    return lookup


def _best_match(query: str, lookup: dict[str, str]) -> str | None:
    """Find the best real page for *query* (a link href stem or link text)."""
    key = _normalize(query)
    if not key:
        return None
    if key in lookup:
        return lookup[key]

    q_tokens = set(key.split())
    if not q_tokens:
        return None

    best: str | None = None
    best_score = 0.0
    for cand_key, fname in lookup.items():
        c_tokens = set(cand_key.split())
        if not c_tokens:
            continue
        overlap = len(q_tokens & c_tokens) / len(q_tokens | c_tokens)
        # All query tokens contained in candidate is a strong signal.
        if q_tokens.issubset(c_tokens):
            overlap = max(overlap, 0.85)
        if overlap > best_score:
            best_score = overlap
            best = fname

    return best if best_score >= 0.7 else None


def resolve_links(text: str) -> tuple[str, dict]:
    """Rewrite or strip dead .md links in *text*.

    Returns ``(new_text, stats)`` where stats counts how many links were
    ``kept`` (already valid), ``resolved`` (rewritten to a real page), or
    ``stripped`` (no match — link replaced by its plain text).
    """
    real_files = {p.name for p in WIKI.glob("*.md") if p.name != "INDEX.md"}
    lookup = _build_page_lookup()
    stats = {"resolved": 0, "kept": 0, "stripped": 0}

    def _replace(m: re.Match) -> str:
        link_text, href = m.group(1), m.group(2)
        href_name = Path(href).name

        if href_name in real_files:
            stats["kept"] += 1
            return m.group(0)

        if lookup:
            target = (
                _best_match(Path(href_name).stem, lookup)
                or _best_match(link_text, lookup)
            )
            if target:
                stats["resolved"] += 1
                return f"[{link_text}]({target})"

        stats["stripped"] += 1
        return link_text

    return _LINK_PATTERN.sub(_replace, text), stats


def resolve_page_file(page_path: Path) -> dict:
    """Resolve links in a single wiki page on disk. Returns the stats dict."""
    original = page_path.read_text(encoding="utf-8")
    new_text, stats = resolve_links(original)
    if new_text != original:
        page_path.write_text(new_text, encoding="utf-8")
    return stats
