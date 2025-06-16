import logging
from pathlib import Path

import streamlit as st
from streamlit.components.v1 import html

from deepwiki_client import LANGUAGE as DEFAULT_LANG
from deepwiki_client import LLM_MODEL as DEFAULT_MODEL
from deepwiki_client import LLM_PROV as DEFAULT_PROV
from deepwiki_client import DeepWikiClient

# Logging config
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Page config
st.set_page_config(page_title="DeepWiki Explorer", layout="wide")

st.title("🕵️‍♀️ DeepWiki Explorer")

# --- Sidebar controls ---
st.sidebar.header("Configuration")
repo_url = st.sidebar.text_input("GitHub Repo URL", placeholder="https://github.com/owner/repo")

col1, col2 = st.sidebar.columns(2)
fmt = col1.selectbox("Format", ["markdown", "html", "zip"], index=0)
language = col2.text_input("Language", value=DEFAULT_LANG)

col3, col4 = st.sidebar.columns(2)
provider = col3.selectbox("Provider", [DEFAULT_PROV, "google", "openrouter", "ollama"], index=0)
model = col4.text_input("Model", value=DEFAULT_MODEL)

github_token = st.sidebar.text_input("GitHub Token", type="password")

run = st.sidebar.button("Generate Wiki 📦")

# --- Main UI ---
if run:
    if not repo_url:
        st.sidebar.error("Please enter a valid GitHub repository URL.")
    else:
        client = DeepWikiClient()
        with st.spinner("Generating wiki... 🤖"):
            try:
                out_dir = client.export_full_wiki(
                    repo_url=repo_url,
                    fmt=fmt,
                    out_dir=Path("data") / Path(repo_url).stem,
                    language=language,
                    provider=provider,
                    model=model,
                    github_token=github_token or None,
                )
                st.success("✅ Wiki ready!")
            except Exception as e:
                st.error(f"Failed to generate wiki: {e}")
                st.stop()

        # List markdown/html files
        files = list(Path(out_dir).glob("**/*.*"))
        file_names = [f.relative_to(out_dir).as_posix() for f in files]
        sel = st.selectbox("Select a file to preview", file_names)
        file_path = Path(out_dir) / sel
        content = file_path.read_text(encoding="utf-8")

        # Render preview
        if sel.endswith((".md", ".markdown")):
            # Detect mermaid code blocks
            import re

            mermaid_blocks = re.findall(r"```mermaid(?:.*?)```", content, re.DOTALL)
            markdown_content = re.sub(r"```mermaid(?:.*?)```", "", content, flags=re.DOTALL)

            st.markdown(markdown_content, unsafe_allow_html=True)
            for block in mermaid_blocks:
                diagram = block.strip().lstrip("```mermaid").rstrip("```").strip()
                html(
                    f"""
                    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                    <div class="mermaid">{diagram}</div>
                    <script>mermaid.initialize({{startOnLoad:true}});</script>
                    """,
                    height=300,
                )
        # zip or html -> embed iframe or download link
        elif sel.endswith(".html"):
            html_str = content
            html(html_str, height=600)
        else:
            st.write("Binary file. ")
            st.download_button(
                label="Download file",
                data=file_path.read_bytes(),
                file_name=sel,
            )

        # Show folder tree
        with st.expander("📂 &nbsp; Folder structure"):
            for f in file_names:
                st.write(f)
