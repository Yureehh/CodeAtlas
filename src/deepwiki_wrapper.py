#!/usr/bin/env python
# src/deepwiki_wrapper.py

from pathlib import Path
import sys, logging
from deepwiki_client import DeepWikiClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

if len(sys.argv) < 2:
    sys.exit("Usage: python -m src.deepwiki_wrapper <github-url> [zip|markdown|html]")

repo = sys.argv[1]
fmt = sys.argv[2] if len(sys.argv) > 2 else "markdown"

client = DeepWikiClient()
out = client.export_full_wiki(repo, fmt=fmt, out_dir=Path("deepwiki_output") / Path(repo).stem)
log.info("✅ done – files in %s", out)
