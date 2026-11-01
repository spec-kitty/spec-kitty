"""No docs tooling default reads a Mission-scoped occurrence map (#2358, #6927).

The docs scripts used to default to a closed Mission's
``kitty-specs/<mission>/occurrence_map.yaml``, which left the next docs move with
no standing home. The standing moves ledger ``site/moves.yaml`` replaced that
binding (ADR ``2026-10-31-1`` D-5, D-6). This gate keeps it closed: no default of
any ``scripts/docs/*.py`` module may name a path under a Mission directory or a
Mission's occurrence map.

A "default" here is a module-level assignment value, an argparse ``default=``
and an ``os.environ.get(..., <fallback>)`` fallback. Docstrings, comments and
the bare ``kitty-specs/`` exclude prefix are not defaults of that kind.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS_SCRIPTS = _REPO_ROOT / "scripts" / "docs"
# A concrete Mission directory, not a glob such as ``kitty-specs/**``.
_MISSION_DIR = re.compile(r"kitty-specs/[^/*]+/")


def _strings(node: ast.AST) -> list[str]:
    return [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]


def _names_mission_map(node: ast.AST) -> bool:
    strings = _strings(node)
    if any(_MISSION_DIR.search(value) for value in strings):
        return True
    # A path joined from parts: ``ROOT / "kitty-specs" / SLUG / "occurrence_map.yaml"``.
    return "kitty-specs" in strings and any("occurrence_map" in value for value in strings)


def _default_expressions(tree: ast.Module) -> list[ast.AST]:
    found: list[ast.AST] = []
    for stmt in tree.body:
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None:
            found.append(stmt.value)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if name == "add_argument":
            found.extend(kw.value for kw in node.keywords if kw.arg == "default")
        elif name == "get" and len(node.args) == 2 and "environ" in ast.unparse(func):
            found.append(node.args[1])
    return found


def mission_scoped_defaults(source: str) -> list[str]:
    """Defaults in *source* that name a Mission directory or occurrence map."""
    tree = ast.parse(source)
    return [ast.unparse(expr) for expr in _default_expressions(tree) if _names_mission_map(expr)]


def test_no_docs_script_default_names_a_mission_occurrence_map() -> None:
    modules = sorted(_DOCS_SCRIPTS.glob("*.py"))
    assert len(modules) >= 10  # non-vacuous: about 40 modules today
    offenders = {path.name: hits for path in modules if (hits := mission_scoped_defaults(path.read_text(encoding="utf-8")))}
    assert offenders == {}, f"Mission-scoped defaults remain: {offenders}"


@pytest.mark.parametrize(
    "source",
    [
        'DEFAULT = "kitty-specs/some-mission-01ABCDEF/occurrence_map.yaml"\n',
        'SLUG = "m"\nMAP = ROOT / "kitty-specs" / SLUG / "occurrence_map.yaml"\n',
        'import os\nX = os.environ.get("V", "kitty-specs/m-01AB/occurrence_map.yaml")\n',
        'p.add_argument("--map", default="kitty-specs/m-01AB/occurrence_map.yaml")\n',
    ],
)
def test_collector_catches_each_default_shape(source: str) -> None:
    """Positive control: every shape the gate claims to cover is caught."""
    assert mission_scoped_defaults(source)


def test_collector_ignores_docstrings_and_the_exclude_prefix() -> None:
    source = '"""Mentions kitty-specs/m-01AB/occurrence_map.yaml in prose."""\nEXCLUDE = ("kitty-specs/", "docs/adr/")\nROOT = REPO / "kitty-specs"\n'
    assert mission_scoped_defaults(source) == []


def test_tooling_defaults_point_at_the_standing_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    from scripts.docs import bulk_ref_rewrite, rename_reconcile

    # The rewriter's default honours an env override; judge the built-in default.
    monkeypatch.delenv("SPEC_KITTY_OCCURRENCE_MAP", raising=False)
    importlib.reload(bulk_ref_rewrite)
    assert rename_reconcile.DEFAULT_MOVES_LEDGER == "site/moves.yaml"
    assert bulk_ref_rewrite.DEFAULT_OCCURRENCE_MAP == "site/moves.yaml"
