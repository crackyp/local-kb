"""Shared utility functions for local-kb."""

import datetime as dt
import glob
import hashlib
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .config import CFG
from .paths import SKIP_PARTS, TEXT_EXTENSIONS, EXTRACTABLE_EXTENSIONS


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

import json


def load_json(path: Path, default):
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Text / file helpers
# ---------------------------------------------------------------------------


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
    seen = set()
    uniq = []
    for p in resolved:
        k = str(p.resolve()) if p.exists() else str(p)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(p)
    return uniq


def truncate_at_sentence(text: str, max_chars: int) -> str:
    """Truncate text to max_chars, cutting at the last sentence boundary."""
    if len(text) <= max_chars:
        return text
    chunk = text[:max_chars]
    for sep in ("\n\n", ".\n", ". ", ".\t"):
        pos = chunk.rfind(sep)
        if pos > max_chars // 2:
            return chunk[: pos + len(sep)].rstrip()
    pos = chunk.rfind("\n")
    if pos > max_chars // 2:
        return chunk[:pos].rstrip()
    return chunk.rstrip()


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

    try:
        head = path.read_bytes()[:2048]
        if b"\x00" in head:
            return False
        head.decode("utf-8")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Ollama helpers
# ---------------------------------------------------------------------------


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
