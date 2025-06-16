"""
Ultra-thin client that correctly mimics the DeepWiki-Open frontend.
This version correctly assembles the wiki by capturing and concatenating
the raw markdown tokens streamed from the server via the WebSocket, then
saves the result to the cache before downloading.
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

# ─────────────────────────── globals & defaults ────────────────────────────
BASE_URL: Final[str] = "http://localhost:8001"
WS_URL: Final[str] = "ws://localhost:8001/ws/chat"
LANGUAGE: Final[str] = "en"
LLM_PROV: Final[str] = "openai"
LLM_MODEL: Final[str] = "gpt-4o"
REQ_TO: Final[int] = 30
HTTP_OK: Final[int] = 200

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ────────────────────────────────── client ─────────────────────────────────
class DeepWikiClient:
    def __init__(self, base: str = BASE_URL, ws_url: str = WS_URL) -> None:
        self.base = base.rstrip("/")
        self.ws_url = ws_url
        log.info("DeepWikiClient → http: %s, ws: %s", self.base, self.ws_url)

    def export_full_wiki(self, *args, **kwargs) -> Path:
        """Convenience wrapper to run the async export method."""
        try:
            return asyncio.run(asyncio.wait_for(self.export_full_wiki_async(*args, **kwargs), timeout=20 * 60))
        except (ConnectionRefusedError, ConnectionError):
            log.exception("Could not connect to the backend at %s. Is the Docker container running?", self.base)
            sys.exit(1)
        except TimeoutError:
            log.exception("The entire process timed out after 20 minutes.")
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
        out = (Path(out_dir) if out_dir else Path("deepwiki_output") / Path(repo_url).stem).expanduser().absolute()
        out.mkdir(parents=True, exist_ok=True)

        file_paths = self._get_repo_files(repo_url, github_token)
        wiki_payload = self._build_payload_scaffold(repo_url, language, provider, model, file_paths)
        generated_content = await self._run_and_capture_stream(wiki_payload["websocket_trigger_payload"])

        if generated_content:
            log.info("Populating final wiki structure with generated content.")
            main_page_id = wiki_payload["wiki_structure"]["pages"][0]["id"]
            # Inject the captured content into both the pages list and the generated_pages dict
            wiki_payload["wiki_structure"]["pages"][0]["content"] = generated_content
            wiki_payload["generated_pages"][main_page_id] = wiki_payload["wiki_structure"]["pages"][0]
        else:
            msg = "Server finished but the client did not capture any content from the stream."
            raise RuntimeError(msg)

        self._save_wiki_to_cache(wiki_payload)
        self._download_and_write(repo_url, fmt, out)
        return out

    def _build_payload_scaffold(
        self, repo_url: str, lang: str, provider: str, model: str, file_paths: list[str]
    ) -> dict[str, Any]:
        """Builds the complete payload structure with placeholders."""
        log.info("Building request payload...")
        prompt = (
            f"Please generate a comprehensive wiki for the codebase with the following file structure:\n\n"
            f"{'\\n'.join(file_paths)}\n\n"
            f"--- \n"
            f"**In addition to the text documentation, please generate a high-level component interaction diagram using Mermaid.js syntax.** "
            f"The diagram should show how the main HTML, CSS, and JavaScript files (like game.js, home.js, and chessBoard.js) relate to each other and their primary roles."
        )

        ws_payload = {
            "repo_url": repo_url,
            "model": model,
            "provider": provider,
            "language": lang,
            "comprehensive": True,
            "messages": [{"role": "user", "content": prompt}],
        }

        main_page = {
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
                "title": "Full Codebase Wiki",
                "description": "Auto-generated wiki",
                "language": lang,
                "pages": [main_page],
            },
            "generated_pages": {},
            "websocket_trigger_payload": ws_payload,
        }

    async def _run_and_capture_stream(self, ws_payload: dict[str, Any]) -> str:
        """Triggers the job and concatenates the streamed raw tokens from the server."""
        log.info("Connecting to WebSocket at %s...", self.ws_url)
        all_tokens = []
        try:
            async with websockets.connect(
                self.ws_url, open_timeout=20, close_timeout=60, ping_interval=20
            ) as websocket:
                await websocket.send(json.dumps(ws_payload))
                log.info("✔ Initial payload sent. Capturing token stream...")

                while True:
                    token = await websocket.recv()
                    all_tokens.append(str(token))

        except websockets.exceptions.ConnectionClosedOK:
            log.info("✔ Server closed connection. Finished capturing stream.")
            full_content = "".join(all_tokens)
            log.info("Assembled content of %d characters.", len(full_content))
            return full_content
        except websockets.exceptions.ConnectionClosedError as e:
            msg = f"The WebSocket connection was terminated unexpectedly: {e}"
            raise RuntimeError(msg) from e
        return "".join(all_tokens)

    def _save_wiki_to_cache(self, wiki_data: dict[str, Any]):
        log.info("Saving assembled wiki to the server's cache...")
        payload_to_save = wiki_data.copy()
        if "websocket_trigger_payload" in payload_to_save:
            del payload_to_save["websocket_trigger_payload"]

        r = requests.post(f"{self.base}/api/wiki_cache", json=payload_to_save, timeout=REQ_TO)
        _ensure_ok(r, "save wiki cache")
        log.info("✔ Wiki successfully saved to server cache.")

    def _download_and_write(self, repo_url: str, fmt: str, dest: Path) -> None:
        log.info("Downloading final wiki from cache...")
        repo_info = self._parse_repo_info_from_url(repo_url)
        cached_data = self._get_cached_wiki(repo_info, LANGUAGE)

        if not cached_data or not cached_data.get("wiki_structure") or not cached_data["wiki_structure"].get("pages"):
            msg = "Failed to retrieve a valid, populated wiki from the server cache."
            raise FileNotFoundError(msg)

        pages_to_export = cached_data["wiki_structure"]["pages"]

        if not any(page.get("content") for page in pages_to_export):
            log.warning("The wiki from the cache has no content.")

        payload = {"repo_url": repo_url, "format": fmt, "pages": pages_to_export}
        r = requests.post(f"{self.base}/export/wiki", json=payload, timeout=max(REQ_TO, 600))
        _ensure_ok(r, "export/wiki")

        ctype = r.headers.get("content-type", "")
        if "zip" in ctype or "octet-stream" in ctype:
            with zipfile.ZipFile(BytesIO(r.content)) as zf:
                zf.extractall(dest)
                log.info("📦 Extracted %d files → %s", len(zf.infolist()), dest)
        else:
            ext = ".md" if fmt == "markdown" else ".html"
            out_file = dest / f"wiki{ext}"
            out_file.write_bytes(r.content)
            log.info("📝 Saved wiki → %s", out_file)

    def _get_cached_wiki(self, repo_info: dict, lang: str) -> dict | None:
        params = {"owner": repo_info["owner"], "repo": repo_info["repo"], "repo_type": "github", "language": lang}
        r = requests.get(f"{self.base}/api/wiki_cache", params=params, timeout=REQ_TO)
        _ensure_ok(r, "get final cache")
        return r.json()

    def _get_repo_files(self, repo_url: str, token: str | None) -> list[str]:
        repo_info = self._parse_repo_info_from_url(repo_url)
        owner, repo = repo_info["owner"], repo_info["repo"]
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        r_repo = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=REQ_TO)
        _ensure_ok(r_repo, "get repo info")
        default_branch = r_repo.json().get("default_branch")
        r_branch = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches/{default_branch}", headers=headers, timeout=REQ_TO
        )
        _ensure_ok(r_branch, "get branch info")
        tree_sha = r_branch.json().get("commit", {}).get("commit", {}).get("tree", {}).get("sha")
        r_tree = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(r_tree, "get git tree")
        return [item["path"] for item in r_tree.json().get("tree", []) if item.get("type") == "blob"]

    def _parse_repo_info_from_url(self, url: str) -> dict[str, str]:
        match = re.match(r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)", url)
        if not match:
            msg = f"Invalid GitHub URL: {url}"
            raise ValueError(msg)
        return {"owner": match.group("owner"), "repo": match.group("repo"), "type": "github"}


def _ensure_ok(resp: requests.Response, step: str) -> None:
    if not resp.ok:
        msg = f"Error during '{step}': {resp.status_code} {resp.reason}\nResponse: {resp.text}"
        raise RuntimeError(msg)
