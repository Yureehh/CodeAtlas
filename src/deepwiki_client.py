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
        """Sync wrapper around the async flow, with a 20 min global timeout."""
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
        github_token: str | None = None,
    ) -> Path:
        # ─── default output goes to data/<repo_name> ────────────────────
        dest = (Path(out_dir) if out_dir else Path("data") / Path(repo_url).stem).expanduser().absolute()
        dest.mkdir(parents=True, exist_ok=True)

        # 1) fetch file list
        file_paths = await asyncio.to_thread(self._get_repo_files, repo_url, github_token)

        # 2) build & stream via WebSocket
        scaffold = self._build_payload_scaffold(repo_url, language, provider, model, file_paths)
        content = await self._run_and_capture_stream(scaffold["ws_payload"])

        if not content:
            msg = "No content streamed from DeepWiki server."
            raise RuntimeError(msg)

        # 3) inject into scaffold + save cache
        main_id = scaffold["wiki_structure"]["pages"][0]["id"]
        scaffold["wiki_structure"]["pages"][0]["content"] = content
        scaffold["generated_pages"][main_id] = scaffold["wiki_structure"]["pages"][0]
        await asyncio.to_thread(self._save_wiki_to_cache, scaffold)

        # 4) download final wiki (zip or single doc)
        await asyncio.to_thread(self._download_and_write, repo_url, fmt, dest)
        return dest

    def _build_payload_scaffold(
        self,
        repo_url: str,
        lang: str,
        provider: str,
        model: str,
        file_paths: list[str],
    ) -> dict[str, Any]:
        """Assemble both REST and WS payloads exactly like the Next.js frontend."""
        log.info("Building request payload scaffold…")
        prompt = (
            "Generate a full codebase wiki for the following file list:\n\n"
            + "\n".join(file_paths)
            + "\n\nInclude Mermaid diagrams of component interactions."
        )
        ws_payload = {
            "repo_url": repo_url,
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
            "repo": self._parse_repo_info_from_url(repo_url),
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
        """WebSocket loop: send, recv all tokens, then return the concat’d string."""
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
            log.info("✔ WS closed—stream complete (%d chars)", len(assembled))
            return assembled
        except Exception as e:
            raise RuntimeError("WS error: " + str(e)) from e

    def _save_wiki_to_cache(self, scaffold: dict[str, Any]) -> None:
        """POST /api/wiki_cache with full wiki_structure + generated_pages."""
        log.info("Saving wiki to server cache…")
        payload = {k: v for k, v in scaffold.items() if k != "ws_payload"}
        r = requests.post(f"{self.base}/api/wiki_cache", json=payload, timeout=REQ_TO)
        _ensure_ok(r, "save wiki cache")
        log.info("✔ Saved wiki cache")

    def _download_and_write(
        self,
        repo_url: str,
        fmt: str | None,
        dest: Path,
    ) -> None:
        """Final call to /export/wiki then unpack or write locally."""
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
        """Hit GitHub REST to list every blob in default branch."""
        info = self._parse_repo_info_from_url(repo_url)
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        rb = requests.get(
            f"https://api.github.com/repos/{info['owner']}/{info['repo']}", headers=headers, timeout=REQ_TO
        )
        _ensure_ok(rb, "repo info")
        default_branch = rb.json().get("default_branch")
        rt = requests.get(
            f"https://api.github.com/repos/{info['owner']}/{info['repo']}/git/trees/{default_branch}?recursive=1",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(rt, "git tree")
        return [i["path"] for i in rt.json().get("tree", []) if i.get("type") == "blob"]

    def _parse_repo_info_from_url(self, url: str) -> dict[str, str]:
        """Now includes both required 'type' and 'repo_type' fields."""
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
    if resp.status_code != HTTP_OK:
        msg = f"{step}: {resp.status_code} {resp.reason}\n{resp.text[:300]}"
        raise RuntimeError(msg)
