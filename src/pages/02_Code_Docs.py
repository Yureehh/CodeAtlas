"""
Streamlit page: Code Doc Generator
Paste or upload Python code → choose provider/model/output → receive docs or
refactored code with docstrings.  Drop this file into `pages/` and restart.

Minor patch ▸ wider Confluence iframe ▸ cleaner Markdown (no giant wrapped links) ▸ proper type-alias so `python-use-type-annotations` passes.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from textwrap import dedent
from typing import TypeAlias

import html2text  # converts pdoc HTML → Markdown
import streamlit as st
from dotenv import load_dotenv

# ────────────────────────── typing helpers ─────────────────────────────
CodeInput: TypeAlias = str | bytes  # static type alias, satisfies hooks
SECONDS_PER_HOUR = 3600  # for temp dir cleanup

# ────────────────────────── logging/env ────────────────────────────────
load_dotenv(override=True)
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ──────────────────────────── UI ───────────────────────────────────────
st.header("📄 Code Doc Generator")

tab_code, tab_upload = st.tabs(["Paste code", "Upload file(s)"])

with tab_code:
    code_text: CodeInput = st.text_area(
        "Paste Python code here",
        height=300,
        placeholder="def foo(x: int) -> int:\n    return x * 2",
    )

with tab_upload:
    up_files = st.file_uploader(
        "Upload one .py file or a ZIP / TAR of a package",
        type=["py", "zip", "tar", "gz", "bz2"],
        accept_multiple_files=False,
    )

col_p, col_m, col_f = st.columns(3)
provider = col_p.selectbox("Provider", ["openai", "anthropic", "google"], index=0)
model = col_m.text_input("Model", value=os.getenv("DEFAULT_MODEL", "gpt-4o"))
out_format = col_f.selectbox("Output format", ["markdown", "confluence", "docstrings"], index=0)

run_btn = st.button("Generate Documentation 🚀", type="primary")
st.divider()

# ─────────────────── internal helpers ──────────────────────────────────
TMP_BASE = Path(tempfile.gettempdir()) / "docgen"
TMP_BASE.mkdir(exist_ok=True)


def _write_to_temp(source: CodeInput, name_hint: str = "snippet.py") -> Path:
    """Persist uploaded or pasted code and return its path inside a temp dir."""
    workdir = Path(tempfile.mkdtemp(dir=TMP_BASE))
    target = workdir / name_hint
    if isinstance(source, bytes):
        target.write_bytes(source)
    else:
        target.write_text(dedent(source), encoding="utf-8")
    return target


def _extract_archive(bytes_data: bytes, workdir: Path) -> None:
    try:
        with tarfile.open(fileobj=BytesIO(bytes_data)) as tf:
            tf.extractall(workdir)
    except tarfile.ReadError:
        with zipfile.ZipFile(BytesIO(bytes_data)) as zf:
            zf.extractall(workdir)


def _run_pdoc(module_path: Path, *, mermaid: bool = True) -> str:
    """Return pdoc-generated **HTML** string for *module_path*."""
    import pdoc
    from pdoc import render

    render.configure(mermaid=mermaid, show_source=False, search=False, math=False)
    sys.path.insert(0, str(module_path.parent))
    return pdoc.pdoc(str(module_path))


def _html_to_md(html_doc: str) -> str:
    """Convert pdoc HTML → Markdown with sensible defaults (no wrap, trimmed ToC)."""
    conv = html2text.HTML2Text()
    conv.body_width = 0  # keep original line lengths
    md = conv.handle(html_doc)
    return re.sub(r"^\s*\[\].*Table of Contents.*?(?:\n\n|$)", "", md, flags=re.MULTILINE | re.DOTALL)


def _call_llm(prompt: str) -> str:
    """Thin provider shim – supports OpenAI, Anthropic, Gemini."""
    if provider == "openai":
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return (
            client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
            .choices[0]
            .message.content
        )
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        return (
            client.messages.create(model=model, max_tokens=4096, messages=[{"role": "user", "content": prompt}])
            .content[0]
            .text
        )
    if provider == "google":
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        return genai.GenerativeModel(model).generate_content(prompt).text
    msg = f"Unknown provider: {provider}"
    raise ValueError(msg)


def _render_mermaid_blocks(md: str) -> None:
    """Preview Mermaid diagrams & render remaining Markdown."""
    from streamlit.components.v1 import html as st_html

    mermaid_blocks = re.findall(r"```mermaid(.*?)```", md, re.DOTALL)
    st.markdown(re.sub(r"```mermaid.*?```", "", md, flags=re.DOTALL))
    for block in mermaid_blocks:
        st_html(
            f"""
            <script src='https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js'></script>
            <div class='mermaid'>{block.strip()}</div>
            <script>mermaid.initialize({{startOnLoad:true}});</script>
            """,
            height=300,
            scrolling=False,
        )


def _docstring_prompt(code: str) -> str:
    return (
        "You are a senior Python engineer. Rewrite the following code **unchanged** except for:\n"
        "• add Google-style docstrings to every public function/class/method\n"
        "• add type hints where missing\n"
        "• DO NOT modify logic\n\n"
        f"```python\n{code}\n```"
    )


# ───────────────────── main action ─────────────────────────────────────
if run_btn:
    try:
        # mutual-exclusion checks
        if up_files and code_text.strip():
            st.error("Please either paste code or upload file(s) – not both.")
            st.stop()
        if not (up_files or code_text.strip()):
            st.error("Please provide some code.")
            st.stop()

        with st.spinner("Processing …"):
            # 1 • materialise upload/paste into temp
            if up_files:
                data = up_files.getvalue()
                if up_files.name.endswith((".zip", ".tar", ".gz", ".bz2")):
                    work = Path(tempfile.mkdtemp(dir=TMP_BASE))
                    _extract_archive(data, work)
                    py_files = [p for p in work.rglob("*.py") if p.name != "__init__.py"]
                    module_path = py_files[0] if len(py_files) == 1 else work
                else:
                    module_path = _write_to_temp(data, up_files.name)
            else:
                module_path = _write_to_temp(code_text)

            # 2 • branch by output format
            if out_format == "docstrings":
                rewritten = _call_llm(_docstring_prompt(Path(module_path).read_text()))
                st.code(rewritten, language="python")
            elif out_format == "markdown":
                md_doc = _html_to_md(_run_pdoc(module_path, mermaid=True))
                _render_mermaid_blocks(md_doc)
            else:  # confluence
                html_doc = _run_pdoc(module_path, mermaid=True)
                st.components.v1.html(html_doc, height=800, width=1200, scrolling=True)
                st.text_area("Copy for Confluence", f"{{panel}}\n{html_doc}\n{{panel}}", height=150)
        st.success("Done! 🚀")

    except (FileNotFoundError, ValueError, ImportError) as exc:
        st.exception(exc)
    finally:
        now = Path().expanduser().stat().st_mtime
        for d in TMP_BASE.glob("*"):
            if d.is_dir() and now - d.stat().st_mtime > SECONDS_PER_HOUR:
                shutil.rmtree(d, ignore_errors=True)
