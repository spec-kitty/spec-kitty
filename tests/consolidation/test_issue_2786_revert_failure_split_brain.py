"""Scope: #2786 — a FAILED coord ``done`` revert during rollback is swallowed (permanent guard; #2786 FIXED).

**Landing note (2026-08, `tests/regression/` campsite clean).** Relocated
from `tests/regression/` to `tests/merge/` — its functional home alongside
the other merge-executor / coordination-rollback tests — now that #2786 is
fixed and this is a green permanent guard, not a red-first reproduction (no
`regression` marker). The issue number is kept as history.

This module reproduces **#2786** and now guards its fix. It began as an
INTENTIONAL, issue-pinned red-first P0 reproduction (per ADR
``docs/adr/3.x/2026-07-17-1``, expected to fail on ``main`` while the P0 was
open). #2786 is now **FIXED** — the rollback marks-not-raises and a strand-gated
``git revert`` heal on ``--resume`` restores coherence — so the reproduction
drives the strand and asserts coherence AFTER the heal. The ``regression`` marker
(which flagged the intentional-red-on-``main`` phase) is removed now that the
defect is closed; the test stays a green regression guard via its ``git_repo`` marker.

Defect (#2786)
--------------
The #2711 Option-A rollback reverts the committed coordination ``done`` commit in
lockstep with the working-tree byte restore
(``specify_cli.consolidation.executor._revert_coord_done_commit``). That revert is
**best-effort**: when the coord-worktree ``git revert`` itself FAILS (a conflict,
a dirty index, a broken worktree), the helper merely runs ``git revert --abort``,
logs a ``warning``, and RETURNS — it neither raises nor writes any durable
reconcile marker (executor.py, the ``if revert.returncode != 0:`` branch).

Consequently the committed coordination ``done`` survives while the working tree
is rolled back to ``approved`` by ``_restore_final_bookkeeping_snapshots`` — the
#2711 split-brain silently RE-OPENS along the revert-failure path that the
Option-A fix did not close. Nothing durable records that the two surfaces
diverged, so a later resume/merge cannot detect the incoherence either.

Reproduction strategy
---------------------
Reuse the proven coord-topology full-merge harness fused in
``test_issue_2711_merge_rollback_resume_coherence`` (itself modeled on the #1772
coord-branch harness the WP02/WP04 work used) and drive the pre-existing entry
point ``_run_lane_based_consolidation``:

* the mission records the per-WP ``approved -> done`` transition on the
  coordination branch BEFORE the target advance (``done_marked_before_target``);
* the target advance is injected to FAIL (``integrate_mission_into_target``),
  triggering the #2711 rollback path;
* the coord-worktree ``git revert`` is forced to return non-zero — exercising the
  REAL ``if revert.returncode != 0:`` failure branch of ``_revert_coord_done_commit``
  (abort + warning + silent return), the exact swallowed-failure path under test.

The coherence assertion (``committed_lane == working_lane``) then FAILS for the
RIGHT reason: the committed coordination reduction is stranded at ``done`` while
the rolled-back working tree reduces to ``approved`` — the swallowed-revert
split-brain. A non-vacuity witness proves the revert branch was actually hit and
returned non-zero, so the red cannot pass as a setup artefact.

#2786 is FIXED — the rollback marks-not-raises (durable ``pending_coord_reconcile``
marker) and the resume heal reverts the stranded coord ``done`` via a strand-gated
``git revert``; this module verifies coherence is restored after the heal and guards
against regression.
"""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the status package before any coordination submodule (mirror the
# production import order; see the #2711 harness module docstring for rationale).
import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.coordination.status_service import wp_lane_actor_from_events
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.status import Lane

# Reuse the fused coord-topology harness (never edited in place — WP01/WP02 note).
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    _INJECTED_TARGET_FAILURE,
    WP_ID,
    _assert_pre_target_done_path,
    _bootstrap_coord_mission,
    _committed_coord_events,
    _init_git_repo,
    _merge_external_mocks,
    _working_coord_events,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "merge-rollback-2711-01KXRRB7"  # harness slug (isolated per tmp repo)
_INJECTED_REVERT_FAILURE = "injected #2786 coord revert conflict"


@contextlib.contextmanager
def _revert_forced_to_fail() -> Iterator[list[list[str]]]:
    """Force the coord-worktree ``git revert`` to return non-zero.

    Intercepts ONLY the forward ``git revert --no-edit <range>`` subprocess call
    inside ``_revert_coord_done_commit`` and returns a non-zero
    ``CompletedProcess`` — exercising the real ``if revert.returncode != 0:``
    failure branch (abort + warning + silent return). Every other subprocess call
    (``rev-parse HEAD``, the follow-up ``git revert --abort``, and all unrelated
    git plumbing) delegates unchanged to the real ``subprocess.run``, so the merge
    flow is otherwise untouched.

    Yields the list of intercepted revert commands so the caller can assert the
    failure branch was genuinely reached (non-vacuity).
    """
    real_run = subprocess.run
    intercepted: list[list[str]] = []

    # A ``subprocess.run`` shim: fully typing it would mean re-declaring
    # ``run``'s large overload set for a two-line test double — mypy is correct
    # that it is untyped, but a faithful annotation adds no safety here.
    def fake_run(cmd, *args, **kwargs):  # type: ignore[no-untyped-def]
        if isinstance(cmd, list) and "revert" in cmd and "--abort" not in cmd:
            intercepted.append(list(cmd))
            return subprocess.CompletedProcess(
                cmd, returncode=1, stdout="", stderr=_INJECTED_REVERT_FAILURE
            )
        return real_run(cmd, *args, **kwargs)

    with patch("specify_cli.consolidation.executor.subprocess.run", side_effect=fake_run):
        yield intercepted


def _reduce_coord_lanes(repo: Path, feature_dir: Path) -> tuple[Lane, Lane]:
    """Reduce ``(committed_lane, working_lane)`` for the mission's WP.

    ``committed_lane`` is the reduction of the events COMMITTED to the
    coordination branch (contract-routed via
    ``EventLogReadContract.coordination_branch_ref``); ``working_lane`` is the
    reduction of the coordination worktree's rolled-back WORKING-tree event log.
    Both legs are git-reducible — no marker/doctor surface is consulted.
    """
    committed_lane = wp_lane_actor_from_events(
        _committed_coord_events(repo, feature_dir), WP_ID
    ).lane
    working_lane = wp_lane_actor_from_events(_working_coord_events(repo), WP_ID).lane
    return committed_lane, working_lane


def _run_merge_with_target_and_revert_failing(
    repo: Path,
) -> tuple[BaseException, list[list[str]]]:
    """Run one merge pass: target advance fails AND the coord revert fails.

    Returns the propagated exception (asserted to be the injected target-advance
    fault) and the intercepted revert commands (asserted non-empty).

    Re-invoked as the ``spec-kitty merge --resume`` heal step: on the mission
    base the second pass detects ``is_resume`` from the persisted ``ConsolidationState``
    and re-drives the same failing merge, so the injected target-advance fault is
    re-raised (and caught here) while the pre-existing strand is left untouched —
    the resume no-ops the coherence heal until WP03 lands it.
    """
    with (
        _merge_external_mocks(),
        patch(
            "specify_cli.lanes.consolidation.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_TARGET_FAILURE),
        ),
        _revert_forced_to_fail() as intercepted,
    ):
        try:
            _run_lane_based_consolidation(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )
        except BaseException as exc:  # noqa: BLE001 — the act under test raises by design
            return exc, intercepted
    raise AssertionError(
        "precondition: injected target-advance failure did not propagate — the "
        "merge unexpectedly succeeded, so the #2711/#2786 rollback path never ran."
    )


def test_swallowed_revert_failure_re_opens_2711_split_brain(tmp_path: Path) -> None:
    """#2786 (RED): a FAILED coord ``done`` revert during rollback is swallowed,
    leaving the committed coordination ``done`` opposed to the rolled-back working
    ``approved`` — the #2711 split-brain re-opened along the revert-failure path —
    and a ``spec-kitty merge --resume`` heal does NOT restore coherence.

    Assert-after-heal contract (FR-001 / SC-006). The pre-fix synchronous
    ``committed_lane == working_lane`` assertion had **no resume step**: under the
    mark-not-raise fix (FR-005) the committed ``done`` is *deliberately* stranded
    until repair, so a synchronous coherence assertion could never go green
    (permanent red — violates SC-001/SC-004). This test instead:

    1. drives the swallowed-revert strand and WITNESSES it (committed ``done`` vs
       working ``approved``) — a state that survives the mark-not-raise fix;
    2. invokes the ``spec-kitty merge --resume`` heal (a no-op on the mission base
       — the coherence-repair entry lands in WP03, so the resume merely re-drives
       the still-failing merge and is caught, leaving the strand untouched);
    3. asserts ``committed_lane == working_lane`` **re-reduced from the coord ref
       AFTER the heal** — RED on the mission base because the no-op resume leaves
       the strand; GREEN once WP03's strand-gated ``git revert`` heal reconciles
       the committed ``done`` back to ``approved``.

    A bare deletion of the coherence assertion would fail SC-006 — it is
    *modified* (moved past the heal step + paired with the pre-heal witness), not
    removed. No marker/doctor surface is referenced (git-reducible reds only).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)

    # Non-vacuity witness A (BEFORE the act): the mission routes status onto the
    # coordination worktree, so a ``done`` is committed pre-target.
    _assert_pre_target_done_path(repo)

    exc, revert_cmds = _run_merge_with_target_and_revert_failing(repo)

    # Non-vacuity witness B: the merge failed via the injected target-advance fault
    # (AFTER the pre-target ``done`` commit), so a ``done`` genuinely landed.
    assert isinstance(exc, RuntimeError) and _INJECTED_TARGET_FAILURE in str(exc), (
        "precondition: the merge must fail via the injected target-advance fault "
        f"(RuntimeError, AFTER the pre-target done commit); got {exc!r}"
    )

    # Non-vacuity witness C: the swallowed-revert branch was genuinely exercised —
    # the coord-worktree ``git revert`` was attempted and forced to return non-zero.
    assert revert_cmds, (
        "precondition: the coord ``done`` revert was never attempted, so the "
        "#2786 revert-failure branch (_revert_coord_done_commit) did not run — "
        "the reproduction would be vacuous."
    )

    committed_lane_pre, working_lane_pre = _reduce_coord_lanes(repo, feature_dir)

    # Precondition: the working tree DID roll back to ``approved`` (the byte-restore
    # leg still runs after the swallowed revert failure).
    assert working_lane_pre == Lane.APPROVED, (
        "precondition: the rolled-back working tree should reduce to ``approved``; "
        f"got {working_lane_pre}"
    )

    # Pre-heal WITNESS (the strand exists): the swallowed revert leaves the
    # committed coordination reduction stranded at ``done`` — the exact incoherence
    # the mark-not-raise fix records durably and the heal must reconcile. GREEN on
    # base AND after the mark-not-raise fix (the strand is deliberate pre-repair).
    assert committed_lane_pre == Lane.DONE, (
        "precondition: the swallowed-revert strand must exist — the committed "
        "coordination ``done`` should survive the rollback while the working tree "
        f"rolls back to ``approved``; got committed={committed_lane_pre}"
    )

    # Heal step — ``spec-kitty merge --resume``. On the mission base no coherence
    # repair entry exists (it lands in WP03), so the resume re-drives the same
    # failing merge: the injected target-advance fault re-raises and is caught
    # here, proving the resume RAN through to the rollback path (not an
    # AttributeError/infra early-abort). The strand is left in place — the heal
    # no-ops today.
    resume_exc, _resume_reverts = _run_merge_with_target_and_revert_failing(repo)
    assert isinstance(resume_exc, RuntimeError) and _INJECTED_TARGET_FAILURE in str(
        resume_exc
    ), (
        "the ``merge --resume`` heal step must RUN through to the injected "
        "target-advance fault (proving the resume reached the rollback path, not "
        f"an infra/AttributeError early-abort); got {resume_exc!r}"
    )

    committed_lane, working_lane = _reduce_coord_lanes(repo, feature_dir)

    # Coherence CONTRACT (RED on base, SC-006): after the heal the committed
    # coordination reduction and the working-tree reduction must AGREE. On the
    # mission base they still disagree because the no-op resume left the swallowed
    # ``done`` stranded (``_revert_coord_done_commit`` logged a warning and
    # returned; no durable reconcile marker; no strand-gated heal). The #2786 fix
    # (mark-not-raise + strand-gated ``git revert`` heal on ``--resume``) flips
    # this GREEN.
    assert committed_lane == working_lane, (
        "#2786 swallowed-revert split-brain (post-heal): the coord-worktree "
        "``git revert`` FAILED during rollback and _revert_coord_done_commit "
        "swallowed it (warning + return, no raise, no durable reconcile marker), "
        "and ``merge --resume`` did NOT reconcile the strand, so the committed "
        "coordination ``done`` remains stranded against the rolled-back working "
        "``approved``.\n"
        f"  committed coord ref (git-tracked): {committed_lane}\n"
        f"  rolled-back working tree:          {working_lane}\n"
        "The revert-failure path must record a durable reconcile marker and "
        "``--resume`` must heal it so the divergence is never silent (#2786)."
    )
