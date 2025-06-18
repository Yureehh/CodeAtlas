# 📘 codebase-explainer

**Visual Python codebase explainer & AI-powered documentation toolkit – powered by [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open)**



## 🔥 Features

- ✅ **Instant Documentation** — Turn any GitHub, GitLab, or BitBucket repository into a Markdown wiki in seconds
- 🔐 **Private Repo Support** — Use personal access tokens to unlock private repositories
- 🧠 **Smart Code Understanding** — Automatically analyzes AST trees, function calls, dependencies, and relationships
- 🪄 **Beautiful Diagrams** — Auto-generates [Mermaid.js](https://mermaid-js.github.io/) diagrams for architecture and data flow
- 🗺️ **Easy Navigation** — Streamlit-based GUI to browse and explore repositories
- 🤖 **Ask Your Code** — RAG-powered chatbot that understands and explains your code
- 🧪 **DeepResearch Mode** — Multi-turn investigation of concepts using full-repo context
- 🔄 **Multi-Provider Support** — Use OpenAI, Google Gemini, OpenRouter, or local Ollama models
- 🎛️ **Maximum Customizability** — Modular, stream-based architecture that supports advanced tuning and extension


## 🏁 Quickstart

```bash
# Install (Python >= 3.12 required)
uv pip install -e .
```

Then either:

```bash
# Launch the Streamlit UI (GUI)
streamlit run app.py
```

or

```bash
# Use the CLI tool directly
python src/deepwiki_wrapper.py <repo-url> [zip|markdown|html] [language] [provider]
```

### Example

```bash
python src/deepwiki_wrapper.py https://github.com/psf/requests markdown en openai
```

---

## 🛠️ Architecture Overview

```
📦 codebase-explainer
├── app.py                  # 🔵 Streamlit UI entrypoint
├── src/
│   ├── deepwiki_client.py  # 🔗 Ultra-thin WebSocket + REST client for DeepWiki backend
│   └── deepwiki_wrapper.py # ⚙️ CLI runner – mimics frontend call chain
├── pyproject.toml          # 📋 Unified config (tooling, dependencies, linting, build)
├── Makefile                # 🧰 Local automation: run, lint, test
└── .pre-commit-config.yaml # ✅ Hooks for formatting & commit hygiene
```



## 📦 Installation Notes

- Requires Python `>= 3.12`
- Dependency management via [`uv`](https://github.com/astral-sh/uv)
- All dependencies declared in `pyproject.toml` – no `requirements.txt`

To install:
```bash
uv pip install -e .
```



## ⚙️ CLI: `deepwiki_wrapper.py`

Generate documentation for any repo:

```bash
python src/deepwiki_wrapper.py <git-url> [zip|markdown|html] [language] [provider]
```

Example:

```bash
python src/deepwiki_wrapper.py https://github.com/psf/requests markdown en openai
```


## 🧪 Development

```bash
# Install project & dev tools
uv pip install -e .

# Run checks
make lint     # static analysis via Ruff
make fmt      # auto-fix style issues
make test     # pytest + coverage
make run REPO=https://github.com/psf/requests  # CLI run
```


## 💡 Workflow & CI

- ✅ Pre-commit hooks via [`pre-commit`](https://pre-commit.com/)
- ✅ Linting & formatting via [`ruff`](https://docs.astral.sh/ruff/)
- ✅ Conventional commits via [`commitizen`](https://commitizen-tools.github.io/commitizen/)
- ✅ GitHub Actions for testing, linting, formatting, MkDocs build/deploy



## 📜 License

MIT License © 2025 Juri Fabbri



## 📞 Contact

For questions, issues, or contributions, please open an issue on the [GitHub repository] or contact me directly at [fabbri.juri@gmail.com]



## Next Steps
A living plan for delivering a multilingual, multi‑provider, deeply navigable documentation and code‑insight platform.


### 📚 1.Documentation & Templating
*Focus: reusable, customizable docs with easy onboarding.*

- **MkDocs site templating** – Production‑ready theme with custom layouts, search and versioning.
- **Multiple wiki support** – Switch between generated wikis (v1, v2, team/public).
  - Descriptive filenames (e.g. `architecture_wiki.md`).
  - Changing the prompt regenerates only the selected wiki.
- **Detail‑level toggle (comprehensive ↔ concise)** – Built‑in prompt profiles `wiki_detailed.j2` & `wiki_summary.j2`; expose a slider to trim examples / keep only TOC.
- **Accept external documentation inputs** – Parse `README.md`, Confluence exports, etc., and merge with generated content.


### 🌍 2.Internationalization (i18n)
*Full multi‑language support across UI, docs, and models.*

- **Locale‑aware UI** – `react‑i18next` (Streamlit: `st.session_state.locale`), RTL support, string externalization.
- **Wiki translation workflow** – Two‑pass generation (original → machine‑translated draft → human edit); suffix files with language code (`architecture_wiki.es.md`).
- **Multilingual embeddings** – “Multilingual” flag switches to e.g. `text‑embedding‑3‑large` or Jina models.



### ☁️ 3.Deployment & Infrastructure
*One‑click to cloud, easy self‑hosting.*

- **Streamlit Cloud / HuggingFace Spaces** deploy buttons with sample configs.
- **Docker & Kubernetes manifests** (optional) – Containerize backend + frontend.



### 🌐 4.VCS Integrations
*First‑class GitHub, GitLab & Bitbucket.*

- OAuth / PAT flows (`python‑social‑auth`); env‑var tokens for headless runs.
- **Repo import wizard** – `GET /archive/{repo}.zip` (GH/GL) or Bitbucket v2 API.
- **Webhook auto‑sync** – On `push`, re‑embed changed files.
- **Pages‑style deploy badges** – GH Pages, GL Pages, Bitbucket Pipelines.



### 🤖 5.Models & Provider Extensibility
*Plug‑and‑play engines with fine‑grained control.*

- **Multi‑model support** – OpenAI, Anthropic, local LLMs via Ollama, etc.
- **Custom endpoint schema**
  ```yaml
  my-model:
    base_url: http://localhost:8000/v1
    auth: x-api-key {{MY_KEY}}
    infer_path: /chat/completions
    embed_path: /embeddings
  ```
- **Provider‑specific tuning** – Rate‑limit, temperature, tokens as CLI/GUI options.
- **Health‑check & model‑card validator** – Surface mismatches (ctx length, tool use).



### 💬 6.Chat & Prompt Handling
*Interactive, multi‑turn reasoning over the entire repo.*

- Editable chat prompt; maintain conversation + embeddings across turns.
- **Efficient embedding reuse** – Disk/memory cache to avoid re‑processing.
- **Prompt templates & profiles** – Save named templates (e.g. “API Explorer”, “Architecture Detective”).



### 🔍 7.Research & Analysis Features
*Deep‑dive tooling for code understanding.*

- **Enhanced DeepResearch mode** – Larger context windows, threaded Q&A with history viz.
- **Advanced AST analysis** – Type inference, call graphs, annotated snippets.



### 📈 8.Diagrams & Visualizations
*Richer mapping of code & flow.*

- Sequence, class, ER, data‑flow diagrams via Mermaid.
- **Custom diagram styling** – Colors, layout, Mermaid config injection.



### 🧩 9.UI/UX & Navigation
*Frictionless exploration of large repos.*

- **Folder structure selector** – Explain root vs. submodule; live preview.
- **Path filters & repo scoping** – Glob/regex include/exclude (`--include "src/**/*.py" --exclude "tests/**"`); GUI tree checkboxes; persist in `.aiassist.yaml`.
- Wiki navigation: breadcrumbs, search filters, “jump to function”, sidebar customisation.



### 🏷️ 10.Per‑Code‑Piece Documentation
*Fine‑grained doc generation for specific snippets.*

- CLI flag / Streamlit widget: “Select function/class → generate standalone MD page” with examples, parameter table, inline diagram.
