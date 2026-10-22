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
    ``from pkg.mod import _private as public_name`` is caught. Docstrings are
    not parsed as imports. There is no allowlist.
    """
    offenders: list[str] = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if _is_private_module(node.module):
                    offenders.append(f"{path}:{node.lineno} -> {node.module}")
                elif node.module.split(".")[0] in _PACKAGES:
                    offenders.extend(f"{path}:{node.lineno} -> {node.module}.{alias.name}" for alias in node.names if _is_private_segment(alias.name))
            elif isinstance(node, ast.Import):
                offenders.extend(f"{path}:{node.lineno} -> {alias.name}" for alias in node.names if _is_private_module(alias.name))
    return offenders


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
        "from spec_kitty_events import __version__\n",
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
        )
    ):
        fault = tmp_path / f"fault{index}.py"
        fault.write_text(source, encoding="utf-8")
        assert _private_imports([fault]) == [f"{fault}:1 -> {expected}"]
