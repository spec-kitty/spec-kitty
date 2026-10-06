"""Scope: #2786 — a coordination ``done`` the rollback cannot undo must stay recoverable (permanent guard).

**Contract since #5385 (single rollback door).** The executor no longer reverts
the committed coordination ``done`` with ``git revert``; the driver's single
rollback door CAS-restores the coordination branch to its pre-run snapshot. The
#2786 failure class (the undo of the committed ``done`` fails, so a committed
``done`` survives against a working tree byte-restored to ``approved``) therefore
has a new trigger: the authority cannot restore the coordination branch because
another actor moved it after this run's last recorded tip. This module pins the
successor contract end-to-end:

* the rollback reports the coordination branch ``NOT restored`` and keeps the
  record;
* the ``pending_coord_reconcile`` marker written inside the phase stays set
  (the authority clears it only after a full restore), naming the stranded WP;
* a ``--resume`` runs the resume-start heal (``_heal_pending_coord_reconcile``
  -> ``coordination.coherence.repair_coord_strand``), which reconciles the
  committed reduction with the working tree and clears the marker.

History (pre-#5385): #2786 was the swallowed failure of
``executor._revert_coord_done_commit``'s forward ``git revert`` (abort + warning
+ silent return). That helper and its forced-revert-failure harness were retired
with #5385; the #2711 harness (``test_issue_2711_merge_rollback_resume_coherence``)
still drives the mission, and the target-advance failure is injected at
``specify_cli.lanes.consolidation.integrate_mission_into_target``.
"""

from __future__ import annotations

import functools
from pathlib import Path
from unittest.mock import patch

import pytest

# Import the status package before any coordination submodule (mirror the
# production import order; see the #2711 harness module docstring for rationale).
import specify_cli.status  # noqa: F401  # import-order guard

from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.coordination.status_service import wp_lane_actor_from_events
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.state import load_state
from specify_cli.status import Lane

# Reuse the fused coord-topology harness (never edited in place — WP01/WP02 note).
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    _INJECTED_TARGET_FAILURE,
    COORD_BRANCH,
    MID8,
    MISSION_ID,
    WP_ID,
    _assert_pre_target_done_path,
    _bootstrap_coord_mission,
    _committed_coord_events,
    _git,
    _init_git_repo,
    _merge_external_mocks,
    _working_coord_events,
)
from tests.consolidation.test_issue_2367_bake_strand import foreign_coord_commit, on_phase_failure

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

MISSION_SLUG = "merge-rollback-2711-01KXRRB7"  # harness slug (isolated per tmp repo)


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


def _run_merge_with_target_failing(repo: Path, *, coord_moved_by_another_actor: bool) -> BaseException:
    """Run one merge pass whose target advance fails AFTER the pre-target ``done`` commit.

    With ``coord_moved_by_another_actor`` another actor commits on the
    coordination branch at the failing phase's exit (before the driver's rollback
    door runs), so the door cannot restore that branch. Returns the propagated
    exception (asserted by callers to be the injected target-advance fault).
    """
    foreign = functools.partial(foreign_coord_commit, repo, MISSION_SLUG, MID8)
    with (
        _merge_external_mocks(),
        patch(
            "specify_cli.lanes.consolidation.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_TARGET_FAILURE),
        ),
        on_phase_failure("_phase_mission_to_target", foreign if coord_moved_by_another_actor else _nothing),
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
            return exc
    raise AssertionError(
        "precondition: injected target-advance failure did not propagate — the "
        "merge unexpectedly succeeded, so the rollback path never ran."
    )


def _nothing() -> None:
    return None


def _marker_wps(repo: Path) -> list[str] | None:
    state = load_state(repo, MISSION_ID)
    marker = state.pending_coord_reconcile if state is not None else None
    return [str(wp) for wp in marker["stranded_wp_ids"]] if marker else None


def test_unrestorable_coordination_branch_keeps_the_marker_and_the_resume_heals(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#2786 successor (#5385): the door cannot restore a moved coordination branch; the marker survives; the resume heals.

    1. Pass 1: the pre-target ``done`` commits, the target advance fails, and
       another actor commits on the coordination branch before the door runs. The
       door reports the coordination branch NOT restored and keeps the record; the
       committed ``done`` is stranded and the marker names the WP (recoverable,
       never silent). Since #5638 the door brings the coordination checkout back to
       the tip it keeps, so the working tree reads that ``done`` too, not the
       byte-restored ``approved``.
    2. Pass 2 (``--resume``): the resume-start heal reverts the stranded ``done``;
       committed and working reductions agree and the marker is cleared. The
       other actor's commit survives.
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)
    _assert_pre_target_done_path(repo)

    exc = _run_merge_with_target_failing(repo, coord_moved_by_another_actor=True)
    output = " ".join(capsys.readouterr().out.split())

    assert isinstance(exc, RuntimeError) and _INJECTED_TARGET_FAILURE in str(exc), (
        f"the ORIGINAL target-advance fault must propagate; got {exc!r}"
    )
    assert f"NOT restored {COORD_BRANCH}" in output and "moved by another actor" in output, (
        f"the door must report the moved coordination branch NOT restored. output={output}"
    )
    assert load_state(repo, MISSION_ID) is not None, "a partial rollback keeps the record"
    committed_lane_pre, working_lane_pre = _reduce_coord_lanes(repo, feature_dir)
    assert (committed_lane_pre, working_lane_pre) == (Lane.DONE, Lane.DONE), (
        "the committed ``done`` is stranded and the coordination checkout matches the kept tip (#5638); "
        f"got committed={committed_lane_pre} working={working_lane_pre}"
    )
    assert _marker_wps(repo) == [WP_ID], "the strand must stay marked for the resume-start heal"
    foreign_tip = _git(repo, "rev-parse", COORD_BRANCH).stdout.strip()

    resume_exc = _run_merge_with_target_failing(repo, coord_moved_by_another_actor=False)
    assert isinstance(resume_exc, RuntimeError) and _INJECTED_TARGET_FAILURE in str(resume_exc), (
        f"the resume must run through to the injected fault again; got {resume_exc!r}"
    )

    committed_lane, working_lane = _reduce_coord_lanes(repo, feature_dir)
    assert committed_lane == working_lane == Lane.APPROVED, (
        "the resume-start heal must reconcile the strand: "
        f"committed={committed_lane} working={working_lane}"
    )
    assert _marker_wps(repo) is None, "the marker is cleared once the heal reconciled the strand"
    assert _git(repo, "merge-base", "--is-ancestor", foreign_tip, COORD_BRANCH).returncode == 0, (
        "the other actor's commit must survive the heal and the rollback"
    )
