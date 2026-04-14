"""File extraction helpers: PDF (with OCR fallback), DOCX, HTML."""

import datetime as dt
import html as html_lib
import re
import urllib.parse
from pathlib import Path

from .config import CFG


def _ocr_pdf(pdf_path: Path, max_pages: int | None = None) -> str:
    """Extract text from a scanned/image PDF using OCR (easyocr + pymupdf)."""
    try:
        import fitz  # type: ignore
        import easyocr  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return ""

    doc = fitz.open(str(pdf_path))
    pages = list(range(len(doc)))
    if max_pages is not None and max_pages > 0:
        pages = pages[:max_pages]

    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    chunks = []
    for i in pages:
        page = doc[i]
        pix = page.get_pixmap(dpi=200)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
        results = reader.readtext(img, detail=0)
        txt = " ".join(results).strip()
        if txt:
            chunks.append(f"\n\n## Page {i + 1}\n\n{txt}")
    doc.close()
    return "".join(chunks).strip()


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

    text = "".join(chunks).strip()

    if not text:
        print(f"  No text layer found, trying OCR on {pdf_path.name}...")
        text = _ocr_pdf(pdf_path, max_pages)
        if text:
            print(f"  OCR extracted {len(text)} chars.")
        else:
            print(f"  OCR failed or no text found in {pdf_path.name}.")

    return text


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


def _collapse_blank_lines(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _join_fragments(parts: list[str]) -> str:
    out = ""
    for part in parts:
        if not part:
            continue
        if out and not out.endswith((" ", "\n")) and not part.startswith((" ", "\n", ".", ",", ":", ";", "!", "?", ")", "]")):
            if out[-1].isalnum() or out[-1] in (")", "]", "*", "`"):
                if part[0].isalnum() or part[0] in ("[", "*", "`", "("):
                    out += " "
        out += part
    return out


def _html_fragment_to_markdown(node) -> str:
    from bs4 import NavigableString, Tag  # type: ignore

    def render(el) -> str:
        if isinstance(el, NavigableString):
            return " ".join(str(el).split())
        if not isinstance(el, Tag):
            return ""

        name = el.name.lower()
        children = [render(child) for child in el.children]
        body = _join_fragments(children).strip()

        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = max(1, min(6, int(name[1])))
            return f"\n\n{'#' * level} {body}\n\n" if body else ""
        if name == "p":
            return f"\n\n{body}\n\n" if body else ""
        if name == "br":
            return "\n"
        if name in {"strong", "b"}:
            return f"**{body}**" if body else ""
        if name in {"em", "i"}:
            return f"*{body}*" if body else ""
        if name == "code":
            return f"`{body}`" if body else ""
        if name == "pre":
            code_text = el.get_text("\n", strip=False).strip("\n")
            return f"\n\n```\n{code_text}\n```\n\n" if code_text else ""
        if name == "blockquote":
            quote = _collapse_blank_lines(el.get_text("\n", strip=True))
            if not quote:
                return ""
            return "\n\n" + "\n".join(
                f"> {line}" if line else ">" for line in quote.splitlines()
            ) + "\n\n"
        if name in {"ul", "ol"}:
            lines = []
            for idx, li in enumerate(el.find_all("li", recursive=False), start=1):
                marker = f"{idx}." if name == "ol" else "-"
                li_text = _collapse_blank_lines(li.get_text("\n", strip=True))
                if not li_text:
                    continue
                li_lines = li_text.splitlines()
                lines.append(f"{marker} {li_lines[0]}")
                for extra in li_lines[1:]:
                    lines.append(f"  {extra}")
            return "\n\n" + "\n".join(lines) + "\n\n" if lines else ""
        if name == "table":
            rows = []
            for tr in el.find_all("tr"):
                cells = [cell.get_text(" ", strip=True) for cell in tr.find_all(["th", "td"])]
                if any(cells):
                    rows.append(cells)
            if not rows:
                return ""
            width = max(len(row) for row in rows)
            padded = [row + [""] * (width - len(row)) for row in rows]
            header = padded[0]
            sep = ["---"] * width
            lines = [
                "| " + " | ".join(header) + " |",
                "| " + " | ".join(sep) + " |",
            ]
            for row in padded[1:]:
                lines.append("| " + " | ".join(row) + " |")
            return "\n\n" + "\n".join(lines) + "\n\n"
        if name == "a":
            href = (el.get("href") or "").strip()
            if href and body:
                return f"[{body}]({href})"
            return body
        if name in {"article", "section", "main", "div"}:
            return f"\n\n{body}\n\n" if body else ""

        return body

    return _collapse_blank_lines(render(node))


def html_to_markdown(url: str, html_text: str):
    """Convert HTML to markdown using a DOM parser. Returns (title, markdown, image_urls)."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "HTML ingest requires beautifulsoup4. Install with: pip install beautifulsoup4"
        ) from exc

    soup = BeautifulSoup(html_text, "html.parser")

    title = url
    if soup.title and soup.title.string:
        title = html_lib.unescape(" ".join(soup.title.string.split()))

    for tag in soup(["script", "style", "noscript", "template", "svg", "canvas", "iframe", "form"]):
        tag.decompose()

    body = soup.body or soup
    candidates = []
    for selector in (
        "main",
        "article",
        "[role='main']",
        ".content",
        ".post-content",
        ".entry-content",
        ".article-content",
    ):
        candidates.extend(body.select(selector))

    content_root = max(candidates, key=lambda node: len(node.get_text(" ", strip=True))) if candidates else body

    for tag in content_root.select("nav, footer, aside, .sidebar, .menu, .breadcrumbs"):
        tag.decompose()

    image_urls = []
    seen = set()
    for img in content_root.find_all("img"):
        src = (img.get("src") or img.get("data-src") or img.get("data-original") or "").strip()
        if not src:
            continue
        full = urllib.parse.urljoin(url, src)
        if full in seen:
            continue
        seen.add(full)
        image_urls.append(full)

    cleaned = _html_fragment_to_markdown(content_root)
    if not cleaned:
        cleaned = _collapse_blank_lines(html_lib.unescape(body.get_text("\n", strip=True)))

    markdown = f"""# {title}

Source URL: {url}
Fetched: {dt.datetime.now().isoformat()}

## Content

{cleaned[:CFG["ingest"]["max_content_chars"]]}
"""
    return title, markdown, image_urls
