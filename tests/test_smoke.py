from pathlib import Path

from codebase_explainer.parse import _fallback_ast


def test_basic_ast():
    mods, classes = _fallback_ast(Path(__file__).parent, verbose=False)
    assert isinstance(mods, dict)
    assert isinstance(classes, dict)
