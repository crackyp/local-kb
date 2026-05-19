# Local KB — Launch Modes

## Prerequisites

- Python 3.11+ with packages: `pip install -r requirements.txt`
- Node.js 18+ (for the web UI)
- `llama-server.exe` from llama.cpp (default location: `H:\llama.cpp\llama-server.exe`)
- At least one chat-model GGUF and one embed-model GGUF reachable by tag (see `kb.toml` `[llamacpp.external_gguf_map]` or the Ollama blob store at `H:\ollama\models`)

By default the app spawns llama-server processes automatically: one for chat on port 8080 (model-swappable) and one for embeddings on port 8081 (fixed model). Set `[llamacpp] auto_spawn = false` in `kb.toml` to manage them yourself.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KB_API_PORT` | `8000` | FastAPI backend port |
| `KB_FRONTEND_PORT` | `3000` | Next.js dev server port |
| `KB_FRONTEND_HOST` | `localhost` | Hostname used in CORS origins |
| `LLAMACPP_DIR` | `H:\llama.cpp` | Directory containing `llama-server.exe` (used when `[llamacpp] server_exe` is empty) |
| `OLLAMA_MODELS` | `H:\ollama\models` | Ollama blob store used to resolve tags that aren't in `external_gguf_map` |

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

Both scripts run preflight checks first (Python deps, node_modules, ports, llama-server). If checks fail you can still continue.

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

Build the frontend and run the API with a production ASGI server.

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

Checks: Python deps, node_modules, port availability, llama-server reachability (or that `llama-server.exe` is available for auto-spawn).
