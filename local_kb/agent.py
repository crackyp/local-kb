"""ReAct-style agent for chatting over the local-kb directory.

Exposes a small read-only toolset (filesystem + wiki search) and runs a
manual tool-call loop against the configured chat model via the OpenAI-
compatible llama-server API.
"""

from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Iterator, Optional

from .config import CFG
from .paths import ROOT, WIKI, OUTPUTS
from .safe_ops import soft_delete
from .llamacpp import _post_json, get_chat_manager  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Path sandboxing
# ---------------------------------------------------------------------------


def _resolve_safe(rel_or_abs: str) -> Path:
    """Resolve a path relative to ROOT and ensure it stays inside ROOT."""
    raw = (rel_or_abs or "").strip().strip('"').strip("'")
    p = Path(raw)
    if not p.is_absolute():
        p = (ROOT / p)
    p = p.resolve()
    try:
        p.relative_to(ROOT.resolve())
    except ValueError:
        raise PermissionError(
            f"Path {p} is outside the project root {ROOT}. Access denied."
        )
    return p


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# Tool implementations (read-only)
# ---------------------------------------------------------------------------


_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".trash", "kb/.trash"}


def _skipped(path: Path) -> bool:
    parts = set(p.lower() for p in path.parts)
    return any(skip in parts for skip in _SKIP_DIRS)


def tool_list_dir(path: str = ".") -> str:
    target = _resolve_safe(path)
    if not target.exists():
        return f"ERROR: path does not exist: {_rel(target)}"
    if not target.is_dir():
        return f"ERROR: not a directory: {_rel(target)}"

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if _skipped(child):
            continue
        rel = _rel(child)
        if child.is_dir():
            entries.append(f"[dir]  {rel}/")
        else:
            try:
                size = child.stat().st_size
                entries.append(f"[file] {rel}  ({size} bytes)")
            except OSError:
                entries.append(f"[file] {rel}")
        if len(entries) >= 200:
            entries.append(f"... (truncated at 200 entries)")
            break
    if not entries:
        return f"(empty directory: {_rel(target)})"
    return "\n".join(entries)


def tool_read_file(path: str, offset: int = 0, limit: int = 20000) -> str:
    target = _resolve_safe(path)
    if not target.exists():
        return f"ERROR: file does not exist: {_rel(target)}"
    if not target.is_file():
        return f"ERROR: not a file: {_rel(target)}"
    try:
        size = target.stat().st_size
    except OSError as e:
        return f"ERROR: stat failed: {e}"

    limit = max(1, min(int(limit), 100_000))
    offset = max(0, int(offset))

    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            text = f.read(limit)
    except UnicodeDecodeError:
        return f"ERROR: file is not utf-8 readable: {_rel(target)}"
    except OSError as e:
        return f"ERROR: read failed: {e}"

    header = f"# {_rel(target)} (offset={offset}, returned={len(text)} of {size} bytes)\n"
    suffix = ""
    if offset + len(text) < size:
        suffix = f"\n... (truncated; call read_file again with offset={offset + len(text)} for more)"
    return header + text + suffix


def tool_glob_files(pattern: str) -> str:
    pattern = (pattern or "").strip()
    if not pattern:
        return "ERROR: pattern is required"

    matches: list[str] = []
    root = ROOT.resolve()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _skipped(p):
            continue
        rel = _rel(p)
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(p.name, pattern):
            matches.append(rel)
            if len(matches) >= 100:
                matches.append("... (truncated at 100 results)")
                break
    if not matches:
        return f"(no files matched: {pattern})"
    return "\n".join(matches)


def tool_grep_files(pattern: str, path: str = ".", glob: str = "*") -> str:
    if not pattern:
        return "ERROR: pattern is required"
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        return f"ERROR: invalid regex: {e}"

    target = _resolve_safe(path)
    if not target.exists():
        return f"ERROR: path does not exist: {_rel(target)}"

    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        for p in target.rglob("*"):
            if _skipped(p) or not p.is_file():
                continue
            if not (fnmatch.fnmatch(p.name, glob) or glob == "*"):
                continue
            files.append(p)

    matches: list[str] = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    if regex.search(line):
                        matches.append(f"{_rel(f)}:{i}: {line.rstrip()[:300]}")
                        if len(matches) >= 100:
                            matches.append("... (truncated at 100 matches)")
                            return "\n".join(matches)
        except (OSError, UnicodeDecodeError):
            continue
    if not matches:
        return f"(no matches for /{pattern}/ in {_rel(target)})"
    return "\n".join(matches)


def tool_wiki_search(query: str, top_k: int = 5) -> str:
    """Semantic search over the compiled wiki using FAISS."""
    if not query:
        return "ERROR: query is required"
    try:
        import sys as _sys
        scripts_dir = str((ROOT / "scripts").resolve())
        if scripts_dir not in _sys.path:
            _sys.path.insert(0, scripts_dir)
        from faiss_index import faiss_available, search_chunks, FAISS_INDEX_FILE
    except Exception as e:
        return f"ERROR: faiss module unavailable: {e}"

    if not faiss_available():
        return "ERROR: faiss-cpu is not installed"
    if not FAISS_INDEX_FILE.exists():
        return "ERROR: FAISS index not built. Run the index command first."

    cfg = dict(CFG)
    cfg["faiss"] = dict(cfg["faiss"])
    cfg["faiss"]["top_k"] = max(1, min(int(top_k), 20))

    try:
        results = search_chunks(query, cfg)
    except Exception as e:
        return f"ERROR: search failed: {e}"

    if not results:
        return f"(no wiki chunks matched: {query})"

    lines = []
    for r in results[: cfg["faiss"]["top_k"]]:
        snippet = (r.get("text") or "").strip().replace("\n", " ")[:400]
        lines.append(
            f"[{r.get('score', 0):.3f}] kb/wiki/{r.get('page')}: {snippet}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Write tools (dry-run + explicit apply)
# ---------------------------------------------------------------------------


_WRITE_ROOTS: list[tuple[Path, str]] = [
    (WIKI.resolve(), "wiki"),
    (OUTPUTS.resolve(), "outputs"),
]


def _writable_path(path: str) -> tuple[Path, str]:
    """Resolve a path and ensure it lives under an allowed write root.

    Returns (resolved_path, category) where category is 'wiki' or 'outputs'.
    """
    target = _resolve_safe(path)
    for base, category in _WRITE_ROOTS:
        try:
            target.relative_to(base)
            return target, category
        except ValueError:
            continue
    raise PermissionError(
        f"Write access denied for {_rel(target)}. "
        "Writes are limited to kb/wiki/ and kb/outputs/."
    )


_PENDING: dict[str, dict] = {}
_PENDING_COUNTER = 0


def _next_change_id() -> str:
    global _PENDING_COUNTER
    _PENDING_COUNTER += 1
    return f"c{_PENDING_COUNTER}"


def _short_diff(old: str, new: str, label: str, max_lines: int = 80) -> str:
    diff = list(
        difflib.unified_diff(
            old.splitlines(keepends=False),
            new.splitlines(keepends=False),
            fromfile=f"{label} (current)",
            tofile=f"{label} (proposed)",
            lineterm="",
            n=3,
        )
    )
    if not diff:
        return "(no textual change)"
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... ({len(diff) - max_lines} more diff lines)"]
    return "\n".join(diff)


def tool_propose_write(path: str, content: str) -> str:
    target, _cat = _writable_path(path)
    exists = target.is_file()
    old = ""
    if exists:
        try:
            old = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            old = ""
    cid = _next_change_id()
    _PENDING[cid] = {"op": "write", "path": target, "content": content}
    verb = "OVERWRITE" if exists else "CREATE"
    diff = _short_diff(old, content, _rel(target))
    return (
        f"[pending {cid}] {verb} {_rel(target)} ({len(content)} chars)\n"
        f"{diff}\n"
        f"Tell the user what you intend and wait for their confirmation. "
        f"Call apply_changes with ids=[\"{cid}\"] only after they say yes."
    )


def tool_propose_edit(path: str, old_string: str, new_string: str) -> str:
    target, _cat = _writable_path(path)
    if not target.is_file():
        return f"ERROR: file does not exist: {_rel(target)}"
    try:
        current = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return f"ERROR: read failed: {e}"
    if not old_string:
        return "ERROR: old_string must be non-empty"
    count = current.count(old_string)
    if count == 0:
        return "ERROR: old_string not found in file"
    if count > 1:
        return (
            f"ERROR: old_string occurs {count} times; "
            "provide more surrounding context to make it unique"
        )
    new_text = current.replace(old_string, new_string, 1)
    cid = _next_change_id()
    _PENDING[cid] = {"op": "write", "path": target, "content": new_text}
    diff = _short_diff(current, new_text, _rel(target))
    return (
        f"[pending {cid}] EDIT {_rel(target)}\n"
        f"{diff}\n"
        f"Tell the user what you intend and wait for their confirmation. "
        f"Call apply_changes with ids=[\"{cid}\"] only after they say yes."
    )


def tool_propose_delete(path: str) -> str:
    target, _cat = _writable_path(path)
    if not target.is_file():
        return f"ERROR: file does not exist: {_rel(target)}"
    cid = _next_change_id()
    _PENDING[cid] = {"op": "delete", "path": target}
    return (
        f"[pending {cid}] DELETE (soft-delete to kb/.trash/) {_rel(target)}\n"
        f"Tell the user what you intend and wait for their confirmation. "
        f"Call apply_changes with ids=[\"{cid}\"] only after they say yes."
    )


def tool_list_pending() -> str:
    if not _PENDING:
        return "(no pending changes)"
    return "\n".join(
        f"{cid}: {info['op']} {_rel(info['path'])}"
        for cid, info in _PENDING.items()
    )


def tool_discard_changes(ids: list) -> str:
    if not ids:
        return "ERROR: ids must be a non-empty list"
    out = []
    for cid in ids:
        if _PENDING.pop(cid, None) is not None:
            out.append(f"{cid}: discarded")
        else:
            out.append(f"{cid}: not found")
    return "\n".join(out)


def tool_apply_changes(ids: list) -> str:
    if not ids:
        return "ERROR: ids must be a non-empty list of pending change ids"
    results: list[str] = []
    for cid in ids:
        op = _PENDING.pop(cid, None)
        if op is None:
            results.append(f"{cid}: ERROR not found (already applied or never proposed)")
            continue
        try:
            path: Path = op["path"]
            if op["op"] == "write":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(op["content"], encoding="utf-8")
                results.append(f"{cid}: wrote {_rel(path)}")
            elif op["op"] == "delete":
                # Determine category from path
                _t, category = _writable_path(_rel(path))
                trash_path = soft_delete(path, category)
                results.append(f"{cid}: moved {_rel(path)} -> kb/.trash/{category}/{trash_path.name}")
            else:
                results.append(f"{cid}: ERROR unknown op {op['op']!r}")
        except Exception as e:
            results.append(f"{cid}: ERROR {e}")
    return "\n".join(results)


# ---------------------------------------------------------------------------
# Tool registry — OpenAI tool-spec format
# ---------------------------------------------------------------------------


TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": (
                "List entries in a directory inside the local-kb project. "
                "Use '.' for the project root. Returns one entry per line, "
                "directories first."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative path (e.g. 'kb/raw' or '.')",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a UTF-8 text file inside the project. Output is capped; "
                "use offset+limit to page through large files."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative file path"},
                    "offset": {"type": "integer", "description": "Byte offset to start reading from", "default": 0},
                    "limit": {"type": "integer", "description": "Max bytes to return (default 20000, max 100000)", "default": 20000},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_files",
            "description": (
                "Find files inside the project whose path or name matches a "
                "shell-style glob (e.g. 'kb/wiki/*.md' or '*.toml')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Shell-style glob pattern"}
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_files",
            "description": (
                "Search file contents (case-insensitive Python regex) under "
                "an optional path, optionally limited to files matching a glob. "
                "Returns 'path:line: text' for each match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Python regex"},
                    "path": {"type": "string", "description": "Project-relative root to search (default '.')", "default": "."},
                    "glob": {"type": "string", "description": "File-name glob filter (default '*')", "default": "*"},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_write",
            "description": (
                "Stage a full-file write to kb/wiki/ or kb/outputs/ for the user's review. "
                "Creates the file if missing, overwrites if it exists. Returns a pending "
                "change id and a diff preview. Nothing is written until apply_changes is "
                "called. Use this for new wiki pages or full rewrites; use propose_edit "
                "for small surgical changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Project-relative path under kb/wiki/ or kb/outputs/",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full new file content (UTF-8 text)",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_edit",
            "description": (
                "Stage a surgical replace of a single unique string in a file under "
                "kb/wiki/ or kb/outputs/. old_string must occur exactly once in the file. "
                "Returns a pending change id and diff. Nothing is written until "
                "apply_changes is called."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative path"},
                    "old_string": {
                        "type": "string",
                        "description": "Exact substring to replace (must be unique in the file)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Replacement text (may be empty to delete the substring)",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "propose_delete",
            "description": (
                "Stage a soft-delete (move to kb/.trash/) of a file under kb/wiki/ or "
                "kb/outputs/. Returns a pending change id. Nothing happens until "
                "apply_changes is called. Useful when merging two overlapping wikis: "
                "edit one to absorb the other's content, then propose_delete the redundant one."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Project-relative path"}
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_pending",
            "description": "List all pending (un-applied) change ids and their target paths.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "discard_changes",
            "description": (
                "Drop pending changes without applying them. Use when the user rejects "
                "a proposal or wants to start over."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Pending change ids to discard",
                    }
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_changes",
            "description": (
                "Commit pending changes to disk. ONLY call this after the user has "
                "explicitly confirmed (e.g. 'yes', 'apply', 'go ahead'). Never call it "
                "in the same turn as the proposal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Pending change ids returned from propose_* tools",
                    }
                },
                "required": ["ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wiki_search",
            "description": (
                "Semantic search over the compiled wiki via FAISS. Returns "
                "the top matching chunks with their wiki page name."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language query"},
                    "top_k": {"type": "integer", "description": "Number of chunks (1-20, default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]


_DISPATCH: dict[str, Callable[..., str]] = {
    "list_dir": tool_list_dir,
    "read_file": tool_read_file,
    "glob_files": tool_glob_files,
    "grep_files": tool_grep_files,
    "wiki_search": tool_wiki_search,
    "propose_write": tool_propose_write,
    "propose_edit": tool_propose_edit,
    "propose_delete": tool_propose_delete,
    "list_pending": tool_list_pending,
    "discard_changes": tool_discard_changes,
    "apply_changes": tool_apply_changes,
}


def _run_tool(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if fn is None:
        return f"ERROR: unknown tool '{name}'"
    try:
        return fn(**(args or {}))
    except PermissionError as e:
        return f"ERROR: {e}"
    except TypeError as e:
        return f"ERROR: invalid arguments for {name}: {e}"
    except Exception as e:
        return f"ERROR: {name} failed: {e}"


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


SYSTEM_PROMPT = (
    "You are a helpful assistant working in a personal knowledge base at "
    "H:\\programz\\knowledge\\local-kb. You have read access to the whole "
    "project and write access to kb/wiki/ and kb/outputs/.\n\n"
    "Read tools: list_dir, read_file, glob_files, grep_files, wiki_search. "
    "Prefer wiki_search for compiled-knowledge questions and the filesystem "
    "tools for code or raw-source questions. Cite file paths when you "
    "reference content.\n\n"
    "Write tools follow a dry-run + confirm pattern. NEVER write directly. "
    "Instead:\n"
    "  1. Call propose_write / propose_edit / propose_delete to stage a change. "
    "Each returns a pending change id (e.g. c1) and a diff preview.\n"
    "  2. Summarize the staged changes to the user in plain language and ask "
    "them to confirm.\n"
    "  3. Only after the user explicitly says yes/apply/go ahead, call "
    "apply_changes with the relevant ids in a SUBSEQUENT turn.\n"
    "  4. If the user rejects or wants changes, call discard_changes or stage "
    "a new proposal.\n\n"
    "Use list_pending to see what's staged. Wiki-merge workflow: read both "
    "pages, propose_write the merged page into the canonical filename, then "
    "propose_delete the redundant one. Wiki pages must keep the project's "
    "conventions: one-paragraph summary at the top, markdown links to other "
    "pages as [Title](slug.md). Keep replies concise. If a tool errors, "
    "report it and try a different approach."
)


def chat_stream(
    messages: list[dict],
    model: str,
    temperature: float = 0.3,
    max_iters: int = 10,
) -> Iterator[dict]:
    """Run a tool-call loop and yield SSE-friendly events.

    Event types:
      - {"type": "tool_call", "name": str, "args": dict}
      - {"type": "tool_result", "name": str, "result": str}
      - {"type": "content", "text": str}
      - {"type": "error", "message": str}
      - {"type": "done"}

    The caller is responsible for serializing these as SSE frames.
    """
    if not messages:
        yield {"type": "error", "message": "messages is empty"}
        yield {"type": "done"}
        return

    # Inject system prompt if absent
    history: list[dict] = list(messages)
    if not history or history[0].get("role") != "system":
        history = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    base_url = get_chat_manager().ensure_running(model)
    timeout = int(CFG["llamacpp"]["timeout"])

    for _ in range(max_iters):
        payload = {
            "model": model,
            "messages": history,
            "temperature": temperature,
            "tools": TOOLS,
            "stream": False,
        }
        try:
            body = _post_json(f"{base_url}/chat/completions", payload, timeout=timeout)
        except RuntimeError as e:
            yield {"type": "error", "message": str(e)}
            yield {"type": "done"}
            return

        choices = body.get("choices") or []
        if not choices:
            yield {"type": "error", "message": "model returned no choices"}
            yield {"type": "done"}
            return
        msg = choices[0].get("message") or {}
        tool_calls = msg.get("tool_calls") or []

        # Append assistant turn to history (must include tool_calls if present)
        assistant_turn: dict = {"role": "assistant", "content": msg.get("content") or ""}
        if tool_calls:
            assistant_turn["tool_calls"] = tool_calls
        history.append(assistant_turn)

        if not tool_calls:
            text = (msg.get("content") or "").strip()
            yield {"type": "content", "text": text}
            yield {"type": "done"}
            return

        # Execute every tool call this turn, append results to history
        for tc in tool_calls:
            fn = (tc or {}).get("function") or {}
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except json.JSONDecodeError:
                args = {}
            yield {"type": "tool_call", "name": name, "args": args}

            result = _run_tool(name, args)
            yield {
                "type": "tool_result",
                "name": name,
                "result": result if len(result) <= 4000 else result[:4000] + "\n... (truncated for display)",
            }

            history.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id") or "",
                    "name": name,
                    "content": result,
                }
            )

    yield {
        "type": "error",
        "message": f"agent stopped after {max_iters} iterations without a final answer",
    }
    yield {"type": "done"}
