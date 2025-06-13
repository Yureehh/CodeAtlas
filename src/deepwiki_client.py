# src/deepwiki_client.py
"""
Ultra-thin client for the DeepWiki-Open FastAPI backend (port 8001).

✓ calls /export/wiki directly – no queue / polling required
✓ downloads either a ZIP (many pages) **or** a single Markdown / HTML document
✓ writes / unpacks everything into an output folder
"""

from __future__ import annotations

import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import requests

# ─────────────────────────── constants ── #
BASE_URL = "http://localhost:8001"  # docker-compose default
SUCCESS = 200  # HTTP status code for success
REQ_TO = 600  # download may take a while


class DeepWikiClient:
    def __init__(self, base: str = BASE_URL) -> None:
        self.base = base.rstrip("/")

    # ───────────────────── public API ── #
    def export_full_wiki(
        self,
        repo_url: str,
        language: str = "python",
        fmt: str = "markdown",  # "zip" | "markdown" | "html"
        out_dir: str | Path | None = None,
    ) -> Path:
        """
        1. Build a *wild-card* WikiStructure that tells DeepWiki to export **everything**
        2. POST /export/wiki  → receive either ZIP or single document
        3. Save / unpack into *out_dir*
        """
        out_dir = (Path(out_dir) if out_dir else Path("deepwiki_output") / Path(repo_url).stem).expanduser().absolute()
        out_dir.mkdir(parents=True, exist_ok=True)

        wiki_struct = _wildcard_root(language)  # export “all pages”

        resp = requests.post(
            f"{self.base}/export/wiki",
            json={
                "repo_url": repo_url,
                "pages": wiki_struct["pages"],
                "format": fmt,
            },
            timeout=REQ_TO,
        )
        _ensure_ok(resp, "export/wiki")

        ctype = resp.headers.get("content-type", "")
        if "zip" in ctype:
            _unpack_zip(resp.content, out_dir)
        else:  # one big doc (md / html)
            ext = ".md" if "markdown" in ctype else ".html"
            (out_dir / f"index{ext}").write_bytes(resp.content)

        return out_dir


# ─────────────────── helper functions ── #
def _wildcard_root(lang: str) -> dict[str, Any]:
    """A minimal WikiStructure that matches *everything*."""
    return {
        "id": "root",
        "title": "Full-Wiki",
        "description": "Export every page",
        "language": lang,
        "pages": [
            {
                "id": f"all-{uuid.uuid4()}",
                "title": "All Pages",
                "content": "",
                "filePaths": ["*"],
                "importance": "high",
                "relatedPages": [],
            }
        ],
    }


def _unpack_zip(data: bytes, dest: Path) -> None:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        zf.extractall(dest)


def _ensure_ok(resp: requests.Response, step: str) -> None:
    if resp.status_code != SUCCESS:
        msg = f"{step}: {resp.status_code} {resp.reason} — {resp.text[:300]}"
        raise RuntimeError(msg)
