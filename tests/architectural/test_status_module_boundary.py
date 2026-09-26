"""Architectural boundary tests for the ``specify_cli.status`` facade.

These tests enforce that no module *outside* ``specify_cli.status`` imports
any ``specify_cli.status.*`` submodule directly.  External consumers must go
through the curated public API surface defined by ``specify_cli.status.__all__``.

Rules enforced:
* **SR-1** (pytestarch): regression-lock on the 6 WP03-owned packages
  (agent_utils, lanes, post_merge, missions, merge, next). These are fully
  clean; SR-1 asserts they never reintroduce a static ``specify_cli.status.*``
  submodule import. It is intentionally *scoped to those packages*, not the
  whole tree — the repo-wide gate is SR-2.
* **SR-2** (AST scan): the **repo-wide** gate. No module across all of
  ``src/specify_cli`` and ``src/runtime`` may import any ``specify_cli.status.*``
  submodule (module-level *or* lazy/function-scoped, which pytestarch's
  import-graph analysis may miss), except the explicitly exempted plumbing /
  cycle-breaker files in ``_ALL_EXEMPT_FILES``.
* **SR-3** (injection proof): The AST scanner is not a no-op — it actively
  catches violations.

WP09 widened the enforced scope from WP03's 6-directory regression-lock to ALL
of ``src/specify_cli`` and ``src/runtime`` — but that repo-wide enforcement
lives in **SR-2**, not SR-1. SR-1 remains the focused regression-lock on the 6
already-clean packages.

Exemptions (C-004 plumbing — permanent):
  - ``coordination/status_transition.py``: internal Mission Management plumbing;
    it IS part of the transactional commit pipeline, not an external caller.
  - ``coordination/transaction.py``: BookkeepingTransaction plumbing.

Residual allow-list (post-WP10):
  WP10 routed every prior ROUTE-deferred file onto the ``status`` facade by
  promoting the relevant symbols into ``status/__init__.__all__``
  (lifecycle_events, work_package_lifecycle, reducer.materialize_snapshot,
  doctor.run_doctor, aggregate.InvalidMissionSlug) and refactoring the sync
  SaaS fan-out handler onto facade helpers. Three entries remain:
  - ``workspace/context.py`` — ``status.wp_metadata``
    (cycle-breaker: status/__init__ → .emit → workspace → .context; facade
    is not yet initialized when workspace.context loads at import time —
    permanent).
  - ``upgrade/migrations/m_3_2_9_migrate_lifecycle_envelope.py`` —
    ``status.migrate_lifecycle_envelope`` (WIRE-M2-03, 2026-08-22,
    rework cycle 2 — temporary, needs a follow-up bead). The one symbol
    this file still reaches directly, the ``migrate_lifecycle_envelope``
    function, cannot be promoted onto the facade under its own name: that
    name is identical to its home submodule's filename
    (``status/migrate_lifecycle_envelope.py``), so promoting it would make
    ``from specify_cli.status import migrate_lifecycle_envelope`` resolve
    to the function everywhere — silently breaking the two pre-existing
    tests that already use that exact shape to reach the MODULE via
    Python's implicit submodule-fallback (``tests/status/
    test_migrate_lifecycle_envelope.py``, ``tests/status/
    test_migrate_lifecycle_envelope_node_id_parity.py``). The file's other
    two symbols (``mission_event_log_path``, ``project_event_log_path``)
    ARE routed through the facade — only this one colliding name is
    deferred.
  - ``runtime/next/committed_authority.py`` —
    ``status.uninitialized_hint.feature_event_log_missing_error``
    (convergence port PR #1066, 2026-09-03 — temporary). The verbatim
    upstream pick of the next-committed-state-authority WP01 fail-loud
    gate imports the error-message helper function-level from its home
    submodule; the symbol is not on the ``status`` facade yet (upstream
    has not promoted it either). TODO(triage): promote
    ``feature_event_log_missing_error`` onto ``status/__init__.__all__``
    and migrate this callsite to the facade, then remove this entry —
    tracked with the #1065 manual re-port queue that carries this
    mission's conflicted WP02 wiring.

See also:
  - ``tests/architectural/test_shared_package_boundary.py`` — template / pattern
  - ADR ``docs/adr/3.x/2026-06-03-1-execution-state-domain-model.md``
  - Contract: ``kitty-specs/execution-state-canonical-surface-01KTG6P9/contracts/status_boundary.md``
"""
from __future__ import annotations

import ast
import pathlib
import textwrap
import time
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

# The one status submodule an outside caller MAY import: the enumerated raw
# append door (fsm-write-path-integrity-01M1TZV6 WP03, FR-010). Its importers
# are gated by tests/architectural/test_status_unsafe_allowlist.py, not here.
_UNSAFE_DOOR_NAME = "_unsafe"
_UNSAFE_DOOR_MODULE = f"specify_cli.status.{_UNSAFE_DOOR_NAME}"

# ---------------------------------------------------------------------------
# Exemption documentation (C-004 — permanent plumbing exemptions)
# ---------------------------------------------------------------------------

# coordination/status_transition.py is exempt: it is internal Mission Management
# domain plumbing that coordinates transactional status transitions. It directly
# coordinates with status.emit, status.reducer, and status.locking as low-level
# building blocks of the transactional commit pipeline. This exemption is
# intentional and documented in the contract.
#
# coordination/transaction.py is exempt: BookkeepingTransaction plumbing that
# coordinates transactional JSONL writes; also a legitimate internal consumer
# of status internals per C-004.
_EXEMPT_FILES: frozenset[Path] = frozenset(
    {
        _SRC / "specify_cli" / "coordination" / "status_transition.py",
        _SRC / "specify_cli" / "coordination" / "transaction.py",
    }
)

# ---------------------------------------------------------------------------
# ROUTE-deferred-to-WP10 allow-list (shrinking ledger)
#
# These files contain deep status imports for symbols NOT yet exposed on the
# facade.  WP10 will add each symbol to `status/__init__.__all__` and migrate
# each callsite to `from specify_cli.status import <symbol>`, then remove the
# entry from this allow-list.
#
# Format: (relative_path_under_src/specify_cli/, imported_submodule)
# ---------------------------------------------------------------------------
#
# WP10 routed every prior ROUTE-deferred file: the lifecycle_events,
# work_package_lifecycle, reducer.materialize_snapshot, doctor.run_doctor, and
# aggregate.InvalidMissionSlug symbols were promoted onto the ``status`` facade
# (``status/__init__.__all__``), and the sync SaaS fan-out handler now consumes
# ``build_saas_lifecycle_queue_event`` / ``repo_root_for_lifecycle_log`` from the
# facade instead of reaching into ``status.lifecycle_events`` internals. Three
# entries remain: the permanent import-time cycle-breaker, one temporary
# WIRE-M2-03 entry pending a follow-up bead (see the module docstring above
# for the full name-collision rationale on the latter), and one temporary
# convergence-port entry (PR #1066) pending facade promotion of
# ``feature_event_log_missing_error``.
_WP10_DEFERRED_FILES: frozenset[Path] = frozenset(
    {
        # cycle-breaker (permanent): status/__init__ → .emit → workspace →
        # .context; the facade isn't initialized when workspace.context loads at
        # import time, so it must import status.wp_metadata directly. Cannot be
        # routed through the facade without an import cycle.
        _SRC / "specify_cli" / "workspace" / "context.py",
        # TEMPORARY (WIRE-M2-03, 2026-08-22, rework cycle 2): the sole
        # remaining direct import in this file is
        # ``from specify_cli.status.migrate_lifecycle_envelope import
        # migrate_lifecycle_envelope`` -- the function's bare name is
        # identical to its home submodule's filename
        # (status/migrate_lifecycle_envelope.py), so promoting it onto the
        # facade under that name would make ``from specify_cli.status
        # import migrate_lifecycle_envelope`` resolve to the function
        # everywhere and silently break the two pre-existing tests that
        # rely on that exact shape resolving to the MODULE (via Python's
        # implicit submodule fallback): tests/status/
        # test_migrate_lifecycle_envelope.py (monkeypatches
        # ``migrate_lifecycle_envelope_module.os.replace``) and
        # tests/status/test_migrate_lifecycle_envelope_node_id_parity.py
        # (calls the private ``_generate_node_id`` helper). This file's
        # other two status imports (mission_event_log_path,
        # project_event_log_path) ARE routed through the facade -- only
        # this one colliding name is deferred. Follow-up bead: either
        # rename the function to something that does not collide with its
        # module's filename, or teach the SR-2 AST scanner to consult
        # status/__init__.__all__ as an override for names that
        # legitimately collide with a submodule filename.
        _SRC
        / "specify_cli"
        / "upgrade"
        / "migrations"
        / "m_3_2_9_migrate_lifecycle_envelope.py",
        # TEMPORARY (convergence port PR #1066, 2026-09-03): the verbatim
        # upstream pick of next-committed-state-authority WP01
        # (committed_authority.py) imports
        # ``feature_event_log_missing_error`` function-level from
        # ``status.uninitialized_hint`` for its fail-loud absent-log gate.
        # The symbol is not on the ``status`` facade yet (upstream has not
        # promoted it either). TODO(triage): promote it onto
        # ``status/__init__.__all__``, migrate this callsite to
        # ``from specify_cli.status import feature_event_log_missing_error``,
        # and remove this entry — tracked with the #1065 manual re-port
        # queue carrying this mission's conflicted WP02 wiring.
        _SRC / "runtime" / "next" / "committed_authority.py",
    }
)

# Combined exemptions for the AST scanner: permanent C-004 plumbing + WP10-deferred
_ALL_EXEMPT_FILES: frozenset[Path] = _EXEMPT_FILES | _WP10_DEFERRED_FILES


# ---------------------------------------------------------------------------
# SR-1 -- pytestarch rule (regression-lock on the 6 WP03 clean packages)
# ---------------------------------------------------------------------------


class TestStatusModuleBoundary:
    """SR-1: regression-lock on the 6 WP03-owned packages.

    SR-1 asserts the six already-clean WP03 packages (agent_utils, lanes,
    post_merge, missions, merge, next) never reintroduce a static
    ``specify_cli.status.*`` submodule import. It is **deliberately scoped to
    those packages** — the repo-wide enforcement (every module in
    ``src/specify_cli`` + ``src/runtime``) is **SR-2** (the AST scan), which also
    catches lazy/function-scoped imports that pytestarch's import-graph analysis
    misses.

    The WP03 packages are fully fixed and NOT in the allow-list; their absence
    from the allow-list is what makes this rule bite for those packages.
    """



# ---------------------------------------------------------------------------
# SR-2 -- AST scan (repo-wide; catches lazy / function-scoped imports)
# ---------------------------------------------------------------------------


def scan_for_bypass_imports(
    files: list[pathlib.Path],
    *,
    exempt_files: set[pathlib.Path] | None = None,
) -> list[str]:
    """Scan ``files`` for direct imports of ``specify_cli.status.*`` submodules.

    Returns a list of violation strings in the form ``"<path>:<lineno>: <module>"``.

    Parameters
    ----------
    files:
        List of ``.py`` files to scan.
    exempt_files:
        Set of file paths to skip entirely.  Defaults to an empty set.

    The function catches both module-level and function-scoped (lazy) imports
    because it walks the full AST tree rather than relying on import-graph
    static analysis.  TYPE_CHECKING-guarded imports are excluded since they
    are only evaluated by type-checkers and do not create runtime coupling.
    """
    if exempt_files is None:
        exempt_files = set()

    violations: list[str] = []
    for py_file in files:
        if py_file in exempt_files:
            continue
        tree = parse_file(py_file)
        # Collect all if-TYPE_CHECKING node ranges to exclude them
        type_checking_linenos: set[int] = _collect_type_checking_linenos(tree)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            node_lineno = getattr(node, "lineno", None)
            if node_lineno in type_checking_linenos:
                continue
            violations.extend(_bypass_violations_for_node(node, py_file, node_lineno))
    return violations


def _bypass_violations_for_node(
    node: ast.Import | ast.ImportFrom, py_file: pathlib.Path, node_lineno: int | None
) -> list[str]:
    """Return the (zero or more) bypass-violation strings a single import
    node produces. Extracted (WP02, T009/NFR-004) so the caller's per-file /
    per-node walk stays under the complexity ceiling once the alias-name
    widening below is added alongside the pre-existing ``node.module`` check.
    """
    if isinstance(node, ast.ImportFrom) and node.module:
        return _bypass_violations_for_import_from(node, py_file, node_lineno)
    if isinstance(node, ast.Import):
        return [
            f"{py_file}:{node_lineno}: {alias.name}"
            for alias in node.names
            if _is_bypass_import(alias.name)
        ]
    return []


def _bypass_violations_for_import_from(
    node: ast.ImportFrom, py_file: pathlib.Path, node_lineno: int | None
) -> list[str]:
    """The ``ImportFrom``-specific half of :func:`_bypass_violations_for_node`.

    Two independent bypass shapes:
    1. ``from specify_cli.status.<submodule> import X`` -- the dotted-path
       form; ``node.module`` itself names the submodule.
    2. ``from specify_cli.status import <submodule>`` (WP02, T009) -- the
       SAME bypass, handing the caller a raw submodule object instead of a
       curated facade symbol. ``node.module`` can't see this shape (its
       module IS the facade, ``"specify_cli.status"``); only the per-alias
       name distinguishes a submodule handle from a legitimate facade symbol.
    """
    assert node.module is not None
    if _is_bypass_import(node.module):
        return [f"{py_file}:{node_lineno}: {node.module}"]
    if node.module != "specify_cli.status":
        return []
    return [
        f"{py_file}:{node_lineno}: {node.module}.{alias.name}"
        for alias in node.names
        if _is_status_submodule_name(alias.name)
    ]


def _is_status_submodule_name(name: str) -> bool:
    """Return True if ``name`` names an actual ``specify_cli.status`` submodule.

    ``name`` is the bare alias from ``from specify_cli.status import <name>``.
    Resolved against the real submodule files on disk (``status/<name>.py``)
    rather than any string-shape heuristic on ``name`` itself: a bare
    ``name.startswith("specify_cli.status")`` (or an equivalent check against
    a reconstructed ``f"{node.module}.{alias.name}"``) would be vacuously
    true for every facade-symbol import too -- ``node.module`` is ALWAYS
    ``"specify_cli.status"`` at this call site -- and would flag 100+
    legitimate ``from specify_cli.status import <symbol>`` sites (C-003).
    ``__init__`` is excluded explicitly: it is the package's own module file,
    never a submodule alias a caller would import by that name.
    """
    if name in {"__init__", _UNSAFE_DOOR_NAME}:
        return False
    return (_SRC / "specify_cli" / "status" / f"{name}.py").is_file()


def _collect_type_checking_linenos(tree: ast.AST) -> set[int]:
    """Collect line numbers of all nodes inside ``if TYPE_CHECKING:`` blocks."""
    linenos: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        # Detect `if TYPE_CHECKING:` — the test is `Name(id='TYPE_CHECKING')`
        # or `Attribute(attr='TYPE_CHECKING')`.
        test = node.test
        is_type_checking = (
            (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING")
            or (isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING")
        )
        if is_type_checking:
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    linenos.add(child.lineno)
    return linenos


def _is_bypass_import(module_name: str) -> bool:
    """Return True if the module is a direct status submodule import (bypass).

    ``specify_cli.status._unsafe`` is NOT a bypass: it is the sanctioned,
    enumerated door for the raw append primitives (fsm-write-path-integrity
    WP03, FR-010), gated separately by
    ``tests/architectural/test_status_unsafe_allowlist.py`` (every importer
    must be in ``_unsafe.ALLOWED_CALLERS``, shrink-only). Treating it as a
    bypass here would force each allowed writer onto ``_ALL_EXEMPT_FILES``
    and widen THIS gate's exemption ledger for a door another gate owns.
    """
    return (
        module_name.startswith("specify_cli.status.")
        and module_name not in {"specify_cli.status", _UNSAFE_DOOR_MODULE}
    )


def _collect_all_src_files() -> list[pathlib.Path]:
    """Collect all .py files under src/specify_cli and src/runtime.

    WP09 widens from WP03's 6-directory scope to the full source tree.
    ``src/specify_cli/status/`` itself is excluded (it is the boundary owner,
    not a consumer).  ``src/runtime/`` is included to catch any future
    imports that might be introduced there.
    """
    files: list[pathlib.Path] = []

    search_roots = [
        _SRC / "specify_cli",
        _SRC / "runtime",
    ]

    for root in search_roots:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            # Skip the status package itself — it is the owner of the boundary,
            # not a consumer that the rule constrains.
            if py_file.is_relative_to(_SRC / "specify_cli" / "status"):
                continue
            files.append(py_file)

    return files


def test_ast_scan_no_direct_status_imports_repo_wide() -> None:
    """AST scan: all modules in src/specify_cli + src/runtime must not bypass the status/ facade.

    WP09 widens the scan from WP03-owned directories to the full source tree.
    The allow-list (_ALL_EXEMPT_FILES) documents:
      1. C-004 permanent plumbing exemptions (coordination/status_transition.py,
         coordination/transaction.py).
      2. ROUTE-deferred-to-WP10 files where facade symbols are not yet available.

    WP10 shrinks the allow-list by adding each deferred symbol to
    ``status/__init__.__all__`` and migrating each callsite.

    This test proves the scan covers the full src/ tree and catches any NEW
    non-allow-listed deep imports introduced after WP09.

    Also asserts that the scan completes within 15 seconds (NFR-005).
    """
    start = time.monotonic()

    files = _collect_all_src_files()
    violations = scan_for_bypass_imports(files, exempt_files=set(_ALL_EXEMPT_FILES))

    elapsed = time.monotonic() - start
    assert elapsed < 15.0, (  # noqa: PLR2004 — NFR-005 numeric literal is the spec
        f"AST scan took {elapsed:.1f}s, exceeds NFR-005 15s budget"
    )

    assert not violations, (
        f"Direct status submodule imports found outside the allow-list "
        f"({len(violations)} violations):\n"
        + "\n".join(f"  {v}" for v in violations[:30])
        + (f"\n  ... and {len(violations) - 30} more" if len(violations) > 30 else "")
        + "\n\n"
        "All imports from status/ must go through `from specify_cli.status import X`.\n"
        "To add a temporary exemption: add the file path to _WP10_DEFERRED_FILES "
        "with a comment explaining WHY and which WP will fix it.\n"
        "Permanent exemptions (C-004 plumbing): coordination/status_transition.py, "
        "coordination/transaction.py."
    )


# ---------------------------------------------------------------------------
# SR-3 -- Injection proof (scanner is not a no-op)
# ---------------------------------------------------------------------------


def test_ast_scan_catches_injected_violation(tmp_path: pathlib.Path) -> None:
    """Injection proof: the scanner detects a synthetic bypass import.

    Proves the enforcement is not vacuous.  If the scanner fails to catch this,
    the entire SR-2 rule has no teeth.
    """
    bad_file = tmp_path / "bad_module.py"
    bad_file.write_text(
        textwrap.dedent(
            """
            # Synthetic SR-2 violator -- proves the scanner has teeth.
            from specify_cli.status.emit import emit_status_transition  # noqa: F401
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    violations = scan_for_bypass_imports([bad_file], exempt_files=set())
    assert len(violations) == 1, (
        f"Expected exactly 1 violation, got {len(violations)}: {violations}"
    )
    assert "status.emit" in violations[0], (
        f"Expected 'status.emit' in violation string, got: {violations[0]}"
    )


def test_ast_scan_catches_submodule_object_import(tmp_path: pathlib.Path) -> None:
    """Two-way teeth (WP02, T009, NFR-002), flagged half.

    A fabricated ``from specify_cli.status import verdict_vocab`` -- the
    exact bypass shape WP02 migrated away from at all 8 verdict_vocab call
    sites -- must be caught. Proves the alias-name widening (not just the
    pre-existing ``node.module`` dotted-path check) has teeth on its own.
    """
    bad_file = tmp_path / "bad_submodule_alias_import.py"
    bad_file.write_text(
        textwrap.dedent(
            """
            # Synthetic SR-2 violator -- submodule-object-via-facade shape.
            from specify_cli.status import verdict_vocab  # noqa: F401
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    violations = scan_for_bypass_imports([bad_file], exempt_files=set())
    assert len(violations) == 1, (
        f"Expected exactly 1 violation, got {len(violations)}: {violations}"
    )
    assert "specify_cli.status.verdict_vocab" in violations[0], (
        f"Expected 'specify_cli.status.verdict_vocab' in violation string, "
        f"got: {violations[0]}"
    )


def test_ast_scan_does_not_flag_facade_symbol_import(tmp_path: pathlib.Path) -> None:
    """Two-way teeth (WP02, T009, NFR-002), unflagged half.

    A fabricated ``from specify_cli.status import is_approved`` -- a curated
    facade **symbol**, not a submodule object -- must NOT be flagged. Guards
    against the C-003 trap: a bare ``startswith("specify_cli.status")`` shape
    check on the imported name (or on a reconstructed ``module.alias`` string)
    would be vacuously true for this import too, since ``node.module`` is
    always ``"specify_cli.status"`` at this call site -- that shape would
    flag every one of the 100+ legitimate facade-symbol imports across the
    repo, not just the ~12 real submodule-object bypasses.
    """
    good_file = tmp_path / "good_facade_symbol_import.py"
    good_file.write_text(
        textwrap.dedent(
            """
            # A legitimate facade-symbol import -- must never be flagged.
            from specify_cli.status import is_approved  # noqa: F401
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    violations = scan_for_bypass_imports([good_file], exempt_files=set())
    assert not violations, (
        f"Facade-symbol import must not be flagged as a bypass, got: {violations}"
    )


def test_ast_scan_does_not_flag_the_sanctioned_unsafe_door(tmp_path: pathlib.Path) -> None:
    """The ``status._unsafe`` door is gated elsewhere, not a bypass here.

    fsm-write-path-integrity-01M1TZV6 WP03 (FR-010): the raw append
    primitives left the facade for ``specify_cli.status._unsafe``. Both import
    shapes of that door must pass SR-2 unflagged -- its importers are
    enumerated and shrink-only under ``test_status_unsafe_allowlist.py``.
    """
    door_file = tmp_path / "allowed_unsafe_door_import.py"
    door_file.write_text(
        textwrap.dedent(
            """
            from specify_cli.status._unsafe import append_raw_rows_atomic  # noqa: F401
            from specify_cli.status import _unsafe  # noqa: F401
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    violations = scan_for_bypass_imports([door_file], exempt_files=set())
    assert not violations, (
        f"The sanctioned _unsafe door must not be flagged as a bypass, got: {violations}"
    )


def test_ast_scan_ignores_type_checking_imports(tmp_path: pathlib.Path) -> None:
    """Verify that TYPE_CHECKING-guarded imports are not flagged as violations.

    These imports are only evaluated by type-checkers, not at runtime, and do
    not create actual module coupling.
    """
    safe_file = tmp_path / "type_safe_module.py"
    safe_file.write_text(
        textwrap.dedent(
            """
            from __future__ import annotations
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                from specify_cli.status.models import StatusEvent  # type-only

            def f(x: StatusEvent) -> None:
                pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    violations = scan_for_bypass_imports([safe_file], exempt_files=set())
    assert not violations, (
        f"TYPE_CHECKING imports should not be flagged as violations, got: {violations}"
    )
