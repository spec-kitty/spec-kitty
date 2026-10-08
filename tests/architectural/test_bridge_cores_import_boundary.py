"""Import-boundary gate for ``runtime_bridge_cores.py``'s zero-dependency-leaf
invariant (WP04, C-007, IC-08).

``runtime_bridge_cores.py``'s own module docstring declares it the bottom of
the ``runtime_bridge`` decomposition's import DAG: it may import stdlib,
``Lane``/decision types (``runtime.next.decision``), and nothing else — in
particular never ``runtime_bridge_io`` / ``runtime_bridge_engine`` /
``runtime_bridge_composition`` / ``runtime_bridge_identity``, and never a
top-level edge back to the thin residual ``runtime_bridge``. Nothing today
pins that invariant by construction; a future edit (this mission's own WP05
included) could add a convenient cross-package import and nothing would
notice.

Mirrors the AST-walk pattern of ``test_kernel_no_charter_offering_import.py`` /
``test_charter_no_specify_cli_import.py`` / ``test_clock_import_ban.py``: it
walks the FULL AST (``ast.walk``) so an in-function or in-``try`` import is
caught, not merely a module-level ``import`` statement, and it parses the
real, live file path -- never a copy -- so the gate tracks the module as it
actually ships.

Scope of the claim this gate proves: zero non-stdlib import edges out of
``src/runtime/next/runtime_bridge_cores.py`` other than ``runtime.next.decision``
(or one of its submodules). Stdlib membership is decided by
``sys.stdlib_module_names`` (Python 3.11+, this repo's floor per the charter's
Python 3.11+ requirement) -- no hand-maintained stdlib allowlist to go stale.
This does not prove the absence of runtime coupling by other indirection
(``importlib``, ``__import__``, string-supplied module names) -- same
out-of-scope boundary the sibling gates in this directory already carry.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_SRC = Path(__file__).resolve().parents[2] / "src"
_TARGET = _SRC / "runtime" / "next" / "runtime_bridge_cores.py"

#: The one non-stdlib package ``runtime_bridge_cores.py`` is allowed to
#: import: ``runtime.next.decision`` itself, or any of its submodules.
_ALLOWED_NON_STDLIB_ROOT = "runtime.next.decision"

#: The module's own package, used to resolve relative (``from . import x``)
#: imports to an absolute dotted path before the stdlib/allowlist check.
_TARGET_PACKAGE = "runtime.next"


def _is_stdlib_module(dotted_name: str) -> bool:
    """True when ``dotted_name``'s top-level segment is a stdlib module."""
    root = dotted_name.split(".", 1)[0]
    return root in sys.stdlib_module_names


def _is_allowed_non_stdlib(dotted_name: str) -> bool:
    """True when ``dotted_name`` is ``runtime.next.decision`` or a submodule of it."""
    return dotted_name == _ALLOWED_NON_STDLIB_ROOT or dotted_name.startswith(f"{_ALLOWED_NON_STDLIB_ROOT}.")


def _resolve_relative_base(level: int, *, package: str = _TARGET_PACKAGE) -> str:
    """Resolve a relative ``ImportFrom`` node's BASE package given the importing package.

    Mirrors Python's own relative-import resolution: ``level=1`` (``from . import x``)
    resolves within ``package`` itself; each additional level strips one trailing
    package segment.
    """
    parts = package.split(".")
    # level=1 means "this package" (no segments stripped); level=2 strips one, etc.
    strip = level - 1
    base_parts = parts[: len(parts) - strip] if strip > 0 else parts
    return ".".join(base_parts)


def _resolve_import_from_targets(node: ast.ImportFrom, *, package: str = _TARGET_PACKAGE) -> list[str]:
    """Return every dotted module target an ``ImportFrom`` node resolves to.

    ``from pkg.mod import a, b`` yields one target (``pkg.mod`` -- ``a``/``b`` are
    attributes, not submodules). ``from . import a, b`` (no ``module``) yields ONE
    target PER alias (``a``/``b`` ARE submodules there) -- the shape a naive
    "just check ``node.module``" resolver misses.
    """
    if not node.level:
        return [node.module] if node.module else []
    base = _resolve_relative_base(node.level, package=package)
    if node.module:
        return [f"{base}.{node.module}" if base else node.module]
    return [f"{base}.{alias.name}" if base else alias.name for alias in node.names]


def collect_non_stdlib_imports(tree: ast.AST, *, package: str = _TARGET_PACKAGE) -> list[tuple[str, int]]:
    """Return ``(dotted_module, lineno)`` for every non-stdlib import edge in ``tree``.

    Full-AST walk (``ast.walk``), so an in-function or in-``try`` import is
    caught, not merely a module-level ``import`` statement.
    """
    violations: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_stdlib_module(alias.name):
                    violations.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            for dotted in _resolve_import_from_targets(node, package=package):
                if dotted and not _is_stdlib_module(dotted):
                    violations.append((dotted, node.lineno))
    return violations


def collect_disallowed_imports(tree: ast.AST, *, package: str = _TARGET_PACKAGE) -> list[tuple[str, int]]:
    """Non-stdlib imports that are ALSO not the one sanctioned ``runtime.next.decision`` edge."""
    return [
        (module, lineno)
        for module, lineno in collect_non_stdlib_imports(tree, package=package)
        if not _is_allowed_non_stdlib(module)
    ]


def test_target_file_exists_at_its_documented_path() -> None:
    """Sanity floor: the gate must be pointed at the real, live module -- not a copy.

    A detector silently parsing a missing/renamed file would vacuously pass
    every assertion below; this guards against that.
    """
    assert _TARGET.is_file(), f"runtime_bridge_cores.py not found at the expected live path: {_TARGET}"


def test_bridge_cores_imports_only_stdlib_and_decision() -> None:
    """C-007/IC-08: the shipped ``runtime_bridge_cores.py`` imports nothing but
    stdlib + ``runtime.next.decision`` (or a submodule of it).

    Parses the REAL file at its live source path (never a copy/mock), so the
    gate tracks the module exactly as it ships and as every other WP touching
    it (this mission's WP05 included) will find it.
    """
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"), filename=str(_TARGET))

    violations = collect_disallowed_imports(tree)

    assert violations == [], (
        "runtime_bridge_cores.py declares itself a stdlib-only zero-dependency "
        "leaf (module docstring, C-007) that may import nothing but stdlib and "
        "runtime.next.decision. Disallowed imports found:\n"
        + "\n".join(f"  line {lineno}: {module}" for module, lineno in violations)
    )


def test_planted_cross_package_import_is_flagged(tmp_path: Path) -> None:
    """Non-vacuity: a synthetic non-stdlib, non-``runtime.next.decision`` import
    inserted into a scratch copy DOES fail this detector (WP04 Test Strategy).

    Proves the gate is load-bearing without ever mutating the real, committed
    ``runtime_bridge_cores.py``.
    """
    offender = tmp_path / "offender.py"
    offender.write_text(
        "from __future__ import annotations\n"
        "import re\n"
        "from runtime.next.decision import Decision\n"
        "from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot\n",
        encoding="utf-8",
    )
    tree = ast.parse(offender.read_text(encoding="utf-8"), filename=str(offender))

    violations = collect_disallowed_imports(tree)

    assert violations == [("runtime.next.runtime_bridge_io", 4)]


def test_planted_bare_import_of_forbidden_package_is_flagged(tmp_path: Path) -> None:
    """A bare ``import specify_cli.x`` (not only ``from ... import ...``) is also caught."""
    offender = tmp_path / "offender.py"
    offender.write_text("import specify_cli.requirement_mapping\n", encoding="utf-8")
    tree = ast.parse(offender.read_text(encoding="utf-8"), filename=str(offender))

    violations = collect_disallowed_imports(tree)

    assert violations == [("specify_cli.requirement_mapping", 1)]


def test_in_function_import_is_caught(tmp_path: Path) -> None:
    """Full-AST walk (not module-level-only): an in-function import is still caught."""
    offender = tmp_path / "offender.py"
    offender.write_text(
        "def helper():\n    import specify_cli.foo\n    return specify_cli.foo\n",
        encoding="utf-8",
    )
    tree = ast.parse(offender.read_text(encoding="utf-8"), filename=str(offender))

    violations = collect_disallowed_imports(tree)

    assert violations == [("specify_cli.foo", 2)]


@pytest.mark.parametrize(
    "source",
    [
        "import re\n",
        "from collections.abc import Callable, Mapping\n",
        "from dataclasses import dataclass, field\n",
        "from typing import Any, Protocol\n",
        "from __future__ import annotations\n",
        "from runtime.next.decision import Decision, DecisionKind, InvalidStepDecision\n",
        "from runtime.next.decision.sub import Thing\n",
        "import runtime.next.decision\n",
    ],
)
def test_stdlib_and_decision_imports_are_never_flagged(tmp_path: Path, source: str) -> None:
    """Every shape ``runtime_bridge_cores.py`` currently uses (plus a hypothetical
    ``runtime.next.decision`` submodule import) stays clean -- pins the negative space."""
    offender = tmp_path / "clean.py"
    offender.write_text(source, encoding="utf-8")
    tree = ast.parse(offender.read_text(encoding="utf-8"), filename=str(offender))

    violations = collect_disallowed_imports(tree)

    assert violations == []


def test_relative_import_within_the_module_own_package_resolves_correctly(tmp_path: Path) -> None:
    """``from . import x`` inside ``runtime.next`` resolves to ``runtime.next.x``,
    so a relative import of the sanctioned ``decision`` sibling is allowed,
    while a relative import of any other sibling (e.g. ``runtime_bridge_io``)
    is flagged -- relative-import syntax is not a bypass for the boundary.
    """
    allowed = tmp_path / "allowed.py"
    allowed.write_text("from . import decision\n", encoding="utf-8")
    tree_allowed = ast.parse(allowed.read_text(encoding="utf-8"), filename=str(allowed))
    assert collect_disallowed_imports(tree_allowed) == []

    disallowed = tmp_path / "disallowed.py"
    disallowed.write_text("from . import runtime_bridge_io\n", encoding="utf-8")
    tree_disallowed = ast.parse(disallowed.read_text(encoding="utf-8"), filename=str(disallowed))
    assert collect_disallowed_imports(tree_disallowed) == [("runtime.next.runtime_bridge_io", 1)]
