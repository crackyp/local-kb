# Local KB

A local-first personal knowledge base compiler.

You collect source material in `kb/raw/`, run a compile step with a local LLM (served by a local llama.cpp-compatible server), and get linked wiki pages in `kb/wiki/`. Then you can run Q&A over the wiki and save outputs as markdown.

## What it does

- Ingest local files into `kb/raw/`
- Ingest web pages as markdown (`ingest-url`)
- Optionally download webpage images to `kb/raw/assets/...`
- Extract PDF text into markdown (`ingest-pdf`)
- Compile raw docs into wiki pages (`compile`)
- Ask questions over wiki pages and save answers (`ask`)
- Lint wiki links and find orphans (`lint`)
- Next.js web UI for click-first usage

## Repo layout

```text
local-kb/
  kb/
    raw/          # source docs
      assets/     # downloaded images from URL ingest
    wiki/         # compiled wiki pages
    outputs/      # Q&A/report markdown outputs
    index/        # internal incremental state and indexes
  backend/        # FastAPI server entrypoint/wiring
  frontend/       # Next.js web UI
  local_kb/       # shared backend/domain logic (incl. llama.cpp runtime)
  scripts/
    kb.py               # main CLI
    faiss_index.py      # FAISS chunking / embedding / search
  start-ui.py           # starts both backend and frontend
  start-ui.bat          # Windows launcher
  kb.toml               # configuration
  requirements.txt
```

## 1) Prerequisites

- Python 3.11+ with `pip install -r requirements.txt`
- Node.js 18+ (for the web UI)
- **A local chat server** running on `127.0.0.1:8080` (default). The bundled `start-llm.py` can download and run Qwen3.6-35B-A3B or Gemma4-E2B via `llama-server`. Advanced users can instead run llama-swap on the same host/port.
- **An embedding server** on `127.0.0.1:11434` (default — Ollama). Anything OpenAI-compatible at `/v1/embeddings` works. Or set `[faiss] enabled = false` in `kb.toml` to skip embeddings entirely and use TF-IDF.

This app does not manage either server's lifecycle — start them yourself before launching the UI. The preflight check probes the chat port and warns if it isn't reachable.

## 2) Quick start

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
pip install -r requirements.txt
cd frontend && npm install && cd ..
# In a separate terminal, start/download the local LLM server:
python start-llm.py
# Then launch the UI:
python start-ui.py
```

`python start-llm.py` uses the default model from `kb.toml`. It chooses Qwen3.6-35B-A3B by default, downloads it to `.llama/` if missing, and can fall back to the smaller Gemma model with `python start-llm.py --model gemma4-e2b`.

## 3) Daily workflow

```bash
# Add source files
python scripts/kb.py ingest "~/Research/*.md" "~/Research/*.txt"

# Add web pages
python scripts/kb.py ingest-url https://example.com --download-images

# Add PDFs
python scripts/kb.py ingest-pdf "~/Papers/*.pdf"

# Compile wiki pages
python scripts/kb.py compile --model qwopus:v3

# Ask questions
python scripts/kb.py ask "What are the key themes and contradictions?" --model qwopus:v3

# Check wiki health
python scripts/kb.py lint
```

## 4) UI mode (Next.js)

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
python start-ui.py
```

Then open http://localhost:3000.

## 5) Supported input formats

### Best-supported now
- `.md`, `.txt`
- `.csv`, `.json`, `.yaml`, `.yml`, `.xml`
- `.html`, `.htm`
- code/docs text files (`.py`, `.js`, `.ts`, `.ipynb`, `.sql`, `.log`, etc.)

### Office docs (text auto-extracted on compile)
- `.pdf` (requires `pypdf`; falls back to OCR via `easyocr` + `pymupdf` for scanned PDFs). Also has a dedicated `ingest-pdf` command / **PDF** UI tab that extracts to markdown upfront.
- `.docx` (requires `python-docx`)
- `.pptx` (requires `python-pptx`)

Drop any of these into `kb/raw/` (or use the **Files** upload tab) and the next `compile` extracts the text and feeds it to the LLM.

### Not natively compiled as source text
- images (`.png`, `.jpg`, etc.)
- audio/video

## 6) Full user guide

See: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)

## 7) Public safety notes

- Keep personal source material out of git. The repo tracks only `.gitkeep` placeholders under `kb/raw/`, `kb/wiki/`, `kb/outputs/`, and `kb/index/`.
- `kb/.trash/`, local Claude settings, tuning files, uploads, caches, and generated indexes are ignored.
- The API binds to `127.0.0.1` by default and is intended for local use, not direct internet exposure.

## 8) Notes

- This is local-first. Nothing leaves your machine — all LLM and embedding calls go to `127.0.0.1`.
- `compile` is incremental by default; use `--force` to recompile everything.
- `ask` writes markdown files to `kb/outputs/` so your research trail stays in the vault.
- The bundled `start-llm.py` runs one selected model at a time. If you use llama-swap instead, expect a one-off reload the first time you hit a new model.

## License

MIT
