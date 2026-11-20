"""The lane-approved done evidence names the approving actor, never the implementer (#5781 fold).

When an approved work package carries no ``review`` slot, done bookkeeping records lane-approved
evidence. It used to name the snapshot ``agent`` slot as the reviewer: that slot holds the
implementer, and since #5781 every claim path fills it, so an orchestrator-claimed work package
would have recorded its implementer as its own reviewer.
"""

from __future__ import annotations

import pytest

from specify_cli.consolidation.done_bookkeeping import _lane_approved_reviewer
from specify_cli.status.models import EventStream, Lane, StatusEvent

pytestmark = pytest.mark.fast


def _event(n: int, wp_id: str, from_lane: str, to_lane: str, actor: object) -> StatusEvent:
    return StatusEvent(
        event_id=f"01HXYZ{n:020d}",
        mission_slug="m",
        wp_id=wp_id,
        from_lane=Lane(from_lane),
        to_lane=Lane(to_lane),
        at=f"2026-11-20T00:00:{n:02d}+00:00",
        actor=actor,
        force=False,
        execution_mode="worktree",
    )


def _stream(*events: StatusEvent) -> EventStream:
    return EventStream(transitions=list(events), annotations=[])


def test_the_reviewer_is_the_actor_of_the_latest_approval() -> None:
    stream = _stream(
        _event(1, "WP01", "planned", "claimed", "claude"),
        _event(2, "WP01", "claimed", "in_progress", "claude"),
        _event(3, "WP01", "in_progress", "for_review", "claude"),
        _event(4, "WP01", "for_review", "in_review", "codex"),
        _event(5, "WP01", "in_review", "approved", "codex"),
    )

    assert _lane_approved_reviewer(stream, "WP01") == "codex"


def test_a_structured_approver_is_named_by_its_identity() -> None:
    approver = {"tool": "codex", "role": "reviewer", "profile": "reviewer-renata", "model": None}
    stream = _stream(_event(1, "WP01", "in_review", "approved", approver))

    assert _lane_approved_reviewer(stream, "WP01") == "codex"


def test_another_work_package_and_no_approval_yield_unknown() -> None:
    stream = _stream(
        _event(1, "WP02", "in_review", "approved", "codex"),
        _event(2, "WP01", "planned", "claimed", "claude"),
    )

    assert _lane_approved_reviewer(stream, "WP01") == "unknown"
