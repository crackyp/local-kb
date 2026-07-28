"""Wiki link integrity and orphan analysis."""

from .links import wiki_link_targets
from .paths import WIKI
from .utils import read_text


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
        # Same link definition the graph uses, so a page never counts as
        # orphaned here while showing edges in the graph view.
        for target in wiki_link_targets(read_text(p), exclude=p.name):
            if target not in names:
                broken.append((p.name, target))
            else:
                incoming[target] += 1

    orphans = [n for n, c in incoming.items() if c == 0]

    return {
        "pages": len(pages),
        "broken": broken,
        "orphans": orphans,
    }
