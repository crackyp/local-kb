"""HTTP client for the chat + embed servers.

local-kb expects two OpenAI-compatible servers to be running externally:

- chat: llama-swap on ``[llamacpp] chat_port`` (default 8080), which
  hot-swaps the underlying ``llama-server.exe`` based on the request's
  ``model`` field.
- embed: any OpenAI-compatible embedding server on ``[llamacpp] embed_port``
  (default 11434 — Ollama).

This module does not spawn either process; it only provides reachability
probes and HTTP helpers.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Optional

from .config import CFG


def _llamacpp_cfg() -> dict:
    return CFG["llamacpp"]


# ---------------------------------------------------------------------------
# Per-server handle
# ---------------------------------------------------------------------------


class LlamaServerManager:
    """Lightweight handle to an external OpenAI-compatible server."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

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
        """Verify the server is reachable; return the OpenAI base URL.

        With llama-swap, model swapping is driven by the request's ``model``
        field, so this no longer needs to start or stop anything — it just
        guards against calling a dead server.
        """
        if not self.is_alive():
            raise RuntimeError(
                f"Server not reachable at http://{self._host}:{self._port}. "
                "Make sure llama-swap (chat) and your embed server are running."
            )
        return self.base_url


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
            )
        return _chat_manager


def get_embed_manager() -> LlamaServerManager:
    global _embed_manager
    with _managers_lock:
        if _embed_manager is None:
            cfg = _llamacpp_cfg()
            _embed_manager = LlamaServerManager(
                host=cfg.get("host", "127.0.0.1"),
                port=int(cfg.get("embed_port", 11434)),
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
        raise RuntimeError(f"server call failed: {msg}")
    except Exception as e:
        raise RuntimeError(f"server call failed: {e}")


def ping() -> bool:
    """Return True if the chat server is reachable."""
    return get_chat_manager().is_alive()


def is_ready() -> bool:
    """Alias for :func:`ping` — kept for callers that import this name."""
    return ping()


def loaded_model() -> Optional[str]:
    """Return the model id currently resident in memory, or None.

    Tries llama-swap's ``/running`` endpoint first (returns only models with a
    live llama-server subprocess). Falls back to the OpenAI ``/v1/models[0]``
    shape, which is what a bare llama.cpp server reports — its single entry is
    the loaded model. With llama-swap that endpoint lists *all configured*
    models and is therefore meaningless for "what's loaded".
    """
    mgr = get_chat_manager()
    if not mgr.is_alive():
        return None

    base = f"http://{mgr.host}:{mgr.port}"
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
        return None
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return None
        # 404 -> not llama-swap; fall through to bare-llama.cpp probe
    except Exception:
        return None

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


def generate(prompt: str, model: str, temperature: float = 0.2) -> str:
    """Run a chat completion against the chat server."""
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
    """Embed a list of strings via the embed server."""
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
                f"embed server returned {len(data)} embeddings for {len(batch)} inputs"
            )
        for item in data:
            vec = item.get("embedding")
            if vec is None:
                raise RuntimeError("embed server response missing 'embedding'")
            all_embeddings.append(vec)
    return all_embeddings


def list_models() -> list[str]:
    """Return the list of configured chat-model tags.

    Reads from ``[llamacpp] models`` in kb.toml. Falls back to the default
    model. Does not query the server.
    """
    cfg = _llamacpp_cfg()
    tags = cfg.get("models", []) or []
    if isinstance(tags, list) and tags:
        return [str(t) for t in tags]
    return [CFG["model"]["default"]]
