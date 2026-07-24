# Local KB — Launch Modes

## Prerequisites

- Python 3.11+ with packages: `python -m pip install -r requirements.txt`
- Node.js 18+ (for the web UI)
- **A local chat server** running on `127.0.0.1:8080` (default). Use `python start-llm.py` for the bundled Qwen/Gemma setup, or configure llama-swap yourself.
- **An embedding server** on `127.0.0.1:11434` (default — Ollama serving `nomic-embed-text` via OpenAI-compat). Any OpenAI-compatible `/v1/embeddings` endpoint works.

Neither server is managed by this app — start them yourself before launching the UI.

Optional scanned-PDF OCR support is split out to keep the core install light:

```bash
python -m pip install -r requirements-ocr.txt
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KB_API_PORT` | `8765` | FastAPI backend port |
| `KB_FRONTEND_PORT` | `3737` | Next.js dev server port |
| `KB_FRONTEND_HOST` | `localhost` | Hostname used in CORS origins |

Set these before launching to change defaults. The frontend reads `NEXT_PUBLIC_API_BASE` (set automatically by the startup scripts).

## Mode 1: CLI Only

Use the CLI directly — no web server needed.

```bash
cd local-kb
python scripts/kb.py ingest /path/to/files
python scripts/kb.py compile
python scripts/kb.py ask "What is ...?"
python scripts/kb.py lint
python scripts/kb.py index
python scripts/kb.py health-check
```

Run `python scripts/kb.py --help` for all commands.

## Mode 2: Dev UI (recommended for daily use)

Starts both the FastAPI backend and Next.js dev server with hot reload.

**Cross-platform (Python):**
```bash
python start-ui.py
```

**Windows only (batch):**
```bash
start-ui.bat
```

Both scripts run preflight checks first (Python deps, node_modules, ports, local chat-server reachability). If checks fail you can still continue.

To use non-default ports:
```bash
KB_API_PORT=9000 KB_FRONTEND_PORT=4000 python start-ui.py
```

Or on Windows:
```cmd
set KB_API_PORT=9000
set KB_FRONTEND_PORT=4000
start-ui.bat
```

## Mode 3: Production / Service

Build the frontend and run the API with a production ASGI server. Keep it bound to localhost unless you add authentication and network controls.

```bash
# Build frontend
cd frontend
npm run build
npm run start -- --port 3000

# In another terminal — run backend without --reload
cd local-kb
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
```

## Preflight Checks

Run checks independently at any time:

```bash
python preflight.py
```

Checks: Python deps, node_modules, port availability, local chat-server reachability on `[llamacpp] chat_port`.
