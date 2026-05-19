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
- `llama-server.exe` from llama.cpp at `H:\llama.cpp\` (or set `LLAMACPP_DIR`)
- One or more chat-model GGUFs (`qwopus:v3` is the default) — referenced in `kb.toml` under `[llamacpp.external_gguf_map]` or resolvable via the Ollama blob store at `H:\ollama\models`
- An embedding GGUF (default tag: `nomic-embed-text:latest`) — required for FAISS retrieval. Set `[faiss] enabled = false` in `kb.toml` to skip and use TF-IDF instead.
- Optional UI: Node.js 18+

`llama-server` is spawned automatically when needed: a chat process on port 8080 (model-swappable per request) and an embeddings process on port 8081 (fixed model). Disable auto-spawn by setting `[llamacpp] auto_spawn = false` in `kb.toml` and start the servers yourself.

---

## Installation

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Configure `kb.toml`:
- `[model] default` — default chat tag
- `[llamacpp] server_exe` — absolute path to `llama-server.exe` (or leave empty and use `$LLAMACPP_DIR`)
- `[llamacpp.external_gguf_map]` — tag → GGUF path overrides
- `[faiss] embed_model` — tag for the embedding model

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

- llama-server hosts one model per port. Swapping the chat tag mid-session forces a stop + reload (~3-10 s). Group calls by model when possible.
- The embedding server stays loaded with one fixed model on its own port — no swap penalty.
- Suggested tags (with appropriate GGUFs):
  - `qwopus:v3` — reasoning + tool calling, the default
  - `gpt-oss:20b` — heavy reasoning (MoE, needs `n_cpu_moe` tuning on 8GB VRAM)
  - `gemma4:e4b` — balanced general work
  - `gemma4:e2b` — fast/cheap drafting
- Per-tag flag tuning lives in `llamacpp_tuned.json` at the project root. Without an entry, safe defaults are used.

---

## Troubleshooting

### `llama-server failed for model 'X': process exited (code N)`
The model failed to load. The error message includes the last 4 KB of stderr — check it for architecture or tensor mismatch errors. If the Ollama blob is incompatible, download a known-good GGUF from HuggingFace and add an entry to `[llamacpp.external_gguf_map]` in `kb.toml`.

### `No GGUF mapping or Ollama manifest for 'X'`
Either add an explicit entry to `[llamacpp.external_gguf_map]` in `kb.toml`, or pull the model via Ollama so its manifest exists at `$OLLAMA_MODELS/manifests/registry.ollama.ai/library/<name>/<version>`.

### `llama-server.exe not found`
Set `[llamacpp] server_exe` in `kb.toml` to the absolute path, or set the `LLAMACPP_DIR` environment variable.

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
