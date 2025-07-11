"""
Streamlit page: Code Doc Generator
Paste or upload Python code → choose provider/model → receive comprehensive
documentation including a Mermaid diagram, refactored code, and Confluence markup.
"""

from __future__ import annotations

import base64
import logging
import os
import re
import shutil
import tarfile
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from textwrap import dedent

import streamlit as st
from dotenv import load_dotenv
from streamlit.components.v1 import html

# ────────────────────────── typing helpers ─────────────────────────────
type CodeInput = str | bytes  # static type alias, satisfies hooks
SECONDS_PER_HOUR: int = 3600  # used for temp dir cleanup

# ────────────────────────── logging/env ────────────────────────────────
load_dotenv(override=True)
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# ──────────────────────────── UI ───────────────────────────────────────
st.set_page_config(layout="wide")
st.header("📄 Code Doc Generator")

st.info(
    "**How it works:** This app sends will refactor the code to add type hints and Google-style docstrings, "
    "and it will generate a Mermaid diagram to visualize the code structure."
)
st.markdown("<br>", unsafe_allow_html=True)

col_p, col_m = st.columns(2)
provider = col_p.selectbox("Provider", ["openai", "anthropic", "google"], index=0)
model = col_m.text_input("Model", value=os.getenv("DEFAULT_MODEL", "gpt-4o"))

tab_code, tab_upload = st.tabs(["Paste code", "Upload file(s)"])
with tab_code:
    code_text: CodeInput = st.text_area(
        "Paste Python code here",
        height=300,
        placeholder="def foo(x: int) -> int:\n    return x * 2",
        label_visibility="collapsed",
    )

with tab_upload:
    up_files = st.file_uploader(
        "Upload one .py file or a ZIP / TAR of a package",
        type=["py", "zip", "tar", "gz", "bz2"],
        accept_multiple_files=False,
        label_visibility="collapsed",
    )

run_btn = st.button("Generate Documentation 🚀", type="primary")
st.divider()

# ─────────────────── internal helpers ──────────────────────────────────
TMP_BASE = Path(tempfile.gettempdir()) / "docgen"
TMP_BASE.mkdir(exist_ok=True)


def _write_to_temp(source: CodeInput, name_hint: str = "snippet.py") -> Path:
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


def _parse_llm_output(llm_response: str) -> tuple[str | None, str]:
    mermaid_content, code_content = None, llm_response
    mermaid_pattern = r"```mermaid(.*?)```"
    mermaid_match = re.search(mermaid_pattern, llm_response, re.DOTALL)
    if mermaid_match:
        mermaid_content = mermaid_match.group(1).strip()
        code_content = llm_response.replace(mermaid_match.group(0), "").strip()
    python_pattern = r"```python(.*?)```"
    python_match = re.search(python_pattern, code_content, re.DOTALL)
    code_content = python_match.group(1).strip() if python_match else code_content.strip()
    return mermaid_content, code_content


def _create_styled_copy_button(text_to_copy: str) -> None:
    """Creates a styled button that copies the given text to the clipboard."""
    text_b64 = base64.b64encode(text_to_copy.encode()).decode()
    button_uuid = f"copy-btn-{hash(text_to_copy)}"

    button_html = f"""
    <style>
        #{button_uuid} {{
            background-color: #0068c9;
            color: white;
            border: none;
            padding: 12px 24px;
            text-align: center;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            font-weight: bold;
            margin-top: 0; /* Align button to the top of the column */
            cursor: pointer;
            border-radius: 8px;
            transition-duration: 0.2s;
            width: 100%;
            min-width: 180px;
        }}
        #{button_uuid}:hover {{
            background-color: #005aa3;
        }}
        #{button_uuid}:active {{
            background-color: #004c8b;
        }}
        #{button_uuid}.copied {{
            background-color: #4CAF50; /* Green */
        }}
    </style>
    <!-- REQ 2 (FIX): Changed button text -->
    <button id="{button_uuid}" onclick="copyToClipboard(this)">Confluence Copy</button>
    <script>
    async function copyToClipboard(element) {{
        const text = atob('{text_b64}');
        await navigator.clipboard.writeText(text);
        element.innerText = 'Copied!';
        element.classList.add('copied');
        element.disabled = true;
        setTimeout(() => {{
            element.innerText = 'Confluence Copy';
            element.classList.remove('copied');
            element.disabled = false;
        }}, 2000);
    }}
    </script>
    """
    html(button_html)


def _call_llm(prompt: str) -> str:
    if provider == "openai":
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
        return response.choices[0].message.content
    if provider == "anthropic":
        import anthropic

        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        response = client.messages.create(model=model, max_tokens=4096, messages=[{"role": "user", "content": prompt}])
        return response.content[0].text
    if provider == "google":
        import google.generativeai as genai

        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        model_instance = genai.GenerativeModel(model)
        return model_instance.generate_content(prompt).text
    msg = f"Unknown provider: {provider}"
    raise ValueError(msg)


def _docstring_prompt(code: str) -> str:
    return (
        "You are a senior Python engineer. Your task is to document the provided Python code.\n"
        "1.  First, create a concise `mermaid` class diagram illustrating the key classes, functions, and their relationships. Enclose it in ```mermaid fences.\n"
        "2.  Then, rewrite the original Python code. The logic must remain **unchanged**.\n"
        "3.  Add Google-style docstrings to every public function, class, and method.\n"
        "4.  Add or complete type hints where they are missing.\n"
        "5.  Enclose the final Python code in ```python fences.\n\n"
        "Here is the code:\n"
        f"```python\n{code}\n```"
    )


# ───────────────────── main action ─────────────────────────────────────
if run_btn:
    try:
        if up_files and code_text.strip():
            st.error("Please either paste code or upload file(s) – not both.")
            st.stop()
        if not (up_files or code_text.strip()):
            st.error("Please provide some code.")
            st.stop()

        with st.spinner("Calling LLM to generate documentation..."):
            if up_files:
                data = up_files.getvalue()
                if up_files.name.endswith((".zip", ".tar", ".gz", ".bz2")):
                    work = Path(tempfile.mkdtemp(dir=TMP_BASE))
                    _extract_archive(data, work)
                    all_code = [
                        f"# --- File: {py_file.name} ---\n\n{py_file.read_text()}"
                        for py_file in sorted(work.rglob("*.py"))
                    ]
                    source_code = "\n\n".join(all_code)
                else:
                    source_code = data.decode("utf-8")
            else:
                source_code = str(code_text)

            llm_response = _call_llm(_docstring_prompt(source_code))
            mermaid_diagram, python_code = _parse_llm_output(llm_response)

        if mermaid_diagram:
            st.subheader("Mermaid Diagram")
            # REQ 1 (FIX): Changed column ratio to give more space to the rendered diagram.
            col_render, col_text = st.columns([3, 2])
            with col_render:
                mermaid_html = f"""
                <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
                <div class="mermaid" style="text-align: center;">
                    {mermaid_diagram}
                </div>
                """
                html(mermaid_html, height=400, scrolling=True)
            with col_text:
                # REQ 1 (FIX): Re-add "Diagram Source" header.
                st.markdown("#### Diagram Source")
                st.code(mermaid_diagram, language="mermaid")

        st.subheader("Documented Code")
        st.code(python_code, language="python")
        st.markdown("<br>", unsafe_allow_html=True)

        st.subheader("Confluence Wiki Markup")
        col_btn, col_desc = st.columns([1, 3])
        with col_btn:
            confluence_markup = []
            if mermaid_diagram:
                confluence_markup.append("{mermaid}\n" + mermaid_diagram + "\n{mermaid}")
            confluence_markup.append(
                "{code:language=python|theme=default|linenumbers=true|title=Python Code}\n" + python_code + "\n{code}"
            )
            _create_styled_copy_button("\n\n".join(confluence_markup))
        with col_desc:
            st.info(
                "Click the 'Confluence Copy' button to copy the complete markup for direct pasting into the Confluence editor."
            )

    except (FileNotFoundError, ValueError, ImportError) as exc:
        st.error(f"An error occurred: {exc}")
        st.exception(exc)
    finally:
        now = Path().expanduser().stat().st_mtime
        for d in TMP_BASE.glob("*"):
            if d.is_dir() and now - d.stat().st_mtime > SECONDS_PER_HOUR:
                shutil.rmtree(d, ignore_errors=True)
