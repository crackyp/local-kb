# Local KB — Launch Modes

## Prerequisites

- Python 3.11+ with packages: `pip install -r requirements.txt`
- Node.js 18+ (for the web UI)
- Ollama running locally (`ollama serve`)

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `KB_API_PORT` | `8000` | FastAPI backend port |
| `KB_FRONTEND_PORT` | `3000` | Next.js dev server port |
| `KB_FRONTEND_HOST` | `localhost` | Hostname used in CORS origins |

Set these before launching to change ports. The frontend reads `NEXT_PUBLIC_API_BASE` (set automatically by the startup scripts).

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

Both scripts run preflight checks first (Python deps, node_modules, ports, Ollama). If checks fail you can still continue.

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
python -m uvicorn frontend.api:app --host 127.0.0.1 --port 8000
```

## Preflight Checks

Run checks independently at any time:

```bash
python preflight.py
```

Checks: Python deps, node_modules, port availability, Ollama reachability.
