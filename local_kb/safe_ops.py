"""Safe file operations: soft-delete with trash and restore."""

import datetime as dt
import shutil
from pathlib import Path

from .paths import TRASH, RAW, WIKI, OUTPUTS, CORRECTIONS, ensure_dirs


CATEGORY_BASES = {
    "raw": RAW,
    "wiki": WIKI,
    "outputs": OUTPUTS,
    "corrections": CORRECTIONS,
}


def soft_delete(file_path: Path, category: str) -> Path:
    """Move a file to kb/.trash/ instead of permanently deleting it.

    The trash preserves the category and timestamp so files can be identified
    and restored later.  Returns the path inside the trash directory.

    Trash layout: kb/.trash/<category>/<timestamp>_<original_name>
    """
    ensure_dirs()
    trash_dir = TRASH / category
    trash_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    trash_name = f"{ts}_{file_path.name}"
    trash_path = trash_dir / trash_name

    shutil.move(str(file_path), str(trash_path))
    return trash_path


def list_trash(category: str | None = None) -> list:
    """List trashed files, optionally filtered by category.

    Returns list of dicts: {name, original_name, category, trashed_at, size, path}.
    """
    results = []
    categories = [category] if category else list(CATEGORY_BASES.keys())

    for cat in categories:
        trash_dir = TRASH / cat
        if not trash_dir.exists():
            continue
        for f in sorted(trash_dir.iterdir()):
            if not f.is_file():
                continue
            # Parse <YYYYMMDD-HHMMSS>_<original_name> format
            name = f.name
            parts = name.split("_", 1)
            if len(parts) == 2:
                trashed_at = parts[0]
                original_name = parts[1]
            else:
                original_name = name
                trashed_at = ""
            results.append({
                "name": name,
                "original_name": original_name,
                "category": cat,
                "trashed_at": trashed_at,
                "size": f.stat().st_size,
                "path": str(f),
            })

    return results


def restore_from_trash(trash_file_name: str, category: str) -> Path:
    """Restore a file from trash back to its original category folder.

    Returns the restored file path.
    """
    trash_path = TRASH / category / trash_file_name
    if not trash_path.exists():
        raise FileNotFoundError(f"Trash file not found: {trash_path}")

    base = CATEGORY_BASES.get(category)
    if not base:
        raise ValueError(f"Invalid category: {category}")

    # Extract original name from <YYYYMMDD-HHMMSS>_<original_name>
    parts = trash_file_name.split("_", 1)
    original_name = parts[1] if len(parts) == 2 else trash_file_name

    dest = base / original_name
    if dest.exists():
        raise FileExistsError(f"File already exists: {dest}")

    shutil.move(str(trash_path), str(dest))
    return dest


def empty_trash(category: str | None = None):
    """Permanently delete all files in the trash, optionally filtered by category."""
    categories = [category] if category else list(CATEGORY_BASES.keys())
    removed = 0
    for cat in categories:
        trash_dir = TRASH / cat
        if trash_dir.exists():
            for f in trash_dir.iterdir():
                if f.is_file():
                    f.unlink()
                    removed += 1
    return removed
