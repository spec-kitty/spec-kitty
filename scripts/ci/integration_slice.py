#!/usr/bin/env python3
"""Nightly home for integration-marked tests no other lane selects.

``module-tests.yml`` runs ``pytest -m "not performance and not stress"`` on a
file list built at runtime (``shard_tests.txt``). The static gate model sees
no paths on that command and therefore treats the marker as covering all of
``tests/``. Rootless trees (``tests/characterization`` and the other
directories absent from ``.github/ci-module-registry.yml`` ``test_dirs``) are
not on that list. The interpreter shards do list many of those directories,
but only under ``-m "fast or unit"``, so a test marked ``integration`` and
not ``fast`` or ``unit`` is collected by nothing. This module is the list the
nightly ``integration-slice`` job runs, and the dead-test / dead-code checkup
that fails when that list or its own helpers go unwired.

Already-run markers stay off the slice on purpose:

- ``fast`` / ``unit`` — interpreter shards (their completeness guard is the
  union of ``-m "fast or unit"``).
- ``performance`` / ``stress`` / ``e2e`` — the nightly jobs of those names.
- ``windows_ci`` — ``ci-windows.yml``.
- ``timing`` / ``quarantine`` / ``live_adapter`` — their own contracts
  (no live CI job, env-gated, or a real network call). They are not
  silently treated as covered by this slice.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

import yaml

SLICE_MARKER_EXPR = (
    "integration and not e2e and not fast and not live_adapter and not performance and not quarantine and not stress and not timing and not unit and not windows_ci"
)
DIRECTORY_LANE_ROOTS: tuple[str, ...] = (
    "tests/architectural",
    "tests/integration",
    "tests/next",
    "tests/specify_cli",
)
ALREADY_RUN_MARKERS: frozenset[str] = frozenset(
    {
        "e2e",
        "fast",
        "live_adapter",
        "performance",
        "quarantine",
        "stress",
        "timing",
        "unit",
        "windows_ci",
    }
)
_REGISTRY_RELATIVE = Path(".github") / "ci-module-registry.yml"
_PYTEST_MARK = "integration"


class IntegrationSliceError(RuntimeError):
    """The slice cannot be computed. The nightly job must fail closed."""


def _mark_name(node: ast.AST) -> str | None:
    target = node.func if isinstance(node, ast.Call) else node
    if not isinstance(target, ast.Attribute):
        return None
    mark = target.value
    if not isinstance(mark, ast.Attribute) or mark.attr != "mark":
        return None
    root = mark.value
    if isinstance(root, ast.Name) and root.id == "pytest":
        return target.attr
    return None


def _marks_of(value: ast.AST) -> set[str]:
    elements: Iterable[ast.AST]
    elements = value.elts if isinstance(value, ast.List | ast.Tuple) else (value,)
    return {name for element in elements if (name := _mark_name(element)) is not None}


def _assigned_pytestmark(node: ast.AST) -> set[str]:
    if not isinstance(node, ast.Assign):
        return set()
    if not any(isinstance(target, ast.Name) and target.id == "pytestmark" for target in node.targets):
        return set()
    return _marks_of(node.value)


def _decorator_marks(node: ast.AST) -> set[str]:
    decorators = getattr(node, "decorator_list", ())
    return {name for decorator in decorators if (name := _mark_name(decorator)) is not None}


def _module_marks(tree: ast.Module) -> set[str]:
    marks: set[str] = set()
    for node in getattr(tree, "body", ()):
        marks |= _assigned_pytestmark(node)
    return marks


def _item_mark_sets(tree: ast.Module) -> list[set[str]]:
    """Effective marker set of every test function, including class and module marks."""
    module_marks = _module_marks(tree)
    items: list[set[str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name.startswith("test_"):
            items.append(module_marks | _decorator_marks(node))
            continue
        if not isinstance(node, ast.ClassDef) or not node.name.startswith("Test"):
            continue
        class_marks = module_marks | _decorator_marks(node) | _class_pytestmark(node)
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) and child.name.startswith("test_"):
                items.append(class_marks | _decorator_marks(child))
    return items


def _class_pytestmark(node: ast.ClassDef) -> set[str]:
    marks: set[str] = set()
    for child in node.body:
        marks |= _assigned_pytestmark(child)
    return marks


def _stranded_item(marks: set[str]) -> bool:
    return _PYTEST_MARK in marks and marks.isdisjoint(ALREADY_RUN_MARKERS)


def _is_test_module(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _under_prefix(relative: str, prefix: str) -> bool:
    return relative == prefix or relative.startswith(prefix.rstrip("/") + "/")


def _registry_test_dirs(repo: Path) -> tuple[str, ...]:
    registry_path = repo / _REGISTRY_RELATIVE
    try:
        loaded = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IntegrationSliceError(f"cannot read {registry_path}") from exc
    except yaml.YAMLError as exc:
        raise IntegrationSliceError(f"cannot parse {registry_path}") from exc
    if not isinstance(loaded, dict):
        raise IntegrationSliceError(f"{registry_path} is not a mapping")
    modules = loaded.get("modules")
    if not isinstance(modules, list):
        raise IntegrationSliceError(f"{registry_path} has no modules list")
    directories: list[str] = []
    for row in modules:
        if not isinstance(row, dict):
            continue
        test_dirs = row.get("test_dirs") or []
        if not isinstance(test_dirs, list):
            raise IntegrationSliceError(f"{registry_path} test_dirs is not a list")
        for entry in test_dirs:
            if not isinstance(entry, str) or not entry:
                raise IntegrationSliceError(f"{registry_path} has a non-string test_dirs entry")
            directories.append(entry.rstrip("/"))
    return tuple(directories)


def covered_prefixes(repo: Path) -> tuple[str, ...]:
    """Directory lanes plus every registry ``test_dirs`` root.

    Those homes already select an ``integration``-only test: the directory
    lanes run by path, and the module matrix marker keeps ``integration``.
    """
    return tuple(sorted({*DIRECTORY_LANE_ROOTS, *_registry_test_dirs(repo)}))


def _has_stranded_item(path: Path) -> bool:
    try:
        source = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IntegrationSliceError(f"cannot read {path}") from exc
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        raise IntegrationSliceError(f"cannot parse {path}") from exc
    return any(_stranded_item(marks) for marks in _item_mark_sets(tree))


def stranded_integration_files(
    repo: Path,
    *,
    covered: Sequence[str] | None = None,
) -> list[str]:
    """Repo-relative test modules whose ``integration`` items no other lane runs."""
    prefixes = tuple(covered) if covered is not None else covered_prefixes(repo)
    tests_root = repo / "tests"
    if not tests_root.is_dir():
        raise IntegrationSliceError(f"{tests_root} is not a directory")
    stranded: list[str] = []
    for path in sorted(tests_root.rglob("*.py")):
        if not _is_test_module(path):
            continue
        relative = path.relative_to(repo).as_posix()
        if any(_under_prefix(relative, prefix) for prefix in prefixes):
            continue
        if _has_stranded_item(path):
            stranded.append(relative)
    return stranded


def unreferenced_public_functions(module: Path, corpus: Sequence[Path]) -> list[str]:
    """Public functions in ``module`` that nothing in ``corpus`` names.

    Charter review rule: no dead code. A function is live when its name
    appears again in its own module (a call, not only ``def``) or in any
    other corpus file (the workflow, the tests). The defining file is
    compared with ``\\bname\\b`` so a longer identifier is not a hit.
    """
    try:
        source = module.read_text(encoding="utf-8")
    except OSError as exc:
        raise IntegrationSliceError(f"cannot read {module}") from exc
    try:
        tree = ast.parse(source, filename=str(module))
    except SyntaxError as exc:
        raise IntegrationSliceError(f"cannot parse {module}") from exc
    names = [node.name for node in tree.body if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_")]
    others: list[str] = []
    module_resolved = module.resolve()
    for path in corpus:
        if path.resolve() == module_resolved:
            continue
        try:
            others.append(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise IntegrationSliceError(f"cannot read {path}") from exc
    dead: list[str] = []
    for name in names:
        pattern = re.compile(rf"\b{re.escape(name)}\b")
        referenced_inside = len(pattern.findall(source)) > 1
        referenced_outside = any(pattern.search(text) for text in others)
        if not referenced_inside and not referenced_outside:
            dead.append(name)
    return dead


def main(argv: Sequence[str] | None = None) -> int:
    """Print stranded integration modules, one repo-relative path per line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        files = stranded_integration_files(args.root)
    except IntegrationSliceError as exc:
        print(f"integration-slice: {exc}", file=sys.stderr)
        return 1
    for relative in files:
        print(relative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
