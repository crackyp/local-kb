# Local KB User Guide

This guide walks you through setup, ingest, compile, Q&A, maintenance, and troubleshooting.

---

## Overview

Local KB is a CLI workflow for building a personal wiki from your research material.

Flow:
1. Collect source files in `kb/raw/`
2. Compile sources into wiki articles in `kb/wiki/`
3. Ask questions and save markdown outputs to `kb/outputs/`
4. Lint links and keep the wiki healthy

You can do this either from CLI (`scripts/kb.py`) or from the Streamlit UI (`app.py`).

---

## Prerequisites

- macOS, Linux, or WSL
- Python 3.10+
- Ollama running locally
- One pulled model (examples: `phi4-mini`, `qwen2.5:7b`)
- Optional for PDF support: `pypdf`
- Optional UI: `streamlit`

---

## Installation

### Option A: Recommended (macOS)

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
./scripts/setup_mac.sh phi4-mini
```

### Option B: Manual setup

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
python3 -m pip install --user -r requirements.txt
ollama pull phi4-mini
```

If Ollama is not running:

```bash
ollama serve
```

(Leave that running in a separate terminal.)

---

## First Run

```bash
cd local-kb
python3 scripts/kb.py compile --model phi4-mini
python3 scripts/kb.py ask "What is this project for?" --model phi4-mini
python3 scripts/kb.py lint
```

---

## UI Mode (Streamlit)

Launch UI:

```bash
python3 -m pip install --user -r requirements.txt
python3 -m streamlit run app.py

# or helper script
./scripts/run_ui.sh
```

The UI includes tabs for:
- Ingest Files
- Ingest URL
- Ingest PDF
- Compile
- Ask
- Lint
- Explorer

Use the sidebar to set your default model (e.g., `phi4-mini`).

---

## Command Reference

### 1) Ingest local files

```bash
python3 scripts/kb.py ingest "~/Research/*.md" "~/Research/*.txt"
```

What it does:
- Copies matching files into `kb/raw/`
- Preserves existing files
- Appends timestamp if name collision occurs

---

### 2) Ingest web pages

```bash
# Basic page ingest
python3 scripts/kb.py ingest-url https://example.com

# Download up to 20 images found in page HTML
python3 scripts/kb.py ingest-url https://example.com --download-images --max-images 20
```

What it does:
- Fetches the URL
- Converts main HTML body to markdown-ish text
- Saves output to `kb/raw/<url-derived>.md`
- Optional image download to `kb/raw/assets/<page>/`

---

### 3) Ingest PDFs

```bash
python3 -m pip install --user -r requirements.txt
python3 scripts/kb.py ingest-pdf "~/Papers/*.pdf"
```

Useful flags:

```bash
# Only first 25 pages
python3 scripts/kb.py ingest-pdf "~/Papers/*.pdf" --max-pages 25

# Also copy original PDF into kb/raw
python3 scripts/kb.py ingest-pdf "~/Papers/*.pdf" --copy-original
```

What it does:
- Extracts text from PDF pages
- Writes markdown files like `kb/raw/paper-name.pdf.md`

---

### 4) Compile wiki pages

```bash
python3 scripts/kb.py compile --model phi4-mini
```

What it does:
- Reads text-like files from `kb/raw/`
- Summarizes each into a wiki page in `kb/wiki/`
- Updates incremental state in `kb/index/`
- Skips unchanged documents by default

Force recompile:

```bash
python3 scripts/kb.py compile --model phi4-mini --force
```

---

### 5) Ask questions

```bash
python3 scripts/kb.py ask "What are the top 5 concepts?" --model phi4-mini
```

What it does:
- Selects relevant wiki pages
- Prompts the model using those pages as context
- Writes markdown answer to `kb/outputs/qa-<timestamp>.md`

Optional context size:

```bash
python3 scripts/kb.py ask "Question" --model phi4-mini --limit 8
```

---

### 6) Lint wiki links

```bash
python3 scripts/kb.py lint
```

What it checks:
- Broken markdown links to missing wiki pages
- Orphan pages with no inbound links

---

## Recommended Workflow

### Daily

1. Capture docs/web pages/PDFs
2. Run `ingest` / `ingest-url` / `ingest-pdf`
3. Run `compile`
4. Run `ask` for current questions

### Weekly

1. Run `lint`
2. Clean bad links
3. Re-run `compile --force` if you changed prompt behavior or model

---

## Obsidian Integration

Open this folder as your vault root:

```text
local-kb/kb
```

Best practice:
- Keep `raw` as source-of-truth intake
- Keep `wiki` as distilled knowledge graph
- Keep `outputs` as query history and reports

---

## Supported Formats

### Strong support
- Markdown/text: `.md`, `.txt`
- Structured text: `.json`, `.yaml`, `.yml`, `.csv`, `.xml`
- Web files: `.html`, `.htm`
- Code/config/log text files

### Supported with dedicated parser
- PDF via `ingest-pdf`

### Not native (convert first)
- `.docx`, `.pptx`
- images/audio/video as source text

---

## Model Tips

- Start with `phi4-mini` for speed on laptops.
- Use larger models if you want richer summaries.
- Always pass model explicitly:

```bash
python3 scripts/kb.py compile --model phi4-mini
python3 scripts/kb.py ask "..." --model phi4-mini
```

---

## Troubleshooting

### `Ollama call failed: HTTP 404`
Model name not installed.

```bash
ollama list
ollama pull phi4-mini
```

### `No relevant wiki pages found`
Compile first:

```bash
python3 scripts/kb.py compile --model phi4-mini
```

### `PDF ingest requires pypdf`
Install dependency:

```bash
python3 -m pip install --user -r requirements.txt
```

### Setup script says Homebrew missing
If Ollama already works, skip setup script and run commands manually.

---

## Updating from older version

If you already have a working `local-kb` folder and want latest code:

```bash
cd local-kb
git pull
python3 -m pip install --user -r requirements.txt
```

Your existing data in `kb/raw`, `kb/wiki`, `kb/outputs`, and `kb/index` stays intact.

---

## FAQ

### Does this send my data to the cloud?
No, not by default. It talks to your local Ollama server (`127.0.0.1`).

### Can I use this without Obsidian?
Yes. Obsidian is optional; files are plain markdown on disk.

### Can it process huge corpora?
Yes, but v1/v2 are simple and local. For very large corpora you may want chunking + embeddings + retrieval.

---

## Contributing

PRs are welcome for:
- Better HTML/article extraction
- Better wiki linking strategy
- Optional embedding-based retrieval
- Slide export and report templates
