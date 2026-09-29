"""AST pin: the consolidation rollback authority has exactly one door (WP03 / T016).

Non-vacuous architectural pin (DIRECTIVE_043 / Standing Order #5) that keeps the
#5318 / #5332 wiring from silently rotting:

1. ``rollback_to_snapshot`` is called only from allow-listed callers, and at
   least ``_CALLER_FLOOR`` of them are discovered (a scanner that finds nothing
   proves nothing).
2. ``restore_branch_ref(..., resync_checkouts=True)`` is called only from
   ``consolidation/rollback.py`` (the authority owns the resyncing restore).
3. The driver's ``_phase_reconcile_before_teardown`` call sits inside a ``try``
   body whose handler calls ``_report_rollback``.
4. Self-mutation tests run the SAME scanner over synthetic sources that violate
   each rule, proving the pin can fail.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

import specify_cli

pytestmark = pytest.mark.fast

# tasks.md T016 requires >= 2 callers: ``executor._report_rollback`` (WP03) and the
# ``--abort`` helper ``consolidate._abort_restore_or_keep_record`` (WP04).
_CALLER_FLOOR = 2

_SRC_ROOT = Path(specify_cli.__file__).resolve().parent.parent
_EXECUTOR = "specify_cli/consolidation/executor.py"
_ROLLBACK = "specify_cli/consolidation/rollback.py"
_CLI_CONSOLIDATE = "specify_cli/cli/commands/consolidate.py"
_DRIVER = "_run_lane_based_consolidation_locked"
_GATE_PHASE = "_phase_reconcile_before_teardown"
_WRAPPER_HELPER = "_report_rollback"
_ABORT_HELPER = "_abort_restore_or_keep_record"

# (module path relative to src/, enclosing function or ``None`` for any) allowed to call the authority.
# The ``--abort`` helper is the only allowed caller in the consolidate CLI module.
_ALLOWED_CALLERS: frozenset[tuple[str, str | None]] = frozenset({(_EXECUTOR, _WRAPPER_HELPER), (_CLI_CONSOLIDATE, _ABORT_HELPER)})


@dataclass(frozen=True)
class _Call:
    module: str
    function: str


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _enclosing_functions(tree: ast.Module) -> dict[int, str]:
    """Map ``id(call node)`` to its innermost enclosing function name (``<module>`` if none)."""
    owners: dict[int, str] = {}

    def visit(node: ast.AST, current: str) -> None:
        for child in ast.iter_child_nodes(node):
            name = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else current
            if isinstance(child, ast.Call):
                owners[id(child)] = current
            visit(child, name)

    visit(tree, "<module>")
    return owners


def _calls_named(source: str, module: str, name: str) -> list[tuple[_Call, ast.Call]]:
    tree = ast.parse(source)
    owners = _enclosing_functions(tree)
    return [(_Call(module, owners[id(n)]), n) for n in ast.walk(tree) if isinstance(n, ast.Call) and _called_name(n) == name]


def scan_authority_callers(source: str, module: str) -> list[_Call]:
    """Every call of ``rollback_to_snapshot`` in *source*."""
    return [call for call, _node in _calls_named(source, module, "rollback_to_snapshot")]


def scan_resyncing_restores(source: str, module: str) -> list[_Call]:
    """Every ``restore_branch_ref(..., resync_checkouts=True)`` call in *source*."""
    hits = []
    for call, node in _calls_named(source, module, "restore_branch_ref"):
        if any(kw.arg == "resync_checkouts" and isinstance(kw.value, ast.Constant) and kw.value.value is True for kw in node.keywords):
            hits.append(call)
    return hits


def gate_call_is_wrapped(source: str) -> bool:
    """True when the driver's gate-phase call is in a ``try`` body whose handler calls ``_report_rollback``."""
    tree = ast.parse(source)
    drivers = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == _DRIVER]
    for driver in drivers:
        for node in ast.walk(driver):
            if not isinstance(node, ast.Try):
                continue
            in_body = any(isinstance(c, ast.Call) and _called_name(c) == _GATE_PHASE for stmt in node.body for c in ast.walk(stmt))
            in_handler = any(isinstance(c, ast.Call) and _called_name(c) == _WRAPPER_HELPER for h in node.handlers for c in ast.walk(h))
            if in_body and in_handler:
                return True
    return False


def _gate_calls_in_driver(source: str) -> int:
    tree = ast.parse(source)
    return sum(
        1
        for d in ast.walk(tree)
        if isinstance(d, ast.FunctionDef) and d.name == _DRIVER
        for c in ast.walk(d)
        if isinstance(c, ast.Call) and _called_name(c) == _GATE_PHASE
    )


def _all_src_files() -> list[tuple[str, str]]:
    return [(p.relative_to(_SRC_ROOT).as_posix(), p.read_text(encoding="utf-8")) for p in sorted(_SRC_ROOT.rglob("*.py"))]


def _is_allowed(call: _Call) -> bool:
    return (call.module, call.function) in _ALLOWED_CALLERS or (call.module, None) in _ALLOWED_CALLERS


def test_rollback_to_snapshot_is_called_only_from_allowed_callers() -> None:
    discovered = [c for module, src in _all_src_files() if module != _ROLLBACK for c in scan_authority_callers(src, module)]
    stray = [c for c in discovered if not _is_allowed(c)]
    assert not stray, f"rollback_to_snapshot called from non-allow-listed sites: {stray}"
    assert len(discovered) >= _CALLER_FLOOR, f"non-vacuity: expected >= {_CALLER_FLOOR} authority caller(s), found {discovered}"
    assert _Call(_EXECUTOR, _WRAPPER_HELPER) in discovered, "the executor wrapper must be the (or a) caller"
    assert _Call(_CLI_CONSOLIDATE, _ABORT_HELPER) in discovered, "the --abort helper must be the (or a) caller"


def test_resyncing_restore_lives_only_in_the_authority() -> None:
    hits = [c for module, src in _all_src_files() for c in scan_resyncing_restores(src, module)]
    assert hits, "non-vacuity: the authority itself must call restore_branch_ref(resync_checkouts=True)"
    stray = [c for c in hits if c.module != _ROLLBACK]
    assert not stray, f"restore_branch_ref(resync_checkouts=True) outside consolidation/rollback.py: {stray}"


def test_driver_gate_call_is_wrapped_with_the_rollback_report() -> None:
    source = (_SRC_ROOT / _EXECUTOR).read_text(encoding="utf-8")
    assert _gate_calls_in_driver(source) == 1, "the driver must call the gate phase exactly once (the pin keys on the literal call)"
    assert gate_call_is_wrapped(source), f"{_GATE_PHASE}(run) must sit in a try whose handler calls {_WRAPPER_HELPER}"


# ---------------------------------------------------------------- self-mutation


def test_scanner_flags_an_unwrapped_gate_call() -> None:
    unwrapped = f"def {_DRIVER}(run):\n    {_GATE_PHASE}(run)\n"
    assert _gate_calls_in_driver(unwrapped) == 1
    assert not gate_call_is_wrapped(unwrapped)


def test_scanner_flags_a_wrapper_that_never_reports() -> None:
    silent = f"def {_DRIVER}(run):\n    try:\n        {_GATE_PHASE}(run)\n    except Exception:\n        raise\n"
    assert not gate_call_is_wrapped(silent)


def test_scanner_accepts_a_wrapped_gate_call() -> None:
    wrapped = f"def {_DRIVER}(run):\n    try:\n        {_GATE_PHASE}(run)\n    except Exit:\n        {_WRAPPER_HELPER}(run)\n        raise\n"
    assert gate_call_is_wrapped(wrapped)


def test_scanner_flags_a_stray_authority_caller() -> None:
    synthetic = "def sneaky(repo, state):\n    return rollback.rollback_to_snapshot(repo, state, target_branch='main')\n"
    (call,) = scan_authority_callers(synthetic, "specify_cli/other.py")
    assert call == _Call("specify_cli/other.py", "sneaky")
    assert not _is_allowed(call)


def test_scanner_flags_a_stray_resyncing_restore() -> None:
    synthetic = "def sneaky(repo):\n    restore_branch_ref(repo, 'b', 'sha', expected_current_sha='x', resync_checkouts=True)\n"
    assert scan_resyncing_restores(synthetic, "specify_cli/other.py") == [_Call("specify_cli/other.py", "sneaky")]
    benign = "def fine(repo):\n    restore_branch_ref(repo, 'b', 'sha', expected_current_sha='x')\n"
    assert scan_resyncing_restores(benign, "specify_cli/other.py") == []


def test_scanner_flags_a_second_rollback_door_in_the_consolidate_cli() -> None:
    """Only the ``--abort`` helper may call the authority from the consolidate CLI module."""
    stray = "def _dispatch_abort(repo, state):\n    return rollback_to_snapshot(repo, state, target_branch='main')\n"
    (call,) = scan_authority_callers(stray, _CLI_CONSOLIDATE)
    assert not _is_allowed(call)
    helper = f"def {_ABORT_HELPER}(repo, state):\n    return rollback_to_snapshot(repo, state, target_branch='main')\n"
    (allowed,) = scan_authority_callers(helper, _CLI_CONSOLIDATE)
    assert _is_allowed(allowed)
