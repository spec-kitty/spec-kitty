"""External consumers reach the charter **activation** layer only through its seam.

Companion to :mod:`tests.architectural.test_runtime_charter_doctrine_boundary` (the
offering seam). The offering / activation split (ADR ``2026-10-06-1`` §1) means each
layer is an independently extractable unit behind its *own* module entry-point seam:

* offering seam  -> ``charter.offering.api`` + the ``charter.*`` offering facades
* activation seam -> ``charter.activation.api``

This gate forbids any module under the external scan roots (``src/specify_cli``,
``src/runtime``, ``src/glossary``, ``src/mission_runtime``) from importing a
``charter.activation`` **internal** — i.e. any ``charter.activation`` /
``charter.activation.<submodule>`` name *except* the seam ``charter.activation.api``.
Depending only on the seam lets the activation internals be rewritten or extracted
(even to a separate, non-Python service) without touching any consumer.

Brownfield introduction (#6188 / owner epic #6099): activation was built with "no
eager re-exports — callers import the owning submodule directly" (see
``src/charter/activation/__init__.py``), so the seam starts with a large set of
pre-existing internal reaches. They are frozen as a **shrink-only baseline** in
``charter_activation_boundary_baseline.yaml`` (per-``(file, module)`` pair), priced
debt drained as consumers move onto ``charter.activation.api``:

* a **new** internal reach (current - baseline) **FAILS** the gate (regression — the
  seam must not be bypassed by new code);
* a **drained** reach (baseline - current) **WARNS** (informational), per the
  charter Burn-down Policy (growth fails, shrinkage warns); evict it from the YAML
  to lower the ``_baselines.yaml`` count.

``if TYPE_CHECKING:`` imports are erased at runtime and are **not** reach-throughs,
so they are exempt (identical treatment to the offering seam gate).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from tests.architectural._ast_scan import parse_file

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASELINE_PATH = Path(__file__).parent / "charter_activation_boundary_baseline.yaml"

#: External consumers of the charter layer. The seam must hold for every one of
#: them, not only specify_cli — src/glossary reached charter internals directly
#: before #6188 (see the offering seam gate's scan-root note).
_SCAN_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "specify_cli",
    _REPO_ROOT / "src" / "runtime",
    _REPO_ROOT / "src" / "glossary",
    _REPO_ROOT / "src" / "mission_runtime",
)

#: The seam itself — the one ``charter.activation`` name consumers MAY import.
_SEAM = "charter.activation.api"
_ACTIVATION = "charter.activation"


def _is_activation_internal(name: str | None) -> bool:
    """True for a ``charter.activation`` / ``charter.activation.<x>`` name that is NOT the seam."""
    if not name:
        return False
    if name == _SEAM or name.startswith(_SEAM + "."):
        return False
    return name == _ACTIVATION or name.startswith(_ACTIVATION + ".")


def _internal_paths(node: ast.AST) -> set[str]:
    """Imported ``charter.activation`` internal module paths bound by *node* (seam excluded)."""
    out: set[str] = set()
    if isinstance(node, ast.ImportFrom):
        if node.level == 0 and _is_activation_internal(node.module):
            out.add(node.module or "")
    elif isinstance(node, ast.Import):
        for alias in node.names:
            if _is_activation_internal(alias.name):
                out.add(alias.name)
    return out


def _is_type_checking_guard(test: ast.expr) -> bool:
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


class _ActivationVisitor(ast.NodeVisitor):
    """Collect runtime (non-TYPE_CHECKING) activation-internal import paths.

    Module-level and lazy (function/class body) imports are both reach-throughs and
    are collected together; only ``if TYPE_CHECKING:`` imports are skipped (erased at
    runtime). Mirrors the offering seam gate's parent-tracking descent.
    """

    def __init__(self) -> None:
        self.paths: set[str] = set()
        self._tc_depth = 0

    def _record(self, node: ast.AST) -> None:
        if self._tc_depth:
            return
        self.paths.update(_internal_paths(node))

    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    def visit_If(self, node: ast.If) -> None:
        guarded = _is_type_checking_guard(node.test)
        if guarded:
            self._tc_depth += 1
        for child in node.body:
            self.visit(child)
        if guarded:
            self._tc_depth -= 1
        for child in node.orelse:
            self.visit(child)


def _rel(path: Path) -> str:
    return str(path.relative_to(_REPO_ROOT))


def current_violators() -> set[tuple[str, str]]:
    """Every (relpath, activation-internal module) reach under the scan roots."""
    found: set[tuple[str, str]] = set()
    for root in _SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            # Fail closed on an unparseable file via the canonical scanner helper
            # (tests/architectural/test_scanner_parse_fail_closed.py forbids swallowing
            # SyntaxError — a dropped file could hide a reach-through).
            visitor = _ActivationVisitor()
            visitor.visit(parse_file(path))
            for module in visitor.paths:
                found.add((_rel(path), module))
    return found


def _load_baseline() -> set[tuple[str, str]]:
    raw = yaml.safe_load(_BASELINE_PATH.read_text(encoding="utf-8")) or []
    return {(entry["file"], entry["module"]) for entry in raw}


#: Exposed for ``tests/architectural/test_ratchet_baselines.py`` (its
#: ``_baselines.yaml`` leaf ``test_runtime_charter_activation_boundary.boundary_baseline``
#: records ``len(BASELINE)``; growing the YAML beyond that count fails the meta-test).
BASELINE: frozenset[tuple[str, str]] = frozenset(_load_baseline())


def test_boundary_predicate_has_prohibited_and_compliant_controls() -> None:
    """Non-vacuity: an internal reach is flagged; the seam and TYPE_CHECKING are not."""
    assert _is_activation_internal("charter.activation.compiler")
    assert _is_activation_internal("charter.activation")
    assert not _is_activation_internal("charter.activation.api")
    assert not _is_activation_internal("charter.activation.api.read_mission_type")
    assert not _is_activation_internal("charter.offering.drg.models")

    v = _ActivationVisitor()
    v.visit(ast.parse("from charter.activation.compiler import compile_charter\n"))
    assert v.paths == {"charter.activation.compiler"}

    v = _ActivationVisitor()
    v.visit(ast.parse("if TYPE_CHECKING:\n    from charter.activation.compiler import compile_charter\n"))
    assert v.paths == set()

    v = _ActivationVisitor()
    v.visit(ast.parse("from charter.activation.api import read_mission_type\n"))
    assert v.paths == set()


def test_external_consumers_add_no_new_activation_internal_reach() -> None:
    """A new (file, module) reach into a ``charter.activation`` internal fails the gate.

    Drained reaches (in the baseline but no longer present) only WARN, so the gate
    never blocks progress; evict them from ``charter_activation_boundary_baseline.yaml``
    and lower the ``_baselines.yaml`` count.
    """
    current = current_violators()
    baseline = _load_baseline()

    new = sorted(current - baseline)
    drained = sorted(baseline - current)

    if drained:
        # Shrinkage warns (Burn-down Policy); it never fails the run.
        print(
            "charter.activation seam: these baselined internal reaches are drained — "
            "evict them from charter_activation_boundary_baseline.yaml and lower the "
            "_baselines.yaml count:\n  - " + "\n  - ".join(f"{f} -> {m}" for f, m in drained)
        )

    assert not new, (
        "New reach into a charter.activation INTERNAL from an external consumer. Route\n"
        "the access through the activation seam `charter.activation.api` instead (grow the\n"
        "seam with an identity re-export if the symbol is missing, tabled in\n"
        "tests/architectural/test_charter_activation_api_reexport.py). A lazy import is not\n"
        "exempt. New file/module pairs:\n  - " + "\n  - ".join(f"{f} -> {m}" for f, m in new)
    )


def test_baseline_entries_are_wellformed_and_sorted() -> None:
    """The YAML baseline is a sorted list of ``{file, module}`` activation-internal pairs."""
    raw = yaml.safe_load(_BASELINE_PATH.read_text(encoding="utf-8")) or []
    pairs = [(e["file"], e["module"]) for e in raw]
    assert pairs == sorted(pairs), "keep charter_activation_boundary_baseline.yaml sorted"
    assert len(pairs) == len(set(pairs)), "no duplicate (file, module) pairs"
    for _file, module in pairs:
        assert _is_activation_internal(module), f"{module} is not a charter.activation internal"
