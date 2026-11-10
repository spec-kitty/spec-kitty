"""Structural gates for the split ``consolidation/reconciliation*.py`` family.

Every module stays within the size limit, no split module imports the facade
(the split is acyclic), and no body is defined in two split modules.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSOLIDATION = _REPO_ROOT / "src" / "specify_cli" / "consolidation"
_FACADE = _CONSOLIDATION / "reconciliation.py"
_MODULES = sorted(_CONSOLIDATION.glob("reconciliation*.py"))
_SPLIT_MODULES = [path for path in _MODULES if path != _FACADE]
_FACADE_MODULE = "specify_cli.consolidation.reconciliation"
_MAX_MODULE_LINES = 1200


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def _top_level_definitions(path: Path) -> list[str]:
    return [node.name for node in _tree(path).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]


def _imports_the_facade(path: Path) -> list[str]:
    """Every import in *path*, function-local ones included, that reaches the facade."""
    hits: list[str] = []
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module == _FACADE_MODULE:
            hits.append(f"line {node.lineno}: from {node.module} import ...")
        elif node.module == "specify_cli.consolidation" and any(alias.name == "reconciliation" for alias in node.names):
            hits.append(f"line {node.lineno}: from specify_cli.consolidation import reconciliation")
    return hits


@pytest.mark.parametrize("path", _MODULES, ids=lambda path: path.name)
def test_every_reconciliation_module_is_at_most_1200_lines(path: Path) -> None:
    length = _line_count(path)
    assert length <= _MAX_MODULE_LINES, f"{path.name} is {length} lines (limit {_MAX_MODULE_LINES})"


def test_split_modules_never_import_the_facade() -> None:
    offenders = {path.name: hits for path in _SPLIT_MODULES if (hits := _imports_the_facade(path))}
    assert not offenders, f"a split module imports the facade (a cycle waiting to happen): {offenders}"


def test_facade_import_scan_catches_a_facade_import(tmp_path: Path) -> None:
    """Control: the scan the gate above relies on can fail, function-local imports included."""
    sample = tmp_path / "sample.py"
    sample.write_text(
        "def f():\n    from specify_cli.consolidation.reconciliation import x\n    return x\nfrom specify_cli.consolidation import reconciliation\n",
        encoding="utf-8",
    )
    assert len(_imports_the_facade(sample)) == 2


def test_no_top_level_name_is_defined_in_two_split_modules() -> None:
    owners: dict[str, list[str]] = {}
    for path in _SPLIT_MODULES:
        for name in _top_level_definitions(path):
            owners.setdefault(name, []).append(path.name)
    duplicates = {name: homes for name, homes in owners.items() if len(homes) > 1}
    assert not duplicates, f"a body exists in two split modules: {duplicates}"
