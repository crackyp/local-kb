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


def html_to_markdown(url: str, html_text: str):
    """Convert HTML to a markdown document. Returns (title, markdown, image_urls)."""
    title_match = re.search(
        r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL
    )
    title = html_lib.unescape(title_match.group(1).strip()) if title_match else url

    img_srcs = re.findall(
        r"<img[^>]+src=[\"']([^\"']+)[\"']", html_text, flags=re.IGNORECASE
    )
    image_urls = []
    seen = set()
    for src in img_srcs:
        full = urllib.parse.urljoin(url, src)
        if full in seen:
            continue
        seen.add(full)
        image_urls.append(full)

    cleaned = re.sub(
        r"<script.*?>.*?</script>", "", html_text, flags=re.IGNORECASE | re.DOTALL
    )
    cleaned = re.sub(
        r"<style.*?>.*?</style>", "", cleaned, flags=re.IGNORECASE | re.DOTALL
    )
    cleaned = re.sub(
        r"<noscript.*?>.*?</noscript>", "", cleaned, flags=re.IGNORECASE | re.DOTALL
    )
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
