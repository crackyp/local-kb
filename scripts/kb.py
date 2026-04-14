#!/usr/bin/env python3
"""Thin CLI wrapper for local-kb. All business logic lives in the local_kb package."""

import argparse
import datetime as dt
import shutil
import sys
from pathlib import Path

# Ensure the project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _configure_stdio():
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(errors="backslashreplace")
        except Exception:
            continue


_configure_stdio()

from local_kb.config import CFG
from local_kb.paths import RAW, RAW_ASSETS, WIKI, OUTPUTS, ensure_dirs
from local_kb.utils import (
    slugify, unique_path, read_text, resolve_input_patterns,
    ping_ollama, ollama_generate, truncate_at_sentence,
)
from local_kb.extract import extract_pdf_text, extract_docx_text
from local_kb.ingest import ingest_urls, format_ingest_report
from local_kb.compile import compile_documents, build_wiki_index
from local_kb.retrieval import relevant_pages
from local_kb.lint import lint_wiki
from local_kb.health import health_check


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------


def cmd_ingest(args):
    ensure_dirs()
    added = 0
    files = resolve_input_patterns(args.paths)

    for src in files:
        if src.is_dir() or not src.exists():
            continue
        target = unique_path(RAW / src.name)
        shutil.copy2(src, target)
        added += 1
        print(f"+ {target}")

    print(f"Ingest complete. Added {added} file(s).")


def cmd_ingest_url(args):
    ensure_dirs()
    result = ingest_urls(
        args.urls,
        download_images=args.download_images,
        max_images=args.max_images,
        timeout=args.timeout,
        crawl=args.crawl,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        same_domain=args.same_domain,
        path_filter=args.path_filter,
        respect_robots=args.respect_robots,
        delay=args.delay,
        progress=print,
    )
    print(format_ingest_report(result, include_added=False))


def cmd_ingest_pdf(args):
    ensure_dirs()
    added = 0
    files = resolve_input_patterns(args.paths)

    for src in files:
        if src.is_dir() or not src.exists():
            continue
        if src.suffix.lower() != ".pdf":
            print(f"! Skipping non-PDF: {src}")
            continue

        try:
            text = extract_pdf_text(src, max_pages=args.max_pages)
        except Exception as e:
            print(f"! Failed {src}: {e}")
            continue

        if not text.strip():
            text = "(No extractable text found in this PDF.)"

        md = f"""# {src.stem}

Source PDF: {src}
Extracted: {dt.datetime.now().isoformat()}

{text[: args.max_chars]}
"""
        out_path = unique_path(RAW / f"{slugify(src.stem)}.pdf.md")
        out_path.write_text(md.strip() + "\n", encoding="utf-8")
        added += 1
        print(f"+ {out_path}")

        if args.copy_original:
            dst_pdf = unique_path(RAW / src.name)
            shutil.copy2(src, dst_pdf)
            print(f"  copied original -> {dst_pdf}")

    print(f"PDF ingest complete. Added {added} extracted markdown file(s).")


def cmd_compile(args):
    result = compile_documents(
        model=args.model,
        force=args.force,
        max_source_chars=getattr(args, "max_source_chars", None),
        chunking=getattr(args, "chunking", False),
    )
    print(f"Compile complete. Updated {result['compiled']} document(s).")
    if result["skipped"]:
        print(f"\nSkipped {len(result['skipped'])} file(s):")
        for name, err in result["skipped"]:
            print(f"  - {name}: {err}")


def cmd_ask(args):
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")

    context = None

    if CFG["faiss"]["enabled"] and not getattr(args, "no_faiss", False):
        try:
            from faiss_index import faiss_available, assemble_context, FAISS_INDEX_FILE
            if faiss_available() and FAISS_INDEX_FILE.exists():
                context, _source_pages = assemble_context(args.question, CFG)
                if context:
                    print(f"Using FAISS retrieval ({len(_source_pages)} pages, {len(context)} chars)")
        except Exception as e:
            print(f"FAISS retrieval failed, falling back to TF-IDF: {e}")

    if context is None:
        pages = relevant_pages(args.question, limit=args.limit)
        if not pages:
            print("No relevant wiki pages found. Run compile first.")
            return
        context_chunks = []
        for p in pages:
            context_chunks.append(
                f"## {p.name}\n"
                + truncate_at_sentence(read_text(p), CFG["ask"]["context_per_page"])
            )
        context = "\n\n".join(context_chunks)

    prompt = f"""You are answering a question using the provided wiki pages.
Return markdown with:
- # Answer
- ## Direct response
- ## Evidence (bullet points with source page names)
- ## Gaps / uncertainty
- ## Suggested follow-up notes

Question: {args.question}

WIKI CONTEXT:
{context}
"""
    answer = ollama_generate(prompt, model=args.model, temperature=CFG["ask"]["temperature"])

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUTS / f"qa-{ts}.md"
    header = f"> **Q:** {args.question}\n\n"
    out_path.write_text(header + answer + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")


def cmd_index(args):
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")
    try:
        from faiss_index import faiss_available, build_faiss_index
    except ImportError:
        raise RuntimeError("faiss_index module not found.")
    if not faiss_available():
        raise RuntimeError("faiss-cpu is not installed. Install with: pip install faiss-cpu")
    if args.model:
        CFG["faiss"]["embed_model"] = args.model
    stats = build_faiss_index(CFG, force=args.force)
    print(f"Index: {stats['pages']} pages, {stats['chunks']} chunks, {stats['dimensions']}d vectors")


def cmd_lint(_args):
    ensure_dirs()
    result = lint_wiki()
    print("\nLint Report")
    print("===========")
    print(f"Pages: {result['pages']}")
    print(f"Broken links: {len(result['broken'])}")
    for src, link in result["broken"][:50]:
        print(f"  - {src} -> {link}")
    print(f"Orphan pages (no incoming links): {len(result['orphans'])}")
    for o in result["orphans"][:50]:
        print(f"  - {o}")


def cmd_promote(args):
    ensure_dirs()
    src = OUTPUTS / args.filename
    if not src.exists():
        print(f"File not found: {src}")
        sys.exit(1)
    dst_name = f"promoted-{args.filename}"
    dst = RAW / dst_name
    if dst.exists():
        dst = unique_path(dst)
    shutil.copy2(src, dst)
    print(f"Promoted: {src.name} -> raw/{dst.name}")


def cmd_correct(args):
    ensure_dirs()
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    content = f"# Correction: {args.question}\n\n"
    content += f"> **Original question:** {args.question}\n\n"
    content += f"## Correct Information\n\n{args.correction}\n"
    dst = RAW / f"correction-{ts}.md"
    dst.write_text(content, encoding="utf-8")
    print(f"Saved correction: raw/{dst.name}")


def cmd_health_check(args):
    result = health_check(model=args.model)
    if not result["page_count"]:
        print("No wiki pages found. Run compile first.")
        return
    print(result["report"])
    print(f"\nWrote: {result['written_path']}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser():
    p = argparse.ArgumentParser(description="Local KB CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Copy files into kb/raw")
    p_ingest.add_argument("paths", nargs="+", help="File paths or glob patterns")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ingest_url = sub.add_parser("ingest-url", help="Fetch URLs and save as markdown in kb/raw")
    p_ingest_url.add_argument("urls", nargs="+", help="One or more URLs")
    p_ingest_url.add_argument("--crawl", action="store_true", help="Follow links recursively from each starting URL")
    p_ingest_url.add_argument("--max-depth", type=int, default=3, help="Maximum crawl depth (depth 0 = only the starting page)")
    p_ingest_url.add_argument("--max-pages", type=int, default=50, help="Maximum pages to ingest per starting URL when crawling")
    p_ingest_url.add_argument(
        "--same-domain",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Only follow links on the same domain as the starting URL (default: true)",
    )
    p_ingest_url.add_argument("--path-filter", default=None, help="Optional regex applied to the URL path when crawling")
    p_ingest_url.add_argument(
        "--respect-robots",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Obey robots.txt while crawling (default: true)",
    )
    p_ingest_url.add_argument("--delay", type=float, default=1.0, help="Delay between crawl requests in seconds")
    p_ingest_url.add_argument("--download-images", action="store_true", help="Download referenced images")
    p_ingest_url.add_argument("--max-images", type=int, default=20)
    p_ingest_url.add_argument("--timeout", type=int, default=30)
    p_ingest_url.set_defaults(func=cmd_ingest_url)

    p_ingest_pdf = sub.add_parser("ingest-pdf", help="Extract PDF text into kb/raw markdown")
    p_ingest_pdf.add_argument("paths", nargs="+", help="PDF file paths or globs")
    p_ingest_pdf.add_argument("--max-pages", type=int, default=None)
    p_ingest_pdf.add_argument("--max-chars", type=int, default=250000)
    p_ingest_pdf.add_argument("--copy-original", action="store_true", help="Also copy original PDF into kb/raw")
    p_ingest_pdf.set_defaults(func=cmd_ingest_pdf)

    p_compile = sub.add_parser("compile", help="Compile raw docs into wiki pages")
    p_compile.add_argument("--model", default=CFG["model"]["default"])
    p_compile.add_argument("--force", action="store_true")
    p_compile.add_argument("--max-source-chars", type=int, default=None, help="Override max chars per source doc")
    p_compile.add_argument("--chunking", action="store_true", help="Enable chunked compilation for long documents")
    p_compile.set_defaults(func=cmd_compile)

    p_ask = sub.add_parser("ask", help="Answer question from wiki and write markdown output")
    p_ask.add_argument("question")
    p_ask.add_argument("--model", default=CFG["model"]["default"])
    p_ask.add_argument("--limit", type=int, default=CFG["ask"]["default_limit"])
    p_ask.add_argument("--no-faiss", action="store_true", help="Force TF-IDF retrieval instead of FAISS")
    p_ask.set_defaults(func=cmd_ask)

    p_index = sub.add_parser("index", help="Build/rebuild FAISS semantic index")
    p_index.add_argument("--model", default=None, help="Embedding model (default: from kb.toml)")
    p_index.add_argument("--force", action="store_true", help="Rebuild even if index is current")
    p_index.set_defaults(func=cmd_index)

    p_lint = sub.add_parser("lint", help="Check link integrity/orphans in wiki")
    p_lint.set_defaults(func=cmd_lint)

    p_promote = sub.add_parser("promote", help="Copy an output file into raw/ for recompilation")
    p_promote.add_argument("filename", help="Filename in kb/outputs/ to promote")
    p_promote.set_defaults(func=cmd_promote)

    p_correct = sub.add_parser("correct", help="Save a correction note to raw/ for recompilation")
    p_correct.add_argument("question", help="The original question that was answered incorrectly")
    p_correct.add_argument("correction", help="The correct information")
    p_correct.set_defaults(func=cmd_correct)

    p_health = sub.add_parser("health-check", help="LLM-powered wiki quality review")
    p_health.add_argument("--model", default=CFG["model"]["default"])
    p_health.set_defaults(func=cmd_health_check)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("Interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
