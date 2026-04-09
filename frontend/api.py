#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "kb"
RAW_DIR = KB_DIR / "raw"
WIKI_DIR = KB_DIR / "wiki"
OUTPUTS_DIR = KB_DIR / "outputs"
SCRIPTS_DIR = ROOT / "scripts"
CLI_PATH = SCRIPTS_DIR / "kb.py"
TMP_UPLOADS = ROOT / ".tmp_uploads"

DEFAULT_MODEL = "gpt-oss:20b"

PREVIEWABLE = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv",
    ".html", ".htm", ".py", ".js", ".ts", ".sql", ".log",
    ".toml", ".ini", ".cfg", ".sh", ".bat",
}

app = FastAPI(title="Local KB API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def ensure_dirs():
    for p in [RAW_DIR, WIKI_DIR, OUTPUTS_DIR, KB_DIR / "index", RAW_DIR / "assets", TMP_UPLOADS]:
        p.mkdir(parents=True, exist_ok=True)


def run_kb(args: List[str]) -> tuple[int, str, str]:
    cmd = [sys.executable, str(CLI_PATH), *args]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    combined = output + ("\n\n" + err if err else "")
    shown_cmd = " ".join([str(x) for x in cmd])
    return proc.returncode, combined.strip(), shown_cmd


def scan_files(directory: Path, pattern: str = "**/*", files_only: bool = True) -> List[Path]:
    if not directory.exists():
        return []
    paths = list(directory.glob(pattern))
    if files_only:
        paths = [p for p in paths if p.is_file() and p.name != ".gitkeep"]
    paths.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return paths


def fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def fmt_date(ts: float) -> str:
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def file_meta(p: Path) -> dict:
    stat = p.stat()
    return {
        "name": p.name,
        "size": stat.st_size,
        "size_h": fmt_size(stat.st_size),
        "modified": stat.st_mtime,
        "modified_h": fmt_date(stat.st_mtime),
        "rel": str(p.relative_to(p.parent.parent)),
    }


def ollama_is_running() -> bool:
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def ollama_models() -> List[str]:
    try:
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def safe_name(name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    cleaned = "".join(ch if ch in allowed else "-" for ch in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-.")
    return cleaned or f"upload-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    ts = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return path.with_name(f"{path.stem}-{ts}{path.suffix}")


def parse_written_path(output: str) -> Optional[Path]:
    marker = "Wrote:"
    for line in output.splitlines():
        if line.startswith(marker):
            maybe = line.replace(marker, "", 1).strip()
            p = Path(maybe)
            return p if p.exists() else None
    return None


class IngestRequest(BaseModel):
    paths: List[str]


class IngestUrlRequest(BaseModel):
    urls: List[str]
    download_images: bool = False
    max_images: int = 20
    timeout: int = 30


class CompileRequest(BaseModel):
    model: str = DEFAULT_MODEL
    force: bool = False


class AskRequest(BaseModel):
    question: str
    model: str = DEFAULT_MODEL
    limit: int = 6
    use_faiss: bool = True


class IndexRequest(BaseModel):
    force: bool = False
    model: Optional[str] = None


@app.on_event("startup")
async def startup():
    ensure_dirs()


@app.get("/api/status")
async def get_status():
    alive = ollama_is_running()
    models = ollama_models() if alive else []
    raw_count = len(scan_files(RAW_DIR))
    wiki_count = len(scan_files(WIKI_DIR, "*.md"))
    out_count = len(scan_files(OUTPUTS_DIR, "*.md"))

    faiss_status = "unknown"
    try:
        sys.path.insert(0, str(SCRIPTS_DIR))
        from faiss_index import faiss_available, is_index_stale, FAISS_INDEX_FILE
        if faiss_available():
            if FAISS_INDEX_FILE.exists():
                faiss_status = "stale" if is_index_stale() else "ready"
            else:
                faiss_status = "not_built"
        else:
            faiss_status = "not_installed"
    except Exception:
        faiss_status = "unavailable"

    return {
        "ollama": {"running": alive, "models": models},
        "files": {"raw": raw_count, "wiki": wiki_count, "outputs": out_count},
        "faiss": faiss_status,
    }


@app.post("/api/ingest/upload")
async def ingest_upload(files: List[UploadFile] = File(...)):
    saved = []
    for f in files:
        name = safe_name(f.filename or "upload")
        dst = unique_path(RAW_DIR / name)
        content = await f.read()
        dst.write_bytes(content)
        saved.append({"name": dst.name, "size": len(content)})
    return {"saved": saved, "count": len(saved)}


@app.post("/api/ingest/path")
async def ingest_path(data: IngestRequest):
    rc, out, cmd = run_kb(["ingest", *data.paths])
    return {"returncode": rc, "output": out, "command": cmd}


@app.post("/api/ingest/url")
async def ingest_url(data: IngestUrlRequest):
    args = ["ingest-url", *data.urls, "--timeout", str(data.timeout), "--max-images", str(data.max_images)]
    if data.download_images:
        args.append("--download-images")
    rc, out, cmd = run_kb(args)
    return {"returncode": rc, "output": out, "command": cmd}


@app.post("/api/ingest/pdf")
async def ingest_pdf(
    files: List[UploadFile] = File(...),
    max_pages: int = 0,
    copy_original: bool = False,
):
    tmp_paths = []
    for f in files:
        name = safe_name(f.filename or "upload.pdf")
        dst = unique_path(TMP_UPLOADS / name)
        content = await f.read()
        dst.write_bytes(content)
        tmp_paths.append(dst)

    args = ["ingest-pdf", *[str(p) for p in tmp_paths]]
    if max_pages > 0:
        args += ["--max-pages", str(max_pages)]
    if copy_original:
        args.append("--copy-original")

    rc, out, cmd = run_kb(args)

    for tmp in tmp_paths:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass

    return {"returncode": rc, "output": out, "command": cmd}


@app.post("/api/compile")
async def compile_wiki(data: CompileRequest):
    args = ["compile", "--model", data.model]
    if data.force:
        args.append("--force")
    rc, out, cmd = run_kb(args)
    return {"returncode": rc, "output": out, "command": cmd}


@app.post("/api/index")
async def build_index(data: IndexRequest):
    args = ["index"]
    if data.force:
        args.append("--force")
    if data.model:
        args.extend(["--model", data.model])
    rc, out, cmd = run_kb(args)
    return {"returncode": rc, "output": out, "command": cmd}


@app.post("/api/ask")
async def ask_wiki(data: AskRequest):
    args = ["ask", data.question, "--model", data.model, "--limit", str(data.limit)]
    # Verify requested model exists
    if data.model not in ollama_models():
        raise HTTPException(404, f"model '{data.model}' not found")
    rc, out, cmd = run_kb(args)

    written = parse_written_path(out) if rc == 0 else None
    answer = ""
    if written and written.exists():
        answer = written.read_text(encoding="utf-8", errors="ignore")

    return {"returncode": rc, "output": out, "command": cmd, "answer": answer, "written_file": written.name if written else None}


@app.post("/api/lint")
async def lint_wiki():
    rc, out, cmd = run_kb(["lint"])
    return {"returncode": rc, "output": out, "command": cmd}


@app.get("/api/files/{category}")
async def list_files(category: str):
    if category == "raw":
        files = scan_files(RAW_DIR)
        base = RAW_DIR
    elif category == "wiki":
        files = scan_files(WIKI_DIR, "*.md")
        base = WIKI_DIR
    elif category == "outputs":
        files = scan_files(OUTPUTS_DIR, "*.md")
        base = OUTPUTS_DIR
    else:
        raise HTTPException(400, "Invalid category")

    result = []
    for p in files:
        try:
            meta = file_meta(p)
            meta["rel"] = str(p.relative_to(base))
            result.append(meta)
        except Exception:
            continue

    return {"files": result, "count": len(result)}


@app.get("/api/file/{category}/{path:path}")
async def get_file(category: str, path: str):
    if category == "raw":
        base = RAW_DIR
    elif category == "wiki":
        base = WIKI_DIR
    elif category == "outputs":
        base = OUTPUTS_DIR
    else:
        raise HTTPException(400, "Invalid category")

    file_path = base / path
    if not file_path.exists():
        raise HTTPException(404, "File not found")

    if file_path.suffix.lower() in PREVIEWABLE:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return {"content": content, "previewable": True}
    else:
        return {"content": None, "previewable": False, "note": f"Binary file ({file_path.suffix})"}


@app.delete("/api/file/{category}/{path:path}")
async def delete_file(category: str, path: str):
    if category == "raw":
        base = RAW_DIR
    elif category == "wiki":
        base = WIKI_DIR
    elif category == "outputs":
        base = OUTPUTS_DIR
    else:
        raise HTTPException(400, "Invalid category")

    file_path = base / path
    if not file_path.exists():
        raise HTTPException(404, "File not found")

    try:
        file_path.unlink()
        return {"success": True, "deleted": str(file_path)}
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
