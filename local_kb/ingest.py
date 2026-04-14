"""Ingest helpers: URL fetching, image downloading, single-page ingest, and optional site crawling."""

from __future__ import annotations

import datetime as dt
import hashlib
import mimetypes
import re
import shutil
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import CFG
from .extract import html_to_markdown
from .paths import RAW, RAW_ASSETS, ensure_dirs
from .utils import slugify

USER_AGENT = "local-kb/1.0 (+https://localhost) Mozilla/5.0"
NON_HTML_EXTENSIONS = {
    ".7z", ".avi", ".bin", ".bz2", ".css", ".csv", ".doc", ".docx", ".dmg",
    ".epub", ".gif", ".gz", ".ico", ".jpeg", ".jpg", ".js", ".json", ".m4a",
    ".m4v", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg", ".pdf", ".png", ".ppt",
    ".pptx", ".rar", ".rss", ".svg", ".tar", ".tgz", ".ts", ".txt", ".wav",
    ".webm", ".webp", ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".zip",
}
ProgressCallback = Callable[[str], None] | None


@dataclass
class PreparedPage:
    url: str
    title: str
    markdown: str
    image_urls: list[str]
    content_type: str
    raw_html: str | None = None


@dataclass
class UrlIngestResult:
    added: list[str] = field(default_factory=list)
    failed_urls: list[tuple[str, str]] = field(default_factory=list)
    failed_images: list[tuple[str, str]] = field(default_factory=list)
    pages_added: int = 0
    pages_updated: int = 0

    def extend(self, other: "UrlIngestResult") -> None:
        self.added.extend(other.added)
        self.failed_urls.extend(other.failed_urls)
        self.failed_images.extend(other.failed_images)
        self.pages_added += other.pages_added
        self.pages_updated += other.pages_updated


def _emit(progress: ProgressCallback, line: str) -> None:
    if progress is not None:
        progress(line)


def _build_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )


def _normalize_input_url(url: str) -> str:
    url = url.strip()
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
        return url
    if url.startswith("//"):
        return "https:" + url
    if not re.match(r"^https?://", url, flags=re.IGNORECASE):
        url = "https://" + url
    return url


def _normalize_netloc(parsed: urllib.parse.ParseResult) -> str:
    host = (parsed.hostname or "").lower()
    port = parsed.port
    if not host:
        return parsed.netloc.lower()
    if port and not ((parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)):
        return f"{host}:{port}"
    return host


def normalize_crawl_url(url: str, *, drop_query: bool = True) -> str:
    parsed = urllib.parse.urlparse(_normalize_input_url(url))
    if parsed.scheme.lower() not in {"http", "https"}:
        return ""
    path = parsed.path or "/"
    query = "" if drop_query else parsed.query
    return urllib.parse.urlunparse(
        (
            parsed.scheme.lower(),
            _normalize_netloc(parsed),
            path,
            "",
            query,
            "",
        )
    )


def fetch_url(url: str, timeout: int = 30):
    req = _build_request(url)
    with _urlopen_with_ssl_fallback(req, timeout) as resp:
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


def url_to_filename(url: str) -> str:
    normalized = normalize_crawl_url(url, drop_query=False)
    parsed = urllib.parse.urlparse(normalized or _normalize_input_url(url))
    base = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc or "url"
    if parsed.query:
        base += "-" + hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
    return slugify(base)[:100] + ".md"


def _urlopen_with_ssl_fallback(req: urllib.request.Request, timeout: int):
    """Try strict SSL first, fall back to unverified if the cert is bad."""
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.URLError as e:
        if "CERTIFICATE_VERIFY_FAILED" in str(e):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return urllib.request.urlopen(req, timeout=timeout, context=ctx)
        raise


def download_image(
    url: str,
    out_dir: Path,
    idx: int,
    timeout: int = 30,
    prefix: str | None = None,
):
    req = _build_request(url)
    with _urlopen_with_ssl_fallback(req, timeout) as resp:
        data = resp.read()
        ctype = resp.headers.get("Content-Type", "").split(";")[0].strip().lower()

    parsed = urllib.parse.urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if not ext:
        ext = mimetypes.guess_extension(ctype) or ".bin"

    stem = slugify(prefix)[:80] if prefix else "img"
    filename = f"{stem}-img-{idx:03d}{ext}" if stem else f"img-{idx:03d}{ext}"
    out_path = out_dir / filename
    out_path.write_bytes(data)
    return out_path.name


def prepare_page(url: str, timeout: int = 30) -> PreparedPage:
    content, ctype = fetch_url(url, timeout=timeout)
    text = decode_bytes(content, ctype)

    if "html" in ctype.lower() or "<html" in text.lower():
        title, markdown, image_urls = html_to_markdown(url, text)
        return PreparedPage(
            url=url,
            title=title,
            markdown=markdown,
            image_urls=image_urls,
            content_type=ctype,
            raw_html=text,
        )

    markdown = f"""# {url}

Source URL: {url}
Fetched: {dt.datetime.now().isoformat()}
Content-Type: {ctype or 'unknown'}

## Content

{text[:CFG["ingest"]["max_content_chars"]]}
"""
    return PreparedPage(
        url=url,
        title=url,
        markdown=markdown,
        image_urls=[],
        content_type=ctype,
        raw_html=None,
    )


def save_prepared_page(
    page: PreparedPage,
    *,
    download_images_flag: bool = False,
    max_images: int = 20,
    timeout: int = 30,
    progress: ProgressCallback = None,
) -> tuple[Path, list[str], list[tuple[str, str]], bool]:
    out_name = url_to_filename(page.url)
    out_path = RAW / out_name
    existed = out_path.exists()

    image_notes = ""
    failed_images: list[tuple[str, str]] = []
    downloaded: list[str] = []

    if download_images_flag and page.image_urls:
        img_dir = RAW_ASSETS / out_path.stem
        if img_dir.exists():
            shutil.rmtree(img_dir)
        img_dir.mkdir(parents=True, exist_ok=True)
        _emit(progress, f"Downloading up to {min(len(page.image_urls), max_images)} image(s) for {page.url}")

        for i, img_url in enumerate(page.image_urls[:max_images], start=1):
            try:
                name = download_image(
                    img_url,
                    img_dir,
                    i,
                    timeout=timeout,
                    prefix=out_path.stem,
                )
                downloaded.append(name)
                _emit(progress, f"  image {i}: {name}")
            except Exception as e:
                failed_images.append((img_url, str(e)))
                _emit(progress, f"  image failed: {img_url}: {e}")

        if downloaded:
            refs = "\n".join([f"- ![](assets/{out_path.stem}/{n})" for n in downloaded])
            image_notes = f"\n\n## Downloaded Images\n\n{refs}\n"

    out_path.write_text(page.markdown.strip() + image_notes + "\n", encoding="utf-8")
    return out_path, downloaded, failed_images, existed


def _format_added_line(out_path: Path, title: str, depth: int | None = None, updated: bool = False) -> str:
    prefix = "~" if updated else "+"
    title_preview = title[:70]
    if depth is None:
        return f"{prefix} {out_path} ({title_preview})"
    return f"{prefix} {out_path} [depth {depth}] ({title_preview})"


def _extract_links(url: str, html_text: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        return []

    soup = BeautifulSoup(html_text, "html.parser")
    links: list[str] = []
    for link_tag in soup.find_all("a", href=True):
        href = (link_tag.get("href") or "").strip()
        if not href:
            continue
        links.append(urllib.parse.urljoin(url, href))
    return links


def is_html_link(url: str) -> bool:
    if not url:
        return False

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        return False

    ext = Path(parsed.path).suffix.lower()
    if ext and ext in NON_HTML_EXTENSIONS:
        return False

    return True


def load_robots_parser(start_url: str, timeout: int = 30):
    parsed = urllib.parse.urlparse(_normalize_input_url(start_url))
    robots_url = urllib.parse.urlunparse(
        (parsed.scheme.lower(), _normalize_netloc(parsed), "/robots.txt", "", "", "")
    )

    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        content, content_type = fetch_url(robots_url, timeout=timeout)
        parser.parse(decode_bytes(content, content_type).splitlines())
        return parser
    except Exception:
        return None


def _allowed_by_robots(parser, url: str) -> bool:
    if parser is None:
        return True
    try:
        return parser.can_fetch(USER_AGENT, url)
    except Exception:
        return True


def crawl_and_ingest(
    start_url: str,
    *,
    max_depth: int = 3,
    max_pages: int = 50,
    same_domain: bool = True,
    path_filter: str | None = None,
    respect_robots: bool = True,
    delay: float = 1.0,
    download_images: bool = False,
    max_images: int = 20,
    timeout: int = 30,
    progress: ProgressCallback = None,
) -> UrlIngestResult:
    ensure_dirs()

    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")
    if max_images < 1:
        raise ValueError("max_images must be >= 1")
    if delay < 0:
        raise ValueError("delay must be >= 0")

    if path_filter:
        try:
            compiled_filter = re.compile(path_filter)
        except re.error as e:
            raise ValueError(f"invalid path_filter regex: {e}") from e
    else:
        compiled_filter = None
    start_url = normalize_crawl_url(start_url, drop_query=False)
    start_domain = urllib.parse.urlparse(start_url).netloc
    visited: set[str] = set()
    queued = {start_url}
    queue = deque([(start_url, 0)])
    result = UrlIngestResult()
    robots_parser = load_robots_parser(start_url, timeout=timeout) if respect_robots else None
    last_request_at = 0.0
    _emit(
        progress,
        f"Starting crawl from {start_url} (max_depth={max_depth}, max_pages={max_pages}, delay={delay}s)",
    )

    while queue and result.pages_added < max_pages:
        url, depth = queue.popleft()
        queued.discard(url)
        if url in visited:
            continue
        visited.add(url)

        if respect_robots and not _allowed_by_robots(robots_parser, url):
            _emit(progress, f"Skipping (robots.txt) [{depth}] {url}")
            continue

        if last_request_at and delay > 0:
            elapsed = time.monotonic() - last_request_at
            if elapsed < delay:
                time.sleep(delay - elapsed)

        try:
            _emit(progress, f"Fetching [{depth}] {url}")
            page = prepare_page(url, timeout=timeout)
            last_request_at = time.monotonic()
            out_path, _downloaded, failed_images, existed = save_prepared_page(
                page,
                download_images_flag=download_images,
                max_images=max_images,
                timeout=timeout,
                progress=progress,
            )
        except Exception as e:
            result.failed_urls.append((url, str(e)))
            _emit(progress, f"! Failed [{depth}] {url}: {e}")
            continue

        result.pages_added += 1
        result.pages_updated += int(existed)
        added_line = _format_added_line(out_path, page.title, depth, updated=existed)
        result.added.append(added_line)
        _emit(progress, added_line)
        result.failed_images.extend(failed_images)

        if depth >= max_depth or not page.raw_html:
            continue

        queued_count = 0
        for full_url in _extract_links(url, page.raw_html):
            clean_url = normalize_crawl_url(full_url)
            if not clean_url or clean_url in visited or clean_url in queued:
                continue
            if not is_html_link(clean_url):
                continue

            parsed = urllib.parse.urlparse(clean_url)
            if same_domain and parsed.netloc != start_domain:
                continue
            if compiled_filter and not compiled_filter.search(parsed.path):
                continue
            if respect_robots and not _allowed_by_robots(robots_parser, clean_url):
                _emit(progress, f"Skipping link (robots.txt) {clean_url}")
                continue

            queue.append((clean_url, depth + 1))
            queued.add(clean_url)
            queued_count += 1

        if queued_count:
            _emit(progress, f"Queued {queued_count} link(s) from depth {depth}: {url}")

    if queue and result.pages_added >= max_pages:
        _emit(progress, f"Reached max_pages limit ({max_pages}); stopping crawl.")

    return result


def ingest_urls(
    urls: list[str],
    *,
    download_images: bool = False,
    max_images: int = 20,
    timeout: int = 30,
    crawl: bool = False,
    max_depth: int = 3,
    max_pages: int = 50,
    same_domain: bool = True,
    path_filter: str | None = None,
    respect_robots: bool = True,
    delay: float = 1.0,
    progress: ProgressCallback = None,
) -> UrlIngestResult:
    ensure_dirs()
    result = UrlIngestResult()

    if max_images < 1:
        raise ValueError("max_images must be >= 1")
    if timeout < 1:
        raise ValueError("timeout must be >= 1")
    if crawl:
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0")
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        if delay < 0:
            raise ValueError("delay must be >= 0")

    cleaned_filter = path_filter.strip() if path_filter else None
    _emit(progress, f"Starting URL ingest for {len(urls)} URL(s).")

    for input_url in urls:
        url = _normalize_input_url(input_url)

        if crawl:
            result.extend(
                crawl_and_ingest(
                    url,
                    max_depth=max_depth,
                    max_pages=max_pages,
                    same_domain=same_domain,
                    path_filter=cleaned_filter,
                    respect_robots=respect_robots,
                    delay=delay,
                    download_images=download_images,
                    max_images=max_images,
                    timeout=timeout,
                    progress=progress,
                )
            )
            continue

        try:
            _emit(progress, f"Fetching {url}")
            page = prepare_page(url, timeout=timeout)
            out_path, _downloaded, failed_images, existed = save_prepared_page(
                page,
                download_images_flag=download_images,
                max_images=max_images,
                timeout=timeout,
                progress=progress,
            )
        except Exception as e:
            result.failed_urls.append((url, str(e)))
            _emit(progress, f"! Failed {url}: {e}")
            continue

        result.pages_added += 1
        result.pages_updated += int(existed)
        added_line = _format_added_line(out_path, page.title, updated=existed)
        result.added.append(added_line)
        _emit(progress, added_line)
        result.failed_images.extend(failed_images)

    return result


def format_ingest_report(result: UrlIngestResult, *, include_added: bool = True) -> str:
    lines = result.added.copy() if include_added else []
    created = result.pages_added - result.pages_updated
    lines.append(
        f"URL ingest complete. Processed {result.pages_added} page(s) "
        f"({created} new, {result.pages_updated} updated)."
    )

    if result.failed_urls:
        lines.append(f"\nFailed URLs ({len(result.failed_urls)}):")
        for url, err in result.failed_urls:
            lines.append(f"  - {url}: {err}")

    if result.failed_images:
        lines.append(f"\nFailed image downloads ({len(result.failed_images)}):")
        for img_url, err in result.failed_images[:20]:
            lines.append(f"  - {img_url}: {err}")

    return "\n".join(lines)
