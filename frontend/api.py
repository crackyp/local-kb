#!/usr/bin/env python3
"""FastAPI backend for local-kb. Calls local_kb package functions directly."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Runtime config from environment
# ---------------------------------------------------------------------------

API_PORT = int(os.environ.get("KB_API_PORT", "8765"))
FRONTEND_PORT = int(os.environ.get("KB_FRONTEND_PORT", "3737"))
FRONTEND_HOST = os.environ.get("KB_FRONTEND_HOST", "localhost")

# ---------------------------------------------------------------------------
# Bootstrap: make local_kb and scripts/ importable
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from local_kb.config import CFG
from local_kb.paths import RAW, RAW_ASSETS, WIKI, OUTPUTS, ensure_dirs
from local_kb.utils import (
    slugify, unique_path, read_text, resolve_input_patterns,
    truncate_at_sentence, ping_ollama, ollama_generate,
)
from local_kb.extract import extract_pdf_text, html_to_markdown
from local_kb.ingest import fetch_url, decode_bytes, url_to_filename, download_image
from local_kb.compile import compile_documents
from local_kb.retrieval import relevant_pages
from local_kb.lint import lint_wiki
from local_kb.health import health_check
from local_kb.status import get_status, ollama_models

# Needed only for streaming compile (still subprocess-based)
CLI_PATH = ROOT / "scripts" / "kb.py"
TMP_UPLOADS = ROOT / ".tmp_uploads"

PREVIEWABLE = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".xml", ".csv",
    ".html", ".htm", ".py", ".js", ".ts", ".sql", ".log",
    ".toml", ".ini", ".cfg", ".sh", ".bat",
}

# ---------------------------------------------------------------------------
# Pydantic models — request
# ---------------------------------------------------------------------------


class IngestRequest(BaseModel):
    paths: List[str]


class IngestUrlRequest(BaseModel):
    urls: List[str]
    download_images: bool = False
    max_images: int = 20
    timeout: int = 30


class CompileRequest(BaseModel):
    model: str = CFG["model"]["default"]
    force: bool = False
    max_source_chars: Optional[int] = None
    chunking: bool = False


class AskRequest(BaseModel):
    question: str
    model: str = CFG["model"]["default"]
    limit: int = 6
    use_faiss: bool = True


class IndexRequest(BaseModel):
    force: bool = False
    model: Optional[str] = None


class PromoteRequest(BaseModel):
    filename: str


class CorrectRequest(BaseModel):
    question: str
    correction: str


class HealthCheckRequest(BaseModel):
    model: str = CFG["model"]["default"]


# ---------------------------------------------------------------------------
# Pydantic models — response
# ---------------------------------------------------------------------------


class Recommendation(BaseModel):
    message: str
    action: Optional[str] = None
    payload: Optional[dict] = None


class CommandResponse(BaseModel):
    returncode: int = 0
    output: str = ""
    command: str = ""
    recommendations: List[Recommendation] = []


class AskResponse(CommandResponse):
    answer: str = ""
    written_file: Optional[str] = None


class HealthCheckResponse(CommandResponse):
    report: str = ""


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def safe_name(name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    cleaned = "".join(ch if ch in allowed else "-" for ch in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-.")
    return cleaned or f"upload-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"


def _error_response(code: str, message: str, status: int = 500):
    """Raise an HTTPException with a structured error body."""
    raise HTTPException(
        status_code=status,
        detail={"ok": False, "error": {"code": code, "message": message}},
    )


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Local KB API")

_cors_origins = [
    f"http://{FRONTEND_HOST}:{FRONTEND_PORT}",
    f"http://127.0.0.1:{FRONTEND_PORT}",
]
if f"http://localhost:{FRONTEND_PORT}" not in _cors_origins:
    _cors_origins.append(f"http://localhost:{FRONTEND_PORT}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    ensure_dirs()
    TMP_UPLOADS.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@app.get("/api/status")
async def api_get_status():
    return get_status()


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


@app.post("/api/ingest/upload")
async def ingest_upload(files: List[UploadFile] = File(...)):
    ensure_dirs()
    saved = []
    for f in files:
        name = safe_name(f.filename or "upload")
        dst = unique_path(RAW / name)
        content = await f.read()
        dst.write_bytes(content)
        saved.append({"name": dst.name, "size": len(content)})
    return {"saved": saved, "count": len(saved)}


@app.post("/api/ingest/path")
async def ingest_path(data: IngestRequest):
    ensure_dirs()
    added = []
    files = resolve_input_patterns(data.paths)

    for src in files:
        if src.is_dir() or not src.exists():
            continue
        target = unique_path(RAW / src.name)
        shutil.copy2(src, target)
        added.append(target.name)

    output = "\n".join(f"+ {n}" for n in added)
    output += f"\nIngest complete. Added {len(added)} file(s)."
    return CommandResponse(returncode=0, output=output).model_dump()


@app.post("/api/ingest/url")
async def ingest_url(data: IngestUrlRequest):
    import re

    ensure_dirs()
    added = []
    failed_urls = []
    failed_images = []

    for input_url in data.urls:
        url = input_url.strip()
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            url = "https://" + url

        try:
            content, ctype = fetch_url(url, timeout=data.timeout)
        except Exception as e:
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
        if data.download_images and image_urls:
            img_dir = RAW_ASSETS / out_path.stem
            img_dir.mkdir(parents=True, exist_ok=True)
            downloaded = []
            for i, img_url in enumerate(image_urls[: data.max_images], start=1):
                try:
                    name = download_image(img_url, img_dir, i, timeout=data.timeout)
                    downloaded.append(name)
                except Exception as e:
                    failed_images.append((img_url, str(e)))

            if downloaded:
                refs = "\n".join(
                    [f"- ![](assets/{out_path.stem}/{n})" for n in downloaded]
                )
                image_notes = f"\n\n## Downloaded Images\n\n{refs}\n"

        out_path.write_text(markdown.strip() + image_notes + "\n", encoding="utf-8")
        added.append(f"+ {out_path} ({title[:70]})")

    lines = added.copy()
    lines.append(f"URL ingest complete. Added {len(added)} page(s).")
    if failed_urls:
        lines.append(f"\nFailed URLs ({len(failed_urls)}):")
        for url, err in failed_urls:
            lines.append(f"  - {url}: {err}")
    if failed_images:
        lines.append(f"\nFailed image downloads ({len(failed_images)}):")
        for img_url, err in failed_images[:20]:
            lines.append(f"  - {img_url}: {err}")

    rc = 0 if not failed_urls else 1
    return CommandResponse(returncode=rc, output="\n".join(lines)).model_dump()


@app.post("/api/ingest/pdf")
async def ingest_pdf(
    files: List[UploadFile] = File(...),
    max_pages: int = 0,
    copy_original: bool = False,
):
    ensure_dirs()
    TMP_UPLOADS.mkdir(parents=True, exist_ok=True)
    added = []
    lines = []

    for f in files:
        name = safe_name(f.filename or "upload.pdf")
        tmp = unique_path(TMP_UPLOADS / name)
        content = await f.read()
        tmp.write_bytes(content)

        try:
            text = extract_pdf_text(tmp, max_pages=max_pages if max_pages > 0 else None)
        except Exception as e:
            lines.append(f"! Failed {name}: {e}")
            tmp.unlink(missing_ok=True)
            continue

        if not text.strip():
            text = "(No extractable text found in this PDF.)"

        md = f"""# {tmp.stem}

Source PDF: {name}
Extracted: {dt.datetime.now().isoformat()}

{text[:250000]}
"""
        out_path = unique_path(RAW / f"{slugify(tmp.stem)}.pdf.md")
        out_path.write_text(md.strip() + "\n", encoding="utf-8")
        added.append(out_path.name)
        lines.append(f"+ {out_path}")

        if copy_original:
            dst_pdf = unique_path(RAW / name)
            shutil.copy2(tmp, dst_pdf)
            lines.append(f"  copied original -> {dst_pdf}")

        tmp.unlink(missing_ok=True)

    lines.append(f"PDF ingest complete. Added {len(added)} extracted markdown file(s).")
    return CommandResponse(returncode=0, output="\n".join(lines)).model_dump()


# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------


@app.post("/api/compile")
async def api_compile(data: CompileRequest):
    try:
        result = compile_documents(
            model=data.model,
            force=data.force,
            max_source_chars=data.max_source_chars,
            chunking=data.chunking,
        )
    except RuntimeError as e:
        _error_response("COMPILE_FAILED", str(e))

    compiled = result["compiled"]
    skipped = result["skipped"]

    lines = [f"Compile complete. Updated {compiled} document(s)."]
    if skipped:
        lines.append(f"\nSkipped {len(skipped)} file(s):")
        for name, err in skipped:
            lines.append(f"  - {name}: {err}")

    recommendations = []
    if compiled > 0:
        recommendations.append(
            Recommendation(
                message="Wiki updated. FAISS index may be stale — rebuild?",
                action="rebuild_index",
            )
        )
    else:
        recommendations.append(
            Recommendation(
                message="All sources up to date. Add new raw files to grow the wiki.",
            )
        )

    return CommandResponse(
        returncode=0,
        output="\n".join(lines),
        recommendations=recommendations,
    ).model_dump()


@app.post("/api/compile/stream")
async def compile_stream(data: CompileRequest):
    """Streaming compile — still uses subprocess for line-by-line SSE."""
    args = ["compile", "--model", data.model]
    if data.force:
        args.append("--force")
    if data.max_source_chars is not None:
        args.extend(["--max-source-chars", str(data.max_source_chars)])
    if data.chunking:
        args.append("--chunking")

    cmd = [sys.executable, "-u", str(CLI_PATH), *args]

    def generate():
        proc = subprocess.Popen(
            cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        full_output = []
        for line in proc.stdout:
            stripped = line.rstrip("\n\r")
            full_output.append(stripped)
            yield f"data: {json.dumps({'type': 'line', 'text': stripped})}\n\n"

        proc.wait()
        output = "\n".join(full_output)
        recommendations = []
        if proc.returncode == 0:
            if "Compiling:" in output or "Merging:" in output:
                recommendations.append({
                    "message": "Wiki updated. FAISS index may be stale — rebuild?",
                    "action": "rebuild_index",
                })
            else:
                recommendations.append({
                    "message": "All sources up to date. Add new raw files to grow the wiki.",
                })
        yield f"data: {json.dumps({'type': 'done', 'returncode': proc.returncode, 'output': output, 'recommendations': recommendations})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


@app.post("/api/index")
async def build_index(data: IndexRequest):
    ensure_dirs()
    if not ping_ollama():
        _error_response("OLLAMA_NOT_RUNNING", "Ollama is not running. Start it with: ollama serve")

    try:
        from faiss_index import faiss_available, build_faiss_index
    except ImportError:
        _error_response("FAISS_NOT_FOUND", "faiss_index module not found.", 500)

    if not faiss_available():
        _error_response("FAISS_NOT_INSTALLED", "faiss-cpu is not installed. Install with: pip install faiss-cpu", 500)

    if data.model:
        CFG["faiss"]["embed_model"] = data.model

    stats = build_faiss_index(CFG, force=data.force)
    output = f"Index: {stats['pages']} pages, {stats['chunks']} chunks, {stats['dimensions']}d vectors"

    return CommandResponse(
        returncode=0,
        output=output,
        recommendations=[
            Recommendation(message="Index ready. Try asking a question.", action="go_ask")
        ],
    ).model_dump()


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------


@app.post("/api/ask")
async def ask_wiki(data: AskRequest):
    ensure_dirs()
    if not ping_ollama():
        _error_response("OLLAMA_NOT_RUNNING", "Ollama is not running. Start it with: ollama serve")

    models = ollama_models()
    if data.model not in models:
        _error_response("MODEL_NOT_FOUND", f"model '{data.model}' not found", 404)

    context = None
    output_lines = []

    # Try FAISS semantic retrieval first
    if CFG["faiss"]["enabled"] and data.use_faiss:
        try:
            from faiss_index import faiss_available, assemble_context, FAISS_INDEX_FILE
            if faiss_available() and FAISS_INDEX_FILE.exists():
                context, _source_pages = assemble_context(data.question, CFG)
                if context:
                    output_lines.append(
                        f"Using FAISS retrieval ({len(_source_pages)} pages, {len(context)} chars)"
                    )
        except Exception as e:
            output_lines.append(f"FAISS retrieval failed, falling back to TF-IDF: {e}")

    # Fallback to TF-IDF keyword retrieval
    if context is None:
        pages = relevant_pages(data.question, limit=data.limit)
        if not pages:
            return AskResponse(
                returncode=1,
                output="No relevant wiki pages found. Run compile first.",
                answer="",
                written_file=None,
            ).model_dump()
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

Question: {data.question}

WIKI CONTEXT:
{context}
"""
    answer = ollama_generate(prompt, model=data.model, temperature=CFG["ask"]["temperature"])

    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUTS / f"qa-{ts}.md"
    header = f"> **Q:** {data.question}\n\n"
    out_path.write_text(header + answer + "\n", encoding="utf-8")

    output_lines.append(f"Wrote: {out_path}")

    recommendations = [
        Recommendation(
            message="Save this answer to the knowledge base?",
            action="promote",
            payload={"filename": out_path.name},
        )
    ]

    return AskResponse(
        returncode=0,
        output="\n".join(output_lines),
        answer=answer,
        written_file=out_path.name,
        recommendations=recommendations,
    ).model_dump()


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------


@app.post("/api/lint")
async def api_lint():
    ensure_dirs()
    result = lint_wiki()

    lines = [
        "\nLint Report",
        "===========",
        f"Pages: {result['pages']}",
        f"Broken links: {len(result['broken'])}",
    ]
    for src, link in result["broken"][:50]:
        lines.append(f"  - {src} -> {link}")
    lines.append(f"Orphan pages (no incoming links): {len(result['orphans'])}")
    for o in result["orphans"][:50]:
        lines.append(f"  - {o}")

    recommendations = []
    if result["broken"]:
        recommendations.append(
            Recommendation(
                message=f"{len(result['broken'])} broken links found. Recompile to fix.",
                action="compile",
            )
        )
    if result["orphans"]:
        recommendations.append(
            Recommendation(
                message=f"{len(result['orphans'])} orphan pages with no incoming links.",
            )
        )

    return CommandResponse(
        returncode=0,
        output="\n".join(lines),
        recommendations=recommendations,
    ).model_dump()


# ---------------------------------------------------------------------------
# Promote / Correct
# ---------------------------------------------------------------------------


@app.post("/api/promote")
async def promote_output(data: PromoteRequest):
    ensure_dirs()
    src = OUTPUTS / data.filename
    if not src.exists():
        _error_response("FILE_NOT_FOUND", f"File not found: {data.filename}", 404)

    dst_name = f"promoted-{data.filename}"
    dst = RAW / dst_name
    if dst.exists():
        dst = unique_path(dst)
    shutil.copy2(src, dst)
    return CommandResponse(
        returncode=0,
        output=f"Promoted: {src.name} -> raw/{dst.name}",
    ).model_dump()


@app.post("/api/correct")
async def correct_answer(data: CorrectRequest):
    from local_kb.paths import CORRECTIONS

    ensure_dirs()
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    content = f"---\nquestion: {data.question}\ndate: {dt.datetime.now().isoformat()}\napplied: false\n---\n\n"
    content += f"# Correction\n\n"
    content += f"> **Original question:** {data.question}\n\n"
    content += f"## Correct Information\n\n{data.correction}\n"
    dst = CORRECTIONS / f"correction-{ts}.md"
    dst.write_text(content, encoding="utf-8")

    # Also copy into raw/ so it gets compiled into the wiki
    raw_dst = RAW / f"correction-{ts}.md"
    raw_dst.write_text(content, encoding="utf-8")

    return CommandResponse(
        returncode=0,
        output=f"Saved correction: corrections/{dst.name}",
        recommendations=[
            Recommendation(
                message="Correction saved. Recompile to update the wiki.",
                action="compile",
            )
        ],
    ).model_dump()


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.post("/api/health-check")
async def api_health_check(data: HealthCheckRequest):
    try:
        result = health_check(model=data.model)
    except RuntimeError as e:
        _error_response("HEALTH_CHECK_FAILED", str(e))

    if not result["page_count"]:
        return HealthCheckResponse(
            returncode=1,
            output="No wiki pages found. Run compile first.",
            report="",
        ).model_dump()

    output = f"Reviewed {result['page_count']} wiki pages."
    if result["written_path"]:
        output += f"\nWrote: {result['written_path']}"

    return HealthCheckResponse(
        returncode=0,
        output=output,
        report=result["report"],
        recommendations=[
            Recommendation(message="Review complete. Check the report for actionable items.")
        ],
    ).model_dump()


# ---------------------------------------------------------------------------
# File explorer
# ---------------------------------------------------------------------------


@app.get("/api/files/{category}")
async def list_files(category: str):
    if category == "raw":
        files = [p for p in scan_files(RAW) if RAW_ASSETS not in p.parents]
        base = RAW
    elif category == "wiki":
        files = scan_files(WIKI, "*.md")
        base = WIKI
    elif category == "outputs":
        files = scan_files(OUTPUTS, "*.md")
        base = OUTPUTS
    else:
        _error_response("INVALID_CATEGORY", f"Invalid category: {category}", 400)

    # For wiki and outputs, attach a human title pulled from the article's
    # first heading. Wiki uses the prebuilt index when available; fall back to
    # reading the file's first non-empty line for both.
    titles: dict[str, str] = {}
    if category == "wiki":
        from local_kb.paths import WIKI_INDEX_FILE
        from local_kb.utils import load_json
        try:
            wiki_index = load_json(WIKI_INDEX_FILE, {})
            for fname, entry in wiki_index.items():
                if isinstance(entry, dict) and entry.get("title"):
                    titles[fname] = entry["title"]
        except Exception:
            pass

    def _read_title(p: Path) -> str | None:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as fh:
                for _ in range(20):
                    line = fh.readline()
                    if not line:
                        break
                    s = line.strip()
                    if s.startswith("#"):
                        return s.lstrip("# ").strip() or None
                    if s:
                        return s
        except Exception:
            return None
        return None

    result = []
    for p in files:
        try:
            meta = file_meta(p)
            meta["rel"] = str(p.relative_to(base))
            if category in ("wiki", "outputs") and p.suffix.lower() == ".md":
                title = titles.get(p.name)
                if not title:
                    title = _read_title(p)
                if title:
                    meta["title"] = title
            result.append(meta)
        except Exception:
            continue

    return {"files": result, "count": len(result)}


@app.get("/api/file/{category}/{path:path}")
async def get_file(category: str, path: str):
    if category == "raw":
        base = RAW
    elif category == "wiki":
        base = WIKI
    elif category == "outputs":
        base = OUTPUTS
    else:
        _error_response("INVALID_CATEGORY", f"Invalid category: {category}", 400)

    file_path = base / path
    if not file_path.exists():
        _error_response("FILE_NOT_FOUND", "File not found", 404)

    if file_path.suffix.lower() in PREVIEWABLE:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return {"content": content, "previewable": True}
    else:
        return {
            "content": None,
            "previewable": False,
            "note": f"Binary file ({file_path.suffix})",
        }


@app.delete("/api/file/{category}/{path:path}")
async def delete_file(category: str, path: str):
    from local_kb.index_state import remove_page_from_index, remove_page_from_wiki_index
    from local_kb.audit import log_action

    if category == "raw":
        base = RAW
    elif category == "wiki":
        base = WIKI
    elif category == "outputs":
        base = OUTPUTS
    else:
        _error_response("INVALID_CATEGORY", f"Invalid category: {category}", 400)

    file_path = base / path
    if not file_path.exists():
        _error_response("FILE_NOT_FOUND", "File not found", 404)

    try:
        # Soft-delete: move to trash instead of permanent removal
        from local_kb.safe_ops import soft_delete
        trash_path = soft_delete(file_path, category)
        log_action("delete", category, path)

        # Clean up indexes when wiki pages are deleted
        if category == "wiki" and file_path.name.endswith(".md"):
            try:
                remove_page_from_index(file_path.name)
                remove_page_from_wiki_index(file_path.name)
            except Exception:
                pass  # non-fatal: index will catch up on next rebuild

        return {"success": True, "deleted": str(file_path), "trash": str(trash_path)}
    except Exception as e:
        _error_response("DELETE_FAILED", str(e))


# ---------------------------------------------------------------------------
# Trash management
# ---------------------------------------------------------------------------


@app.get("/api/trash")
async def list_trash(category: str | None = None):
    from local_kb.safe_ops import list_trash as _list_trash
    return {"files": _list_trash(category)}


@app.post("/api/trash/restore")
async def restore_trash(data: dict):
    from local_kb.safe_ops import restore_from_trash
    from local_kb.audit import log_action as _log

    name = data.get("name", "")
    category = data.get("category", "")
    if not name or not category:
        _error_response("MISSING_FIELDS", "name and category are required", 400)

    try:
        restored = restore_from_trash(name, category)
        _log("restore", category, name, f"-> {restored}")
        return {"success": True, "restored": str(restored)}
    except FileNotFoundError as e:
        _error_response("NOT_FOUND", str(e), 404)
    except FileExistsError as e:
        _error_response("ALREADY_EXISTS", str(e), 409)
    except Exception as e:
        _error_response("RESTORE_FAILED", str(e))


@app.delete("/api/trash")
async def empty_trash(category: str | None = None):
    from local_kb.safe_ops import empty_trash as _empty_trash
    from local_kb.audit import log_action as _log

    removed = _empty_trash(category)
    _log("empty_trash", category or "all", f"{removed} files")
    return {"success": True, "removed": removed}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=API_PORT)
