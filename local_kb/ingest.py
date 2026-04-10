"""Ingest helpers: URL fetching, image downloading, filename generation."""

import datetime as dt
import hashlib
import mimetypes
import ssl
import urllib.parse
import urllib.request
from pathlib import Path

from .utils import slugify, unique_path


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


def url_to_filename(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc or "url"
    if parsed.query:
        base += "-" + hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
    return slugify(base)[:100] + ".md"


def _urlopen_with_ssl_fallback(req, timeout: int):
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


def download_image(url: str, out_dir: Path, idx: int, timeout: int = 30):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36"
        },
        method="GET",
    )
    with _urlopen_with_ssl_fallback(req, timeout) as resp:
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
