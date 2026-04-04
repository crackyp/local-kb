#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import streamlit as st

ROOT = Path(__file__).resolve().parent
KB_DIR = ROOT / "kb"
RAW_DIR = KB_DIR / "raw"
WIKI_DIR = KB_DIR / "wiki"
OUTPUTS_DIR = KB_DIR / "outputs"
CLI_PATH = ROOT / "scripts" / "kb.py"
TMP_UPLOADS = ROOT / ".tmp_uploads"


def ensure_dirs() -> None:
    for p in [RAW_DIR, WIKI_DIR, OUTPUTS_DIR, KB_DIR / "index", RAW_DIR / "assets", TMP_UPLOADS]:
        p.mkdir(parents=True, exist_ok=True)


def run_kb(args: List[str]) -> Tuple[int, str, str]:
    cmd = [sys.executable, str(CLI_PATH), *args]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    combined = output + ("\n\n" + err if err else "")
    shown_cmd = " ".join([str(x) for x in cmd])
    return proc.returncode, combined.strip(), shown_cmd


def safe_name(name: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_."
    cleaned = "".join(ch if ch in allowed else "-" for ch in name.strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-.")
    return cleaned or f"upload-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    ts = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    return path.with_name(f"{path.stem}-{ts}{path.suffix}")


def save_uploaded_to(dir_path: Path, files) -> List[Path]:
    saved = []
    for f in files:
        name = safe_name(f.name)
        dst = unique_path(dir_path / name)
        dst.write_bytes(f.getbuffer())
        saved.append(dst)
    return saved


def list_files(directory: Path, pattern: str = "*.md") -> List[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)


def parse_written_path(output: str) -> Optional[Path]:
    marker = "Wrote:"
    for line in output.splitlines():
        if line.startswith(marker):
            maybe = line.replace(marker, "", 1).strip()
            p = Path(maybe)
            return p if p.exists() else None
    return None


def show_cmd_result(returncode: int, output: str, shown_cmd: str) -> None:
    if returncode == 0:
        st.success("Done")
    else:
        st.error(f"Command failed (exit {returncode})")

    with st.expander("Command details", expanded=(returncode != 0)):
        st.code(shown_cmd, language="bash")
        st.code(output or "(no output)")


def render_sidebar() -> str:
    st.sidebar.title("Local KB")
    st.sidebar.caption("Ollama + Obsidian")

    model = st.sidebar.text_input("Default model", value="phi4-mini")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Directories**")
    st.sidebar.code(str(KB_DIR))

    raw_count = len([p for p in RAW_DIR.glob("**/*") if p.is_file()])
    wiki_count = len(list_files(WIKI_DIR, "*.md"))
    out_count = len(list_files(OUTPUTS_DIR, "*.md"))

    st.sidebar.metric("Raw files", raw_count)
    st.sidebar.metric("Wiki pages", wiki_count)
    st.sidebar.metric("Output files", out_count)

    return model


def tab_ingest_files() -> None:
    st.subheader("Ingest Local Files")
    uploaded = st.file_uploader(
        "Upload source files",
        accept_multiple_files=True,
        help="Saves uploaded files into kb/raw/",
    )

    if st.button("Save uploaded files", use_container_width=True):
        if not uploaded:
            st.warning("Select at least one file first.")
        else:
            saved = save_uploaded_to(RAW_DIR, uploaded)
            st.success(f"Saved {len(saved)} file(s) to kb/raw")
            for p in saved[:20]:
                st.write(f"- `{p.name}`")

    st.markdown("---")
    st.caption("Or ingest files by path/glob from the machine running this app.")
    path_globs = st.text_area(
        "Path globs (one per line)",
        value="",
        placeholder="/Users/you/Research/*.md\n/Users/you/Research/*.txt",
    )
    if st.button("Ingest by path", use_container_width=True):
        lines = [ln.strip() for ln in path_globs.splitlines() if ln.strip()]
        if not lines:
            st.warning("Add at least one path/glob.")
        else:
            rc, out, cmd = run_kb(["ingest", *lines])
            show_cmd_result(rc, out, cmd)


def tab_ingest_url() -> None:
    st.subheader("Ingest URLs")
    urls_text = st.text_area(
        "URLs (one per line)",
        placeholder="https://example.com\nhttps://arxiv.org/abs/...",
        height=140,
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        dl_images = st.checkbox("Download images", value=False)
    with col2:
        max_images = st.number_input("Max images", min_value=1, max_value=200, value=20, step=1)
    with col3:
        timeout = st.number_input("Timeout sec", min_value=5, max_value=300, value=30, step=5)

    if st.button("Ingest URL(s)", use_container_width=True):
        urls = [u.strip() for u in urls_text.splitlines() if u.strip()]
        if not urls:
            st.warning("Add at least one URL.")
        else:
            args = ["ingest-url", *urls, "--timeout", str(timeout), "--max-images", str(max_images)]
            if dl_images:
                args.append("--download-images")
            rc, out, cmd = run_kb(args)
            show_cmd_result(rc, out, cmd)


def tab_ingest_pdf() -> None:
    st.subheader("Ingest PDFs")
    st.caption("Extracts text from PDF(s) into markdown files in kb/raw/")

    uploaded = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)
    col1, col2 = st.columns(2)
    with col1:
        max_pages = st.number_input("Max pages (0 = all)", min_value=0, max_value=5000, value=0, step=1)
    with col2:
        copy_original = st.checkbox("Copy original PDF into kb/raw", value=False)

    if st.button("Extract PDF text", use_container_width=True):
        if not uploaded:
            st.warning("Upload at least one PDF first.")
            return

        saved = save_uploaded_to(TMP_UPLOADS, uploaded)
        args = ["ingest-pdf", *[str(p) for p in saved]]
        if max_pages > 0:
            args += ["--max-pages", str(max_pages)]
        if copy_original:
            args.append("--copy-original")

        rc, out, cmd = run_kb(args)
        show_cmd_result(rc, out, cmd)


def tab_compile(default_model: str) -> None:
    st.subheader("Compile Wiki")
    model = st.text_input("Model", value=default_model, key="compile_model")
    force = st.checkbox("Force recompile all docs", value=False)

    if st.button("Run compile", type="primary", use_container_width=True):
        args = ["compile", "--model", model]
        if force:
            args.append("--force")
        rc, out, cmd = run_kb(args)
        show_cmd_result(rc, out, cmd)


def tab_ask(default_model: str) -> None:
    st.subheader("Ask the Wiki")
    question = st.text_area(
        "Question",
        placeholder="What are the recurring claims about retrieval quality?",
        height=120,
    )
    col1, col2 = st.columns([2, 1])
    with col1:
        model = st.text_input("Model", value=default_model, key="ask_model")
    with col2:
        limit = st.number_input("Page limit", min_value=1, max_value=30, value=6, step=1)

    if st.button("Run Q&A", type="primary", use_container_width=True):
        if not question.strip():
            st.warning("Please enter a question.")
            return
        args = ["ask", question.strip(), "--model", model, "--limit", str(limit)]
        rc, out, cmd = run_kb(args)
        show_cmd_result(rc, out, cmd)

        written = parse_written_path(out)
        if written:
            st.markdown("### Answer preview")
            st.markdown(written.read_text(encoding="utf-8", errors="ignore"))


def tab_lint() -> None:
    st.subheader("Lint Wiki")
    st.caption("Checks broken markdown links and orphan pages.")
    if st.button("Run lint", use_container_width=True):
        rc, out, cmd = run_kb(["lint"])
        show_cmd_result(rc, out, cmd)


def tab_explorer() -> None:
    st.subheader("File Explorer")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Wiki pages")
        wiki_files = list_files(WIKI_DIR, "*.md")
        if not wiki_files:
            st.info("No wiki pages yet.")
        else:
            options = [p.name for p in wiki_files]
            selected = st.selectbox("Pick wiki file", options=options, key="wiki_pick")
            path = WIKI_DIR / selected
            st.markdown(path.read_text(encoding="utf-8", errors="ignore"))

    with col2:
        st.markdown("#### Output files")
        output_files = list_files(OUTPUTS_DIR, "*.md")
        if not output_files:
            st.info("No outputs yet.")
        else:
            options = [p.name for p in output_files]
            selected = st.selectbox("Pick output file", options=options, key="out_pick")
            path = OUTPUTS_DIR / selected
            st.markdown(path.read_text(encoding="utf-8", errors="ignore"))


def main() -> None:
    ensure_dirs()
    st.set_page_config(page_title="Local KB", page_icon="📚", layout="wide")
    st.title("📚 Local KB UI")
    st.caption("Ingest → Compile → Ask → Lint")

    default_model = render_sidebar()

    tabs = st.tabs([
        "Ingest Files",
        "Ingest URL",
        "Ingest PDF",
        "Compile",
        "Ask",
        "Lint",
        "Explorer",
    ])

    with tabs[0]:
        tab_ingest_files()
    with tabs[1]:
        tab_ingest_url()
    with tabs[2]:
        tab_ingest_pdf()
    with tabs[3]:
        tab_compile(default_model)
    with tabs[4]:
        tab_ask(default_model)
    with tabs[5]:
        tab_lint()
    with tabs[6]:
        tab_explorer()


if __name__ == "__main__":
    main()
