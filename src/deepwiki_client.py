# src/deepwiki_client.py
"""
Ultra-thin DeepWiki client:
  • Streams doc tokens over WebSocket
  • Saves assembled markdown to /api/wiki_cache
  • Calls /export/wiki to download ZIP or MD/HTML
Supports GitHub, GitLab.com and Bitbucket.org repositories.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import urllib.parse
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Final, Literal

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

GIT_HOST_RE = re.compile(
    r"""https?://
        (?P<host>github\.com|gitlab\.com|bitbucket\.org)
        /(?P<owner>[^/]+)/(?P<repo>[^/]+)""",
    re.VERBOSE,
)

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


class DeepWikiClient:
    def __init__(self, base: str = BASE_URL, ws_url: str = WS_URL) -> None:
        self.base = base.rstrip("/")
        self.ws_url = ws_url
        log.info("DeepWikiClient → http: %s  ws: %s", self.base, self.ws_url)

    # ────────────────────────── public API ──────────────────────────────
    def export_full_wiki(self, *args, **kwargs) -> Path:
        """Sync wrapper around the async flow (20 min timeout)."""
        try:
            coro = self.export_full_wiki_async(*args, **kwargs)
            return asyncio.run(asyncio.wait_for(coro, timeout=20 * 60))
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
        # 1 ) prepare output folder
        dest = (Path(out_dir) if out_dir else Path("data") / Path(repo_url).stem).expanduser().absolute()
        dest.mkdir(parents=True, exist_ok=True)

        file_paths = await asyncio.to_thread(self._get_repo_files, repo_url, token)

        # 2 ) generate via WebSocket → capture full markdown stream
        scaffold = self._build_payload_scaffold(repo_url, language, provider, model, file_paths, token)
        content = await self._run_and_capture_stream(scaffold["ws_payload"])
        if not content:
            msg = "No content streamed from DeepWiki server."
            raise RuntimeError(msg)

        # 3 ) stitch into cache payload & POST to /api/wiki_cache
        main_id = scaffold["wiki_structure"]["pages"][0]["id"]
        scaffold["wiki_structure"]["pages"][0]["content"] = content
        scaffold["generated_pages"][main_id] = scaffold["wiki_structure"]["pages"][0]
        await asyncio.to_thread(self._save_wiki_to_cache, scaffold)

        # 4 ) download final wiki
        await asyncio.to_thread(self._download_and_write, repo_url, fmt, dest)
        return dest

    # ────────────────────────── helpers ─────────────────────────────────
    def _build_payload_scaffold(
        self,
        repo_url: str,
        lang: str,
        provider: str,
        model: str,
        file_paths: list[str],
        token: str | None,
    ) -> dict[str, Any]:
        log.info("Building request payload scaffold …")

        # If a token is provided, inject it into the clone URL (works for GitHub PAT,
        # GitLab PAT, and Bitbucket app-password):
        payload_repo_url = repo_url.replace("https://", f"https://{token}@") if token else repo_url

        prompt = (
            "Generate a full codebase wiki for the following file list:\n\n"
            + "\n".join(file_paths)
            + "\n\nInclude Mermaid diagrams of component interactions."
        )
        ws_payload = {
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
        log.info("Connecting WS → %s …", self.ws_url)
        tokens: list[str] = []
        try:
            async with websockets.connect(self.ws_url, open_timeout=20, close_timeout=60, ping_interval=20) as ws:
                await ws.send(json.dumps(ws_payload))
                while True:
                    tok = await ws.recv()
                    tokens.append(str(tok))
        except websockets.exceptions.ConnectionClosedOK:
            assembled = "".join(tokens)
            log.info("✔ WS closed — %d chars received", len(assembled))
            return assembled
        except Exception as e:  # pragma: no cover
            msg = f"WS error: {e!s}"
            raise RuntimeError(msg) from e

    def _save_wiki_to_cache(self, scaffold: dict[str, Any]) -> None:
        payload = {k: v for k, v in scaffold.items() if k != "ws_payload"}
        r = requests.post(f"{self.base}/api/wiki_cache", json=payload, timeout=REQ_TO)
        _ensure_ok(r, "save wiki cache")

    def _download_and_write(self, repo_url: str, fmt: str, dest: Path) -> None:
        info = self._parse_repo_info_from_url(repo_url)
        params = {"owner": info["owner"], "repo": info["repo"], "repo_type": info["repo_type"], "language": LANGUAGE}
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
        else:
            ext = ".md" if fmt == "markdown" else ".html"
            (dest / f"wiki{ext}").write_bytes(r.content)

    # ──────────────── multi-provider blob listing ───────────────────────
    def _get_repo_files(self, repo_url: str, token: str | None) -> list[str]:
        """Return a flat list of file paths for GitHub, GitLab or Bitbucket."""
        info = self._parse_repo_info_from_url(repo_url)
        host: Literal["github", "gitlab", "bitbucket"] = info["repo_type"]

        if host == "github":
            return self._list_github_blobs(info["owner"], info["repo"], token)
        if host == "gitlab":
            return self._list_gitlab_blobs(info["owner"], info["repo"], token)
        return self._list_bitbucket_blobs(info["owner"], info["repo"], token)

    # ───────────────── GitHub ─────────────────
    def _list_github_blobs(self, owner: str, repo: str, token: str | None) -> list[str]:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            scheme = "Bearer" if token.startswith(("ghp_", "github_pat_")) else "token"
            headers["Authorization"] = f"{scheme} {token}"

        # 1 ) repo → default branch
        r_repo = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=REQ_TO)
        _ensure_ok(r_repo, "repo info")
        branch = r_repo.json().get("default_branch")

        # 2 ) branch → tree SHA
        r_branch = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/branches/{branch}", headers=headers, timeout=REQ_TO
        )
        _ensure_ok(r_branch, "branch info")
        tree_sha = r_branch.json()["commit"]["commit"]["tree"]["sha"]

        # 3 ) recursive tree
        r_tree = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(r_tree, "git tree")
        return [item["path"] for item in r_tree.json()["tree"] if item["type"] == "blob"]

    # ───────────────── GitLab ─────────────────
    def _list_gitlab_blobs(self, owner: str, repo: str, token: str | None) -> list[str]:
        project = urllib.parse.quote_plus(f"{owner}/{repo}")
        headers = {"PRIVATE-TOKEN": token} if token else {}
        r = requests.get(
            f"https://gitlab.com/api/v4/projects/{project}/repository/tree?per_page=100&recursive=true",
            headers=headers,
            timeout=REQ_TO,
        )
        _ensure_ok(r, "gitlab tree")
        return [item["path"] for item in r.json() if item["type"] == "blob"]

    # ──────────────── Bitbucket ───────────────
    def _list_bitbucket_blobs(self, owner: str, repo: str, token: str | None) -> list[str]:
        # 1 ) repo → main branch
        auth_hdr = {"Authorization": f"Bearer {token}"} if token else {}
        r_repo = requests.get(
            f"https://api.bitbucket.org/2.0/repositories/{owner}/{repo}", headers=auth_hdr, timeout=REQ_TO
        )
        _ensure_ok(r_repo, "bitbucket repo")
        branch = r_repo.json().get("mainbranch", {}).get("name", "master")

        # 2 ) src listing (paginated)
        next_url = f"https://api.bitbucket.org/2.0/repositories/{owner}/{repo}/src/{branch}?pagelen=100&format=meta"
        paths: list[str] = []
        while next_url:
            resp = requests.get(next_url, headers=auth_hdr, timeout=REQ_TO)
            _ensure_ok(resp, "bitbucket tree page")
            data = resp.json()
            paths.extend(v["path"] for v in data.get("values", []) if v["type"] == "commit_file")
            next_url = data.get("next")
        return paths

    # ───────────────────────── URL parser ───────────────────────────────
    def _parse_repo_info_from_url(self, url: str) -> dict[str, str]:
        m = GIT_HOST_RE.match(url)
        if not m:
            msg = f"Unsupported repository URL: {url}"
            raise ValueError(msg)
        host_map = {
            "github.com": "github",
            "gitlab.com": "gitlab",
            "bitbucket.org": "bitbucket",
        }
        return {
            "owner": m.group("owner"),
            "repo": m.group("repo"),
            "host": m.group("host"),
            "repo_type": host_map[m.group("host")],
        }


def _ensure_ok(resp: requests.Response, step: str) -> None:
    if resp.status_code != HTTP_OK:
        msg = f"{step}: {resp.status_code} {resp.reason}\n{resp.text[:300]}"
        raise RuntimeError(msg)
