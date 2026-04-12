"""Audit log for destructive operations.

Appends a line to kb/index/audit.log for every delete, restore, or empty-trash
action.  The log is append-only and human-readable.
"""

import datetime as dt
from .paths import INDEX, ensure_dirs


AUDIT_LOG = INDEX / "audit.log"


def log_action(action: str, category: str, target: str, detail: str = ""):
    """Append an audit entry.

    Args:
        action: e.g. "delete", "restore", "empty_trash"
        category: e.g. "raw", "wiki", "outputs"
        target: filename or path affected
        detail: optional extra info
    """
    ensure_dirs()
    ts = dt.datetime.now().isoformat()
    parts = [ts, action, category, target]
    if detail:
        parts.append(detail)
    line = " | ".join(parts) + "\n"
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(line)
