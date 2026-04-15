# Local KB

## What This Is

A local-first personal knowledge base. Raw source material goes into `kb/raw/`, an LLM (via Ollama) compiles it into organized wiki pages in `kb/wiki/`, and Q&A answers are saved to `kb/outputs/`. Everything is markdown. There is a Next.js web UI for all operations.

## Architecture

```
local-kb/
  scripts/
    kb.py              # CLI entry point (all commands)
    faiss_index.py     # FAISS semantic indexing (chunking, embedding, search)
  local_kb/            # Core Python package (compile, ingest, retrieval, health, etc.)
  backend/
    app.py             # FastAPI backend (default port 8765), wraps CLI as subprocess
  frontend/
    src/
      app/page.tsx     # Main page (tab router)
      components/      # AskTab, CompileTab, IngestTab, ExplorerTab, QualityTab, Sidebar
      lib/api.ts       # HTTP client for backend
      types/index.ts   # TypeScript interfaces
  kb/
    raw/               # Unprocessed source material. NEVER modify these files.
    wiki/              # AI-maintained wiki pages. Never hand-edit.
    outputs/           # Q&A answers, health-check reports
    index/             # Internal state (state.json, docs.json, wiki_index.json, FAISS files)
  kb.toml              # All configuration (model, timeouts, char limits, FAISS settings)
  start-ui.py          # Launches backend + frontend together
```

## Key Data Flows

### Compile: `raw/ -> wiki/`
1. Reads all files from `kb/raw/` (text, PDF, DOCX — scanned PDFs use OCR via easyocr+pymupdf)
2. Incremental: skips files whose SHA256 hash matches `kb/index/state.json`
3. Each file sent to LLM to produce a wiki page
4. Wiki page written to `kb/wiki/`, mapping stored in `kb/index/docs.json`
5. `build_wiki_index()` updates `wiki_index.json` and `wiki/INDEX.md` (incrementally if not --force)
6. FAISS auto-rebuilds incrementally if enabled

### Ask: `wiki/ -> outputs/`
1. FAISS semantic search retrieves relevant chunks (or TF-IDF fallback)
2. Context assembled within budget, truncated at sentence boundaries
3. LLM generates answer, saved to `kb/outputs/qa-<timestamp>.md`

### Promote (compounding loop): `outputs/ -> raw/`
Copies a Q&A answer back into `raw/` so it gets compiled into the wiki next cycle.

## CLI Commands

All in `scripts/kb.py`: `ingest`, `ingest-url`, `ingest-pdf`, `compile`, `ask`, `index`, `lint`, `promote`, `health-check`

## Configuration

All tunables are in `kb.toml`. The code has fallback defaults in `DEFAULTS` dict at the top of `kb.py`. The toml values override the code defaults.

Key settings:
- `[model] default` — Ollama model name
- `[compile] max_source_chars` — how much source text to send per LLM call (UI-adjustable)
- `[faiss] enabled` — toggle FAISS vs TF-IDF
- `[ollama] timeout` — seconds per LLM call

## State Files (kb/index/)

- `state.json` — `{filename: sha256}` for incremental compile
- `docs.json` — `{filename: {wiki_page, sha256, updated_at}}` maps raw files to wiki pages
- `wiki_index.json` — `{page: {title, links_to, words}}` metadata for all wiki pages
- `faiss.index` — FAISS vector index (IndexIDMap wrapping IndexFlatIP)
- `faiss_meta.json` — chunk metadata keyed by vector ID
- `faiss_state.json` — page hashes + settings for staleness detection

## Important Patterns

- The backend (`backend/app.py`) wraps CLI commands via `subprocess.run`. It does not call Python functions directly.
- API responses include a `recommendations` array — context-aware suggestions for what to do next. The frontend renders these as actionable buttons.
- FAISS index uses `IndexIDMap` for incremental updates (add/remove vectors without full rebuild).
- PDF extraction tries pypdf first, falls back to OCR (pymupdf + easyocr) for scanned/image PDFs.
- `truncate_at_sentence()` is used everywhere text is capped — cuts at sentence boundaries, not mid-word.
- Wiki page filename collisions are checked against both the filesystem and `docs.json` to prevent unrelated documents from merging.

## Rules

- Never modify files in `kb/raw/` — that's the user's source material.
- Never hand-edit files in `kb/wiki/` — the AI maintains these entirely.
- Every wiki page starts with a one-paragraph summary.
- Wiki pages link related topics using `[[topic-name]]` format.
- `wiki/INDEX.md` is auto-generated — do not edit it manually.
- When adding new API endpoints, always include `recommendations` in the response.
- When adding new CLI commands, register them in `build_parser()` at the bottom of `kb.py`.
