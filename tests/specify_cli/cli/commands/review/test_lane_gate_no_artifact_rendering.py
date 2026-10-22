"""Regression test: the lane-gate JSON payload must not render a missing
on-disk review artifact as the literal string ``"None"``.

FG (the review-durability-matrix mission) widened
``RejectedReviewArtifactFinding.artifact_path`` to ``Path | None`` to cover
the event-sourced, no-on-disk-artifact conflict shape (see
``_no_artifact_terminal_conflict`` in
``specify_cli.post_merge.review_artifact_consistency``). ``check_wp_lanes``
(``specify_cli.cli.commands.review._lane_gate``) built its JSON finding via
an unconditional ``str(conflict.artifact_path)``, which — for ``None`` —
renders the misleading literal ``"None"`` instead of a clear placeholder.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from specify_cli.cli.commands.review._lane_gate import check_wp_lanes
from specify_cli.status.models import Lane, ReviewResult, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.reliability.fixtures import WorkPackageSpec, create_mission_fixture, write_work_package

pytestmark = pytest.mark.fast


def test_check_wp_lanes_renders_no_artifact_conflict_without_literal_none(
    tmp_path: Path,
) -> None:
    """A terminal WP with an event-sourced ``changes_requested`` verdict and
    NO on-disk review artifact must surface a readable placeholder, not the
    string ``"None"``, in the JSON finding's ``artifact_path``.
    """
    mission = create_mission_fixture(tmp_path)
    write_work_package(mission, WorkPackageSpec(lane="approved"))
    seed_status_event(
        mission.mission_dir,
        StatusEvent(
            event_id="01KQKV85NOARTIFACTRENDER01",
            mission_slug=mission.mission_slug,
            mission_id=mission.mission_id,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-05-03T12:00:00+00:00",
            actor="operator",
            force=True,
            execution_mode="worktree",
            reason="force-approved despite rejection",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="changes_requested",
                reference="feedback://release-320-workflow-reliability-01KQKV85/WP01/1",
            ),
        ),
    )
    artifact_dir = mission.tasks_dir / "WP01-regression-harness"
    assert not artifact_dir.exists() or not list(
        artifact_dir.glob("review-cycle-*.md")
    ), "precondition: no on-disk review artifact must exist for this WP"

    findings: list[dict[str, str]] = []
    check_wp_lanes(
        mission.mission_dir,
        mission.repo_root,
        Console(),
        findings,
    )

    artifact_findings = [
        finding for finding in findings if finding["type"] == "rejected_review_artifact"
    ]
    assert len(artifact_findings) == 1, findings
    assert artifact_findings[0]["artifact_path"] == "<no review artifact>"
    assert artifact_findings[0]["artifact_path"] != "None"
