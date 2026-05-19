# Local KB (llama.cpp)

A local-first personal knowledge base compiler.

You collect source material in `kb/raw/`, run a compile step with a local LLM (llama.cpp), and get linked wiki pages in `kb/wiki/`. Then you can run Q&A over the wiki and save outputs as markdown.

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
  llamacpp_tuned.json   # (optional) per-tag llama-server flag overrides
  requirements.txt
```

## 1) Prerequisites

- Python 3.11+ with `pip install -r requirements.txt`
- Node.js 18+ (for the web UI)
- `llama-server.exe` from llama.cpp at `H:\llama.cpp\` (override with the `LLAMACPP_DIR` env var or `[llamacpp] server_exe` in `kb.toml`)
- One or more GGUF models available — either via the Ollama blob store at `H:\ollama\models` (resolved by tag) or as standalone files referenced from `[llamacpp.external_gguf_map]` in `kb.toml`
- An embedding GGUF (e.g. `nomic-embed-text:latest`) for FAISS — or set `[faiss] enabled = false` in `kb.toml` to fall back to TF-IDF

The app spawns `llama-server.exe` automatically when needed. Two server processes are used: one for chat (default port 8080, model-swappable per request) and one for embeddings (default port 8081, fixed model). Set `[llamacpp] auto_spawn = false` if you prefer to start servers manually.

## 2) Quick start

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
pip install -r requirements.txt
cd frontend && npm install && cd ..
python start-ui.py
```

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

## 7) Notes

- This is local-first. Nothing leaves your machine — all LLM and embedding calls go to `127.0.0.1`.
- `compile` is incremental by default; use `--force` to recompile everything.
- `ask` writes markdown files to `kb/outputs/` so your research trail stays in the vault.
- llama-server only loads one model per port. Swapping the chat tag mid-session forces a stop + reload (~3-10 s).

## License

MIT
