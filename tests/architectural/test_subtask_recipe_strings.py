"""Keep code-emitted mark-status recipes at their shared renderer.

Like test_commit_recipe_strings, this belongs in the architectural battery,
not a fast CLI shard. It sees complete literals/f-strings, not commands built
from several separate pieces. Docstrings and command-only telemetry labels
are not recipes. Source ownership is one specific renderer, not a growing
exception list.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural
_SRC = Path(__file__).resolve().parents[2] / "src"
_OWNER = "specify_cli/core/subtask_recipe.py"
_PREFIX = "spec-kitty agent tasks mark-status"


def _recipe_lines(source: str) -> set[int]:
    tree = ast.parse(source)
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, holders) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)
    }
    hits: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            text = "".join(part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}" for part in node.values)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            text = node.value
        else:
            continue
        if _PREFIX in text and "--status" in text:
            hits.add(node.lineno)
    return hits


def test_only_the_renderer_builds_the_recipe_text() -> None:
    files = list(_SRC.rglob("*.py"))
    assert len(files) > 100, f"source census is vacuous under {_SRC}"
    offenders = [
        f"{path.relative_to(_SRC).as_posix()}:{line}"
        for path in files
        if path.relative_to(_SRC).as_posix() != _OWNER
        for line in _recipe_lines(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"hand-formatted mark-status recipes outside the renderer: {offenders}"


@pytest.mark.parametrize(
    ("source", "is_recipe"),
    [
        ('print("spec-kitty agent tasks mark-status T001 --status done")', True),
        ('print(f"spec-kitty agent tasks mark-status {ids} --status done")', True),
        ('label = "spec-kitty agent tasks mark-status"', False),
        ('"""Example: spec-kitty agent tasks mark-status T001 --status done"""', False),
    ],
)
def test_classifier_distinguishes_printed_recipes_from_labels_and_docstrings(source: str, is_recipe: bool) -> None:
    """Exercise the actual detector: an always-empty or over-broad scan must fail."""
    assert bool(_recipe_lines(source)) is is_recipe
