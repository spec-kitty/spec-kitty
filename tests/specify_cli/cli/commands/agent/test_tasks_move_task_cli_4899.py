"""Real-CLI ``move-task`` scenarios for the #4899 review-rejection edges.

Split out of ``test_tasks_move_task_seam.py`` (#5619 SPLIT-BY-KIND): the three
classes below drive the REAL ``agent tasks move-task`` CLI against a real git
repo and keep ``regression`` plus their tier marker; the seam file keeps only
the unmarked interception / ``_MOVE_SET`` battery.

Mission ``review-feedback-to-implementer-01M3GKZ8`` (#4899) and FR-008
(#3451). The harness helpers (``_build_in_review_repo``, ``_move_task_cli``,
``_PARITY_*``) live here and are imported by
``tests/agent/test_workflow_review_cycle_pointer.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from kernel.clock import parse_iso, timedelta
from specify_cli.cli.commands.agent import tasks
from specify_cli.frontmatter import write_frontmatter
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.review.artifacts import ReviewCycleArtifact
from specify_cli.review.cycle import is_non_resolvable_review_ref
from specify_cli.status import Lane, StatusEvent
from specify_cli.status._unsafe import append_event
from specify_cli.status.store import read_events

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ===========================================================================
# WP01 (review-feedback-to-implementer-01M3GKZ8, #4899) -- SC-001/SC-002
# regression battery, T001 (the defect is fixed; permanent guard).
#
# Real-CLI, real-git harness (mirrors ``tests/integration/
# test_review_cycle_rejection_only.py::for_review_repo``, extended one hop
# further into ``in_review`` so the two rejection edges under test --
# ``in_review -> planned`` and ``in_review -> in_progress`` (the
# re-implement/"doing" edge) -- both start from a genuine in-review WP.
# ===========================================================================

_PARITY_MISSION_SLUG = "001-parity-mission"
_PARITY_WP_SLUG = "WP01-test-task"
_FEEDBACK_BODY = "## Reviewer feedback\n\nAlign the widget margin and add the missing docstring.\n"


def _write_parity_wp(wp_path: Path) -> None:
    write_frontmatter(
        wp_path,
        {
            "work_package_id": "WP01",
            "subtasks": ["T001"],
            "title": "Test Task",
            "phase": "Phase 1",
            "lane": "planned",
            "dependencies": [],
            "assignee": "",
            "agent": "claude",
            "shell_pid": "",
            "review_status": "none",
            "review_feedback": "",
            "history": [],
        },
        "# WP01 Prompt\n",
    )


def _build_in_review_repo(root: Path, mission_slug: str = _PARITY_MISSION_SLUG) -> tuple[Path, Path, Path]:
    """Build a git repo with one WP driven event-by-event into ``in_review``.

    Returns ``(repo_root, feature_dir, sub_artifact_dir)``. The lifecycle hops
    (``planned -> claimed -> in_progress -> for_review -> in_review``) are
    written directly to the event log (mirrors the existing integration
    fixtures) so the two edges under test start from an identical, genuine
    in-review WP -- only the REAL ``move-task`` CLI invocation under test is
    driven through the real command surface.
    """
    repo = root / "repo"
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)

    (repo / ".kittify").mkdir()

    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "feature_number": "001",
                "mission_slug": mission_slug,
                "created_at": "2026-09-27T00:00:00Z",
                "friendly_name": mission_slug,
                "mission": "software-dev",
                "slug": mission_slug,
                "target_branch": "main",
                "vcs": "git",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=f"mission-{mission_slug}",
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("core",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-09-27T00:00:00Z",
            computed_from="test",
        ),
    )
    (feature_dir / "tasks.md").write_text("## WP01 Test\n\n- [x] T001 Placeholder task\n", encoding="utf-8")
    _write_parity_wp(tasks_dir / f"{_PARITY_WP_SLUG}.md")

    hops: tuple[tuple[Lane, Lane], ...] = (
        (Lane.PLANNED, Lane.CLAIMED),
        (Lane.CLAIMED, Lane.IN_PROGRESS),
        (Lane.IN_PROGRESS, Lane.FOR_REVIEW),
        (Lane.FOR_REVIEW, Lane.IN_REVIEW),
    )
    for index, (from_lane, to_lane) in enumerate(hops, start=1):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"01PARITY{str(index).zfill(18)}",
                mission_slug=mission_slug,
                wp_id="WP01",
                from_lane=from_lane,
                to_lane=to_lane,
                at=f"2026-09-27T12:00:{index:02d}Z",
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed in-review fixture"], cwd=repo, check=True, capture_output=True)

    sub_artifact_dir = feature_dir / "tasks" / _PARITY_WP_SLUG
    return repo, feature_dir, sub_artifact_dir


def _move_task_cli(
    *,
    mission_slug: str,
    to: str,
    feedback_file: Path | None,
    agent: str = "reviewer-rita",
) -> Any:
    """Invoke the REAL ``move-task`` CLI. Caller must already have chdir'd
    (``monkeypatch.chdir``) into the target repo."""
    args = [
        "move-task",
        "WP01",
        "--to",
        to,
        "--mission",
        mission_slug,
        "--agent",
        agent,
        "--no-auto-commit",
    ]
    if feedback_file is not None:
        args += ["--review-feedback-file", str(feedback_file)]
    runner = CliRunner()
    return runner.invoke(tasks.app, args)


@pytest.mark.regression
class TestReviewRejectionEdgeValueParity:
    """SC-001 (#4899, issue-pinned): ``in_review -> in_progress`` (the
    re-implement edge) must match ``in_review -> planned`` BY VALUE on a
    shared feedback fixture -- a committed review-cycle record, a populated
    feedback location, a resolvable ``review-cycle://`` reference, and (gate
    5 coverage) the EMITTED event's ``review_result`` matching field-for-field
    -- NOT the approval-shaped fallback (``verdict=approved``,
    ``reference="auto-forward:<WP>"``). This assertion fails if
    ``_mt_hop_review_result`` (gate 5) is not ALSO routed through the
    rejection-edge predicate, so the fix cannot be masked by gates 1-4 alone.
    """

    def test_reimplement_edge_matches_planned_edge_by_value(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo_planned, feature_dir_planned, sub_planned = _build_in_review_repo(tmp_path / "planned-side")
        repo_reimpl, feature_dir_reimpl, sub_reimpl = _build_in_review_repo(tmp_path / "reimpl-side")

        feedback_planned = repo_planned / "feedback.md"
        feedback_planned.write_text(_FEEDBACK_BODY, encoding="utf-8")
        feedback_reimpl = repo_reimpl / "feedback.md"
        feedback_reimpl.write_text(_FEEDBACK_BODY, encoding="utf-8")

        monkeypatch.chdir(repo_planned)
        result_planned = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="planned", feedback_file=feedback_planned)
        monkeypatch.chdir(repo_reimpl)
        result_reimpl = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_reimpl)

        assert result_planned.exit_code == 0, result_planned.stdout
        assert result_reimpl.exit_code == 0, result_reimpl.stdout

        # (a) a committed review-cycle-<N>.md record exists on BOTH edges.
        artifact_planned = ReviewCycleArtifact.latest(sub_planned)
        artifact_reimpl = ReviewCycleArtifact.latest(sub_reimpl)
        assert artifact_planned is not None
        assert artifact_reimpl is not None, (
            "the re-implement edge (in_review -> in_progress) produced no review-cycle record -- gates 1/2 are not routed through the rejection-edge predicate."
        )

        # (b) the feedback body is populated and equal BY VALUE to the input,
        # and matches the sibling ->planned edge on the same fixture.
        assert artifact_reimpl.body.strip() == _FEEDBACK_BODY.strip()
        assert artifact_reimpl.body == artifact_planned.body
        assert artifact_reimpl.cycle_number == artifact_planned.cycle_number == 1

        events_planned = read_events(feature_dir_planned)
        events_reimpl = read_events(feature_dir_reimpl)
        event_planned = events_planned[-1]
        event_reimpl = events_reimpl[-1]

        # (c) the emitted review_ref is resolvable on BOTH edges -- never the
        # non-resolvable synthetic ``review:<WP>`` marker.
        assert event_planned.review_ref is not None
        assert event_reimpl.review_ref is not None
        assert is_non_resolvable_review_ref(event_planned.review_ref) is False
        assert is_non_resolvable_review_ref(event_reimpl.review_ref) is False, (
            f"expected a resolvable review-cycle:// pointer, got {event_reimpl.review_ref!r} -- gate 3 is not routed through the rejection-edge predicate."
        )
        assert event_reimpl.review_ref.startswith("review-cycle://")
        assert event_reimpl.review_ref == event_planned.review_ref

        # (d) GATE 5 COVERAGE: the EMITTED event's review_result matches the
        # in_review -> planned edge BY VALUE (reviewer/verdict/reference) --
        # NOT the approval-shaped fallback. This is the assertion that fails
        # if only gates 1-4 are routed and gate 5 (``_mt_hop_review_result``)
        # is left selecting the ``target == Lane.PLANNED`` arm alone.
        assert event_planned.review_result is not None
        assert event_reimpl.review_result is not None, (
            "the re-implement edge emitted no review_result at all -- gate 5 (_mt_hop_review_result) is not routed through the predicate."
        )
        assert event_reimpl.review_result.verdict == event_planned.review_result.verdict == "changes_requested"
        assert event_reimpl.review_result.reviewer == event_planned.review_result.reviewer
        assert event_reimpl.review_result.reference == event_planned.review_result.reference
        assert event_reimpl.review_result.reference == event_reimpl.review_ref
        assert event_reimpl.review_result.verdict != "approved", (
            "the re-implement edge's emitted review_result is approval-shaped "
            "-- gate 5 fell through to the auto-forward branch instead of "
            "returning the rejection result."
        )
        assert event_reimpl.review_result.reference != f"auto-forward:{'WP01'}"


@pytest.mark.regression
class TestReimplementEdgeRequiresRationale:
    """SC-002 (#4899, issue-pinned): a no-rationale rejection on the
    re-implement edge (``in_review -> in_progress``) is REFUSED as an
    observable failure (non-zero exit, no recorded transition) -- never a
    logged no-op that still advances the lane. Paired with an accepted
    with-rationale rejection on the SAME fixture."""

    def test_no_rationale_refused_then_with_rationale_accepted(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, feature_dir, _sub = _build_in_review_repo(tmp_path / "sc-002")
        monkeypatch.chdir(repo)

        refused = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=None)

        assert refused.exit_code != 0, (
            f"a no-rationale in_review -> in_progress rejection must be refused (non-zero exit), got {refused.exit_code}. stdout:\n{refused.stdout}"
        )
        events_after_refusal = read_events(feature_dir)
        assert events_after_refusal[-1].to_lane == Lane.IN_REVIEW, (
            f"a refused move must never still record the transition -- latest event is {events_after_refusal[-1].to_lane}, expected it to remain in_review."
        )

        feedback_file = repo / "feedback.md"
        feedback_file.write_text(_FEEDBACK_BODY, encoding="utf-8")
        accepted = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_file)

        assert accepted.exit_code == 0, accepted.stdout
        events_after_accept = read_events(feature_dir)
        assert events_after_accept[-1].to_lane == Lane.IN_PROGRESS


def _seconds_after_latest_event(feature_dir: Path, *offsets: int) -> list[str]:
    """ISO-8601 timestamps ``offsets`` seconds after the latest status event."""
    latest = parse_iso(read_events(feature_dir)[-1].at.replace("Z", "+00:00"))
    return [(latest + timedelta(seconds=offset)).isoformat() for offset in offsets]


@pytest.mark.regression
class TestFr008ReviewCycleCounterOnReimplementEdge:
    """FR-008 (conditional, #3451): the review-cycle counter must increment
    EXACTLY ONCE per real rejection on the re-implement edge. WP01's fix
    routes this edge through a SINGLE persist call site
    (``_mt_persist_rejection_cycle``, called once per CLI invocation from
    ``_mt_finalize_plan``) -- this scenario proves the counter does not
    reproduce #3451's double-increment on the newly-routed edge. See the WP
    Activity Log for the disposition (does not reproduce; recorded
    out-of-scope reasoning)."""

    def test_two_sequential_reimplement_rejections_advance_by_exactly_one_each(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        repo, feature_dir, sub_artifact_dir = _build_in_review_repo(tmp_path / "fr-008")
        monkeypatch.chdir(repo)

        feedback_1 = repo / "feedback-1.md"
        feedback_1.write_text("## Cycle 1 issues\n\nFix the off-by-one.\n", encoding="utf-8")
        first = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_1)
        assert first.exit_code == 0, first.stdout

        latest_after_first = ReviewCycleArtifact.latest(sub_artifact_dir)
        assert latest_after_first is not None
        assert latest_after_first.cycle_number == 1, (
            "expected the FIRST rejection to allocate cycle 1 exactly once, "
            f"got {latest_after_first.cycle_number} -- a value of 2+ here "
            "would indicate a double-increment on a single rejection."
        )

        # Drive the WP back through for_review -> in_review for a genuine
        # second review round (mirrors the real implement/review lifecycle).
        # Stamp the hand-appended events AFTER the first rejection, which the
        # CLI stamped with the wall clock: a fixed literal timestamp sorts
        # before it once the clock passes the literal, and the lane reducer
        # then sees in_progress -> in_progress.
        second_round_at = _seconds_after_latest_event(feature_dir, 1, 2)
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01PARITYSECONDROUND000001",
                mission_slug=_PARITY_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.IN_PROGRESS,
                to_lane=Lane.FOR_REVIEW,
                at=second_round_at[0],
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )
        append_event(
            feature_dir,
            StatusEvent(
                event_id="01PARITYSECONDROUND000002",
                mission_slug=_PARITY_MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.FOR_REVIEW,
                to_lane=Lane.IN_REVIEW,
                at=second_round_at[1],
                actor="claude",
                force=False,
                execution_mode="worktree",
            ),
        )

        feedback_2 = repo / "feedback-2.md"
        feedback_2.write_text("## Cycle 2 issues\n\nFix the remaining edge case.\n", encoding="utf-8")
        second = _move_task_cli(mission_slug=_PARITY_MISSION_SLUG, to="in_progress", feedback_file=feedback_2)
        assert second.exit_code == 0, second.stdout

        latest_after_second = ReviewCycleArtifact.latest(sub_artifact_dir)
        assert latest_after_second is not None
        assert latest_after_second.cycle_number == 2, (
            "expected the SECOND rejection to advance the counter by EXACTLY "
            f"one (1 -> 2), got {latest_after_second.cycle_number} -- "
            "#3451's double-increment would show 3+ here."
        )
        cycle_files = sorted(p.name for p in sub_artifact_dir.glob("review-cycle-*.md"))
        assert cycle_files == ["review-cycle-1.md", "review-cycle-2.md"], f"expected exactly two review-cycle artifacts (1 and 2), got: {cycle_files}"
