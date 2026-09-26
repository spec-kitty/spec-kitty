"""Architectural test: every __deprecated__ = True module must be in the shim registry (FR-010)."""
from __future__ import annotations

import ast
from pathlib import Path

from ruamel.yaml import YAML

import pytest

from tests.architectural._ast_scan import UnparseableSourceError, parse_file

# ``docs_scoped``: reads ``docs/migrations/shim-registry.yaml`` as its expected
# set, so a docs-only PR editing that registry could newly-red it — it MUST run
# on the arch pole's docs-only trim.
pytestmark = [pytest.mark.architectural, pytest.mark.docs_scoped]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_REGISTRY_PATH = _REPO_ROOT / "docs" / "migrations" / "shim-registry.yaml"


def _scan_deprecated_modules(src_root: Path) -> set[str]:
    """Walk src_root for .py files that carry __deprecated__ = True (assignment or annotation)."""
    found: set[str] = set()
    for py_file in src_root.rglob("*.py"):
        tree = parse_file(py_file)
        for node in ast.walk(tree):
            if _is_deprecated_assignment(node):
                found.add(str(py_file))
                break
    return found


def _is_deprecated_assignment(node: ast.AST) -> bool:
    if isinstance(node, ast.Assign):
        return any(
            isinstance(t, ast.Name) and t.id == "__deprecated__"
            for t in node.targets
        ) and isinstance(node.value, ast.Constant) and node.value.value is True
    if isinstance(node, ast.AnnAssign):
        return (
            isinstance(node.target, ast.Name)
            and node.target.id == "__deprecated__"
            and isinstance(node.value, ast.Constant)
            and node.value.value is True
        )
    return False


def _load_registry_paths() -> set[str]:
    yaml = YAML(typ="safe")
    with _REGISTRY_PATH.open() as fp:
        data = yaml.load(fp)
    paths: set[str] = set()
    for entry in data.get("shims", []):
        lp: str = entry["legacy_path"]
        parts = lp.split(".")
        base = _REPO_ROOT / "src" / Path(*parts)
        paths.add(str(base.with_suffix(".py")))
        paths.add(str(base / "__init__.py"))
    return paths


class TestShimScanner:
    def test_scanner_root_includes_top_level_modules(self) -> None:
        assert _SRC_ROOT == _REPO_ROOT / "src"

    def test_zero_unregistered_shims_in_src(self) -> None:
        deprecated_modules = _scan_deprecated_modules(_SRC_ROOT)
        registry_paths = _load_registry_paths()

        unregistered = deprecated_modules - registry_paths
        assert not unregistered, (
            "Found __deprecated__ = True modules not in shim-registry.yaml:\n"
            + "\n".join(f"  {p}" for p in sorted(unregistered))
        )

    def test_scanner_detects_simple_assignment(self, tmp_path: Path) -> None:
        shim = tmp_path / "my_shim.py"
        shim.write_text("__deprecated__ = True\n")
        found = _scan_deprecated_modules(tmp_path)
        assert str(shim) in found

    def test_scanner_detects_annotated_assignment(self, tmp_path: Path) -> None:
        shim = tmp_path / "annotated_shim.py"
        shim.write_text("__deprecated__: bool = True\n")
        found = _scan_deprecated_modules(tmp_path)
        assert str(shim) in found

    def test_scanner_ignores_false_assignment(self, tmp_path: Path) -> None:
        non_shim = tmp_path / "not_shim.py"
        non_shim.write_text("__deprecated__ = False\n")
        found = _scan_deprecated_modules(tmp_path)
        assert not found

    def test_scanner_ignores_comment_occurrence(self, tmp_path: Path) -> None:
        comment_file = tmp_path / "comment_only.py"
        comment_file.write_text("# __deprecated__ = True at mission start\n")
        found = _scan_deprecated_modules(tmp_path)
        assert not found

    def test_scanner_fails_closed_on_syntax_error(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def (: pass\n")
        with pytest.raises(UnparseableSourceError, match="broken.py"):
            _scan_deprecated_modules(tmp_path)
