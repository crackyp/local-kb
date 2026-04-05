#!/usr/bin/env python3
import argparse
import datetime as dt
import glob
import hashlib
import html as html_lib
import json
import mimetypes
import os
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"
RAW = KB / "raw"
RAW_ASSETS = RAW / "assets"
WIKI = KB / "wiki"
OUTPUTS = KB / "outputs"
INDEX = KB / "index"
STATE_FILE = INDEX / "state.json"
DOC_INDEX_FILE = INDEX / "docs.json"
WIKI_INDEX_FILE = INDEX / "wiki_index.json"

TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".ipynb", ".log", ".ini", ".cfg", ".toml", ".sql", ".sh",
}
EXTRACTABLE_EXTENSIONS = {".docx", ".pdf"}
SKIP_PARTS = {"assets", ".git", "node_modules", "__pycache__"}

# ---------------------------------------------------------------------------
# Configuration (reads kb.toml at project root, falls back to defaults)
# ---------------------------------------------------------------------------

_CFG_DEFAULTS = {
    "model": {"default": "phi4-mini"},
    "ollama": {"url": "http://127.0.0.1:11434", "timeout": 240},
    "compile": {"temperature": 0.2, "max_source_chars": 12000},
    "ask": {"temperature": 0.1, "context_per_page": 5000, "default_limit": 6},
    "ingest": {"max_content_chars": 120000},
}


def _load_config() -> dict:
    cfg = json.loads(json.dumps(_CFG_DEFAULTS))  # deep copy
    toml_path = ROOT / "kb.toml"
    if not toml_path.exists():
        return cfg
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return cfg
    try:
        with open(toml_path, "rb") as f:
            user = tomllib.load(f)
        for section, defaults in _CFG_DEFAULTS.items():
            if section in user:
                for key, default_val in defaults.items():
                    if key in user[section]:
                        val = user[section][key]
                        cfg[section][key] = type(default_val)(val)
    except Exception:
        pass
    return cfg


CFG = _load_config()


def ensure_dirs():
    for p in [RAW, RAW_ASSETS, WIKI, OUTPUTS, INDEX]:
        p.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s._-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:120].strip("-._") or "untitled"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    ts = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return path.with_name(f"{stem}-{ts}{suffix}")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig", errors="ignore")
    except Exception:
        return ""


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def extract_links(markdown: str):
    return re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", markdown)


def resolve_input_patterns(patterns):
    resolved = []
    for pattern in patterns:
        pattern = os.path.expanduser(pattern)
        matches = glob.glob(pattern, recursive=True)
        if matches:
            resolved.extend(Path(m) for m in matches)
        else:
            p = Path(pattern)
            if p.exists():
                resolved.append(p)
    # de-dupe, preserve order
    seen = set()
    uniq = []
    for p in resolved:
        k = str(p.resolve()) if p.exists() else str(p)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    return uniq


def should_compile_file(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if not path.is_file():
        return False
    if path.name == ".gitkeep":
        return False

    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS or suffix in EXTRACTABLE_EXTENSIONS:
        return True

    # Fallback sniff for text-like files with uncommon extensions.
    try:
        head = path.read_bytes()[:2048]
        if b"\x00" in head:
            return False
        head.decode("utf-8")
        return True
    except Exception:
        return False


def ping_ollama() -> bool:
    try:
        req = urllib.request.Request(CFG["ollama"]["url"] + "/", method="GET")
        with urllib.request.urlopen(req, timeout=5):
            return True
    except Exception:
        return False


def ollama_generate(prompt: str, model: str, temperature: float = 0.2) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temperature},
    }
    req = urllib.request.Request(
        CFG["ollama"]["url"] + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=CFG["ollama"]["timeout"]) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "").strip()
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        msg = f"HTTP {e.code}"
        if body:
            msg += f" - {body[:300]}"
        raise RuntimeError(f"Ollama call failed: {msg}")
    except Exception as e:
        raise RuntimeError(f"Ollama call failed: {e}")


def fetch_url(url: str, timeout: int = 30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36"
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get("Content-Type", "")


def decode_bytes(content: bytes, content_type: str = "") -> str:
    charset = None
    if "charset=" in content_type.lower():
        charset = content_type.lower().split("charset=")[-1].split(";")[0].strip()

    for enc in [charset, "utf-8", "latin-1"]:
        if not enc:
            continue
        try:
            return content.decode(enc, errors="ignore")
        except Exception:
            continue
    return content.decode("utf-8", errors="ignore")


def html_to_markdown(url: str, html_text: str):
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    title = html_lib.unescape(title_match.group(1).strip()) if title_match else url

    img_srcs = re.findall(r"<img[^>]+src=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE)
    image_urls = []
    seen = set()
    for src in img_srcs:
        full = urllib.parse.urljoin(url, src)
        if full in seen:
            continue
        seen.add(full)
        image_urls.append(full)

    cleaned = re.sub(r"<script.*?>.*?</script>", "", html_text, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<style.*?>.*?</style>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<noscript.*?>.*?</noscript>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<[^>]+>", "\n", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"\r", "", cleaned)
    cleaned = re.sub(r"\n\s*\n\s*\n+", "\n\n", cleaned)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())

    markdown = f"""# {title}

Source URL: {url}
Fetched: {dt.datetime.now().isoformat()}

## Content

{cleaned[:CFG["ingest"]["max_content_chars"]]}
"""
    return title, markdown, image_urls


def url_to_filename(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc or "url"
    if parsed.query:
        base += "-" + hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
    return slugify(base)[:100] + ".md"


def download_image(url: str, out_dir: Path, idx: int, timeout: int = 30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36"
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()

    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if not ext:
        ext = mimetypes.guess_extension(ctype) or ".bin"

    filename = f"img-{idx:03d}{ext}"
    out_path = unique_path(out_dir / filename)
    out_path.write_bytes(data)
    return out_path.name


def extract_pdf_text(pdf_path: Path, max_pages: int | None = None) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        raise RuntimeError(
            "PDF ingest requires pypdf. Install with: pip3 install pypdf"
        )

    reader = PdfReader(str(pdf_path))
    pages = reader.pages
    if max_pages is not None and max_pages > 0:
        pages = pages[:max_pages]

    chunks = []
    for i, page in enumerate(pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        txt = txt.strip()
        if txt:
            chunks.append(f"\n\n## Page {i}\n\n{txt}")

    return "".join(chunks).strip()


def extract_docx_text(docx_path: Path) -> str:
    try:
        from docx import Document  # type: ignore
    except Exception:
        raise RuntimeError(
            "DOCX extraction requires python-docx. Install with: pip install python-docx"
        )

    doc = Document(str(docx_path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def build_wiki_index():
    index = {}
    for path in sorted(WIKI.glob("*.md")):
        text = read_text(path)
        links = extract_links(text)
        first = ""
        for ln in text.splitlines():
            if ln.strip():
                first = ln.strip()
                break
        title = first.lstrip("# ").strip() if first else path.stem
        index[path.name] = {
            "title": title,
            "links_to": [l[1] for l in links],
            "words": len(text.split()),
        }
    save_json(WIKI_INDEX_FILE, index)
    return index


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
    added = 0
    failed_urls = []
    failed_images = []

    for input_url in args.urls:
        url = input_url.strip()
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            url = "https://" + url

        try:
            content, ctype = fetch_url(url, timeout=args.timeout)
        except Exception as e:
            print(f"! Failed {url}: {e}")
            failed_urls.append((url, str(e)))
            continue

        text = decode_bytes(content, ctype)
        if "html" in ctype.lower() or "<html" in text.lower():
            title, markdown, image_urls = html_to_markdown(url, text)
        else:
            title = url
            markdown = f"""# {url}

Source URL: {url}
Fetched: {dt.datetime.now().isoformat()}
Content-Type: {ctype or 'unknown'}

## Content

{text[:CFG["ingest"]["max_content_chars"]]}
"""
            image_urls = []

        out_name = url_to_filename(url)
        out_path = unique_path(RAW / out_name)

        image_notes = ""
        if args.download_images and image_urls:
            img_dir = RAW_ASSETS / out_path.stem
            img_dir.mkdir(parents=True, exist_ok=True)
            downloaded = []
            for i, img_url in enumerate(image_urls[: args.max_images], start=1):
                try:
                    name = download_image(img_url, img_dir, i, timeout=args.timeout)
                    downloaded.append(name)
                except Exception as e:
                    failed_images.append((img_url, str(e)))
                    continue

            if downloaded:
                refs = "\n".join([f"- ![](assets/{out_path.stem}/{n})" for n in downloaded])
                image_notes = f"\n\n## Downloaded Images\n\n{refs}\n"

        out_path.write_text(markdown.strip() + image_notes + "\n", encoding="utf-8")
        added += 1
        print(f"+ {out_path} ({title[:70]})")

    print(f"URL ingest complete. Added {added} page(s).")
    if failed_urls:
        print(f"\nFailed URLs ({len(failed_urls)}):")
        for url, err in failed_urls:
            print(f"  - {url}: {err}")
    if failed_images:
        print(f"\nFailed image downloads ({len(failed_images)}):")
        for img_url, err in failed_images[:20]:
            print(f"  - {img_url}: {err}")


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


def summarize_doc(filename: str, text: str, model: str) -> str:
    prompt = f"""You are compiling a personal research wiki.
Create a concise markdown article from this source document.

Requirements:
- Start with '# <Title>'
- Include sections: Summary, Key Points, Notable Quotes, Open Questions, Related Concepts
- Add 3-8 wiki style links in markdown form like [Concept](concept.md) when relevant.
- Keep it factual and grounded in the source.

Source file: {filename}

SOURCE:
{text[:CFG["compile"]["max_source_chars"]]}
"""
    return ollama_generate(prompt, model=model)


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


def cmd_compile(args):
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")
    state = load_json(STATE_FILE, {"compiled": {}})
    docs_index = load_json(DOC_INDEX_FILE, {})

    raw_files = sorted([p for p in RAW.glob("**/*") if should_compile_file(p)])
    compiled_now = 0
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
        if prev == digest and not args.force:
            continue

        print(f"Compiling: {rel_name}")
        article = summarize_doc(rel_name, text, model=args.model)
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
            if out_path.exists():
                out_path = unique_path(out_path)

        source_note = f"\n\n---\nSource: `{rel_name}`\nCompiled: {dt.datetime.now().isoformat()}\n"
        out_path.write_text(article.strip() + source_note, encoding="utf-8")

        state["compiled"][rel_name] = digest
        docs_index[rel_name] = {
            "wiki_page": out_path.name,
            "sha256": digest,
            "updated_at": dt.datetime.now().isoformat(),
        }
        compiled_now += 1

    save_json(STATE_FILE, state)
    save_json(DOC_INDEX_FILE, docs_index)
    if compiled_now > 0:
        build_wiki_index()
    print(f"Compile complete. Updated {compiled_now} document(s).")
    if skipped:
        print(f"\nSkipped {len(skipped)} file(s):")
        for name, err in skipped:
            print(f"  - {name}: {err}")


def relevant_pages(question: str, limit: int = 6):
    import math

    q_terms = set(re.findall(r"[a-zA-Z0-9]{3,}", question.lower()))
    all_pages = list(WIKI.glob("*.md"))
    if not all_pages or not q_terms:
        all_pages.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return all_pages[:limit]

    # Build per-page term frequencies and document frequencies
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


def cmd_ask(args):
    ensure_dirs()
    if not ping_ollama():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")
    pages = relevant_pages(args.question, limit=args.limit)
    if not pages:
        print("No relevant wiki pages found. Run compile first.")
        return

    context_chunks = []
    for p in pages:
        context_chunks.append(f"## {p.name}\n" + read_text(p)[:CFG["ask"]["context_per_page"]])
    context = "\n\n".join(context_chunks)

    prompt = f"""You are answering a research question using the provided wiki pages.
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
    out_path.write_text(answer + "\n", encoding="utf-8")
    print(f"Wrote: {out_path}")


def cmd_lint(_args):
    ensure_dirs()
    pages = sorted(WIKI.glob("*.md"))
    names = {p.name for p in pages}

    incoming = {n: 0 for n in names}
    broken = []

    for p in pages:
        text = read_text(p)
        for _, link in extract_links(text):
            if link.endswith(".md"):
                target = Path(link).name
                if target not in names:
                    broken.append((p.name, link))
                else:
                    incoming[target] += 1

    orphans = [n for n, c in incoming.items() if c == 0]

    print("\nLint Report")
    print("===========")
    print(f"Pages: {len(pages)}")
    print(f"Broken links: {len(broken)}")
    for src, link in broken[:50]:
        print(f"  - {src} -> {link}")

    print(f"Orphan pages (no incoming links): {len(orphans)}")
    for o in orphans[:50]:
        print(f"  - {o}")


def build_parser():
    p = argparse.ArgumentParser(description="Local KB CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Copy files into kb/raw")
    p_ingest.add_argument("paths", nargs="+", help="File paths or glob patterns")
    p_ingest.set_defaults(func=cmd_ingest)

    p_ingest_url = sub.add_parser("ingest-url", help="Fetch URLs and save as markdown in kb/raw")
    p_ingest_url.add_argument("urls", nargs="+", help="One or more URLs")
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
    p_compile.set_defaults(func=cmd_compile)

    p_ask = sub.add_parser("ask", help="Answer question from wiki and write markdown output")
    p_ask.add_argument("question")
    p_ask.add_argument("--model", default=CFG["model"]["default"])
    p_ask.add_argument("--limit", type=int, default=CFG["ask"]["default_limit"])
    p_ask.set_defaults(func=cmd_ask)

    p_lint = sub.add_parser("lint", help="Check link integrity/orphans in wiki")
    p_lint.set_defaults(func=cmd_lint)

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
