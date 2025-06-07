# Codebase Explainer (MVP) 🕵️‍♀️🖼️

CLI that **clones ↔︎ parses ↔︎ graphs** any *Python* project and spits out
Mermaid markdown or SVG architecture diagrams in seconds.

## 0. Prerequisites
* Python ≥ 3.9
* [Graphviz](https://graphviz.org/) CLI (`dot`) in `$PATH` for SVG output.
* [uv package-manager](https://astral.sh/uv) – 10× faster than pip.
  Install once:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh

1. Bootstrap
bash
Copy
Edit
git clone https://github.com/your-org/codebase-explainer.git
cd codebase-explainer
make venv     # or: uv venv
make sync     # installs deps from pyproject.toml or uv.lock
2. Usage
bash
Copy
Edit
codebase-explainer --repo https://github.com/pallets/flask \
                   --output out/flask \
                   --format mermaid
Open out/flask/module_graph.md in VS Code/GitHub to see rendered diagrams.

3. uv workflow cheat-sheet
Purpose	Command
Add a dep	make add pkg=ruff
Lock exact versions	make lock
Re-install exactly	make sync

uv.lock should be committed for deterministic builds
docs.astral.sh
docs.astral.sh
.

4. Road-map
Function-level call-graph.

RAG-powered natural-language explanations (GPT-4 / Claude).

Automatic code documentation generation from docstrings.

Documentation generation in markdown or HTML like Confluence.

GitHub Action to auto-attach diagrams to PRs.


### `codebase_explainer/__init__.py`
```python
"""Codebase-Explainer — static code cartography for Python projects."""
__version__ = "0.1.1"
