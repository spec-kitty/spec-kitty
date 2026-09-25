"""Tests for WP02: verdict guard + lane guard UX improvements.

Covers:
- T009: approve/done after a ``rejected`` verdict now persists a fresh approved
  artifact instead of blocking (FR-001, review-verdict-write-integrity-01KZ1CGF
  -- an INTENTIONAL behaviour change; see ``_guard_rejected_verdict``'s
  docstring). An unparseable verdict still blocks unconditionally.
- T010: --skip-review-artifact-check still records a durable arbiter override
  (unchanged mechanism, no longer required for the ordinary path)
- T011 / T012 / T013: lane guard names the planning branch (or falls back for legacy)

(T007/T008, the ``_get_latest_review_cycle_verdict`` helper and its
unknown-verdict warning, were retired by WP05,
verdict-seam-write-unification-01KZ9Q35/FR-003 -- see the retirement note
near the former ``TestGetLatestReviewCycleVerdict``/``TestUnknownVerdictWarning``
location below.)
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from kernel.clock import now_utc, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import Result
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import (
    _VALID_VERDICTS,
    _lane_targets_for_emit,
    _wp_lane_from_status_events,
    app,
)
from specify_cli.status.lifecycle_events import (
    REVIEWER_SELF_APPROVAL,
    mission_event_log_path,
    read_lifecycle_events,
)
from specify_cli.status.models import (
    InnerStateChanged,
    Lane,
    ReviewResult,
    StatusEvent,
    WPInnerStateDelta,
    actor_identity_str,
)
from specify_cli.status.store import append_annotations_atomic_verified, append_event
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

runner = CliRunner()


def test_move_task_help_surfaces_review_artifact_override_audit_path() -> None:
    """Help keeps the rejected-artifact override path discoverable."""
    result = runner.invoke(app, ["move-task", "--help"], terminal_width=160)

    assert result.exit_code == 0, result.output
    group = get_command(app)
    assert isinstance(group, click.Group)
    click_command = group.commands["move-task"]
    skip_review_help = next(
        param.help
        for param in click_command.params
        if isinstance(param, click.Option) and param.name == "skip_review_artifact_check"
    )
    assert skip_review_help is not None

    assert "rejected" in skip_review_help
    assert "review artifact" in skip_review_help
    assert "arbiter-approving" in skip_review_help
    assert "requires --note" in skip_review_help
    assert "records override" in skip_review_help
    assert "evidence" in skip_review_help


def test_move_task_lane_chain_uses_canonical_status_events() -> None:
    """Coord-backed current lane must not restart forward chains from planned."""
    event = StatusEvent(
        event_id="test-WP01-for-review",
        mission_slug="test-mission",
        wp_id="WP01",
        from_lane=Lane.IN_PROGRESS,
        to_lane=Lane.FOR_REVIEW,
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=False,
        execution_mode="worktree",
    )

    current_lane = _wp_lane_from_status_events([event], "WP01")
    targets = _lane_targets_for_emit(current_lane, Lane.APPROVED)

    assert current_lane == Lane.FOR_REVIEW
    assert targets == [Lane.IN_REVIEW, Lane.APPROVED]


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _write_review_cycle(wp_dir: Path, cycle_n: int, verdict: str) -> Path:
    """Write a review-cycle-N.md with the given verdict."""
    wp_dir.mkdir(parents=True, exist_ok=True)
    artifact = wp_dir / f"review-cycle-{cycle_n}.md"
    artifact.write_text(
        f"---\n"
        f"cycle_number: {cycle_n}\n"
        f"mission_slug: test-mission\n"
        f"reviewed_at: '2026-04-30T12:00:00Z'\n"
        f"reviewer_agent: test-reviewer\n"
        f"verdict: {verdict}\n"
        f"wp_id: WP01\n"
        f"---\n\nReview body.\n",
        encoding="utf-8",
    )
    return artifact


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str) -> tuple[Path, Path]:
    """Create minimal WP + feature structure.

    Returns (feature_dir, wp_file_path).
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"execution_mode: code_change\n"
        f"agent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir, wp_file


def _seed_wp_event(
    feature_dir: Path,
    wp_id: str,
    to_lane: str,
    *,
    review_result: ReviewResult | None = None,
) -> None:
    """Seed a WP event so the canonical event log knows the WP exists.

    ``review_result`` (WP05, verdict-seam-write-unification-01KZ9Q35): every
    verdict reader now resolves the event authority
    (``event_sourced_review_result``), never ``review-cycle-N.md``
    frontmatter -- callers that need the guard/writer to see a CURRENT
    rejection/approval must seed it here, not merely write the on-disk
    artifact.
    """
    event = StatusEvent(
        event_id=f"test-{wp_id}-{to_lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(to_lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
        review_result=review_result,
    )
    append_event(feature_dir, event)


def _seed_snapshot_agent(feature_dir: Path, wp_id: str, agent: str) -> None:
    """Seed the reduced snapshot's runtime ``agent`` slot (event-sourced, WP07).

    Post-#2816 the runtime ``agent`` is read ONLY from the reduced event-log
    snapshot, never from WP frontmatter — so prior-owner attribution used by the
    implementation-handoff hop must be seeded here, not in the WP file.
    """
    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                event_id="01KXAGENT" + "0" * 17,
                wp_id=wp_id,
                at="2026-01-01T00:00:30+00:00",
                actor="test",
                delta=WPInnerStateDelta(agent=agent),
            )
        ],
    )


def _assert_no_wp_activity_log(wp_file: Path) -> None:
    """Post-#2816 the WP-file ``## Activity Log`` is retired — move-task writes no rows.

    Runtime attribution now lives solely in the event log; the WP markdown must
    carry NO ``- `` activity rows (its ``owned_files`` frontmatter uses ``  - ``
    indentation, so it is never mistaken for an activity row).
    """
    activity_rows = [
        line
        for line in wp_file.read_text(encoding="utf-8").splitlines()
        if line.startswith("- ")
    ]
    assert not activity_rows, f"expected no retired WP-file activity rows, found: {activity_rows}"


def test_move_task_for_review_without_agent_uses_assigned_actor(tmp_path: Path) -> None:
    """Omitted --agent still attributes the handoff to the snapshot-assigned agent.

    Post-#2816 the prior-owner agent is read from the reduced snapshot (not WP
    frontmatter). A ``for_review`` handoff with no ``--agent`` therefore uses the
    snapshot ``agent`` slot, never a ``user`` override."""
    mission_slug = "test-move-task-for-review-actor"
    feature_dir, _wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_progress")
    _seed_snapshot_agent(feature_dir, "WP01", "testbot")

    with setup_mocked_env(
        tmp_path,
        mission_slug=mission_slug,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "for_review",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 0, result.output
    events = list((feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines())
    emitted = json.loads(events[-1])
    assert emitted["actor"] == "testbot"
    assert emitted["to_lane"] == "for_review"
    assert emitted["force"] is False


def test_move_task_approval_without_agent_does_not_use_assigned_actor(tmp_path: Path) -> None:
    """Omitted --agent on reviewer actions must not impersonate the implementer."""
    mission_slug = "test-move-task-approval-actor"
    feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
    _seed_wp_event(feature_dir, "WP01", "for_review")
    # Even with an assigned snapshot agent, reviewer hops must NOT impersonate it.
    _seed_snapshot_agent(feature_dir, "WP01", "testbot")

    with setup_mocked_env(
        tmp_path,
        mission_slug=mission_slug,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "approved",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    emitted = [event for event in events if event.get("kind") != "annotation"][1:]
    assert [event["to_lane"] for event in emitted] == ["in_review", "approved"]
    # Reviewer hops fall back to the operator, never the assigned implementer.
    emitted_actors = [actor_identity_str(event["actor"]) for event in emitted]
    assert set(emitted_actors) == {"user"}
    assert "testbot" not in emitted_actors
    assert emitted[0]["actor"] == {
        "model": None,
        "profile": None,
        "role": "reviewer",
        "tool": "user",
    }
    # WP-file activity log retired (#2816): attribution lives in the event log only.
    _assert_no_wp_activity_log(wp_file)


def test_move_task_direct_approval_without_agent_uses_hop_specific_actors(tmp_path: Path) -> None:
    """Composite moves attribute implementation and review hops separately."""
    mission_slug = "test-move-task-direct-approval-actors"
    feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
    _seed_wp_event(feature_dir, "WP01", "in_progress")
    _seed_snapshot_agent(feature_dir, "WP01", "testbot")

    with setup_mocked_env(
        tmp_path,
        mission_slug=mission_slug,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "approved",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 0, result.output
    events = [json.loads(line) for line in (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()]
    emitted = [event for event in events if event.get("kind") != "annotation"][1:]
    # The implementation handoff keeps the snapshot-assigned agent; the review
    # hops attribute to the operator — separate attribution per hop.
    assert [
        (event["to_lane"], actor_identity_str(event["actor"]))
        for event in emitted
    ] == [
        ("for_review", "testbot"),
        ("in_review", "user"),
        ("approved", "user"),
    ]
    assert emitted[1]["actor"] == {
        "model": None,
        "profile": None,
        "role": "reviewer",
        "tool": "user",
    }
    # WP-file activity log retired (#2816): attribution lives in the event log only.
    _assert_no_wp_activity_log(wp_file)


def test_move_task_self_review_fallback_without_agent_records_operator(tmp_path: Path) -> None:
    """Self-review fallback payload must not impersonate the assigned implementer."""
    mission_slug = "test-move-task-self-review-actor"
    feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
    _seed_wp_event(feature_dir, "WP01", "for_review")
    # Even with an assigned snapshot agent, the self-review fallback records the
    # operator as the implementing actor, never the assigned implementer.
    _seed_snapshot_agent(feature_dir, "WP01", "testbot")

    with setup_mocked_env(
        tmp_path,
        mission_slug=mission_slug,
        extra_patches={
            "_validate_ready_for_review": (True, []),
            "_check_unchecked_subtasks": [],
        },
    ):
        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "approved",
                "--mission",
                mission_slug,
                "--force",
                "--self-review-fallback",
                "--intended-reviewer",
                "reviewbot",
                "--reviewer-failure-reason",
                "review agent exited 1",
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 0, result.output
    lifecycle_events = [
        event
        for event in read_lifecycle_events(mission_event_log_path(feature_dir))
        if event.get("event_type") == REVIEWER_SELF_APPROVAL
    ]
    assert len(lifecycle_events) == 1
    assert lifecycle_events[0]["payload"]["implementing_actor"] == "user"
    # WP-file activity log retired (#2816): attribution lives in the event log only.
    _assert_no_wp_activity_log(wp_file)


# ---------------------------------------------------------------------------
# WP05 (verdict-seam-write-unification-01KZ9Q35, FR-003) retired
# ``_get_latest_review_cycle_verdict`` -- the frontmatter verdict-reader
# helper ``TestGetLatestReviewCycleVerdict``/``TestUnknownVerdictWarning``
# (formerly T007/T008) directly unit-tested. The classes below are
# REPOINTED, not deleted (a prior mission's NFR-001 node-id floor,
# ``tests/architectural/mission_exit_baseline.txt``, pins their names): each
# method now exercises the event-sourced successor
# (``status.event_sourced_review_result``) of what it originally asserted
# about the retired frontmatter function.
# ---------------------------------------------------------------------------


class TestGetLatestReviewCycleVerdict:
    """Event-sourced successor of the retired ``_get_latest_review_cycle_verdict``
    frontmatter-parser unit tests (WP05)."""

    def test_returns_none_none_when_no_artifacts(self, tmp_path: Path) -> None:
        """No event at all -> absent."""
        from specify_cli.status import event_sourced_review_result

        lookup = event_sourced_review_result(tmp_path, "WP01")
        assert lookup.slot_present is False
        assert lookup.result is None

    def test_reads_verdict_from_single_cycle(self, tmp_path: Path) -> None:
        """A single review_result-carrying event resolves that verdict."""
        from specify_cli.status import event_sourced_review_result
        from specify_cli.status._unsafe import append_event

        append_event(
            tmp_path,
            StatusEvent(
                event_id="01T007SINGLE0000000000001",
                mission_slug=tmp_path.name,
                wp_id="WP01",
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00+00:00",
                actor="reviewer-renata",
                force=False,
                execution_mode="worktree",
                review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
            ),
        )

        lookup = event_sourced_review_result(tmp_path, "WP01")
        assert lookup.slot_present is True
        assert lookup.result is not None
        assert lookup.result.verdict == "changes_requested"

    def test_picks_highest_numbered_cycle(self, tmp_path: Path) -> None:
        """The MOST RECENT review CYCLE's verdict wins -- the event-sourced
        successor of "the highest-numbered cycle wins".

        Cycle 1 ends with a reject (``in_review -> in_progress``, causally a
        rollback). Cycle 2 reworks the WP back through
        ``for_review -> in_review`` before the approve, so the approve's
        ``from_lane`` causally follows the rework rather than branching off
        the same pre-rollback ``in_review`` state the reject already
        resolved (spec-kitty-events #4990: a rollback is never overwritten
        by a forward transition that does not causally follow it, regardless
        of wall-clock order -- see ``_should_apply_event``). This keeps the
        "latest cycle wins" intent while being correct under the causal
        reducer.
        """
        from specify_cli.status import event_sourced_review_result
        from specify_cli.status._unsafe import append_event

        append_event(
            tmp_path,
            StatusEvent(
                event_id="01T007HIGHEST000000000001",
                mission_slug=tmp_path.name,
                wp_id="WP01",
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00+00:00",
                actor="reviewer-renata",
                force=False,
                execution_mode="worktree",
                review_result=ReviewResult(reviewer="reviewer-renata", verdict="changes_requested", reference="x"),
            ),
        )
        # Cycle 2 rework: back into review before the second verdict, so the
        # approve below causally follows this cycle rather than the reject.
        append_event(
            tmp_path,
            StatusEvent(
                event_id="01T007HIGHEST000000000002",
                mission_slug=tmp_path.name,
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at="2026-01-01T12:00:00+00:00",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )
        append_event(
            tmp_path,
            StatusEvent(
                event_id="01T007HIGHEST000000000003",
                mission_slug=tmp_path.name,
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.IN_REVIEW,
                at="2026-01-01T18:00:00+00:00",
                actor="reviewer-renata",
                force=False,
                execution_mode="worktree",
            ),
        )
        append_event(
            tmp_path,
            StatusEvent(
                event_id="01T007HIGHEST000000000004",
                mission_slug=tmp_path.name,
                wp_id="WP01",
                from_lane=Lane.IN_REVIEW,
                to_lane=Lane.APPROVED,
                at="2026-01-02T00:00:00+00:00",
                actor="reviewer-renata",
                force=False,
                execution_mode="worktree",
                review_result=ReviewResult(reviewer="reviewer-renata", verdict="approved", reference="y"),
            ),
        )

        lookup = event_sourced_review_result(tmp_path, "WP01")
        assert lookup.slot_present is True
        assert lookup.result is not None
        assert lookup.result.verdict == "approved"

    def test_returns_none_artifact_when_frontmatter_absent(self, tmp_path: Path) -> None:
        """A damaged ``review_result`` slot is distinguishable
        (``slot_present=True, result=None``) from a genuinely absent one --
        the event-sourced successor of "an artifact without frontmatter
        returns a distinguishable non-None artifact path"."""
        from unittest.mock import patch

        from specify_cli.status import event_sourced_review_result

        with patch(
            "specify_cli.status.reducer.wp_snapshot_state",
            return_value={"lane": "in_progress", "review_result": {"reviewer": "reviewer-renata"}},
        ):
            lookup = event_sourced_review_result(tmp_path, "WP01")
        assert lookup.slot_present is True
        assert lookup.result is None

    def test_valid_verdicts_frozenset_contents(self) -> None:
        """_VALID_VERDICTS contains the four canonical values."""
        assert "approved" in _VALID_VERDICTS
        assert "approved_after_orchestrator_fix" in _VALID_VERDICTS
        assert "arbiter_override" in _VALID_VERDICTS
        assert "rejected" in _VALID_VERDICTS


class TestUnknownVerdictWarning:
    """Event-sourced successor: a damaged/unrecognized verdict record still
    surfaces distinctly, never silently as "no verdict" (WP05)."""

    def test_unknown_verdict_emits_warning(self, tmp_path: Path) -> None:
        """A damaged ``review_result`` slot is reported distinctly by the
        board's own damaged-verdict channel, not silently folded into "no
        verdict" -- the event-sourced successor of "an unrecognized verdict
        value emits a warning, not a silent pass"."""
        from unittest.mock import patch

        from specify_cli.cli.commands.agent.tasks_parsing_validation import (
            _apply_wp_review_verdict_flag,
        )
        from specify_cli.status.reducer import ReviewResultLookup

        stale_verdicts: list[dict[str, object]] = []
        wp: dict[str, object] = {"id": "WP01"}
        with patch(
            "specify_cli.cli.commands.agent.tasks_parsing_validation.event_sourced_review_result",
            return_value=ReviewResultLookup(slot_present=True, result=None),
        ):
            _apply_wp_review_verdict_flag(
                wp, wp_id="WP01", feature_dir=tmp_path, stale_verdicts=stale_verdicts
            )
        assert wp["_damaged_verdict"] is True
        assert stale_verdicts and stale_verdicts[0]["damaged"] is True


# ---------------------------------------------------------------------------
# T009 + T010: verdict guard in move_task  (decorator-style patches)
# ---------------------------------------------------------------------------


class TestVerdictGuardInMoveTask:
    """move_task's rejected-verdict guard (T009/T010).

    FR-001 (review-verdict-write-integrity-01KZ1CGF), INTENTIONAL behaviour
    change: approve/done no longer fails-closed merely because the latest
    review artifact is ``rejected`` -- see ``_guard_rejected_verdict``'s
    docstring (``tasks_transition_core.py``). The durable writer
    (T001/T005's ``_persist_approved_review_cycle``) now persists a fresh
    ``verdict: approved`` artifact on that path instead. An unparseable
    verdict (a broken artifact) still fails closed unconditionally.
    """

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_approve_after_rejected_verdict_without_force_persists_approval(
        self,
        _mock_auto_commit: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FR-001: approve succeeds and persists a fresh approved artifact
        when the latest review artifact has ``verdict: rejected`` -- even
        with NO ``--force`` and NO ``--skip-review-artifact-check``.

        Renamed + rewritten from
        ``test_approve_blocked_by_rejected_verdict_without_force`` (cycle 1
        of this WP's review): this is an INTENTIONAL behaviour change, not a
        regression -- see ``_guard_rejected_verdict``'s docstring
        (``tasks_transition_core.py``) for the full rationale.
        """
        mission_slug = "test-mission-001"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        # WP05 (verdict-seam-write-unification-01KZ9Q35): the "current verdict
        # is a rejection" probe is now event-sourced -- seed the
        # ``review_result`` on the in_review-entering event, not just the
        # on-disk artifact (written below only as realistic surrounding state).
        _seed_wp_event(
            feature_dir,
            wp_id,
            "in_review",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        # Write a review-cycle-1.md with verdict: rejected inside the WP sub-dir
        wp_dir = wp_file.parent / wp_file.stem  # tasks/WP01-test/
        _write_review_cycle(wp_dir, 1, "rejected")
        # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01):
        # ``_commit_review_cycle_artifact`` now inspects the real
        # ``CommitArtifactResult.status`` and raises on anything but
        # "committed" -- configure the mocked ``commit_for_mission`` to
        # report success so this happy-path test reflects a real commit,
        # not an unconfigured MagicMock status that would (correctly) fail.
        mock_safe_commit.return_value.status = "committed"

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_review",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["move-task", wp_id, "--to", "approved", "--mission", mission_slug, "--no-auto-commit"],
        )

        assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output:\n{result.output}"
        from specify_cli.review.artifacts import ReviewCycleArtifact

        latest = ReviewCycleArtifact.latest(wp_dir)
        assert latest is not None, f"expected a fresh approved artifact. Output:\n{result.output}"
        assert latest.cycle_number == 2, (
            f"expected the approval at the next sequential cycle number, got "
            f"{latest.cycle_number}. Output:\n{result.output}"
        )
        # WP06 (FR-003/SC-007): ReviewCycleArtifact no longer carries a
        # verdict field -- the approval write's own synthesized body
        # ("Approved by ...") is the checkable proxy.
        assert latest.body.startswith("Approved by "), (
            f"expected an 'Approved by ...' body, got "
            f"{latest.body!r}. Output:\n{result.output}"
        )
        assert latest.reviewer_agent != "unknown", (
            f"expected a real reviewer_agent, not 'unknown'. Output:\n{result.output}"
        )
        # The stale rejected cycle 1 remains untouched.
        assert (wp_dir / "review-cycle-1.md").exists()

    @patch(
        "specify_cli.cli.commands.agent.tasks_verdict_persistence.event_sourced_review_result"
    )
    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_malformed_latest_review_artifact_blocks_approval(
        self,
        _mock_auto_commit: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        mock_event_sourced_lookup: MagicMock,
        tmp_path: Path,
    ) -> None:
        """A damaged event-log ``review_result`` record fails diagnostically
        before mutation (WP05, verdict-seam-write-unification-01KZ9Q35: the
        guard's feed is now event-sourced, so "malformed" means a damaged
        event slot, not a malformed on-disk ``review-cycle-N.md`` -- injected
        directly at the seam since the real store never produces a
        Mapping-but-missing-fields ``review_result`` through its own typed
        API)."""
        from specify_cli.status.reducer import ReviewResultLookup

        mission_slug = "test-mission-malformed"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        _seed_wp_event(feature_dir, wp_id, "in_review")
        mock_event_sourced_lookup.return_value = ReviewResultLookup(slot_present=True, result=None)

        wp_dir = wp_file.parent / wp_file.stem
        wp_dir.mkdir(parents=True)
        (wp_dir / "review-cycle-1.md").write_text("not frontmatter", encoding="utf-8")

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_review",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["move-task", wp_id, "--to", "approved", "--mission", mission_slug, "--no-auto-commit"],
        )

        assert result.exit_code == 1
        assert "no parseable review verdict" in result.output
        mock_emit.assert_not_called()

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.resolve_workspace_for_wp")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_force_done_after_rejected_verdict_persists_approval(
        self,
        _mock_auto_commit: MagicMock,
        mock_resolve_workspace: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FR-001, Acceptance Scenario 3 (spec.md): a WP approved directly to
        ``--to done`` (skipping an intermediate ``approved`` lane) from a
        rejected-latest state gets the SAME approved-artifact persistence --
        the write is not conditional on which terminal lane is the target.

        Renamed + rewritten from ``test_force_done_blocked_by_rejected_verdict``
        (cycle 1 of this WP's review): this is an INTENTIONAL behaviour
        change -- see ``_guard_rejected_verdict``'s docstring
        (``tasks_transition_core.py``).

        ``resolve_workspace_for_wp`` is mocked to resolve
        ``execution_mode="planning_artifact"`` so the (unrelated)
        done-ancestry merge-verification machinery is skipped cleanly (FR-008a)
        -- this test's focus is the rejected-verdict guard and the writer, not
        ancestry verification, which has its own dedicated coverage
        elsewhere.
        """
        from specify_cli.workspace.context import ResolvedWorkspace

        mission_slug = "test-mission-002"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        # WP05 (verdict-seam-write-unification-01KZ9Q35): seed the
        # event-sourced rejection the writer's probe now reads, not just the
        # on-disk artifact (written below only as realistic surrounding state).
        _seed_wp_event(
            feature_dir,
            wp_id,
            "approved",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        wp_dir = wp_file.parent / wp_file.stem
        _write_review_cycle(wp_dir, 1, "rejected")
        # Cycle 2 fix (review-verdict-write-integrity-01KZ1CGF WP01):
        # ``_commit_review_cycle_artifact`` now inspects the real
        # ``CommitArtifactResult.status`` and raises on anything but
        # "committed" -- configure the mocked ``commit_for_mission`` to
        # report success so this happy-path test reflects a real commit,
        # not an unconfigured MagicMock status that would (correctly) fail.
        mock_safe_commit.return_value.status = "committed"

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="approved",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp
        mock_resolve_workspace.return_value = ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id=wp_id,
            execution_mode="planning_artifact",
            mode_source="test",
            resolution_kind="repo_root",
            workspace_name="repo_root",
            worktree_path=tmp_path,
            branch_name=None,
            lane_id=None,
            lane_wp_ids=[],
        )

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            ["move-task", wp_id, "--to", "done", "--force", "--mission", mission_slug, "--no-auto-commit"],
        )

        assert result.exit_code == 0, f"Expected exit 0. Output:\n{result.output}"
        from specify_cli.review.artifacts import ReviewCycleArtifact

        latest = ReviewCycleArtifact.latest(wp_dir)
        assert latest is not None, f"expected a fresh approved artifact. Output:\n{result.output}"
        assert latest.cycle_number == 2, (
            f"expected the approval at the next sequential cycle number, got "
            f"{latest.cycle_number}. Output:\n{result.output}"
        )
        # WP06 (FR-003/SC-007): ReviewCycleArtifact no longer carries a
        # verdict field -- the approval write's own synthesized body
        # ("Approved by ...") is the checkable proxy.
        assert latest.body.startswith("Approved by "), (
            f"expected an 'Approved by ...' body, got "
            f"{latest.body!r}. Output:\n{result.output}"
        )
        assert latest.reviewer_agent != "unknown", (
            f"expected a real reviewer_agent, not 'unknown'. Output:\n{result.output}"
        )
        assert (wp_dir / "review-cycle-1.md").exists()


class TestSkipReviewArtifactCheck:
    """--skip-review-artifact-check records a durable override."""

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_force_approve_allowed_with_skip_flag(
        self,
        _mock_auto_commit: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """With --skip-review-artifact-check, rejected verdict is durably overridden."""
        mission_slug = "test-mission-004"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        # WP05 (verdict-seam-write-unification-01KZ9Q35): the override-authorize
        # guard requires a non-None ``review_artifact_name``, now resolved from
        # the event-sourced verdict, not just the on-disk artifact (written
        # below only as realistic surrounding state).
        _seed_wp_event(
            feature_dir,
            wp_id,
            "in_review",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        wp_dir = wp_file.parent / wp_file.stem
        artifact = _write_review_cycle(wp_dir, 1, "rejected")

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_review",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "move-task",
                wp_id,
                "--to",
                "approved",
                "--force",
                "--skip-review-artifact-check",
                "--note",
                "Arbiter override: latest rejection was superseded by manual release review",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

        # Must NOT exit with the rejected-verdict guard (exit 1 with artifact name)
        # The guard message is: "Error: WP01 review-cycle-1.md has verdict: rejected."
        guard_triggered = result.exit_code == 1 and "review-cycle-1.md" in result.output and "rejected" in result.output
        assert not guard_triggered, (
            f"Verdict guard fired despite --skip-review-artifact-check.\nOutput:\n{result.output}"
        )
        # FR-009 (WP09): the override is event-sourced into the ``review`` snapshot
        # slot, not stamped onto the artifact frontmatter.
        from specify_cli.status import materialize

        review = materialize(feature_dir).work_packages["WP01"]["review"]
        assert review["actor"]
        assert review["reason"] == (
            "Arbiter override: latest rejection was superseded by manual release review"
        )
        assert review["at"]
        assert "review_artifact_override" not in artifact.read_text(encoding="utf-8")

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_override_persist_survives_later_guard_refusal(
        self,
        _mock_auto_commit: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """FR-004 partial-write-on-refusal: the review-artifact override is stamped
        at its OLD guard position (rejected-verdict proceed arm), so a LATER guard
        (here review-currency) refusing with exit 1 STILL leaves the override
        frontmatter on disk — matching the un-refactored ``move_task`` timing.

        RED against the cycle-1 wiring (which deferred the persist to ``Emit``,
        after all guards clear, so a refusal wrote nothing); GREEN once the persist
        fires ahead of the guard sequence.
        """
        mission_slug = "test-mission-partial-write"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        # WP05 (verdict-seam-write-unification-01KZ9Q35): seed the
        # event-sourced rejection the override-authorize guard now reads.
        _seed_wp_event(
            feature_dir,
            wp_id,
            "in_review",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        wp_dir = wp_file.parent / wp_file.stem
        artifact = _write_review_cycle(wp_dir, 1, "rejected")

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_review",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        # A LATER guard (review-currency, guard position 9) refuses AFTER the
        # rejected-verdict override arm (guard position 5) would have persisted.
        mock_review_valid.return_value = (False, ["Uncommitted changes present in workspace."])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "move-task",
                wp_id,
                "--to",
                "approved",
                "--force",
                "--skip-review-artifact-check",
                "--note",
                "Arbiter override: rejection superseded by manual release review",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

        # The LATER guard refuses the operation (exit 1) and nothing is emitted.
        assert result.exit_code == 1, f"Expected review-currency refusal. Output:\n{result.output}"
        assert "Uncommitted changes present in workspace." in result.output
        # It must be the review-currency guard, NOT the rejected-verdict guard.
        assert "rejected review artifact" not in result.output
        mock_emit.assert_not_called()
        # FR-004 partial-write-on-refusal, now event-sourced (FR-009 / WP09): the
        # review override is emitted at its OLD guard position (ahead of the later
        # refusing guard), so the ``review`` snapshot slot carries the override even
        # though the operation exits 1. The transition emit (mock_emit) is still not
        # called — only the off-axis override annotation is persisted.
        from specify_cli.status import materialize

        review = materialize(feature_dir).work_packages["WP01"].get("review")
        assert review is not None, (
            "Override evidence was NOT persisted before the later guard refused — "
            "partial-write-on-refusal timing broken."
        )
        assert review["reason"] == (
            "Arbiter override: rejection superseded by manual release review"
        )
        assert review["actor"]
        assert review["at"]
        assert "review_artifact_override" not in artifact.read_text(encoding="utf-8")

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    @patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning")
    @patch("specify_cli.cli.commands.agent.tasks.get_auto_commit_default", return_value=False)
    def test_skip_flag_requires_note(
        self,
        _mock_auto_commit: MagicMock,
        _mock_sparse: MagicMock,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Override attempts without a note fail before mutation."""
        mission_slug = "test-mission-skip-no-note"
        wp_id = "WP01"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, wp_id)
        # WP05 (verdict-seam-write-unification-01KZ9Q35): seed the
        # event-sourced rejection ``_guard_rejected_verdict``'s
        # note-required-with-skip-flag check now reads.
        _seed_wp_event(
            feature_dir,
            wp_id,
            "in_review",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        wp_dir = wp_file.parent / wp_file.stem
        _write_review_cycle(wp_dir, 1, "rejected")

        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_review",
            relative_subpath=Path(f"tasks/{wp_file.name}"),
            frontmatter=f"work_package_id: {wp_id}\ntitle: Test\nagent: testbot\n",
            body="\n## Activity Log\n",
            padding="\n",
        )
        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)
        mock_locate_wp.return_value = mock_wp

        from specify_cli.status.store import read_events as _real_re
        mock_read_events.return_value = _real_re(feature_dir)
        mock_emit.return_value = MagicMock()

        result = runner.invoke(
            app,
            [
                "move-task",
                wp_id,
                "--to",
                "approved",
                "--force",
                "--skip-review-artifact-check",
                "--mission",
                mission_slug,
                "--no-auto-commit",
            ],
        )

        assert result.exit_code == 1
        assert "--skip-review-artifact-check requires --note" in result.output
        mock_emit.assert_not_called()


# ---------------------------------------------------------------------------
# T023 / T025: user-facing status command warnings
# ---------------------------------------------------------------------------


class TestTasksStatusReviewWarnings:
    """`spec-kitty agent tasks status` surfaces review artifact problems."""

    def _invoke_status(self, tmp_path: Path, mission_slug: str) -> Result:
        with setup_mocked_env(
            tmp_path,
            mission_slug=mission_slug,
            workspace_resolution=FileNotFoundError,
        ):
            return runner.invoke(app, ["status", "--mission", mission_slug])

    def test_status_warns_for_done_wp_with_rejected_review_artifact(
        self, tmp_path: Path
    ) -> None:
        """The CLI status command resolves the event-sourced verdict (WP05,
        verdict-seam-write-unification-01KZ9Q35: never ``review-cycle-N.md``
        frontmatter -- the artifact below is written only as realistic
        surrounding state)."""
        mission_slug = "test-status-stale-verdict"
        feature_dir, wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
        _seed_wp_event(
            feature_dir,
            "WP01",
            "done",
            review_result=ReviewResult(
                reviewer="test-reviewer", verdict="changes_requested", reference="x"
            ),
        )

        wp_dir = wp_file.parent / wp_file.stem
        _write_review_cycle(wp_dir, 1, "rejected")

        result = self._invoke_status(tmp_path, mission_slug)

        assert result.exit_code == 0, result.output
        assert "review artifact: verdict=rejected" in result.output

    def test_status_warns_for_stalled_in_review_wp(self, tmp_path: Path) -> None:
        """The CLI status command flags in_review WPs past the review threshold."""
        mission_slug = "test-status-stalled-review"
        feature_dir, _wp_file = _build_wp_file(tmp_path, mission_slug, "WP01")
        event_time = now_utc() - timedelta(minutes=45)
        event = StatusEvent(
            event_id="test-WP01-in-review",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.IN_REVIEW,
            at=event_time.isoformat(),
            actor="test",
            force=False,
            execution_mode="worktree",
        )
        append_event(feature_dir, event)

        result = self._invoke_status(tmp_path, mission_slug)

        assert result.exit_code == 0, result.output
        assert "STALLED" in result.output
        assert "no move-task" in result.output


# ---------------------------------------------------------------------------
# T011 / T012 / T013: lane guard error message variants
# ---------------------------------------------------------------------------


class TestLaneGuardErrorMessage:
    """_validate_ready_for_review names planning branch (or falls back)."""

    def _run_lane_guard(
        self,
        tmp_path: Path,
        mission_slug: str,
        feature_dir: Path,
        meta: Mapping[str, object] | None,
        contamination: list[str],
    ) -> tuple[bool, list[str]]:
        """Helper: invoke _validate_ready_for_review with contamination mocked."""
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        if meta is not None:
            (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        fake_worktree = tmp_path / "worktree"
        fake_worktree.mkdir(exist_ok=True)
        # #1833 husk guard: a resolved workspace must carry a .git entry; all
        # git calls below are mocked, so a marker file is sufficient.
        (fake_worktree / ".git").write_text("gitdir: mocked\n", encoding="utf-8")

        def _mock_subprocess(cmd: object, *args: object, **kwargs: object) -> MagicMock:
            result_mock = MagicMock()
            result_mock.returncode = 0
            result_mock.stdout = ""
            cmd_list = cmd if isinstance(cmd, list) else []
            cmd_str = " ".join(str(c) for c in cmd_list)
            if "rev-parse" in cmd_str and "--show-toplevel" in cmd_str:
                # #1833 toplevel assertion: the workspace is its own toplevel.
                result_mock.stdout = f"{fake_worktree}\n"
            elif "status" in cmd_str and "--porcelain" in cmd_str:
                # No uncommitted changes in main or worktree
                result_mock.stdout = ""
            elif "rev-list" in cmd_str and "HEAD.." in cmd_str:
                # branch-behind count: 0 (not behind)
                result_mock.stdout = "0\n"
            elif "rev-list" in cmd_str and "..HEAD" in cmd_str:
                # commits ahead of base: 1 (so we reach the contamination guard)
                result_mock.stdout = "1\n"
            elif "rev-parse" in cmd_str and any(
                ref in cmd_str for ref in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD")
            ):
                # No in-progress git operation
                result_mock.returncode = 1
                result_mock.stdout = ""
            return result_mock

        with (
            patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.agent.tasks._list_wp_branch_kitty_specs_changes",
                return_value=contamination,
            ),
            patch("specify_cli.cli.commands.agent.tasks.resolve_workspace_for_wp") as mock_ws,
            patch("specify_cli.cli.commands.agent.tasks.get_feature_target_branch", return_value="main"),
            patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev"),
            # Patch get_current_branch so the worktree doesn't look detached
            patch(
                "specify_cli.core.git_ops.get_current_branch",
                return_value=f"kitty/mission-{mission_slug}-lane-a",
            ),
            patch("subprocess.run", side_effect=_mock_subprocess),
        ):
            mock_workspace = MagicMock()
            mock_workspace.resolution_kind = "lane_workspace"
            mock_workspace.worktree_path = fake_worktree
            mock_workspace.context = MagicMock()
            mock_workspace.context.base_branch = f"kitty/mission-{mission_slug}"
            mock_ws.return_value = mock_workspace

            return _validate_ready_for_review(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                wp_id="WP01",
                force=False,
                target_lane="for_review",
            )

    def test_lane_guard_names_planning_branch(self, tmp_path: Path) -> None:
        """When meta.json has planning_base_branch, error names the branch."""
        mission_slug = "test-lane-guard-001"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        meta = {
            "mission_slug": mission_slug,
            "mission_id": "01KQFF35TESTTEST01",
            "planning_base_branch": "my-planning-branch",
            "mission_type": "software-dev",
        }
        contamination = ["kitty-specs/test-lane-guard-001/extra-plan.md"]

        is_valid, guidance = self._run_lane_guard(tmp_path, mission_slug, feature_dir, meta, contamination)

        assert not is_valid, "Expected validation to fail (lane contamination)"
        guidance_text = "\n".join(guidance)
        assert "my-planning-branch" in guidance_text, (
            f"Expected planning branch name in guidance; got:\n{guidance_text}"
        )
        assert "git show" in guidance_text, (
            f"Expected git show example in guidance; got:\n{guidance_text}"
        )
        assert "git show my-planning-branch:kitty-specs/test-lane-guard-001/extra-plan.md" in guidance_text

    def test_lane_guard_fallback_no_meta(self, tmp_path: Path) -> None:
        """When meta.json is absent, error says 'planning branch unknown'."""
        mission_slug = "test-lane-guard-002"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)

        # No meta.json — legacy mission
        contamination = ["kitty-specs/test-lane-guard-002/extra-plan.md"]

        is_valid, guidance = self._run_lane_guard(tmp_path, mission_slug, feature_dir, None, contamination)

        assert not is_valid, "Expected validation to fail (lane contamination)"
        guidance_text = "\n".join(guidance)
        assert "planning branch unknown" in guidance_text, (
            f"Expected fallback message; got:\n{guidance_text}"
        )

    def test_missing_workspace_context_checks_coord_branch_not_pr_branch(
        self, tmp_path: Path
    ) -> None:
        """Legacy workspace fixtures still use the coord branch as review base."""
        from mission_runtime import CommitTarget, MissionTopology
        from specify_cli.cli.commands.agent.tasks import _validate_ready_for_review

        mission_slug = "test-review-base-003"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        feature_dir.mkdir(parents=True)
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev", "target_branch": "fix/pr-branch"}),
            encoding="utf-8",
        )
        fake_worktree = tmp_path / "worktree"
        fake_worktree.mkdir()
        (fake_worktree / ".git").write_text("gitdir: mocked\n", encoding="utf-8")
        seen_rev_lists: list[str] = []

        def _mock_subprocess(cmd: object, *args: object, **kwargs: object) -> MagicMock:
            result_mock = MagicMock()
            result_mock.returncode = 0
            result_mock.stdout = ""
            cmd_list = cmd if isinstance(cmd, list) else []
            cmd_str = " ".join(str(c) for c in cmd_list)
            if "rev-parse" in cmd_str and "--show-toplevel" in cmd_str:
                result_mock.stdout = f"{fake_worktree}\n"
            elif "rev-parse" in cmd_str and any(
                ref in cmd_str for ref in ("MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD")
            ):
                result_mock.returncode = 1
            elif "status" in cmd_str and "--porcelain" in cmd_str:
                result_mock.stdout = ""
            elif "rev-list" in cmd_str:
                rev_range = str(cmd_list[-1])
                seen_rev_lists.append(rev_range)
                result_mock.stdout = "1\n" if rev_range.endswith("..HEAD") else "0\n"
            return result_mock

        coord_branch = f"kitty/mission-{mission_slug}"
        with (
            patch("specify_cli.cli.commands.agent.tasks.get_main_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.agent.tasks._list_wp_branch_kitty_specs_changes",
                return_value=[],
            ),
            patch("specify_cli.cli.commands.agent.tasks.resolve_workspace_for_wp") as mock_ws,
            patch(
                "specify_cli.cli.commands.agent.tasks.resolve_placement_only",
                return_value=CommitTarget(
                    ref=coord_branch,
                ),
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks.resolve_topology",
                return_value=MissionTopology.COORD,
            ),
            patch(
                "specify_cli.cli.commands.agent.tasks.get_feature_target_branch",
                return_value="fix/pr-branch",
            ),
            patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev"),
            patch(
                "specify_cli.core.git_ops.get_current_branch",
                return_value=f"{coord_branch}-lane-a",
            ),
            patch("subprocess.run", side_effect=_mock_subprocess),
        ):
            mock_workspace = MagicMock()
            mock_workspace.resolution_kind = "lane_workspace"
            mock_workspace.worktree_path = fake_worktree
            mock_workspace.context = None
            mock_ws.return_value = mock_workspace

            is_valid, guidance = _validate_ready_for_review(
                repo_root=tmp_path,
                mission_slug=mission_slug,
                wp_id="WP01",
                force=False,
                target_lane="for_review",
            )

        assert is_valid, guidance
        assert f"HEAD..{coord_branch}" in seen_rev_lists
        assert f"{coord_branch}..HEAD" in seen_rev_lists
        assert "HEAD..fix/pr-branch" not in seen_rev_lists
        assert "fix/pr-branch..HEAD" not in seen_rev_lists
