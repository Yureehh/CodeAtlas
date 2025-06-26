#!/usr/bin/env bash
# Recreate requirements.txt from pyproject.toml (uv ≥ 0.2 or Poetry ≥1.7)

set -e
echo "🔄  Exporting requirements.txt …"

# choose ONE of the next two commands:
uv pip compile --no-annotate pyproject.toml -o requirements.txt    # ← uv
# poetry export -f requirements.txt --output requirements.txt --without-hashes # ← poetry

echo "-e ." >> requirements.txt      # install your package itself
echo "✅  requirements.txt updated"
