from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from pathlib import Path

console = Console()
AnalyserT = None

# Attempt DeepWiki-Open first
try:
    from deepwiki_open.analyser import Analyser as AnalyserT  # type: ignore
except ImportError:
    try:
        from deepwiki_open.backend.analyser import Analyser as AnalyserT  # alt path
    except ImportError:
        console.print("[yellow]DeepWiki-Open not importable — falling back to pure AST[/]")


def _fallback_ast(root: Path, verbose: bool = False) -> tuple[dict[str, list[str]], dict[str, str]]:
    mods: dict[str, list[str]] = {}
    inh: dict[str, str] = {}
    for py in root.rglob("*.py"):
        if py.parts[-1].startswith("__init__"):
            continue
        rel = str(py.relative_to(root))
        mods.setdefault(rel, [])
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for alias in n.names:
                    mods[rel].append(alias.name)
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods[rel].append(n.module)
            elif isinstance(n, ast.ClassDef) and n.bases:
                child = f"{rel}:{n.name}"
                base = _base_name(n.bases[0])
                inh[child] = base
        if verbose:
            console.print(f"[grey58]Parsed {rel}")
    return mods, inh


def _base_name(base):
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return repr(base)


def parse_codebase(root: Path, verbose: bool = False):
    if AnalyserT is None:
        return _fallback_ast(root, verbose)

    try:
        analyser = AnalyserT(project_dir=str(root), include_tests=False)
        data = analyser.run()  # returns dict with 'modules' & 'classes'
        modules = {m["name"]: m.get("imports", []) for m in data.get("modules", [])}
        classes = {f"{c['module']}:{c['name']}": c["base"] for c in data.get("classes", []) if c.get("base")}
        return modules, classes
    except Exception as exc:
        console.print(f"[yellow]DeepWiki analyser error: {exc} → using AST[/]")
        return _fallback_ast(root, verbose)
