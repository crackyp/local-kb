"""llama.cpp runtime + HTTP client for local-kb.

Manages one or more `llama-server.exe` subprocesses (one per port) and exposes
helpers that talk to them over the OpenAI-compatible HTTP API. Two managers
are pre-configured: a chat manager (model-swappable, default port 8080) and a
dedicated embeddings manager (loads one fixed embed model on a separate port).

Resolves Ollama-style tags (e.g. "qwopus:v3", "nomic-embed-text:latest") to
GGUF blob paths via either the project-local override map (kb.toml or
``llamacpp_external_map.json``) or the on-disk Ollama manifest store.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from .config import CFG
from .paths import ROOT


_OLLAMA_MODEL_MEDIA_TYPE = "application/vnd.ollama.image.model"

# Tuned-flag JSON file: optional, lives at project root.
TUNED_JSON_PATH = ROOT / "llamacpp_tuned.json"


def _llamacpp_cfg() -> dict:
    return CFG["llamacpp"]


def _server_exe() -> str:
    cfg_path = _llamacpp_cfg().get("server_exe", "")
    if cfg_path:
        return os.path.expandvars(os.path.expanduser(cfg_path))
    llamacpp_dir = os.environ.get("LLAMACPP_DIR", r"H:\llama.cpp")
    return os.path.join(llamacpp_dir, "llama-server.exe")


def _ollama_manifests_dir() -> str:
    cfg_dir = _llamacpp_cfg().get("ollama_models_dir", "")
    base = os.path.expandvars(os.path.expanduser(cfg_dir)) if cfg_dir else os.environ.get(
        "OLLAMA_MODELS", r"H:\ollama\models"
    )
    return os.path.join(base, "manifests", "registry.ollama.ai", "library")


def _ollama_blobs_dir() -> str:
    cfg_dir = _llamacpp_cfg().get("ollama_models_dir", "")
    base = os.path.expandvars(os.path.expanduser(cfg_dir)) if cfg_dir else os.environ.get(
        "OLLAMA_MODELS", r"H:\ollama\models"
    )
    return os.path.join(base, "blobs")


def _external_gguf_map() -> dict:
    """Combined override map: kb.toml [llamacpp.external_gguf_map] + llamacpp_external_map.json."""
    merged: dict = {}
    cfg_map = _llamacpp_cfg().get("external_gguf_map", {}) or {}
    if isinstance(cfg_map, dict):
        merged.update(cfg_map)
    json_path = ROOT / "llamacpp_external_map.json"
    if json_path.is_file():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                from_json = json.load(f)
            if isinstance(from_json, dict):
                merged.update(from_json)
        except (OSError, json.JSONDecodeError):
            pass
    return merged


def _perf_flags() -> list[str]:
    """Default fallback flags when a tag has no tuned entry."""
    return [
        "-ngl", "99",
        "-t", "8",
        "-b", "512",
        "-c", "4096",
        "--cache-type-k", "q8_0",
        "--cache-type-v", "q8_0",
    ]


def _load_tuned_flags(tag: str) -> Optional[list[str]]:
    if not TUNED_JSON_PATH.is_file():
        return None
    try:
        with open(TUNED_JSON_PATH, "r", encoding="utf-8") as f:
            tuned = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    entry = tuned.get(tag)
    if not entry:
        return None

    flags: list[str] = []
    if "n_gpu_layers" in entry:
        flags += ["-ngl", str(entry["n_gpu_layers"])]
    if "n_cpu_moe" in entry:
        flags += ["--n-cpu-moe", str(entry["n_cpu_moe"])]
    if "n_threads" in entry:
        flags += ["-t", str(entry["n_threads"])]
    if "n_batch" in entry:
        flags += ["-b", str(entry["n_batch"])]
    if "n_ubatch" in entry:
        flags += ["-ub", str(entry["n_ubatch"])]
    if "type_k" in entry:
        flags += ["--cache-type-k", str(entry["type_k"])]
    if "type_v" in entry:
        flags += ["--cache-type-v", str(entry["type_v"])]
    if entry.get("flash_attn"):
        flags += ["-fa", "on"]
    if entry.get("jinja"):
        flags += ["--jinja"]
    flags += ["-c", str(entry.get("n_ctx", 4096))]
    return flags


def resolve_tag_to_gguf(tag: str) -> str:
    """Map a model tag to an absolute GGUF path.

    Checks the project override map first, then falls back to Ollama
    manifest resolution at OLLAMA_MODELS_DIR. Tag without ':' implies ':latest'.
    """
    override = _external_gguf_map().get(tag)
    if override:
        path = os.path.expandvars(os.path.expanduser(override))
        if not os.path.isfile(path):
            raise FileNotFoundError(f"External GGUF for {tag!r} not found at {path}")
        return path

    if ":" in tag:
        name, version = tag.split(":", 1)
    else:
        name, version = tag, "latest"

    manifest_path = os.path.join(_ollama_manifests_dir(), name, version)
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            f"No GGUF mapping or Ollama manifest for {tag!r}. "
            f"Add an entry to kb.toml [llamacpp.external_gguf_map] or "
            f"llamacpp_external_map.json."
        )

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    for layer in manifest.get("layers", []):
        if layer.get("mediaType") == _OLLAMA_MODEL_MEDIA_TYPE:
            digest = layer["digest"]
            blob_filename = digest.replace(":", "-")
            blob_path = os.path.join(_ollama_blobs_dir(), blob_filename)
            if not os.path.isfile(blob_path):
                raise FileNotFoundError(f"Model blob missing for {tag!r}: {blob_path}")
            return blob_path

    raise ValueError(f"No model layer found in manifest for {tag!r}")


# ---------------------------------------------------------------------------
# Server lifecycle
# ---------------------------------------------------------------------------


class LlamaServerManager:
    """Owns a single llama-server.exe subprocess on one port. Thread-safe."""

    def __init__(
        self,
        host: str,
        port: int,
        extra_flags: Optional[list[str]] = None,
        startup_timeout: int = 90,
    ) -> None:
        self._host = host
        self._port = port
        self._extra_flags = list(extra_flags or [])
        self._startup_timeout = startup_timeout
        self._proc: Optional[subprocess.Popen] = None
        self._current_tag: Optional[str] = None
        self._stderr_path: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def base_url(self) -> str:
        return f"http://{self._host}:{self._port}/v1"

    def is_alive(self) -> bool:
        for path in ("/health", "/v1/models"):
            try:
                req = urllib.request.Request(
                    f"http://{self._host}:{self._port}{path}", method="GET"
                )
                with urllib.request.urlopen(req, timeout=2) as r:
                    if r.status == 200:
                        return True
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    return False
            except Exception:
                return False
        return False

    def ensure_running(self, tag: str) -> str:
        """Make sure llama-server is running with the requested model tag.

        Returns the OpenAI-compatible base URL.
        """
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                if self._current_tag == tag:
                    return self.base_url
                self._stop_locked()

            # If auto-spawn is disabled, just verify the server is already up.
            if not _llamacpp_cfg().get("auto_spawn", True):
                if not self.is_alive():
                    raise RuntimeError(
                        f"llama-server not reachable at {self.base_url} and "
                        "auto_spawn is disabled. Start it manually."
                    )
                self._current_tag = tag
                return self.base_url

            gguf_path = resolve_tag_to_gguf(tag)
            self._spawn_locked(tag, gguf_path)
            return self.base_url

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def _spawn_locked(self, tag: str, gguf_path: str) -> None:
        exe = _server_exe()
        if not os.path.isfile(exe):
            raise FileNotFoundError(
                f"llama-server.exe not found at {exe}. "
                "Set [llamacpp] server_exe in kb.toml or LLAMACPP_DIR env var."
            )

        flags = _load_tuned_flags(tag) or _perf_flags()
        cmd = [
            exe,
            "-m", gguf_path,
            "--host", self._host,
            "--port", str(self._port),
            "--alias", tag,
            *flags,
            *self._extra_flags,
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        stderr_fd, stderr_path = tempfile.mkstemp(prefix="llama-server-", suffix=".log")
        self._stderr_path = stderr_path
        self._proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=stderr_fd,
            creationflags=creationflags,
        )
        os.close(stderr_fd)
        self._current_tag = tag

        if not self._wait_for_health():
            exit_code = self._proc.returncode if self._proc else None
            tail = self._read_stderr_tail()
            self._stop_locked()
            reason = (
                f"process exited (code {exit_code})"
                if exit_code is not None
                else f"no /health response within {self._startup_timeout}s"
            )
            raise RuntimeError(
                f"llama-server failed for model {tag!r}: {reason}\n"
                f"--- last stderr ---\n{tail}"
            )

    def _wait_for_health(self) -> bool:
        deadline = time.time() + self._startup_timeout
        health_url = f"http://{self._host}:{self._port}/health"
        while time.time() < deadline:
            if self._proc is None or self._proc.poll() is not None:
                return False
            try:
                req = urllib.request.Request(health_url, method="GET")
                with urllib.request.urlopen(req, timeout=2) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def _read_stderr_tail(self, max_bytes: int = 4096) -> str:
        if not self._stderr_path or not os.path.isfile(self._stderr_path):
            return "(stderr unavailable)"
        try:
            with open(self._stderr_path, "rb") as f:
                f.seek(0, os.SEEK_END)
                size = f.tell()
                f.seek(max(0, size - max_bytes))
                return f.read().decode("utf-8", errors="replace")
        except OSError as e:
            return f"(stderr read failed: {e})"

    def _stop_locked(self) -> None:
        if self._proc is None:
            self._cleanup_stderr_file()
            return
        try:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        except Exception:
            pass
        finally:
            self._proc = None
            self._current_tag = None
            self._cleanup_stderr_file()

    def _cleanup_stderr_file(self) -> None:
        if self._stderr_path and os.path.isfile(self._stderr_path):
            try:
                os.unlink(self._stderr_path)
            except OSError:
                pass
        self._stderr_path = None


# ---------------------------------------------------------------------------
# Singletons: one chat server, one embed server (different ports).
# ---------------------------------------------------------------------------


_chat_manager: Optional[LlamaServerManager] = None
_embed_manager: Optional[LlamaServerManager] = None
_managers_lock = threading.Lock()


def get_chat_manager() -> LlamaServerManager:
    global _chat_manager
    with _managers_lock:
        if _chat_manager is None:
            cfg = _llamacpp_cfg()
            _chat_manager = LlamaServerManager(
                host=cfg.get("host", "127.0.0.1"),
                port=int(cfg.get("chat_port", 8080)),
                startup_timeout=int(cfg.get("startup_timeout", 90)),
            )
        return _chat_manager


def get_embed_manager() -> LlamaServerManager:
    global _embed_manager
    with _managers_lock:
        if _embed_manager is None:
            cfg = _llamacpp_cfg()
            _embed_manager = LlamaServerManager(
                host=cfg.get("host", "127.0.0.1"),
                port=int(cfg.get("embed_port", 8081)),
                extra_flags=["--embeddings"],
                startup_timeout=int(cfg.get("startup_timeout", 90)),
            )
        return _embed_manager


# ---------------------------------------------------------------------------
# HTTP helpers (OpenAI-compatible API)
# ---------------------------------------------------------------------------


def _post_json(url: str, payload: dict, timeout: int) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": "Bearer not-needed"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        msg = f"HTTP {e.code}"
        if body:
            msg += f" - {body[:300]}"
        raise RuntimeError(f"llama-server call failed: {msg}")
    except Exception as e:
        raise RuntimeError(f"llama-server call failed: {e}")


def ping() -> bool:
    """Return True if the chat server is reachable. Does not auto-spawn."""
    return get_chat_manager().is_alive()


def loaded_model() -> Optional[str]:
    """Return the model id currently resident in memory, or None.

    Tries llama-swap's ``/running`` endpoint first (returns only models with a
    live llama-server subprocess). Falls back to the OpenAI ``/v1/models[0]``
    shape, which is what a bare llama.cpp server reports — its single entry is
    the loaded model. With llama-swap that endpoint lists *all configured*
    models alphabetically and is therefore meaningless for "what's loaded".
    """
    mgr = get_chat_manager()
    if not mgr.is_alive():
        return None

    # llama-swap: GET /running -> {"running": [{"model": "...", "state": "ready"}]}
    base = f"http://{mgr._host}:{mgr._port}"
    try:
        req = urllib.request.Request(f"{base}/running", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            body = json.loads(r.read().decode("utf-8"))
        running = body.get("running") or []
        for entry in running:
            if isinstance(entry, dict) and entry.get("state") == "ready":
                model_id = entry.get("model")
                if model_id:
                    return str(model_id)
        if running:  # something is starting but not ready yet
            return None
        # /running returned empty: nothing loaded right now
        return None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None
        # 404 -> not llama-swap; fall through to bare-llama.cpp probe
    except Exception:
        return None

    # Bare llama.cpp: /v1/models returns the single loaded model
    try:
        req = urllib.request.Request(f"{mgr.base_url}/models", method="GET")
        with urllib.request.urlopen(req, timeout=2) as r:
            body = json.loads(r.read().decode("utf-8"))
    except Exception:
        return None
    data = body.get("data") or []
    if not data:
        return None
    first = data[0] or {}
    model_id = first.get("id")
    return str(model_id) if model_id else None


def is_ready() -> bool:
    """Return True if a chat call would succeed without manual setup.

    True when the chat server is already alive OR auto_spawn is enabled and
    llama-server.exe exists on disk.
    """
    if get_chat_manager().is_alive():
        return True
    if not _llamacpp_cfg().get("auto_spawn", True):
        return False
    return os.path.isfile(_server_exe())


def generate(prompt: str, model: str, temperature: float = 0.2) -> str:
    """Run a chat completion against the chat server, spawning if needed."""
    cfg = _llamacpp_cfg()
    base_url = get_chat_manager().ensure_running(model)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": False,
    }
    body = _post_json(f"{base_url}/chat/completions", payload, timeout=int(cfg["timeout"]))
    choices = body.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    return (msg.get("content") or "").strip()


_BATCH_SIZE = 32


def embed(texts: list, model: str, timeout: Optional[int] = None) -> list:
    """Embed a list of strings via the embed server, spawning if needed."""
    cfg = _llamacpp_cfg()
    if timeout is None:
        timeout = int(cfg["timeout"])
    base_url = get_embed_manager().ensure_running(model)

    all_embeddings: list = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        payload = {"model": model, "input": batch}
        body = _post_json(f"{base_url}/embeddings", payload, timeout=timeout)
        data = body.get("data") or []
        if len(data) != len(batch):
            raise RuntimeError(
                f"llama-server returned {len(data)} embeddings for {len(batch)} inputs"
            )
        for item in data:
            vec = item.get("embedding")
            if vec is None:
                raise RuntimeError("llama-server embedding response missing 'embedding'")
            all_embeddings.append(vec)
    return all_embeddings


def list_models() -> list[str]:
    """Return the list of configured chat-model tags.

    Reads from kb.toml [llamacpp.models]. Falls back to the default model.
    Does not spawn or query the server.
    """
    cfg = _llamacpp_cfg()
    tags = cfg.get("models", []) or []
    if isinstance(tags, list) and tags:
        return [str(t) for t in tags]
    return [CFG["model"]["default"]]
