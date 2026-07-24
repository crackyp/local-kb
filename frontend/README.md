# Local KB Frontend

Next.js UI for Local KB.

Most users should launch the full app from the repo root:

```bash
python start-ui.py
```

For frontend-only development:

```bash
npm install
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8765 npm run dev
```

The backend must be running separately for API-backed features:

```bash
cd ..
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765
```

Useful checks:

```bash
npm run lint
npm run build
```
