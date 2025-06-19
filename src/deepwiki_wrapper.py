# src/deepwiki_wrapper.py

import argparse
import logging
import sys
from pathlib import Path

from src.deepwiki_client import LANGUAGE as DEFAULT_LANG
from src.deepwiki_client import LLM_MODEL as DEFAULT_MODEL
from src.deepwiki_client import LLM_PROV as DEFAULT_PROV
from src.deepwiki_client import DeepWikiClient

# ─────────────────────────── Logging Setup ────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="CLI wrapper around DeepWikiClient. Generates a full wiki for a GitHub repo."
    )

    p.add_argument(
        "repo_url",
        help="HTTPS URL of the GitHub repository (e.g. https://github.com/owner/repo)",
    )
    p.add_argument(
        "--format",
        "-f",
        choices=["zip", "markdown", "html"],
        default="markdown",
        help="Output format: zip (many files) or markdown/html single doc (default: markdown)",
    )
    p.add_argument(
        "--language",
        "-l",
        default=DEFAULT_LANG,
        help=f"Language code for the wiki (default: {DEFAULT_LANG})",
    )
    p.add_argument(
        "--provider",
        "-p",
        default=DEFAULT_PROV,
        help=f"LLM provider to use (default: {DEFAULT_PROV})",
    )
    p.add_argument(
        "--model",
        "-m",
        default=DEFAULT_MODEL,
        help=f"LLM model identifier (default: {DEFAULT_MODEL})",
    )
    p.add_argument(
        "--out-dir",
        "-o",
        type=Path,
        default=None,
        help="Directory to write results into (default: ./data/<repo_name>)",
    )
    p.add_argument(
        "--token",
        "-t",
        dest="github_token",
        default=None,
        help="GitHub personal access token (if you need to fetch private repos)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    client = DeepWikiClient()

    # Build output path default if none provided
    if args.out_dir:
        out_dir = args.out_dir
    else:
        repo_name = Path(args.repo_url).stem
        out_dir = Path("data") / repo_name

    log.info("Starting full-wiki export for %s …", args.repo_url)
    try:
        client.export_full_wiki(
            repo_url=args.repo_url,
            fmt=args.format,
            out_dir=out_dir,
            language=args.language,
            provider=args.provider,
            model=args.model,
            github_token=args.github_token,
        )
    except Exception:
        log.exception("❌ Export failed. Please check the error message above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
