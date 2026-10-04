"""AST pin: the consolidation rollback authority has exactly one door (WP03 / T016).

Non-vacuous architectural pin (DIRECTIVE_043 / Standing Order #5) that keeps the
#5318 / #5332 wiring from silently rotting:

1. ``rollback_to_snapshot`` is called only from allow-listed callers, and at
   least ``_CALLER_FLOOR`` of them are discovered (a scanner that finds nothing
   proves nothing).
2. ``restore_branch_ref(..., resync_checkouts=True)`` is called only from
   ``consolidation/rollback.py`` (the authority owns the resyncing restore).
3. #5385 (ADR 2026-09-19-1 A3): every driver call to a post-mutation span phase
   (``_SPAN_PHASES``, from ``_phase_merge_lanes`` through the gate) sits inside the
   body of ONE ``try`` whose ``BaseException`` handler calls ``_report_rollback``,
   whose every reporting handler ends in a bare ``raise`` (the original error
   propagates) and whose ``typer.Exit`` handler reports only under an ``if`` on
   ``exit_code`` (``Exit(0)`` never rolls back) -- the single rollback door. This
   replaces the older gate-only rule.
4. No per-phase ``git revert`` survives in ``consolidation/executor.py`` (no
   ``"revert"`` constant in an argv list or call args), and none of the retired
   rollback helpers (``_RETIRED_NAMES``) is defined or referenced anywhere in src.
5. ``_heal_pending_coord_reconcile`` (a forward ``git revert``) is called only from
   the driver's resume-start site, never from a restore primitive in the span.
6. Self-mutation tests run the SAME scanners over synthetic sources that violate
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
_HEAL = "_heal_pending_coord_reconcile"

# #5385: the post-mutation span the door covers, first mutation through the gate.
_SPAN_PHASES: frozenset[str] = frozenset(
    {
        "_phase_merge_lanes",
        "_phase_baseline_and_surface",
        "_phase_bake_and_pre_target_done",
        "_capture_pre_target_gate_artifacts",
        "_phase_mission_to_target",
        "_switch_write_checkout_after_single_branch_landing",
        "_phase_capture_and_baseline",
        "_phase_record_done_and_project",
        "_phase_porcelain_invariant",
        "_phase_commit_and_assert",
        _GATE_PHASE,
    }
)
_SPAN_FLOOR = len(_SPAN_PHASES)

# #5385: per-phase rollback helpers and their anchor, retired in favour of the door.
_RETIRED_NAMES: frozenset[str] = frozenset(
    {
        "_reset_coord_to_checkpoint",
        "_revert_coord_done_commit",
        "_rollback_to_pre_mutation_checkpoint",
        "_revert_orphan_target_bake_commit",
        "_capture_pre_mutation_coord_checkpoint",
        "pre_bake_target_baseline_sha",
    }
)

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


def _catches(handler: ast.ExceptHandler, name: str) -> bool:
    types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any((isinstance(t, ast.Name) and t.id == name) or (isinstance(t, ast.Attribute) and t.attr == name) for t in types)


def _reports(node: ast.AST) -> bool:
    return any(isinstance(c, ast.Call) and _called_name(c) == _WRAPPER_HELPER for c in ast.walk(node))


def _ends_in_bare_raise(handler: ast.ExceptHandler) -> bool:
    """The handler re-raises the ORIGINAL error: its last statement is a bare ``raise``."""
    last = handler.body[-1]
    return isinstance(last, ast.Raise) and last.exc is None


def _guards_on_exit_code(stmt: ast.stmt) -> bool:
    """``stmt`` reports the rollback only under an ``if`` that tests ``exit_code`` (never on ``Exit(0)``)."""
    if not isinstance(stmt, ast.If) or _reports(ast.Module(body=stmt.orelse, type_ignores=[])):
        return False
    return any(isinstance(n, ast.Attribute) and n.attr == "exit_code" for n in ast.walk(stmt.test))


def _is_sound_handler(handler: ast.ExceptHandler) -> bool:
    """A reporting handler re-raises, and a ``typer.Exit`` handler reports only for a non-zero exit code."""
    if not _ends_in_bare_raise(handler):
        return False
    if not _catches(handler, "Exit"):
        return True
    return all(_guards_on_exit_code(stmt) for stmt in handler.body if _reports(stmt))


def _is_door(node: ast.Try) -> bool:
    """A ``try`` is the rollback door when its ``BaseException`` handler reports the rollback and every
    reporting handler is sound (re-raises the original; an ``Exit`` handler guards on ``exit_code``)."""
    reporting = [h for h in node.handlers if _reports(h)]
    catches_all = any(_catches(h, "BaseException") for h in reporting)
    return catches_all and all(_is_sound_handler(h) for h in reporting)


def scan_span_phase_calls(source: str) -> tuple[list[str], list[str]]:
    """Driver calls to ``_SPAN_PHASES``, split into (inside a door ``try`` body, outside it)."""
    wrapped: list[str] = []
    unwrapped: list[str] = []
    for driver in (n for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef) and n.name == _DRIVER):
        doors = [n for n in ast.walk(driver) if isinstance(n, ast.Try) and _is_door(n)]
        covered = {id(c) for door in doors for stmt in door.body for c in ast.walk(stmt) if isinstance(c, ast.Call)}
        for call in (c for c in ast.walk(driver) if isinstance(c, ast.Call) and _called_name(c) in _SPAN_PHASES):
            (wrapped if id(call) in covered else unwrapped).append(str(_called_name(call)))
    return wrapped, unwrapped


def _is_revert_constant(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value == "revert"


def scan_revert_argvs(source: str, module: str) -> list[_Call]:
    """Every argv list/tuple or call whose arguments carry the ``"revert"`` literal."""
    tree = ast.parse(source)
    owners = _enclosing_functions(tree)
    hits: list[_Call] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and any(
            _is_revert_constant(a) or (isinstance(a, ast.List | ast.Tuple) and any(_is_revert_constant(e) for e in a.elts)) for a in node.args
        ):
            hits.append(_Call(module, owners[id(node)]))
    return hits


def scan_retired_names(source: str) -> set[str]:
    """Retired rollback helpers defined or referenced in *source*."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            found.add(node.name)
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
    return found & _RETIRED_NAMES


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


def test_every_span_phase_call_sits_inside_the_one_rollback_door() -> None:
    """#5385: a failure anywhere between the first mutation and the gate rolls back through one door."""
    source = (_SRC_ROOT / _EXECUTOR).read_text(encoding="utf-8")
    wrapped, unwrapped = scan_span_phase_calls(source)
    assert not unwrapped, f"span phase call(s) outside the rollback door: {unwrapped}"
    assert len(wrapped) >= _SPAN_FLOOR, f"non-vacuity: expected >= {_SPAN_FLOOR} wrapped span calls, found {sorted(wrapped)}"
    assert set(wrapped) == _SPAN_PHASES, f"every span phase must be called inside the door: missing {sorted(_SPAN_PHASES - set(wrapped))}"


# #2026: executor.py was split along its phase boundaries; every module of the
# split family is held to the no-per-phase-revert rule, not executor.py alone.
_EXECUTOR_FAMILY: tuple[str, ...] = tuple(
    f"specify_cli/consolidation/{name}.py"
    for name in (
        "executor",
        "run_state",
        "coord_strand",
        "phase_claim",
        "phase_advance",
        "phase_bookkeeping",
        "phase_gate",
        "phase_teardown",
        "phase_finalize",
        "entry_preflight",
        "resume_recovery",
    )
)


def test_executor_builds_no_revert_argv() -> None:
    for module in _EXECUTOR_FAMILY:
        source = (_SRC_ROOT / module).read_text(encoding="utf-8")
        assert scan_revert_argvs(source, module) == [], f"a per-phase git revert is back in {module}; roll back through the door"
    coherence = "specify_cli/coordination/coherence.py"
    assert scan_revert_argvs((_SRC_ROOT / coherence).read_text(encoding="utf-8"), coherence), (
        "non-vacuity: the scanner must see repair_coord_strand's own revert argv"
    )


def test_no_retired_rollback_helper_survives_in_src() -> None:
    hits = {module: names for module, src in _all_src_files() if (names := scan_retired_names(src))}
    assert not hits, f"retired #5385 rollback helper(s) still defined or referenced: {hits}"


def scan_heal_calls(files: list[tuple[str, str]]) -> tuple[list[_Call], list[_Call]]:
    """Every ``_heal_pending_coord_reconcile`` call in *files*, and the strays outside the driver."""
    calls = [call for module, src in files for call, _node in _calls_named(src, module, _HEAL)]
    return calls, [c for c in calls if c != _Call(_EXECUTOR, _DRIVER)]


def test_resume_heal_is_called_only_from_the_driver() -> None:
    calls, stray = scan_heal_calls(_all_src_files())
    assert calls, f"non-vacuity: the driver's resume-start {_HEAL} call must be found"
    assert not stray, f"{_HEAL} (a forward git revert) called outside the driver's resume-start site: {stray}"


# ---------------------------------------------------------------- self-mutation


_DOOR = (
    "    except typer.Exit as exc:\n        if exc.exit_code:\n            {h}(run)\n        raise\n    except BaseException:\n        {h}(run)\n        raise\n"
)


def _driver(body: str) -> str:
    return f"def {_DRIVER}(run):\n{body}"


def test_scanner_accepts_the_door() -> None:
    door = _driver(f"    try:\n        _phase_merge_lanes(run)\n        {_GATE_PHASE}(run)\n" + _DOOR.format(h=_WRAPPER_HELPER))
    assert scan_span_phase_calls(door) == (["_phase_merge_lanes", _GATE_PHASE], [])


def test_scanner_flags_a_span_phase_call_outside_the_door() -> None:
    leaky = _driver(f"    _phase_merge_lanes(run)\n    try:\n        {_GATE_PHASE}(run)\n" + _DOOR.format(h=_WRAPPER_HELPER))
    assert scan_span_phase_calls(leaky) == ([_GATE_PHASE], ["_phase_merge_lanes"])


def test_scanner_flags_a_door_that_catches_only_typer_exit() -> None:
    exit_only = _driver(f"    try:\n        _phase_mission_to_target(run)\n    except typer.Exit:\n        {_WRAPPER_HELPER}(run)\n        raise\n")
    assert scan_span_phase_calls(exit_only) == ([], ["_phase_mission_to_target"])


def test_scanner_flags_a_door_that_never_reports() -> None:
    silent = _driver(f"    try:\n        {_GATE_PHASE}(run)\n    except BaseException:\n        raise\n")
    assert scan_span_phase_calls(silent) == ([], [_GATE_PHASE])


def test_scanner_flags_a_call_in_the_handler_not_the_body() -> None:
    in_handler = _driver(
        f"    try:\n        pass\n    except BaseException:\n        {_WRAPPER_HELPER}(run)\n        _phase_commit_and_assert(run)\n        raise\n"
    )
    assert scan_span_phase_calls(in_handler) == ([], ["_phase_commit_and_assert"])


def test_scanner_flags_a_door_that_swallows_the_error() -> None:
    swallowing = _driver(
        f"    try:\n        _phase_mission_to_target(run)\n"
        f"    except typer.Exit as exc:\n        if exc.exit_code:\n            {_WRAPPER_HELPER}(run)\n        raise\n"
        f"    except BaseException:\n        {_WRAPPER_HELPER}(run)\n"
    )
    assert scan_span_phase_calls(swallowing) == ([], ["_phase_mission_to_target"])


def test_scanner_flags_a_door_that_rolls_back_on_a_zero_exit() -> None:
    unguarded = _driver(
        f"    try:\n        _phase_mission_to_target(run)\n"
        f"    except typer.Exit:\n        {_WRAPPER_HELPER}(run)\n        raise\n"
        f"    except BaseException:\n        {_WRAPPER_HELPER}(run)\n        raise\n"
    )
    assert scan_span_phase_calls(unguarded) == ([], ["_phase_mission_to_target"])
    else_branch = _driver(
        f"    try:\n        _phase_mission_to_target(run)\n"
        f"    except typer.Exit as exc:\n        if exc.exit_code:\n            pass\n        else:\n            {_WRAPPER_HELPER}(run)\n        raise\n"
        f"    except BaseException:\n        {_WRAPPER_HELPER}(run)\n        raise\n"
    )
    assert scan_span_phase_calls(else_branch) == ([], ["_phase_mission_to_target"])


def test_scanner_flags_a_per_phase_git_revert() -> None:
    synthetic = "def _undo(run):\n    subprocess.run(['git', '-C', str(run.repo), 'revert', '--no-edit', 'abc'], check=True)\n"
    assert scan_revert_argvs(synthetic, _EXECUTOR) == [_Call(_EXECUTOR, "_undo")]
    via_helper = "def _undo(run):\n    _git(run.repo, 'revert', 'abc')\n"
    assert scan_revert_argvs(via_helper, _EXECUTOR) == [_Call(_EXECUTOR, "_undo")]
    benign = "def _msg():\n    return 'revert'\n"
    assert scan_revert_argvs(benign, _EXECUTOR) == []


def test_scanner_flags_a_retired_helper() -> None:
    assert scan_retired_names("def _reset_coord_to_checkpoint(run):\n    pass\n") == {"_reset_coord_to_checkpoint"}
    assert scan_retired_names("def f(run):\n    return run.pre_bake_target_baseline_sha\n") == {"pre_bake_target_baseline_sha"}
    assert scan_retired_names("def f(run):\n    _revert_coord_done_commit(run)\n") == {"_revert_coord_done_commit"}


def test_scanner_flags_a_heal_inside_a_restore_primitive() -> None:
    in_driver = f"def {_DRIVER}(run):\n    {_HEAL}(run)\n"
    in_primitive = f"def _restore_and_guard_coord_coherence(run, snaps):\n    {_HEAL}(run)\n"
    assert scan_heal_calls([(_EXECUTOR, in_driver)]) == ([_Call(_EXECUTOR, _DRIVER)], [])
    calls, stray = scan_heal_calls([(_EXECUTOR, in_driver), (_EXECUTOR, in_primitive)])
    assert stray == [_Call(_EXECUTOR, "_restore_and_guard_coord_coherence")] and len(calls) == 2
    elsewhere = f"def {_DRIVER}(run):\n    {_HEAL}(run)\n"
    assert scan_heal_calls([("specify_cli/other.py", elsewhere)])[1] == [_Call("specify_cli/other.py", _DRIVER)]


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
