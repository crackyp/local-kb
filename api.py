#!/usr/bin/env python3
"""Compatibility shim for the backend entrypoint moved to backend/app.py."""

import os

from backend.app import API_PORT, app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("KB_API_PORT", str(API_PORT))))
