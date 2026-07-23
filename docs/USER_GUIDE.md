# Local KB User Guide

This guide walks you through setup, ingest, compile, Q&A, maintenance, and troubleshooting.

---

## Overview

Local KB is a CLI + web UI workflow for building a personal wiki from your research material.

Flow:
1. Collect source files in `kb/raw/`
2. Compile sources into wiki articles in `kb/wiki/`
3. Ask questions and save markdown outputs to `kb/outputs/`
4. Lint links and keep the wiki healthy

You can do this either from CLI (`scripts/kb.py`) or from the Next.js web UI.

---

## Prerequisites

- Windows, macOS, Linux, or WSL
- Python 3.11+
- **llama-swap** running on `127.0.0.1:8080` (default). It fronts `llama-server` and swaps the underlying model based on the request's `model` field. Chat-model aliases listed in `kb.toml [llamacpp] models` must exist in llama-swap's own `config.yaml`.
- **An embedding server** on `127.0.0.1:11434` (default — Ollama, serving e.g. `nomic-embed-text:latest`). Any OpenAI-compatible `/v1/embeddings` endpoint works. Set `[faiss] enabled = false` in `kb.toml` to skip embeddings and use TF-IDF instead.
- Optional UI: Node.js 18+

This app does not manage either server's lifecycle — start llama-swap and your embed server yourself.

---

## Installation

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Configure `kb.toml`:
- `[model] default` — default chat tag (must match an alias in llama-swap's `config.yaml`)
- `[llamacpp] chat_port` / `embed_port` — where llama-swap and your embed server are listening
- `[llamacpp] models` — chat-model alias dropdown shown in the UI sidebar
- `[faiss] embed_model` — tag for the embedding model on the embed server

---

## First Run

```bash
cd local-kb
python scripts/kb.py compile --model qwopus:v3
python scripts/kb.py ask "What is this project for?" --model qwopus:v3
python scripts/kb.py lint
```

---

## UI Mode (Next.js)

Launch UI:

```bash
pip install -r requirements.txt
cd frontend && npm install && cd ..
python start-ui.py
```

```bat
REM Windows one-click
start-ui.bat
```

Then open http://localhost:3000.

---

## Command Reference

### 1) Ingest local files

```bash
python scripts/kb.py ingest "~/Research/*.md" "~/Research/*.txt"
```

### 2) Ingest web pages

```bash
python scripts/kb.py ingest-url https://example.com
python scripts/kb.py ingest-url https://example.com --download-images --max-images 20
```

### 3) Ingest PDFs

```bash
python scripts/kb.py ingest-pdf "~/Papers/*.pdf"
python scripts/kb.py ingest-pdf "~/Papers/*.pdf" --max-pages 25
python scripts/kb.py ingest-pdf "~/Papers/*.pdf" --copy-original
```

### 4) Compile wiki pages

```bash
python scripts/kb.py compile --model qwopus:v3
python scripts/kb.py compile --model qwopus:v3 --force
```

### 5) Ask questions

```bash
python scripts/kb.py ask "What are the top 5 concepts?" --model qwopus:v3
python scripts/kb.py ask "Question" --model qwopus:v3 --limit 8
```

### 6) Lint wiki links

```bash
python scripts/kb.py lint
```

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

---

## Supported Formats

### Strong support
- Markdown/text: `.md`, `.txt`
- Structured text: `.json`, `.yaml`, `.yml`, `.csv`, `.xml`
- Web files: `.html`, `.htm`
- Code/config/log text files

### Office docs (text auto-extracted on compile)
- `.pdf` — `pypdf` with OCR fallback (`easyocr` + `pymupdf`) for scanned/image PDFs. Also has a dedicated `ingest-pdf` CLI command / **PDF** UI tab that extracts to markdown upfront so you can review before compiling.
- `.docx` — `python-docx`
- `.pptx` — `python-pptx`

Drop the file into `kb/raw/` (or use the **Files** upload tab) and the next `compile` pulls the text out.

### Not native
- images/audio/video as source text

---

## Model Tips

- llama-swap hot-swaps the underlying `llama-server` when the requested tag changes — expect a one-off ~3-10 s reload the first time you hit a new model. Group calls by model when possible.
- The embedding server stays on its own port with one fixed model — no swap penalty.
- Per-model flag tuning (gpu layers, batch size, cache types, etc.) lives in llama-swap's `config.yaml`, not in this repo.

---

## Troubleshooting

### `llama-swap is not reachable at 127.0.0.1:8080`
Start llama-swap before launching the UI. Check it's bound to the host/port configured in `kb.toml [llamacpp] host` / `chat_port`.

### `model 'X' not configured in kb.toml`
Add the tag to `kb.toml [llamacpp] models` (and make sure llama-swap's `config.yaml` defines a matching alias).

### `No relevant wiki pages found`
Compile first:

```bash
python scripts/kb.py compile --model qwopus:v3
```

### `PDF ingest requires pypdf`
Install dependencies:

```bash
python -m pip install -r requirements.txt
```

---

## Updating from older version

```bash
cd local-kb
git pull
python -m pip install -r requirements.txt
```

Your existing data in `kb/raw`, `kb/wiki`, `kb/outputs`, and `kb/index` stays intact.

---

## FAQ

### Does this send my data to the cloud?
No. All LLM and embedding calls go to a local `llama-server` process bound to `127.0.0.1`.

### Can I use this without Obsidian?
Yes. Obsidian is optional; files are plain markdown on disk.

### Can it process huge corpora?
Yes, but be mindful: each unique chat-model swap forces a server reload. Consider sticking to one tag for a long compile job.
