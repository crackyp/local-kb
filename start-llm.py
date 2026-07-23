#!/usr/bin/env python3
"""Launch a bundled llama.cpp server with auto-download.

Usage:
    python start-llm.py              # Use default model from kb.toml
    python start-llm.py --model gemma4-e2b
    python start-llm.py --model qwen3.6-35b-a3b
    python start-llm.py --port 8081  # Custom port if you also update kb.toml

Environment variables:
    KB_LLM_PORT      Server port (default 8080)
    KB_LLM_MODEL     Model name (overrides kb.toml default)
    KB_LLM_NGPU      GPU layers 0=cpu (default 99=all)
    KB_LLM_NTHREADS  CPU threads (default 8)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
LLM_DIR = ROOT / ".llama"  # Where downloaded models live
LLM_PORT = int(os.environ.get("KB_LLM_PORT", "8080"))
DEFAULT_N_GPU = 99
DEFAULT_N_THREADS = 8

# Model definitions: (hf_repo, gguf_filename, label, min_ram_gb)
MODELS = {
    "qwen3.6-35b-a3b": {
        "repo": "Qwen/Qwen3-35B-A3B",
        "filename": "Qwen3-35B-A3B-Q4_K_M.gguf",
        "label": "Qwen3.6-35B-A3B (Q4_K_M, ~22 GB)",
        "min_ram_gb": 32,
        "desc": "High-end — strong reasoning, 256K context",
    },
    "gemma4-e2b": {
        "repo": "bartowski/gemma-4-3b-A3B-GGUF",
        "filename": "gemma-4-3b-A3B-IQ4_XS.gguf",
        "label": "Gemma4-E2B (IQ4_XS, ~2.3 GB)",
        "min_ram_gb": 8,
        "desc": "Laptop-friendly — fast, 128K context",
    },
}

# ---------------------------------------------------------------------------
# TOML reader helper
# ---------------------------------------------------------------------------


def _read_toml(path: Path) -> dict | None:
    """Read a TOML file, returning None if unavailable."""
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return None
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Model download
# ---------------------------------------------------------------------------


def model_path(tag: str) -> Path:
    """Return the expected path for a model by tag."""
    info = MODELS[tag]
    return LLM_DIR / "models" / tag / info["filename"]


def download_model(tag: str) -> Path:
    """Download a model via huggingface_hub if it doesn't exist locally."""
    info = MODELS[tag]
    target = model_path(tag)
    target_dir = target.parent

    if target.exists():
        size_gb = target.stat().st_size / (1024 ** 3)
        print(f"  Model already exists: {target} ({size_gb:.1f} GB)")
        return target

    target_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nDownloading {info['label']} ...")
    print(f"  Repo: {info['repo']}")
    print(f"  This may take several minutes. Please be patient.\n")

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub is not installed.")
        print("  pip install huggingface_hub")
        sys.exit(1)

    try:
        snapshot_download(
            repo_id=info["repo"],
            allow_patterns=[info["filename"]],
            local_dir=str(target_dir),
            local_dir_use_symlinks=False,
        )
    except Exception as e:
        print(f"\nDownload failed: {e}")
        print("You can also download manually:")
        print(f"  https://huggingface.co/{info['repo']}/blob/main/{info['filename']}")
        print(f"  Place it at: {target}")
        sys.exit(1)

    if target.exists():
        print(f"  Downloaded to {target}")
    return target


# ---------------------------------------------------------------------------
# Server launch
# ---------------------------------------------------------------------------


def find_llama_server() -> Path | None:
    """Find the llama-server binary (from llama-cpp-python or system PATH)."""
    # Try llama-cpp-python's bundled binary first
    try:
        from llama_cpp import server
        pkg_dir = Path(server.__file__).resolve().parent
        for name in ("llama-server", "llama-server.exe"):
            candidate = pkg_dir / name
            if candidate.exists():
                return candidate
    except ImportError:
        pass

    # Try system PATH
    return shutil.which("llama-server")


def wait_for_server(url: str, timeout: int = 60) -> bool:
    """Poll the server's /health endpoint until ready or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(f"{url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def start_server(
    model_path: Path,
    port: int = LLM_PORT,
    n_gpu_layers: int = DEFAULT_N_GPU,
    n_threads: int = DEFAULT_N_THREADS,
) -> subprocess.Popen | None:
    """Launch llama-server and return the process handle."""
    server_bin = find_llama_server()
    if server_bin is None:
        print(
            "ERROR: llama-server binary not found.\n"
            "  Install llama-cpp-python: pip install llama-cpp-python\n"
            "  Or place a llama-server binary on your PATH."
        )
        return None

    print(f"\nStarting llama-server on http://127.0.0.1:{port} ...")
    print(f"  Model: {model_path}")
    print(f"  GPU layers: {n_gpu_layers}, Threads: {n_threads}\n")

    cmd = [
        str(server_bin),
        "-m", str(model_path),
        "--host", "127.0.0.1",
        "--port", str(port),
        "--gpu-layers", str(n_gpu_layers),
        "--threads", str(n_threads),
        "--threads-batch", str(n_threads),
        "--chat-template", "llama3",
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for server to be ready (non-blocking — the process keeps running)
    health_url = f"http://127.0.0.1:{port}/health"
    if wait_for_server(health_url, timeout=120):
        print(f"  Server is ready at {health_url}")
    else:
        print(f"  WARNING: Server may not be ready yet (timeout after 120s)")
        print(f"  Check the output above for errors.")

    return proc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Start a bundled llama.cpp chat server with auto-download."
    )
    parser.add_argument(
        "--model",
        choices=list(MODELS.keys()),
        default=None,
        help="Model to download and run (default: first available)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Server port (default: {LLM_PORT})",
    )
    parser.add_argument(
        "--ngpu",
        type=int,
        default=None,
        help=f"GPU layers 0=CPU (default: {DEFAULT_N_GPU})",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=None,
        help=f"CPU threads (default: {DEFAULT_N_THREADS})",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Skip model download (fail if model not found)",
    )
    args = parser.parse_args()

    port = args.port or int(os.environ.get("KB_LLM_PORT", str(LLM_PORT)))
    n_gpu = args.ngpu if args.ngpu is not None else DEFAULT_N_GPU
    n_threads = args.threads if args.threads is not None else DEFAULT_N_THREADS

    # Determine which model to use
    model_tag = args.model
    if not model_tag:
        # Try to read from kb.toml
        toml_path = ROOT / "kb.toml"
        if toml_path.exists():
            try:
                _cfg = _read_toml(toml_path)
                if _cfg:
                    default_model = _cfg.get("model", {}).get("default", "")
                    if default_model in MODELS:
                        model_tag = default_model
            except Exception:
                pass

        if not model_tag:
            # Fallback: pick the first (smallest) model
            model_tag = "gemma4-e2b"

    info = MODELS[model_tag]
    print(f"=== Local KB — LLM Server ===")
    print(f"Model: {info['label']}")
    print(f"  {info['desc']}")
    print(f"  Minimum RAM: {info['min_ram_gb']} GB")
    print()

    # Check RAM
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        if ram_gb < info["min_ram_gb"]:
            print(
                f"WARNING: Your system has {ram_gb:.1f} GB RAM, "
                f"but {info['label']} requires ~{info['min_ram_gb']} GB.\n"
                f"  Consider using --model gemma4-e2b instead.\n"
            )
    except ImportError:
        pass  # psutil not installed, skip check

    # Download model if needed
    target = model_path(model_tag)
    if not target.exists() and not args.no_download:
        target = download_model(model_tag)
    elif not target.exists():
        print(f"ERROR: Model not found at {target}. Run without --no-download to download.")
        sys.exit(1)

    # Launch server
    proc = start_server(target, port=port, n_gpu_layers=n_gpu, n_threads=n_threads)
    if proc is None:
        sys.exit(1)

    # Keep script alive so the server process persists
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down server ...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


if __name__ == "__main__":
    main()
