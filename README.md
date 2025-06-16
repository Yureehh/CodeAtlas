# 📘 codebase-explainer

**Visual Python codebase explainer & AI-powered documentation toolkit – powered by [DeepWiki-Open](https://github.com/AsyncFuncAI/deepwiki-open)**

---

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

---

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

---

## 📦 Installation Notes

- Requires Python `>= 3.12`
- Dependency management via [`uv`](https://github.com/astral-sh/uv)
- All dependencies declared in `pyproject.toml` – no `requirements.txt`

To install:
```bash
uv pip install -e .
```

---

## ⚙️ CLI: `deepwiki_wrapper.py`

Generate documentation for any repo:

```bash
python src/deepwiki_wrapper.py <git-url> [zip|markdown|html] [language] [provider]
```

Example:

```bash
python src/deepwiki_wrapper.py https://github.com/psf/requests markdown en openai
```

---

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

---

## 💡 Workflow & CI

- ✅ Pre-commit hooks via [`pre-commit`](https://pre-commit.com/)
- ✅ Linting & formatting via [`ruff`](https://docs.astral.sh/ruff/)
- ✅ Conventional commits via [`commitizen`](https://commitizen-tools.github.io/commitizen/)
- ✅ GitHub Actions for testing, linting, formatting, MkDocs build/deploy

---

## 📜 License

MIT License © 2025 Juri Fabbri

---

## 📞 Contact

For questions, issues, or contributions, please open an issue on the [GitHub repository] or contact me directly at [fabbri.juri@gmail.com]

---

## Next Steps
- MkDocs site templating
- Streamlit Cloud / HuggingFace deployment
- Expanding to more models and providers
- Enhancing DeepResearch capabilities
- Improving code understanding and visualization
- Adding more diagram types (e.g., sequence diagrams)
