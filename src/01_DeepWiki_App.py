"""
DeepWiki Explorer – locale-aware (EN / IT) and multi-host (GitHub, GitLab, Bitbucket).

Drop this file into `src/app.py` (or equivalent entry-point) and restart Streamlit.
"""



from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from streamlit.components.v1 import html

# ────────────────────────── env & logging ─────────────────────────────
load_dotenv(override=True)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ───────────── DeepWiki client defaults ───────────────────────────────
from deepwiki_client import LLM_MODEL as DEFAULT_MODEL
from deepwiki_client import LLM_PROV as DEFAULT_PROV
from deepwiki_client import DeepWikiClient

DEFAULT_TOKEN = os.getenv("GITHUB_TOKEN")

# ───────────── locale & i18n helpers ─────────────────────────
locale = st.session_state.get("locale", "en").lower()

STRINGS = {
    "en": {
        "title": "🕵️‍♀️ DeepWiki Explorer",
        "config": "Configuration",
        "repo_input": "GitHub / GitLab / Bitbucket Repo URL",
        "fmt": "Format",
        "language": "Wiki language",
        "provider": "Provider",
        "model": "Model",
        "private": "Private Repo",
        "token": "Access Token",
        "token_help": "Required for private repositories (PAT / App-password).",
        "generate": "Generate Wiki 📦",
        "select_file": "Select a file to preview",
        "binary": "Binary file.",
        "folder": "📂 Folder structure",
        "err_repo": "Please enter a valid repository URL.",
        "err_token": "A token is required for private repositories.",
        "spinner": "Generating wiki… 🤖",
        "wiki_ready": "✅ Wiki ready!",
        "err_connect": "Failed to connect to DeepWiki server:",
        "err_runtime": "Failed to generate wiki:",
    },
    "it": {
        "title": "🕵️‍♀️ Esploratore DeepWiki",
        "config": "Configurazione",
        "repo_input": "URL del repository (GitHub/GitLab/Bitbucket)",
        "fmt": "Formato",
        "language": "Lingua wiki",
        "provider": "Provider",
        "model": "Modello",
        "private": "Repository privato",
        "token": "Token di accesso",
        "token_help": "Necessario per repo private (PAT / App-password).",
        "generate": "Genera Wiki 📦",
        "select_file": "Seleziona un file da visualizzare",
        "binary": "File binario.",
        "folder": "📂 Struttura cartelle",
        "err_repo": "Inserisci un URL di repository valido.",
        "err_token": "Serve un token per i repository privati.",
        "spinner": "Generazione wiki… 🤖",
        "wiki_ready": "✅ Wiki pronta!",
        "err_connect": "Connessione al server DeepWiki fallita:",
        "err_runtime": "Errore nella generazione della wiki:",
    },
}
_ = STRINGS["it" if locale.startswith("it") else "en"].get

# ───────────── supported wiki languages ─────────────────────
SUPPORTED_LANGS = {
    "en": "English",
    "es": "Español",
    "ja": "日本語",
    "ko": "한국어",
    "vi": "Tiếng Việt",
    "pt-br": "Português (BR)",
    "zh": "中文",
    "zh-tw": "繁體中文",
    "fr": "Français",
}

# ──────────────────── UI ───────────────────────────────────
st.set_page_config(page_title=_("title"), layout="wide")
st.title(_("title"))

st.sidebar.header(_("config"))
repo_url = st.sidebar.text_input(
    _("repo_input"),
    placeholder="https://gitlab.com/owner/repo  |  https://bitbucket.org/owner/repo",
)

col1, col2 = st.sidebar.columns(2)
fmt = col1.selectbox(_("fmt"), ["markdown", "html", "zip"], index=0)
language = col2.selectbox(_("language"), list(SUPPORTED_LANGS.keys()), format_func=SUPPORTED_LANGS.get)

col3, col4 = st.sidebar.columns(2)
provider = col3.selectbox(
    _("provider"),
    [DEFAULT_PROV, "openai", "google", "openrouter", "ollama"],
    index=0,
)
model = col4.text_input(_("model"), value=DEFAULT_MODEL)

is_private = st.sidebar.checkbox(_("private"), value=False)
token_input = st.sidebar.text_input(_("token"), type="password", help=_("token_help"))
final_github_token = (token_input or DEFAULT_TOKEN) if is_private else None

if run := st.sidebar.button(_("generate")):
    if not repo_url:
        st.sidebar.error(_("err_repo"))
        st.stop()
    if is_private and not final_github_token:
        st.sidebar.error(_("err_token"))
        st.stop()

    client = DeepWikiClient()
    with st.spinner(_("spinner")):
        try:
            st.info(f"Accessing repo: {repo_url}")
            out_dir = client.export_full_wiki(
                repo_url=repo_url,
                fmt=fmt,
                out_dir=Path("data") / Path(repo_url).stem,
                language=language,
                provider=provider,
                model=model,
                token=final_github_token,
            )
            st.success(_("wiki_ready"))
        except ConnectionError as e:
            st.error(f"{_('err_connect')} {e}")
            st.stop()
        except RuntimeError as e:
            st.error(f"{_('err_runtime')} {e}")
            st.stop()

    # ───────────── file preview ─────────────
    files = sorted(Path(out_dir).glob("**/*.*"))
    file_names = [f.relative_to(out_dir).as_posix() for f in files]
    sel = st.selectbox(_("select_file"), file_names)
    file_path = Path(out_dir) / sel
    content = file_path.read_text(encoding="utf-8")

    if sel.endswith((".md", ".markdown")):
        mermaid_blocks = re.findall(r"```mermaid(.*?)```", content, re.DOTALL)
        md_clean = re.sub(r"```mermaid.*?```", "", content, flags=re.DOTALL)
        st.markdown(md_clean, unsafe_allow_html=True)
        for block in mermaid_blocks:
            html(
                f"""
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                <div class="mermaid">{block.strip()}</div>
                <script>mermaid.initialize({{startOnLoad:true}});</script>
                """,
                height=300,
            )
    elif sel.endswith(".html"):
        html(content, height=600)
    else:
        st.write(_("binary"))
        st.download_button("Download file", data=file_path.read_bytes(), file_name=sel)

    with st.expander(_("folder")):
        st.write("\n".join(file_names))
