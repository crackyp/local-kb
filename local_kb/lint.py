"""Wiki link integrity and orphan analysis."""

from .paths import WIKI
from .utils import read_text, extract_links


def lint_wiki() -> dict:
    """Check wiki link integrity and orphan pages.

    Returns a dict with keys: pages (int), broken (list of (src, link)),
    orphans (list of page names).
    """
    pages = sorted(WIKI.glob("*.md"))
    names = {p.name for p in pages}

    incoming = {n: 0 for n in names}
    broken = []

    for p in pages:
        text = read_text(p)
        for _, link in extract_links(text):
            if link.endswith(".md"):
                from pathlib import Path as _P
                target = _P(link).name
                if target not in names:
                    broken.append((p.name, link))
                else:
                    incoming[target] += 1

    orphans = [n for n, c in incoming.items() if c == 0]

    return {
        "pages": len(pages),
        "broken": broken,
        "orphans": orphans,
    }
