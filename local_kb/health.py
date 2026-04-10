"""LLM-powered wiki health-check report generation."""

import datetime as dt
from pathlib import Path

from .config import CFG
from .paths import WIKI, OUTPUTS, ensure_dirs
from .utils import read_text, extract_links, ping_ollama, ollama_generate


def health_check(model: str) -> dict:
    """Run an LLM-powered wiki quality review.

    Returns a dict with keys: report (str), written_path (Path or None),
    page_count (int).
    """
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")

    pages = sorted(WIKI.glob("*.md"))
    pages = [p for p in pages if p.name != "INDEX.md"]
    if not pages:
        return {"report": "", "written_path": None, "page_count": 0}

    summaries = []
    for p in pages:
        text = read_text(p)
        links = extract_links(text)
        lines = text.splitlines()
        first_para = ""
        for ln in lines:
            if ln.strip():
                first_para += ln.strip() + " "
                if len(first_para) > 500:
                    break
        link_names = [l[1] for l in links]
        summaries.append(
            f"## {p.name}\n{first_para.strip()}\nLinks to: {', '.join(link_names) if link_names else 'none'}"
        )

    wiki_summary = "\n\n".join(summaries)
    max_chars = CFG["compile"].get("max_source_chars", 12000) * 2
    if len(wiki_summary) > max_chars:
        wiki_summary = wiki_summary[:max_chars] + "\n\n[...truncated...]"

    prompt = f"""You are reviewing a personal knowledge base wiki for quality.
The wiki has {len(pages)} pages. Here is a summary of each page:

{wiki_summary}

Produce a health-check report in markdown with these sections:
- # Wiki Health Check
- ## Contradictions (statements in one article that conflict with another)
- ## Unexplained Topics (topics mentioned or linked but never have their own article)
- ## Unsourced Claims (assertions that appear to lack supporting evidence or source references)
- ## Suggested New Articles (3-5 new articles that would fill gaps in the wiki)

Be specific. Reference page filenames. If a section has no issues, say "None found."
"""
    print(f"Reviewing {len(pages)} wiki pages...")
    report = ollama_generate(prompt, model=model, temperature=CFG["ask"]["temperature"])

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUTS / f"health-check-{ts}.md"
    out_path.write_text(report + "\n", encoding="utf-8")

    return {"report": report, "written_path": out_path, "page_count": len(pages)}
