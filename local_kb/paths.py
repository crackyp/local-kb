"""Canonical directory and file-path constants for local-kb."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"
KB_DIR = KB  # alias used by api.py
SCRIPTS_DIR = ROOT / "scripts"
RAW = KB / "raw"
RAW_ASSETS = RAW / "assets"
WIKI = KB / "wiki"
OUTPUTS = KB / "outputs"
INDEX = KB / "index"
CORRECTIONS = KB / "corrections"
TRASH = KB / ".trash"

STATE_FILE = INDEX / "state.json"
DOC_INDEX_FILE = INDEX / "docs.json"
WIKI_INDEX_FILE = INDEX / "wiki_index.json"

TEXT_EXTENSIONS = {
    ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".ipynb", ".log", ".ini", ".cfg", ".toml", ".sql", ".sh",
}
EXTRACTABLE_EXTENSIONS = {".docx", ".pdf"}
SKIP_PARTS = {"assets", ".git", "node_modules", "__pycache__"}


def ensure_dirs():
    for p in [RAW, RAW_ASSETS, WIKI, OUTPUTS, INDEX, CORRECTIONS, TRASH]:
        p.mkdir(parents=True, exist_ok=True)
