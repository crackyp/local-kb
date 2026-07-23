# Local KB

## What This Is

A local-first personal knowledge base. Raw source material goes into `kb/raw/`, an LLM (served by llama-swap fronting llama.cpp) compiles it into organized wiki pages in `kb/wiki/`, and Q&A answers are saved to `kb/outputs/`. Everything is markdown. There is a Next.js web UI for all operations.

## Architecture

```
GSA-kb/
  scripts/
    kb.py              # CLI entry point (all commands)
    faiss_index.py     # FAISS semantic indexing (chunking, embedding, search)
  local_kb/            # Core Python package (compile, ingest, retrieval, health, llamacpp client, etc.)
    llamacpp.py        # OpenAI-compatible HTTP client + reachability probe (no process management)
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
  kb.toml              # All configuration (model, timeouts, char limits, FAISS, [llamacpp] client)
  start-ui.py          # Launches backend + frontend together
```

## External services (not managed by this app)

- **llama-swap** on `127.0.0.1:8080` (default) — hot-swaps the underlying `llama-server.exe` based on each request's `model` field. The aliases listed in `kb.toml [llamacpp] models` must match aliases defined in llama-swap's own `config.yaml`. Per-model flag tuning (gpu layers, batch size, cache types) lives in that config too — not in this repo.
- **Embed server** on `127.0.0.1:11434` (default — Ollama serving `nomic-embed-text` via OpenAI-compat).

Both must be started before launching the UI. `local_kb/llamacpp.py` only provides the HTTP client and a reachability probe (`ping()` / `loaded_model()`); it never spawns or stops anything.

## Key Data Flows

### Compile: `raw/ -> wiki/` (iterative-incremental)
1. Reads files from `kb/raw/` (text, PDF, DOCX, PPTX — scanned PDFs use OCR via easyocr+pymupdf)
2. Incremental: skips files whose SHA256 hash matches `kb/index/state.json`
3. For each changed file: FAISS-search the existing wiki for the top-K most-similar pages, then send the source + those pages to the LLM
4. LLM returns a JSON decision: `{writes: [{filename, content}], deletes: [filename]}` — it can update an existing page in place, merge multiple pages, or create a new one
5. Writes go to `kb/wiki/`; deletes are soft (moved to `kb/.trash/wiki/` via `safe_ops.soft_delete`)
6. `build_wiki_index()` refreshes `wiki_index.json` and `wiki/INDEX.md`
7. FAISS auto-rebuilds if enabled

The LLM never sees the whole corpus — only the new source + the few wiki pages it's likely to affect — so the flow scales as `raw/` and `wiki/` grow. `kb/index/docs.json` now just tracks `{filename: {sha256, updated_at}}`; the old 1:1 raw→wiki mapping is gone because one raw file may touch multiple pages.

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
- `[model] default` — default chat model tag (must match a llama-swap alias)
- `[compile] max_source_chars` — how much source text to send per LLM call (UI-adjustable)
- `[faiss] enabled` — toggle FAISS vs TF-IDF
- `[faiss] embed_model` — embedding model tag (must match a model loaded on the embed server)
- `[llamacpp] timeout` — seconds per LLM call
- `[llamacpp] host` — host where both servers are listening (typically `127.0.0.1`)
- `[llamacpp] chat_port` — llama-swap port (default 8080); model is selected per-request
- `[llamacpp] embed_port` — embed server port (default 11434, Ollama)
- `[llamacpp] models` — list of chat aliases shown in the UI dropdown

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
- Wiki pages link related topics using standard markdown links: `[Topic Title](topic-slug.md)`. After compile, `local_kb/links.py` rewrites LLM-invented hrefs to real pages and strips ones it can't resolve.
- `wiki/INDEX.md` is auto-generated — do not edit it manually.
- When adding new API endpoints, always include `recommendations` in the response.
- When adding new CLI commands, register them in `build_parser()` at the bottom of `kb.py`.
