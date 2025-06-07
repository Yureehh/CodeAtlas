import signal
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress

from .clone import get_local_repo
from .graph import build_graphs
from .parse import parse_codebase
from .visualize import render_graphs

console = Console()
app = typer.Typer(add_completion=False, rich_markup_mode="rich")


def _sigint_handler(_sig, _frame):
    console.print("\n[red]Interrupted — exiting.[/]")
    sys.exit(130)


signal.signal(signal.SIGINT, _sigint_handler)


@app.command()
def main(
    repo: str = typer.Option(None, "--repo", "-r", help="Public Git URL to analyse"),
    path: Path = typer.Option(None, "--path", "-p", dir_okay=True, exists=True, help="Local folder"),
    output: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination folder (default: ./output/<project>)",
    ),
    fmt: str = typer.Option(
        "mermaid",
        "--format",
        "-f",
        help="Diagram backend: mermaid | svg",
        show_default=True,
        case_sensitive=False,
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Entry-point – drive clone → parse → graph → visualize."""
    target, project = get_local_repo(repo, path)
    output = output or Path("output") / project
    output.mkdir(parents=True, exist_ok=True)

    console.rule(f"[bold blue]Codebase Explainer – {project}")

    with Progress() as progress:
        t1 = progress.add_task("Parsing AST / DeepWiki…", start=False)
        t2 = progress.add_task("Building graphs…", start=False)
        t3 = progress.add_task("Rendering diagrams…", start=False)

        progress.start_task(t1)
        mods, classes = parse_codebase(target, verbose=verbose)
        progress.update(t1, completed=100)

        progress.start_task(t2)
        graphs = build_graphs(mods, classes)
        progress.update(t2, completed=100)

        progress.start_task(t3)
        render_graphs(graphs, output, fmt=fmt)
        progress.update(t3, completed=100)

    console.print(f"[green]✔ All artefacts in {output}[/]")
