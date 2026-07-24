#!/usr/bin/env python3
"""Small public-readiness smoke test for Local KB.

This intentionally avoids requiring a running LLM server. It checks that Python
files parse, core imports work, and the CLI is wired.
"""

from __future__ import annotations

import compileall
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print("$ " + " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> int:
    print("Smoke test: Python syntax")
    ok = compileall.compile_dir(str(ROOT / "backend"), quiet=1)
    ok = compileall.compile_dir(str(ROOT / "local_kb"), quiet=1) and ok
    ok = compileall.compile_dir(str(ROOT / "scripts"), quiet=1) and ok
    for file_name in ("preflight.py", "start-api.py", "start-llm.py", "start-ui.py"):
        ok = compileall.compile_file(str(ROOT / file_name), quiet=1) and ok
    if not ok:
        print("Python syntax check failed.", file=sys.stderr)
        return 1

    print("Smoke test: core imports")
    run([sys.executable, "-c", "import backend.app; import local_kb.config; import local_kb.extract"])

    print("Smoke test: CLI help")
    run([sys.executable, "scripts/kb.py", "--help"])

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
