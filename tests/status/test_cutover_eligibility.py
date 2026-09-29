"""Tests for ``status.cutover_eligibility.mission_carries_event_log_runtime`` (WP03 campsite, T014).

FR-001 of mission ``mixed-lane-authorship-soundness-01M3M7Y0`` started
stamping a best-effort ``lane_head`` key onto ``policy_metadata`` for EVERY
persisted lane-mapped transition -- independent of claim state. Before this
WP, :func:`mission_carries_event_log_runtime` treated any non-empty
``policy_metadata`` as runtime-carrying evidence, which a bare stamp on a
never-claimed mission would have misclassified.

**Conservative fix (orchestrator decision, review-feedback-1 Issue 5):**
rather than re-keying on the claim triple alone (which would also have
stopped counting approval/pre-review-gate/migration ``policy_metadata``
shapes that carried no claim keys, a broader narrowing than intended), the
predicate excludes ONLY a ``policy_metadata`` dict whose keys are entirely
``lane_head`` (or empty). Every other shape -- a real claim, an
APPROVED/DONE hop's ``tool``/``profile``/``model``/``shell_pid``
(``tasks_move_task._mt_approval_policy_metadata``), etc. -- keeps counting
exactly as it did before WP03.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.status.cutover_eligibility import mission_carries_event_log_runtime
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = pytest.mark.fast

_MISSION_SLUG = "cutover-eligibility-wp03"
_MISSION_ID = "01CUTOVERWP03000000000001"


def _genesis_to_planned(*, event_id: str) -> StatusEvent:
    return StatusEvent(
        event_id=event_id,
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.GENESIS,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:00:00+00:00",
        actor="seed",
        force=False,
        reason="seed",
        execution_mode="worktree",
    )


def test_no_event_log_is_not_detected(tmp_path: Path) -> None:
    assert mission_carries_event_log_runtime(tmp_path) is False


def test_bootstrap_only_events_are_not_detected(tmp_path: Path) -> None:
    """A ``genesis -> planned`` bootstrap anchor carries no runtime signal at all."""
    append_event(tmp_path, _genesis_to_planned(event_id="01BOOTSTRAPONLYAAAAAAAAAA1"))

    assert mission_carries_event_log_runtime(tmp_path) is False


def test_claim_policy_metadata_is_detected(tmp_path: Path) -> None:
    """A real ``planned -> claimed`` claim (``shell_pid``/``agent`` keys) IS evidence."""
    append_event(tmp_path, _genesis_to_planned(event_id="01CLAIMDETECTEDAAAAAAAAA1"))
    claim = StatusEvent(
        event_id="01CLAIMDETECTEDAAAAAAAAA2",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.CLAIMED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=False,
        execution_mode="worktree",
        policy_metadata=build_claim_policy_metadata(
            shell_pid=1234,
            shell_pid_created_at="2026-01-01T00:00:30+00:00",
            agent="claude",
        ),
    )
    append_event(tmp_path, claim)

    assert mission_carries_event_log_runtime(tmp_path) is True


def test_approval_only_policy_metadata_is_detected(tmp_path: Path) -> None:
    """Conservative fix (Issue 5): an APPROVED/DONE hop's ``tool``/``profile``/``model``
    sidecar (``tasks_move_task._mt_approval_policy_metadata``) carries no claim keys at
    all, yet must still count as runtime evidence -- the exact shape a claim-keys-only
    re-key (the rejected alternative) would have stopped detecting.
    """
    append_event(tmp_path, _genesis_to_planned(event_id="01APPROVALONLYAAAAAAAAA01"))
    approval_only = StatusEvent(
        event_id="01APPROVALONLYAAAAAAAAA02",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.IN_REVIEW,
        to_lane=Lane.APPROVED,
        at="2026-01-01T00:02:00+00:00",
        actor="reviewer-1",
        force=False,
        execution_mode="worktree",
        policy_metadata={"tool": "reviewer-1", "profile": None, "model": None},
    )
    append_event(tmp_path, approval_only)

    assert mission_carries_event_log_runtime(tmp_path) is True


def test_lane_head_only_policy_metadata_is_not_detected(tmp_path: Path) -> None:
    """FR-001 regression guard: a bare ``lane_head`` stamp is NOT runtime evidence.

    A transition that carries only the WP03 lane-head stamp (no other keys)
    must not flip a never-claimed mission to "runtime-carrying" -- the exact
    misclassification a bare ``bool(policy_metadata)`` check would produce.
    """
    append_event(tmp_path, _genesis_to_planned(event_id="01LANEHEADONLYAAAAAAAAA1"))
    stamped_but_unclaimed = StatusEvent(
        event_id="01LANEHEADONLYAAAAAAAAA2",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=True,
        reason="re-anchor",
        execution_mode="worktree",
        policy_metadata={"lane_head": "d" * 40},
    )
    append_event(tmp_path, stamped_but_unclaimed)

    assert mission_carries_event_log_runtime(tmp_path) is False


def test_empty_policy_metadata_is_not_detected(tmp_path: Path) -> None:
    append_event(tmp_path, _genesis_to_planned(event_id="01EMPTYMETADATAAAAAAAAA01"))
    empty_metadata = StatusEvent(
        event_id="01EMPTYMETADATAAAAAAAAA02",
        mission_slug=_MISSION_SLUG,
        mission_id=_MISSION_ID,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.PLANNED,
        at="2026-01-01T00:01:00+00:00",
        actor="claude",
        force=True,
        reason="re-anchor",
        execution_mode="worktree",
        policy_metadata={},
    )
    append_event(tmp_path, empty_metadata)

    assert mission_carries_event_log_runtime(tmp_path) is False
