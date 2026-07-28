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


_provider_managers: Optional[dict] = None
_embed_manager: Optional[LlamaServerManager] = None
_managers_lock = threading.Lock()


def _discover_providers() -> dict:
    """Discover all [llamacpp*] sections in CFG and build server managers.

    Returns a dict: { provider_name: {"manager": LlamaServerManager, "models": set[str]} }
    The primary provider is always named "llamacpp" (from [llamacpp] in kb.toml).
    Additional providers are any [llamacpp_*] sections.
    """
    global _provider_managers
    if _provider_managers is not None:
        return _provider_managers

    result: dict = {}
    all_keys = dict(CFG)

    # Primary provider: [llamacpp]
    primary_cfg = all_keys.get("llamacpp", {})
    if primary_cfg:
        result["llamacpp"] = {
            "manager": LlamaServerManager(
                host=primary_cfg.get("host", "127.0.0.1"),
                port=int(primary_cfg.get("chat_port", 8080)),
            ),
            "models": {str(m) for m in (primary_cfg.get("models") or [])},
        }

    # Additional providers: [llamacpp_*]
    for key, value in all_keys.items():
        if key != "llamacpp" and key.startswith("llamacpp_") and isinstance(value, dict):
            host = value.get("host", "127.0.0.1")
            port = int(value.get("chat_port", 8080))
            models = {str(m) for m in (value.get("models") or [])}
            if models:  # only register if it has models defined
                result[key] = {
                    "manager": LlamaServerManager(host=host, port=port),
                    "models": models,
                }

    with _managers_lock:
        _provider_managers = result
    return result


def get_chat_manager(provider: str = "llamacpp") -> LlamaServerManager:
    """Return the LlamaServerManager for a given provider name."""
    providers = _discover_providers()
    if provider in providers:
        return providers[provider]["manager"]
    # Fall back to primary
    primary = providers.get("llamacpp", {})
    mgr = primary.get("manager")
    if mgr is not None:
        return mgr
    # Last resort: build from raw config
    cfg = _llamacpp_cfg()
    return LlamaServerManager(
        host=cfg.get("host", "127.0.0.1"),
        port=int(cfg.get("chat_port", 8080)),
    )


def resolve_provider(model: str) -> tuple[LlamaServerManager, str]:
    """Find which provider serves the given model.

    Accepts both plain names (``qwen3.6-27b``) and prefixed names
    (``remote/qwen3.6-27b``). Returns ``(manager, provider_name)``.
    Raises ``ValueError`` if the model is not found.
    """
    providers = _discover_providers()

    # Handle provider/model prefix
    target_model: str = model
    forced_provider: str | None = None
    if "/" in model:
        parts = model.split("/", 1)
        forced_provider = parts[0]
        target_model = parts[1]

    # If provider was forced, look it up directly
    if forced_provider:
        full_key = f"llamacpp_{forced_provider}" if forced_provider != "local" else "llamacpp"
        if full_key in providers and target_model in providers[full_key]["models"]:
            return providers[full_key]["manager"], full_key
        raise ValueError(
            f"Provider '{forced_provider}' does not have model '{target_model}'."
        )

    # Otherwise search all providers (first match wins)
    for name, info in providers.items():
        if target_model in info["models"]:
            return info["manager"], name

    raise ValueError(
        f"Model '{model}' not found in any configured provider. "
        f"Available: {', '.join(m for p in providers.values() for m in p['models'])}"
    )


def get_embed_manager() -> LlamaServerManager:
    """Return the embed server manager (always from primary [llamacpp] section)."""
    global _embed_manager
    with _managers_lock:
        if _embed_manager is None:
            cfg = _llamacpp_cfg()
            embed_port = cfg.get("embed_port", 11434)
            _embed_manager = LlamaServerManager(
                host=cfg.get("host", "127.0.0.1"),
                port=int(embed_port),
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


def ping(provider: str = "llamacpp") -> bool:
    """Return True if a specific provider's server is reachable.

    If no provider is given, checks the primary (llamacpp) provider.
    """
    return get_chat_manager(provider).is_alive()


def ping_any() -> bool:
    """Return True if any provider's server is reachable."""
    providers = _discover_providers()
    return any(info["manager"].is_alive() for info in providers.values())


def is_ready() -> bool:
    """Alias for :func:`ping_any` — kept for callers that import this name."""
    return ping_any()


def loaded_model(provider: str = "llamacpp") -> Optional[str]:
    """Return the model id currently resident in memory, or None.

    Tries llama-swap's ``/running`` endpoint first (returns only models with a
    live llama-server subprocess). Falls back to the OpenAI ``/v1/models[0]``
    shape, which is what a bare llama.cpp server reports — its single entry is
    the loaded model. With llama-swap that endpoint lists *all configured*
    models and is therefore meaningless for "what's loaded".
    """
    mgr = get_chat_manager(provider)
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
    """Run a chat completion against the correct provider's chat server."""
    cfg = _llamacpp_cfg()
    mgr, provider_name = resolve_provider(model)
    base_url = mgr.ensure_running(model)

    # Strip provider prefix (e.g. "remote/qwen3.6-35b-a3b" -> "qwen3.6-35b-a3b")
    # so the server receives a plain model name it understands.
    server_model = model.split("/", 1)[-1] if "/" in model else model

    # Use timeout from the provider's config section if available
    provider_cfg = CFG.get(provider_name, cfg)
    timeout = int(provider_cfg.get("timeout", cfg.get("timeout", 1200)))

    payload = {
        "model": server_model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "stream": False,
    }
    body = _post_json(f"{base_url}/chat/completions", payload, timeout=timeout)
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
    """Return the list of configured chat-model tags across all providers.

    Reads from ``[llamacpp] models`` and any ``[llamacpp_*]`` sections in kb.toml.
    Falls back to the default model. Does not query the server.

    If a model name appears in multiple providers it is prefixed with
    ``provider/model`` so the UI dropdown has unique keys.
    """
    providers = _discover_providers()
    if not providers:
        return [CFG["model"]["default"]]

    # Collect all (display_tag, model_name, provider_name) tuples
    entries: list[tuple[str, str, str]] = []
    for name, info in providers.items():
        for model in info["models"]:
            entries.append((model, model, name))

    # Detect duplicates across providers
    seen: dict[str, int] = {}
    for _, model, _ in entries:
        seen[model] = seen.get(model, 0) + 1
    dupes = {m for m, c in seen.items() if c > 1}

    # Prefix duplicates with provider short-name for disambiguation
    result: list[str] = []
    for display, model, provider in entries:
        if model in dupes:
            # "local" (not "llamacpp") for the primary — that is the prefix
            # resolve_provider() maps back to the [llamacpp] section.
            short = "local" if provider == "llamacpp" else provider.replace("llamacpp_", "")
            result.append(f"{short}/{model}")
        else:
            result.append(display)
    return result
