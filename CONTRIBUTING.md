# Contributing

Thanks for helping improve Local KB.

## Development setup

```bash
git clone https://github.com/crackyp/local-kb.git
cd local-kb
python -m pip install -r requirements.txt
cd frontend && npm install && cd ..
```

Optional scanned-PDF OCR support:

```bash
python -m pip install -r requirements-ocr.txt
```

## Quick checks

Run these before opening a PR:

```bash
python scripts/smoke_test.py
cd frontend
npm run lint
npm run build
```

If you changed Python dependencies, also run:

```bash
python preflight.py
```

## Notes

- Do not commit personal knowledge-base content from `kb/raw`, `kb/wiki`, `kb/outputs`, or `kb/index`.
- Keep the API local-only by default.
- Prefer small PRs with a short explanation and manual test notes.
