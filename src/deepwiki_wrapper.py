#!/usr/bin/env python
# src/deepwiki_wrapper.py

import logging
import sys
from pathlib import Path

from deepwiki_client import DeepWikiClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MINIMUM_ARGVS = 2  # Minimum number of arguments required (repo URL + format)

if len(sys.argv) < MINIMUM_ARGVS:
    sys.exit("Usage: python -m src.deepwiki_wrapper <github-url> [zip|markdown|html]")

repo = sys.argv[1]
fmt = sys.argv[2] if len(sys.argv) > MINIMUM_ARGVS else "markdown"

client = DeepWikiClient()
out = client.export_full_wiki(repo, fmt=fmt, out_dir=Path("deepwiki_output") / Path(repo).stem)
log.info("✅ done – files in %s", out)
