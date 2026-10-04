"""WP05 / FR-008 — behavioral class-closing guard for INV-COORD-ROLLBACK (#2786 + #2367-B).

Un-marked ``@pytest.mark.regression`` (landing fold: make
``@pytest.mark.regression`` mean exactly one thing). This module is a
PERMANENT behavioral guard, not a red-first P0 reproduction: it passes today
by construction (T015's own non-vacuity half deliberately drives the guard
RED via a runtime-stubbed mark to prove it is not a tautology, but that red
is an in-test ``pytest.raises`` assertion, never a marker-visible collection
failure) and is expected to stay green as long as INV-COORD-ROLLBACK holds.

INV-COORD-ROLLBACK (data-model): *after any merge rollback, either the
coordination branch is coherent (no WP from this merge's write-set still reduces
to ``DONE`` on the committed coord ref while its lane rolled back to
``approved``) OR a ``pending_coord_reconcile`` marker names the stranded WP(s).*
No rollback path may leave a stranded committed ``done`` **and** marker-absent.

The invariant is **behavioral**, so this guard is behavioral — NOT a source grep
for the mark call. Two complementary halves close the whole defect class:

* **T015 — behavioral falsifier (non-vacuity).** The SAME invariant assertion
  (:func:`_assert_coord_rollback_invariant`) is driven against a REAL bake-path
  strand. With the real mark in place it is GREEN (the strand is marked, so the
  committed/working split-brain is recoverable). When
  ``_persist_coord_reconcile_marker`` / ``coord_incoherent_done_wps`` is
  monkeypatched to a runtime no-op and the same real strand is re-driven, the
  guard REDS (``strand-on-committed-ref ∧ marker-absent``). A guard that stayed
  green under a runtime-stubbed mark would be a tautology and is rejected — these
  ``pytest.raises(AssertionError)`` tests prove it does not.

* **T016 — programmatic restore-site enumeration + topology-gating.** The seven
  ``_restore_final_bookkeeping_snapshots`` restore-shape sites are enumerated
  from the executor AST (never a hardcoded line-number list — they drift as
  helpers move). The class-closing structural invariant is that the ONLY raw
  ``_restore_final_bookkeeping_snapshots(`` call lives inside the marking
  primitive ``_restore_and_guard_coord_coherence`` — every other restore site
  routes through it, so a future un-routed restore site cannot strand silently.
  Site ≈691 is asserted dead-for-coord (inside ``if not
  run.done_marked_before_target:``) and site ≈701
  (``_project_status_bookkeeping_to_target`` failure) is asserted
  coord-reachable-and-routed — the live same-shape site the original six-site
  enumeration missed.

**#5385 re-pin (single rollback door).** The driver now wraps the whole
post-mutation span in one rollback door that CAS-restores the coordination
branch after the phase's own byte restore + mark, so a strand no longer survives
the run. T015's falsifiers therefore evaluate the invariant at the bake PHASE's
exit (``on_phase_failure``: the real phase runs, the observation is taken, then
the original error propagates into the door) -- the strand-marking guard is
still exercised exactly where it runs. One driver-level case pins the door's own
outcome: coordination branch at its pre-run tip, no strand, marker cleared.

Behavioral harnesses (fixture bootstrap + bake-mid-write-set failure injection +
git-reducible committed/working readers) are REUSED verbatim from the WP01
red-first repro and the WP03 executor integration tests; this module never
re-authors them.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import cast

import pytest

# Import the status package before any coordination submodule (production import
# order; see the #2711 / #2367-B harness docstrings for rationale).
import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.coordination.coherence import coord_incoherent_done_wps
from specify_cli.consolidation import executor as ex
from specify_cli.consolidation.state import load_state

# --- Reused bake-strand (#2367-B / WP01) harness ----------------------------
# (relocated from tests/regression/ in the 2026-08 landing fold; see
# tests/merge/test_issue_2367_bake_strand.py's module docstring)
from tests.consolidation.test_issue_2367_bake_strand import (
    COHERENT_WP,
    COORD_BRANCH,
    MISSION_ID,
    MISSION_SLUG,
    STRANDED_WP,
    _bootstrap_two_wp_coord_mission,
    _git,
    _run_bake_failing_merge,
    on_phase_failure,
)

# ``_init_git_repo`` is DEFINED in the #2711 harness and only re-exported by the
# #2367-B module; import it from its definition site so mypy's strict
# no-implicit-reexport check is satisfied.
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    _init_git_repo,
)
from specify_cli.consolidation import coord_strand

pytestmark = [
    pytest.mark.architectural,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]

# This merge's pre-target ``done`` write-set for the 2-WP fixture. ``STRANDED_WP``
# commits ``done`` before the injected bake failure (→ stranded on the committed
# coord ref); ``COHERENT_WP`` is only ever ``approved`` (the coherent control).
_WRITE_SET: list[str] = [STRANDED_WP, COHERENT_WP]


# ===========================================================================
# The behavioral invariant checker + guard (the thing T015 falsifies)
# ===========================================================================


def _feature_dir(repo: Path) -> Path:
    """Primary feature dir (``name == slug``) anchoring the committed-coord read.

    Mirrors ``executor._coord_reconcile_read_feature_dir`` — the same placement the
    rollback marker derivation uses, so the checker reads the identical committed
    coordination ref.
    """
    return repo / "kitty-specs" / MISSION_SLUG


def _marker_stranded_wps(repo: Path) -> set[str]:
    """WP ids named by the persisted ``pending_coord_reconcile`` marker (∅ if none)."""
    state = load_state(repo, MISSION_ID)
    marker = state.pending_coord_reconcile if state is not None else None
    if not marker:
        return set()
    return {str(wp) for wp in marker["stranded_wp_ids"]}


def _coord_rollback_violation(repo: Path) -> set[str]:
    """Return the INV-COORD-ROLLBACK violation set (∅ ⇒ invariant holds).

    The strand is derived from the COMMITTED coordination ref via the single
    coordination authority :func:`coord_incoherent_done_wps` over this merge's
    write-set — never a committed-vs-working diff (empty at the mark point per
    data-model D7). The invariant holds when there is no strand OR every stranded
    WP is named by a ``pending_coord_reconcile`` marker (recoverable). A stranded
    WP with NO marker is the violation this guard exists to catch.
    """
    stranded = set(
        coord_incoherent_done_wps(
            COORD_BRANCH,
            _WRITE_SET,
            repo_root=repo,
            feature_dir=_feature_dir(repo),
        )
    )
    if not stranded:
        return set()
    return stranded - _marker_stranded_wps(repo)


def _assert_coord_rollback_invariant(repo: Path) -> None:
    """FR-008 behavioral guard: no rollback may strand a committed ``done`` unmarked."""
    _assert_no_violation(_coord_rollback_violation(repo))


def _assert_no_violation(unreconciled: set[str]) -> None:
    """The SINGLE assertion T015 drives both ways: GREEN with the real mark,
    RED (``AssertionError`` carrying ``INV-COORD-ROLLBACK``) when the mark is
    stubbed to a runtime no-op. Takes a violation set so it can judge the state
    observed at the bake phase's exit, before the #5385 rollback door runs.
    """
    assert not unreconciled, (
        "INV-COORD-ROLLBACK violated (FR-008): the committed coordination ref "
        f"strands {sorted(unreconciled)} at ``done`` while the working tree rolled "
        "back to ``approved`` and NO pending_coord_reconcile marker names it — a "
        "silent committed/working split-brain. The rollback must mark (or revert) "
        "the stranded coord ``done`` so it stays recoverable."
    )


# ===========================================================================
# T015 — behavioral falsifier: GREEN with the real mark, RED under a stubbed mark
# ===========================================================================


def _bake_failure_observed_at_phase_exit(repo: Path) -> dict[str, object]:
    """Drive a REAL #2367-B bake failure; observe the invariant at the bake phase's exit.

    The observation is taken after the phase's own byte restore + mark and before
    the driver's single rollback door (#5385) restores the coordination branch.
    """
    observed: dict[str, object] = {}

    def observe() -> None:
        observed["stranded"] = coord_incoherent_done_wps(
            COORD_BRANCH, _WRITE_SET, repo_root=repo, feature_dir=_feature_dir(repo)
        )
        observed["marker"] = _marker_stranded_wps(repo)
        observed["violation"] = _coord_rollback_violation(repo)

    with on_phase_failure("_phase_bake_and_pre_target_done", observe):
        exc, _calls = _run_bake_failing_merge(repo)
    assert isinstance(exc, RuntimeError), f"expected the injected bake fault; got {exc!r}"
    assert observed, "precondition: the bake phase must have failed (observation taken)"
    return observed


def test_guard_is_green_with_the_real_mark(tmp_path: Path) -> None:
    """With the real mark, a bake-path strand is recorded → the invariant holds.

    Drives a REAL #2367-B bake-mid-write-set failure. At the bake phase's exit the
    leg-b byte-restore has rolled the working tree back to ``approved`` while
    ``STRANDED_WP``'s committed coord ``done`` survives — a strand — but
    ``_persist_coord_reconcile_marker`` records it, so ``strand ∧ marked`` ⇒
    recoverable ⇒ INV-COORD-ROLLBACK holds.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)

    observed = _bake_failure_observed_at_phase_exit(repo)

    # Precondition: the strand genuinely exists (else the guard would be vacuously
    # green — nothing to reconcile). The real mark then names it.
    assert observed["stranded"] == [STRANDED_WP], "precondition: the bake path must strand exactly STRANDED_WP"
    assert observed["marker"] == {STRANDED_WP}, (
        "the real mark must record the stranded WP in pending_coord_reconcile"
    )

    # The behavioral guard is GREEN: strand present, but marked → recoverable.
    _assert_no_violation(cast("set[str]", observed["violation"]))


def test_guard_reds_when_persist_marker_is_stubbed_to_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-vacuity (FR-008 / SC-005): stub the marker-persist → the guard REDS.

    ``_persist_coord_reconcile_marker`` is monkeypatched to a runtime no-op and the
    SAME real bake strand is re-driven. At the phase's exit the leg-b byte-restore
    still ran (working → ``approved``) and ``STRANDED_WP``'s committed ``done``
    still survives, but NO marker names it → ``strand-on-committed-ref ∧
    marker-absent``. The behavioral guard must raise ``AssertionError`` — proving
    it is not a tautology that stays green regardless of whether the mark fires.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)

    monkeypatch.setattr(
        coord_strand, "_persist_coord_reconcile_marker", lambda run, error: None
    )
    observed = _bake_failure_observed_at_phase_exit(repo)

    # The strand is real (leg-b restore ran; committed ``done`` survives) …
    assert observed["stranded"] == [STRANDED_WP], "precondition: the strand must exist even with the mark stubbed"
    # … and, with the mark stubbed, unrecorded.
    assert observed["marker"] == set(), (
        "precondition: the stubbed mark must leave pending_coord_reconcile absent"
    )

    # The falsifier: the SAME guard that was green above now REDS.
    with pytest.raises(AssertionError, match="INV-COORD-ROLLBACK"):
        _assert_no_violation(cast("set[str]", observed["violation"]))
    assert observed["violation"] == {STRANDED_WP}


def test_guard_reds_when_strand_authority_is_stubbed_to_noop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Non-vacuity (second seam): stub the strand-derivation authority → guard REDS.

    ``executor.coord_incoherent_done_wps`` is monkeypatched to always return ``[]``.
    ``_persist_coord_reconcile_marker`` then derives an empty strand and writes no
    marker, while the leg-b byte-restore still strands ``STRANDED_WP``'s committed
    ``done``. The checker's OWN (unpatched) strand read still sees the strand at
    the phase's exit, so the behavioral guard REDS — falsifying the mark at the
    derivation seam as well as the persist seam.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)

    monkeypatch.setattr(
        coord_strand, "coord_incoherent_done_wps", lambda *args, **kwargs: []
    )
    observed = _bake_failure_observed_at_phase_exit(repo)

    assert observed["marker"] == set(), (
        "precondition: a no-op strand authority must leave the marker absent"
    )
    with pytest.raises(AssertionError, match="INV-COORD-ROLLBACK"):
        _assert_no_violation(cast("set[str]", observed["violation"]))
    assert observed["violation"] == {STRANDED_WP}


def test_rollback_door_restores_the_coordination_branch_and_clears_the_marker(tmp_path: Path) -> None:
    """#5385 driver level: after the door, no strand survives and no marker is left behind."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_two_wp_coord_mission(repo)
    pre_run_coord = _git(repo, "rev-parse", COORD_BRANCH).stdout.strip()

    exc, _calls = _run_bake_failing_merge(repo)

    assert isinstance(exc, RuntimeError), f"expected the injected bake fault; got {exc!r}"
    assert _git(repo, "rev-parse", COORD_BRANCH).stdout.strip() == pre_run_coord, "the door must restore the coordination branch"
    assert coord_incoherent_done_wps(COORD_BRANCH, _WRITE_SET, repo_root=repo, feature_dir=_feature_dir(repo)) == []
    assert _marker_stranded_wps(repo) == set(), "a full restore clears pending_coord_reconcile"
    _assert_coord_rollback_invariant(repo)


# ===========================================================================
# T016 — programmatic restore-site enumeration + topology-gating
# ===========================================================================

_EXECUTOR_PATH = Path(ex.__file__)
_PRIMITIVE = "_restore_and_guard_coord_coherence"
# WP09 (T048 / TAO-3): the final-bookkeeping restore compensator was retired to the
# SINGLE owner compensator ``restore_generated_artifact_snapshots``; the FR-008
# class-closer invariant (exactly one raw restore call, inside the marking
# primitive) is preserved under the new name.
_RAW_RESTORE = "restore_generated_artifact_snapshots"
_RECORD_DONE_PHASE = "_phase_record_done_and_project"
_DONE_GATE_TOKEN = "done_marked_before_target"
_RECORD_DONE_CALLEE = "_record_merged_wps_done_for_merge"
_PROJECT_CALLEE = "_project_status_bookkeeping_to_target"

# Restore-shape sites that route through the marking primitive today (≈407, 536,
# 670, 691, 701, 757, 786). Derived by enumerating the primitive's call-sites from
# the AST below — NOT hardcoded line numbers. This is a drift tripwire: if you add
# a legitimately-routed restore site, bump this AND confirm it routes; if you add a
# RAW restore, ``test_only_raw_restore_call_routes_through_the_primitive`` reds.
_EXPECTED_ROUTED_SITES = 7


def _load_executor_ast() -> tuple[ast.Module, dict[ast.AST, ast.AST]]:
    tree = ast.parse(_EXECUTOR_PATH.read_text(encoding="utf-8"), filename=str(_EXECUTOR_PATH))
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return tree, parents


def _call_name(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _calls_named(tree: ast.Module, name: str) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) == name]


def _path_to_root(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[ast.AST]:
    path: list[ast.AST] = [node]
    cur: ast.AST = node
    while cur in parents:
        cur = parents[cur]
        path.append(cur)
    return path


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    for anc in _path_to_root(node, parents)[1:]:
        if isinstance(anc, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return anc.name
    return ""


def _enclosing_if_tests(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> list[str]:
    """Unparsed test source of every ``If`` whose *body* (not ``orelse``) holds node."""
    path = _path_to_root(node, parents)
    tests: list[str] = []
    for lower, upper in zip(path, path[1:], strict=False):
        if isinstance(upper, ast.If) and lower in upper.body:
            tests.append(ast.unparse(upper.test))
    return tests


def _enclosing_except_try_body_callees(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> set[str]:
    """Callee names in the *try body* of the nearest ``Try`` whose handler holds node."""
    path = _path_to_root(node, parents)
    for lower, upper in zip(path, path[1:], strict=False):
        if isinstance(upper, ast.Try) and lower in upper.handlers:
            return {
                _call_name(n)
                for stmt in upper.body
                for n in ast.walk(stmt)
                if isinstance(n, ast.Call)
            }
    return set()
