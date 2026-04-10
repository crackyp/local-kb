"""TF-IDF keyword retrieval fallback for wiki pages."""

import math
import re
from pathlib import Path

from .paths import WIKI
from .utils import read_text


def relevant_pages(question: str, limit: int = 6):
    """Return up to *limit* wiki pages ranked by TF-IDF relevance to *question*."""
    q_terms = set(re.findall(r"[a-zA-Z0-9]{3,}", question.lower()))
    all_pages = list(WIKI.glob("*.md"))
    if not all_pages or not q_terms:
        all_pages.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return all_pages[:limit]

    page_tokens = []
    for p in all_pages:
        tokens = re.findall(r"[a-zA-Z0-9]{3,}", read_text(p).lower())
        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        page_tokens.append(freq)

    n_docs = len(all_pages)
    doc_freq = {}
    for freq in page_tokens:
        for t in freq:
            doc_freq[t] = doc_freq.get(t, 0) + 1

    scores = []
    for i, freq in enumerate(page_tokens):
        score = 0.0
        for term in q_terms:
            tf = freq.get(term, 0)
            if tf == 0:
                continue
            df = doc_freq.get(term, 1)
            idf = math.log((n_docs + 1) / (df + 1)) + 1
            score += (1 + math.log(tf)) * idf
        if score > 0:
            scores.append((score, all_pages[i]))

    scores.sort(key=lambda x: x[0], reverse=True)
    if scores:
        return [p for _, p in scores[:limit]]

    all_pages.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return all_pages[:limit]
