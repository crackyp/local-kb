"""Configuration loading for local-kb (kb.toml + defaults)."""

import json
from .paths import ROOT

_CFG_DEFAULTS = {
    "model": {"default": "qwopus:v3"},
    "llamacpp": {
        "host": "127.0.0.1",
        "chat_port": 8080,
        "embed_port": 11434,
        "timeout": 1800,
        "models": [],
    },
    "compile": {
        "temperature": 0.2,
        "max_source_chars": 192000,
        "related_pages_top_k": 5,
    },
    "ask": {"temperature": 0.1, "context_per_page": 8000, "default_limit": 6},
    "ingest": {"max_content_chars": 120000},
    "faiss": {
        "embed_model": "nomic-embed-text",
        "chunk_size": 800,
        "chunk_overlap": 100,
        "context_budget": 12000,
        "top_k": 20,
        "enabled": True,
    },
}


def _load_config() -> dict:
    cfg = json.loads(json.dumps(_CFG_DEFAULTS))  # deep copy
    toml_path = ROOT / "kb.toml"
    if not toml_path.exists():
        return cfg
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ModuleNotFoundError:
            return cfg
    try:
        with open(toml_path, "rb") as f:
            user = tomllib.load(f)
        for section, defaults in _CFG_DEFAULTS.items():
            if section in user:
                for key, default_val in defaults.items():
                    if key in user[section]:
                        val = user[section][key]
                        if isinstance(default_val, bool):
                            cfg[section][key] = (
                                val
                                if isinstance(val, bool)
                                else str(val).lower() in ("true", "1", "yes")
                            )
                        else:
                            cfg[section][key] = type(default_val)(val)
    except Exception:
        pass
    return cfg


CFG = _load_config()
