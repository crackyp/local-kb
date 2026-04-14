# Local KB (Ollama)

A local-first personal knowledge base compiler.

You collect source material in `kb/raw/`, run a compile step with a local LLM (Ollama), and get linked wiki pages in `kb/wiki/`. Then you can run Q&A over the wiki and save outputs as markdown.

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
  local_kb/       # shared backend/domain logic
  scripts/
    kb.py               # main CLI
    setup_mac.sh        # one-shot mac setup helper
    setup_windows.ps1   # one-shot Windows setup helper
  start-ui.py           # starts both backend and frontend
  start-ui.bat          # Windows launcher
  requirements.txt
```

## 1) Quick start

### macOS

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
./scripts/setup_mac.sh phi4-mini
```

### Windows (PowerShell)

```powershell
git clone https://github.com/crackyp/local-kb.git
cd local-kb
powershell -ExecutionPolicy Bypass -File .\scripts\setup_windows.ps1 -Model phi4-mini
```

Then either use CLI or UI.

## 2) Daily workflow

> On Windows, replace `python3` with `py` and use Windows-style paths.

```bash
# Add source files
python3 scripts/kb.py ingest "~/Research/*.md" "~/Research/*.txt"

# Add web pages
python3 scripts/kb.py ingest-url https://example.com --download-images

# Add PDFs (first install pypdf)
python3 -m pip install --user -r requirements.txt
python3 scripts/kb.py ingest-pdf "~/Papers/*.pdf"

# Compile wiki pages
python3 scripts/kb.py compile --model phi4-mini

# Ask questions
python3 scripts/kb.py ask "What are the key themes and contradictions?" --model phi4-mini

# Check wiki health
python3 scripts/kb.py lint
```

## 3) UI mode (Next.js)

Start the app:

```bash
# Install Python deps
pip install -r requirements.txt

# Install frontend deps
cd frontend && npm install && cd ..

# Start both backend and frontend
python start-ui.py
```

```bat
REM Windows one-click
start-ui.bat
```

Then open http://localhost:3000.

## 4) Supported input formats

### Best-supported now
- `.md`, `.txt`
- `.csv`, `.json`, `.yaml`, `.yml`, `.xml`
- `.html`, `.htm`
- code/docs text files (`.py`, `.js`, `.ts`, `.ipynb`, `.sql`, `.log`, etc.)

### Supported via dedicated command
- `.pdf` via `ingest-pdf` (requires `pypdf`)

### Not natively compiled as source text
- images (`.png`, `.jpg`, etc.)
- audio/video
- Office docs (`.docx`, `.pptx`) unless you export to text/markdown first

## 5) Full user guide

See: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)

## 6) Notes

- This is local-first and model-agnostic for Ollama model names.
- `compile` is incremental by default; use `--force` to recompile everything.
- `ask` writes markdown files to `kb/outputs/` so your research trail stays in the vault.

## License

MIT
