"""IC-04 / WP05 — snapshot-sourced done-evidence + rerouted bypass readers.

Scope: the merge gate's event-sourced done-evidence read (built in T018 BEFORE
the frontmatter synthesis is deleted in T020 — the C-001 proof), the shared
review-slot reader, the ``workflow_cores`` frontmatter-fallback deletion
(FR-006a/FR-007), and the ``tasks_move_task`` ownership read reroute (FR-007).

No test mocks ``wp_snapshot_state`` / the reducer / ``resolve_snapshot_review``
to force a pass — every review slot is seeded as a real ``InnerStateChanged``
annotation over a real event log. Only the git-transactional lane read/write
helpers are isolated (the same pattern the existing merge unit tests use), so
the reviewer identity in the emitted evidence comes solely from the seeded
snapshot slot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.missions._read_path_resolver import resolve_planning_read_dir
from specify_cli.status import (
    CurrentWpState,
    Lane,
    ReviewOverride,
    WPInnerStateDelta,
    emit_inner_state_changed,
    read_event_stream,
    resolve_snapshot_review,
)

pytestmark = pytest.mark.fast

_MISSION_SLUG = "021-test"


def _seed_mission(repo_root: Path, *, review_status: str = "", reviewed_by: str = "") -> Path:
    """Create ``kitty-specs/<slug>/`` with meta.json + a WP file, return feature_dir.

    ``review_status``/``reviewed_by`` default to empty — an event-only mission
    carries NO frontmatter review authority.
    """
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": "01TEST00000000000000000000", "mission_slug": _MISSION_SLUG}),
        encoding="utf-8",
    )
    (tasks_dir / "WP01-test.md").write_text(
        "\n".join(
            [
                "---",
                'work_package_id: "WP01"',
                'title: "Test WP"',
                "dependencies: []",
                f'review_status: "{review_status}"',
                f'reviewed_by: "{reviewed_by}"',
                "---",
                "# WP01",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return resolve_planning_read_dir(
        repo_root, _MISSION_SLUG, kind=MissionArtifactKind.WORK_PACKAGE_TASK
    )


def _seed_review_slot(feature_dir: Path, wp_id: str, *, actor: str, reason: str = "approved") -> None:
    """Seed a real snapshot ``review`` slot as an off-axis InnerStateChanged."""
    emit_inner_state_changed(
        feature_dir,
        wp_id,
        WPInnerStateDelta(
            review=ReviewOverride(
                at="2026-07-20T12:00:00+00:00",
                actor=actor,
                wp_id=wp_id,
                reason=reason,
            )
        ),
        actor=actor,
        mission_slug=_MISSION_SLUG,
    )


def _isolate_transactional_lane(monkeypatch: Any, emit_mock: Mock, *, lane: Lane) -> None:
    """Isolate ONLY the git-transactional lane read/write helpers (not the reducer)."""
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.emit_status_transition_transactional",
        emit_mock,
    )
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.read_current_wp_state_transactional",
        lambda **_kw: CurrentWpState(lane, "prior-actor", None),
    )
    monkeypatch.setattr(
        "specify_cli.coordination.status_transition.has_transition_to_transactional",
        lambda **_kw: False,
    )


# ---------------------------------------------------------------------------
# T023 test 1 — event-only merge evidence (C-001 guard, non-vacuous)
# ---------------------------------------------------------------------------


def test_event_only_mission_reaches_done_with_snapshot_evidence(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A mission whose approval lives ONLY in the snapshot ``review`` slot (no
    frontmatter review) reaches ``done`` with correct DoneEvidence through the
    merge path — proving T018's event-sourced read BEFORE T020 deletes the
    frontmatter synthesis (C-001 / D-05).
    """
    from specify_cli.consolidation.done_bookkeeping import _mark_wp_merged_done

    feature_dir = _seed_mission(tmp_path)  # event-only: no frontmatter review
    _seed_review_slot(feature_dir, "WP01", actor="reviewer-snap")

    emit_mock = Mock()
    _isolate_transactional_lane(monkeypatch, emit_mock, lane=Lane.APPROVED)

    _mark_wp_merged_done(tmp_path, _MISSION_SLUG, "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.to_lane == "done"
    assert request.actor == "merge"
    # Reviewer identity comes from the seeded snapshot ``review.actor`` — NOT
    # frontmatter (there is none) and NOT the lane-approved ``metadata.agent``.
    assert request.evidence["review"]["reviewer"] == "reviewer-snap"
    assert request.evidence["review"]["verdict"] == "approved"
    assert request.evidence["review"]["reference"] == "snapshot-review:WP01"


def test_event_only_evidence_is_non_vacuous_without_snapshot_slot(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Guard: with NO snapshot review slot and NO frontmatter review, the merge
    path falls through to the lane-approved fallback (reference != snapshot).

    This pins that the ``snapshot-review:`` reference in the test above is
    produced by the seeded slot, not by any residual frontmatter/lane path.
    """
    from specify_cli.consolidation.done_bookkeeping import _mark_wp_merged_done

    _seed_mission(tmp_path)  # event-only, and NO review slot seeded

    emit_mock = Mock()
    _isolate_transactional_lane(monkeypatch, emit_mock, lane=Lane.APPROVED)

    _mark_wp_merged_done(tmp_path, _MISSION_SLUG, "WP01", "main")

    emit_mock.assert_called_once()
    request = emit_mock.call_args.args[0]
    assert request.to_lane == "done"
    assert request.evidence["review"]["reference"] == "lane-approved:WP01"


# ---------------------------------------------------------------------------
# T023 test 2 — shared review-slot reader (one canonical interpretation)
# ---------------------------------------------------------------------------


def test_resolve_snapshot_review_returns_typed_override_or_none(tmp_path: Path) -> None:
    feature_dir = _seed_mission(tmp_path)
    _seed_review_slot(feature_dir, "WP01", actor="reviewer-snap", reason="approved after fix")

    override = resolve_snapshot_review(feature_dir, "WP01")
    assert override is not None
    assert override.actor == "reviewer-snap"
    assert override.wp_id == "WP01"
    assert override.reason == "approved after fix"

    # A WP with no review slot → None (never raises for the absent case).
    assert resolve_snapshot_review(feature_dir, "WP02") is None


def test_empty_actor_review_slot_is_treated_as_absent(tmp_path: Path) -> None:
    """A snapshot review slot with a blank ``actor`` must not synthesize a
    ``reviewer=""`` approval — the merge helper treats it as absent."""
    from specify_cli.consolidation.done_bookkeeping import _resolve_snapshot_done_evidence

    feature_dir = _seed_mission(tmp_path)
    _seed_review_slot(feature_dir, "WP01", actor="   ")  # whitespace-only actor

    assert _resolve_snapshot_done_evidence(read_event_stream(feature_dir), "WP01") is None


def test_shared_reader_is_the_single_canonical_interpretation() -> None:
    """The facade and module expose ONE event-stream review reader,
    and the merge gate's done-evidence helper consumes it (D-14: the merge gate
    and the CLI cannot diverge on the review slot's interpretation)."""
    import specify_cli.status as status_facade
    import specify_cli.status.wp_review as wp_review

    assert status_facade.resolve_event_stream_review is wp_review.resolve_event_stream_review


def test_done_evidence_helper_consumes_the_shared_reader(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """``_resolve_snapshot_done_evidence`` routes through ``resolve_snapshot_review``
    (the shared reader), so patching the shared symbol changes the merge helper's
    output — the single interpretation seam, not a re-derived one."""
    import specify_cli.status as status_facade
    from specify_cli.consolidation import done_bookkeeping

    feature_dir = _seed_mission(tmp_path)
    _seed_review_slot(feature_dir, "WP01", actor="reviewer-snap")

    calls: list[str] = []
    real = status_facade.resolve_event_stream_review

    def _tracking(event_stream: Any, wp: str) -> Any:
        calls.append(wp)
        return real(event_stream, wp)

    monkeypatch.setattr(status_facade, "resolve_event_stream_review", _tracking)

    evidence = done_bookkeeping._resolve_snapshot_done_evidence(
        read_event_stream(feature_dir), "WP01"
    )
    assert evidence is not None
    assert evidence.review.reviewer == "reviewer-snap"
    assert calls == ["WP01"]


# ---------------------------------------------------------------------------
# T023 test 3 — workflow_cores: frontmatter review is no longer authority
# ---------------------------------------------------------------------------

_EVID = "01J8Z9ABCDEFGHJKMNPQRSTVWX"


def test_workflow_cores_frontmatter_feedback_is_not_authority(tmp_path: Path) -> None:
    """FR-006a/FR-007: a mission with frontmatter ``review_status: has_feedback``
    but NO canonical ``review_ref`` event now returns "no feedback present" — the
    frontmatter fallback is deleted."""
    from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_context

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    frontmatter = 'review_status: "has_feedback"\nreview_feedback: "legacy-ref"\n'

    result = resolve_review_feedback_context(feature_dir, "WP01", frontmatter)

    assert result == (False, None, None, None)


def test_workflow_cores_canonical_review_ref_wins(tmp_path: Path) -> None:
    """The canonical event read (``event.review_ref``) is the sole authority and
    reports source ``"canonical"``."""
    from specify_cli.cli.commands.agent.workflow_cores import resolve_review_feedback_context
    from specify_cli.status.models import StatusEvent
    from specify_cli.status.store import append_event

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    append_event(
        feature_dir,
        StatusEvent(
            event_id=_EVID,
            mission_slug=_MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.IN_PROGRESS,
            at="2026-07-20T12:00:00+00:00",
            actor="reviewer",
            force=False,
            execution_mode="worktree",
            review_ref="review-cycle://mission/WP01/review-cycle-1.md",
        ),
    )

    has_feedback, ref, _path, source = resolve_review_feedback_context(feature_dir, "WP01", "")

    assert has_feedback is True
    assert ref == "review-cycle://mission/WP01/review-cycle-1.md"
    assert source == "canonical"


# ---------------------------------------------------------------------------
# T023 test 4 — tasks_move_task ownership read resolves the snapshot
# ---------------------------------------------------------------------------


def _make_move_task_state(tmp_path: Path, **overrides: object) -> Any:
    """Minimal ``_MoveTaskState`` mirroring the sibling move-task test builders."""
    from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState

    kwargs: dict[str, object] = {
        "task_id": "WP01",
        "to": "in_progress",
        "mission": None,
        "agent": None,
        "assignee": None,
        "shell_pid": None,
        "note": None,
        "review_feedback_file": None,
        "approval_ref": None,
        "reviewer": None,
        "self_review_fallback": False,
        "intended_reviewer": None,
        "reviewer_failure_reason": None,
        "done_override_reason": None,
        "force": False,
        "tracker_ref": None,
        "skip_review_artifact_check": False,
        "auto_commit": None,
        "json_output": False,
        "mission_slug": _MISSION_SLUG,
    }
    kwargs.update(overrides)
    return _MoveTaskState(**kwargs)


def test_mt_resolve_current_agent_reads_snapshot_slot(tmp_path: Path) -> None:
    """FR-007: the extracted ownership helper resolves the snapshot ``agent`` slot
    (not ``extract_scalar(frontmatter, "agent")``)."""
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_current_agent

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    emit_inner_state_changed(
        feature_dir,
        "WP01",
        WPInnerStateDelta(agent="claude-runtime"),
        actor="claude-runtime",
        mission_slug=_MISSION_SLUG,
    )
    st = _make_move_task_state(tmp_path)
    st.feature_dir = feature_dir

    assert _mt_resolve_current_agent(st) == "claude-runtime"


def test_mt_resolve_current_agent_none_for_unclaimed_wp(tmp_path: Path) -> None:
    """An unclaimed WP (no snapshot ``agent`` slot) resolves to ``None`` — matching
    the pre-reroute "no agent in frontmatter" result."""
    from specify_cli.cli.commands.agent.tasks_move_task import _mt_resolve_current_agent

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    st = _make_move_task_state(tmp_path)
    st.feature_dir = feature_dir

    assert _mt_resolve_current_agent(st) is None
