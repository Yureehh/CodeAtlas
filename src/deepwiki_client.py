# src/deepwiki_client.py
"""
Ultra-thin client that fully mimics the DeepWiki-Open frontend:
  • Streams doc tokens over WebSocket
  • Saves the assembled markdown to /api/wiki_cache
  • Then calls /export/wiki to download ZIP or MD/HTML
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Final

import requests
import websockets

# ───────────────────────── globals & defaults ────────────────────────────
BASE_URL: Final[str] = "http://localhost:8001"
WS_URL: Final[str] = "ws://localhost:8001/ws/chat"
LANGUAGE: Final[str] = "en"
LLM_PROV: Final[str] = "openai"
LLM_MODEL: Final[str] = "gpt-4o"
REQ_TO: Final[int] = 30
HTTP_OK: Final[int] = 200

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class DeepWikiClient:
    def __init__(self, base: str = BASE_URL, ws_url: str = WS_URL) -> None:
        self.base = base.rstrip("/")
        self.ws_url = ws_url
        log.info("DeepWikiClient → http: %s, ws: %s", self.base, self.ws_url)

    def export_full_wiki(self, *args, **kwargs) -> Path:
        """Sync wrapper around the async flow (20 min timeout)."""
        try:
            return asyncio.run(asyncio.wait_for(self.export_full_wiki_async(*args, **kwargs), timeout=20 * 60))
        except (ConnectionRefusedError, ConnectionError):
            log.exception("Could not connect to %s – is DeepWiki running?", self.base)
            sys.exit(1)
        except TimeoutError:
            log.exception("Timed out (20 min) for export_full_wiki")
            sys.exit(1)

    async def export_full_wiki_async(
        self,
        repo_url: str,
        fmt: str = "markdown",
        out_dir: str | Path | None = None,
        language: str = LANGUAGE,
        provider: str = LLM_PROV,
        model: str = LLM_MODEL,
        token: str | None = None,
    ) -> Path:
        # ─── 1) prepare output folder ────────────────────────────────────
        dest = (Path(out_dir) if out_dir else Path("data") / Path(repo_url).stem).expanduser().absolute()
        dest.mkdir(parents=True, exist_ok=True)

        file_paths = await asyncio.to_thread(self._get_repo_files, repo_url, token)

        # ─── 3) generate via WebSocket → capture full markdown stream ───
        scaffold = self._build_payload_scaffold(repo_url, language, provider, model, file_paths, token)
        content = await self._run_and_capture_stream(scaffold["ws_payload"])
        if not content:
            msg = "No content streamed from DeepWiki server."
            raise RuntimeError(msg)

        # ─── 4) stitch into cache payload & POST to /api/wiki_cache ────
        main_id = scaffold["wiki_structure"]["pages"][0]["id"]
        scaffold["wiki_structure"]["pages"][0]["content"] = content
        scaffold["generated_pages"][main_id] = scaffold["wiki_structure"]["pages"][0]
        await asyncio.to_thread(self._save_wiki_to_cache, scaffold)

        # ─── 5) download final wiki (zip or MD/HTML) ────────────────────
        await asyncio.to_thread(self._download_and_write, repo_url, fmt, dest)
        return dest

    def _build_payload_scaffold(
        self,
        repo_url: str,
        lang: str,
        provider: str,
        model: str,
        file_paths: list[str],
        token: str | None,
    ) -> dict[str, Any]:
        log.info("Building request payload scaffold…")

        # --- START: MODIFIED LOGIC ---
        # If a token is provided, inject it into the repo_url for cloning.
        # This is for the server-side payload only, to allow `git clone`.
        payload_repo_url = repo_url
        if token:
            # Transforms https://github.com/owner/repo
            # into      https://<token>@github.com/owner/repo
            payload_repo_url = repo_url.replace("https://", f"https://{token}@")
            log.info("Injecting token into repo_url for server-side cloning.")
        # --- END: MODIFIED LOGIC ---

        prompt = (
            "Generate a full codebase wiki for the following file list:\n\n"
            + "\n".join(file_paths)
            + "\n\nInclude Mermaid diagrams of component interactions."
        )
        ws_payload = {
            # Use the potentially modified URL here
            "repo_url": payload_repo_url,
            "model": model,
            "provider": provider,
            "language": lang,
            "comprehensive": True,
            "messages": [{"role": "user", "content": prompt}],
        }
        page = {
            "id": f"all-files-{uuid.uuid4()}",
            "title": "Full Codebase Overview",
            "content": "",
            "filePaths": file_paths,
            "importance": "high",
            "relatedPages": [],
        }
        return {
            "repo": self._parse_repo_info_from_url(repo_url),  # Use original URL here
            "language": lang,
            "provider": provider,
            "model": model,
            "wiki_structure": {
                "id": "root",
                "title": "Wiki",
                "description": "Auto-generated",
                "language": lang,
                "pages": [page],
            },
            "generated_pages": {},
            "ws_payload": ws_payload,
        }

    async def _run_and_capture_stream(self, ws_payload: dict[str, Any]) -> str:
        log.info("Connecting WS → %s …", self.ws_url)
        tokens: list[str] = []
        try:
            async with websockets.connect(self.ws_url, open_timeout=20, close_timeout=60, ping_interval=20) as ws:
                await ws.send(json.dumps(ws_payload))
                log.info("✔ WS payload sent—capturing stream…")
                while True:
                    tok = await ws.recv()
                    tokens.append(str(tok))
        except websockets.exceptions.ConnectionClosedOK:
            assembled = "".join(tokens)
            log.info("✔ WS closed—%d chars received", len(assembled))
            return assembled
        except Exception as e:
            raise RuntimeError("WS error: " + str(e)) from e

    def _save_wiki_to_cache(self, scaffold: dict[str, Any]) -> None:
        log.info("Saving wiki to server cache…")
        payload = {k: v for k, v in scaffold.items() if k != "ws_payload"}
        r = requests.post(f"{self.base}/api/wiki_cache", json=payload, timeout=REQ_TO)
        _ensure_ok(r, "save wiki cache")
        log.info("✔ Saved wiki cache")

    def _download_and_write(self, repo_url: str, fmt: str, dest: Path) -> None:
        log.info("Downloading final wiki…")
        info = self._parse_repo_info_from_url(repo_url)
        params = {
            "owner": info["owner"],
            "repo": info["repo"],
            "repo_type": info["repo_type"],
            "language": LANGUAGE,
        }
        cache = requests.get(f"{self.base}/api/wiki_cache", params=params, timeout=REQ_TO)
        _ensure_ok(cache, "get cache")
        pages = cache.json().get("wiki_structure", {}).get("pages", [])

        payload = {"repo_url": repo_url, "pages": pages, "format": fmt}
        r = requests.post(f"{self.base}/export/wiki", json=payload, timeout=max(REQ_TO, 600))
        _ensure_ok(r, "export/wiki")

        ctype = r.headers.get("content-type", "")
        if "zip" in ctype or "octet-stream" in ctype:
            with zipfile.ZipFile(BytesIO(r.content)) as zf:
                zf.extractall(dest)
                log.info("📦 Extracted %d files → %s", len(zf.infolist()), dest)
        else:
            ext = ".md" if fmt == "markdown" else ".html"
            out = dest / f"wiki{ext}"
            out.write_bytes(r.content)
            log.info("📝 Saved → %s", out)

    def _get_repo_files(self, repo_url: str, token: str | None) -> list[str]:
        """
        Hit GitHub’s REST API to list every blob in the default branch,
        using the passed-in token or the one from .env.
        """
        info = self._parse_repo_info_from_url(repo_url)
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            # Fine‐grained PATs (ghp_… or github_pat_…) require Bearer; classic tokens/token apps still work with `token`
            scheme = "Bearer" if token.startswith(("ghp_", "github_pat_")) else "token"
            headers["Authorization"] = f"{scheme} {token}"

        # 1) Repo → default branch
        r_repo = requests.get(
            f"https://api.github.com/repos/{info['owner']}/{info['repo']}", headers=headers, timeout=REQ_TO
        )
        _ensure_ok(r_repo, "repo info")

        branch = r_repo.json().get("default_branch")

        # 2) Branch → commit tree SHA
        r_branch = requests.get(
            f"https://api.github.com/repos/{info['owner']}/{info['repo']}/branches/{branch}",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(r_branch, "branch info")

        tree_sha = r_branch.json().get("commit", {}).get("commit", {}).get("tree", {}).get("sha")

        # 3) Recursive tree → file list
        r_tree = requests.get(
            f"https://api.github.com/repos/{info['owner']}/{info['repo']}/git/trees/{tree_sha}?recursive=1",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(r_tree, "git tree")

        return [item["path"] for item in r_tree.json().get("tree", []) if item.get("type") == "blob"]

    def _parse_repo_info_from_url(self, url: str) -> dict[str, str]:
        m = re.match(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)", url)
        if not m:
            msg = f"Invalid GitHub URL: {url}"
            raise ValueError(msg)
        return {
            "owner": m.group("owner"),
            "repo": m.group("repo"),
            "type": "github",
            "repo_type": "github",
        }


def _ensure_ok(resp: requests.Response, step: str) -> None:
    """Raise if HTTP status is not 200."""
    if resp.status_code != HTTP_OK:
        msg = f"{step}: {resp.status_code} {resp.reason}\n{resp.text[:300]}"
        raise RuntimeError(msg)
