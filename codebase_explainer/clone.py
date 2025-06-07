import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import typer
from rich.console import Console

console = Console()


def _is_git(url: str) -> bool:
    p = urlparse(url)
    return bool(p.scheme and p.netloc and p.path.endswith(".git"))


def _clone(url: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="cbx_"))
    console.print(f"[cyan]Cloning {url} → {tmp}")
    subprocess.run(
        ["git", "clone", "--depth", "1", url, str(tmp)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return tmp


def get_local_repo(repo: str | None, path: Path | None) -> tuple[Path, str]:
    if path:
        return path.resolve(), path.name
    if repo and _is_git(repo):
        p = _clone(repo)
        return p, Path(repo).stem
    msg = "Provide --repo <url> or --path <folder>"
    raise typer.BadParameter(msg)
