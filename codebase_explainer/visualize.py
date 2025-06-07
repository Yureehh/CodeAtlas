import shutil
import subprocess
from pathlib import Path

import networkx as nx
from rich.console import Console

console = Console()


def _to_mermaid(g: nx.DiGraph) -> str:
    lines = ["```mermaid", "graph LR;"]
    lines += [f'    "{s}" --> "{t}"' for s, t in g.edges()]
    lines.append("```")
    return "\n".join(lines)


def _to_dot(g: nx.DiGraph) -> str:
    lines = ["digraph G {"]
    lines += [f'    "{n}";' for n in g.nodes()]
    lines += [f'    "{s}" -> "{t}";' for s, t in g.edges()]
    lines.append("}")
    return "\n".join(lines)


def _detect_graphviz() -> bool:
    return shutil.which("dot") is not None


def render_graphs(graphs, dest: Path, fmt: str = "mermaid"):
    module_g, class_g = graphs
    dest.mkdir(parents=True, exist_ok=True)

    if fmt.lower() == "mermaid":
        (dest / "module_graph.md").write_text(_to_mermaid(module_g), encoding="utf-8")
        (dest / "class_hierarchy.md").write_text(_to_mermaid(class_g), encoding="utf-8")
    elif fmt.lower() == "svg":
        if not _detect_graphviz():
            console.print("[red]Graphviz 'dot' not found — cannot render SVGs[/]")
            return
        for name, g in [("module_graph", module_g), ("class_hierarchy", class_g)]:
            (dest / f"{name}.dot").write_text(_to_dot(g), encoding="utf-8")
            subprocess.run(
                ["dot", "-Tsvg", str(dest / f"{name}.dot"), "-o", str(dest / f"{name}.svg")],
                check=True,
            )
    else:
        msg = "format must be mermaid or svg"
        raise ValueError(msg)
    console.print("[green]Diagrams generated successfully.[/]")
