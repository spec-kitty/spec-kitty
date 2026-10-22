"""Keep every production root on the public events/tracker package boundary."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.architectural.test_shared_package_boundary import _PRODUCTION_ROOTS

pytestmark = pytest.mark.architectural

_PACKAGES = ("spec_kitty_events", "spec_kitty_tracker")


def _is_private_segment(segment: str) -> bool:
    """A single leading underscore marks private; dunders (``__version__``) are public."""
    return segment.startswith("_") and not (segment.startswith("__") and segment.endswith("__"))


def _is_private_module(module: str) -> bool:
    """True when *module* is one of the packages or a submodule with a private segment."""
    head, *rest = module.split(".")
    return head in _PACKAGES and any(_is_private_segment(part) for part in rest)


def _private_imports(paths: list[Path]) -> list[str]:
    """Report private events/tracker imports: a private module path or a private imported name.

    The gate checks ``alias.name`` (the name taken from the package), never
    ``asname``, so ``from pkg import public as _local`` stays clean and
    ``from pkg.mod import _private as public_name`` is caught. A private
    attribute read through a name bound from either package
    (``from pkg.conformance import validators; validators._MAP``) is caught
    too. Docstrings are not parsed as imports. There is no allowlist. Known
    limit: a dynamic ``importlib.import_module("pkg._mod")`` is not followed.
    """
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(_private_import_findings(path, tree))
        offenders.extend(_private_attribute_findings(path, tree))
    return offenders


def _private_import_findings(path: Path, tree: ast.Module) -> list[str]:
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if _is_private_module(node.module):
                found.append(f"{path}:{node.lineno} -> {node.module}")
            elif node.module.split(".")[0] in _PACKAGES:
                found.extend(f"{path}:{node.lineno} -> {node.module}.{alias.name}" for alias in node.names if _is_private_segment(alias.name))
        elif isinstance(node, ast.Import):
            found.extend(f"{path}:{node.lineno} -> {alias.name}" for alias in node.names if _is_private_module(alias.name))
    return found


def _package_bound_names(tree: ast.Module) -> dict[str, str]:
    """Local names bound by an import from either package, mapped to their origin."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0 and node.module.split(".")[0] in _PACKAGES:
            bound.update({alias.asname or alias.name: f"{node.module}.{alias.name}" for alias in node.names})
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in _PACKAGES:
                    local = alias.asname or alias.name.split(".")[0]
                    bound[local] = alias.name if alias.asname else local
    return bound


def _private_attribute_findings(path: Path, tree: ast.Module) -> list[str]:
    bound = _package_bound_names(tree)
    return [
        f"{path}:{node.lineno} -> {bound[node.value.id]}.{node.attr}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in bound and _is_private_segment(node.attr)
    ]


def test_cli_never_imports_private_events_or_tracker_names(tmp_path: Path) -> None:
    """Scan every production root and prove the same oracle rejects planted bypasses."""
    corpus = sorted(path for root in _PRODUCTION_ROOTS for path in root.rglob("*.py"))
    assert corpus
    assert _private_imports(corpus) == []

    control = tmp_path / "control.py"
    control.write_text(
        '"""from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL"""\n'
        "from spec_kitty_events import Event as _Event\n"
        "from spec_kitty_events.diary import reduce\n"
        "from spec_kitty_events import __version__\n"
        "from spec_kitty_events.conformance import validators\n"
        "validators.validate_event\n"
        "reduce.__name__\n",
        encoding="utf-8",
    )
    assert _private_imports([control]) == []

    for index, (source, expected) in enumerate(
        (
            ("from spec_kitty_tracker._internal.store import TrackerStore\n", "spec_kitty_tracker._internal.store"),
            (
                "from spec_kitty_events.conformance.validators import _EVENT_TYPE_TO_MODEL\n",
                "spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL",
            ),
            ("from spec_kitty_events.diary import _RUNTIME_SLOTS as slots\n", "spec_kitty_events.diary._RUNTIME_SLOTS"),
            ("import spec_kitty_events._private\n", "spec_kitty_events._private"),
            (
                "from spec_kitty_events.conformance import validators\nvalidators._EVENT_TYPE_TO_MODEL\n",
                "spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL",
            ),
            (
                "import spec_kitty_events.conformance.validators as v\nv._EVENT_TYPE_TO_MODEL\n",
                "spec_kitty_events.conformance.validators._EVENT_TYPE_TO_MODEL",
            ),
        )
    ):
        fault = tmp_path / f"fault{index}.py"
        fault.write_text(source, encoding="utf-8")
        assert [finding.split(" -> ", 1)[1] for finding in _private_imports([fault])] == [expected]
