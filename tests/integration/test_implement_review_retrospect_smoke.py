from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app
from specify_cli.cli.commands.agent import workflow_cores
from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.charter_pack_synthesizer import SynthesisResult
from runtime.next.runtime_bridge import _finalized_task_board_override_step
from runtime.next.decision import _compute_wp_progress
from specify_cli.review.cycle import create_rejected_review_cycle, resolve_review_cycle_pointer
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = pytest.mark.git_repo

MISSION_ID = "01KQ6YEG000000000000000000"
MISSION_SLUG = "001-loop-smoke"


def _init_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)


def _empty_result() -> SynthesisResult:
    return SynthesisResult(
        dry_run=True,
        planned=[],
        applied=[],
        conflicts=[],
        rejected=[],
        events_emitted=[],
    )


def test_reject_fix_next_retrospect_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    (repo / ".kittify").mkdir()
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": MISSION_ID, "mission_type": "software-dev"}), encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    (tasks_dir / "WP01-core.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\ntitle: Core\n---\n# WP01\n",
        encoding="utf-8",
    )
    for idx, lane in enumerate(
        [Lane.PLANNED, Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW],
        start=1,
    ):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-{idx}",
                mission_slug=MISSION_SLUG,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=lane,
                at=f"2026-01-01T00:00:0{idx}+00:00",
                actor="fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

    feedback = tmp_path / "feedback.md"
    feedback.write_text("**Issue**: Smoke-test rejection context.\n", encoding="utf-8")
    cycle = create_rejected_review_cycle(
        main_repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id="WP01",
        wp_slug="WP01-core",
        feedback_source=feedback,
        reviewer_agent="codex",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-rejected",
            mission_slug=MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.PLANNED,
            at="2026-01-01T00:00:10+00:00",
            actor="codex",
            force=False,
            execution_mode="worktree",
            review_ref=cycle.pointer,
        ),
    )

    resolved = resolve_review_cycle_pointer(repo, cycle.pointer)
    assert resolved.path == cycle.artifact_path.resolve()
    has_feedback, ref, path, source = workflow_cores.resolve_review_feedback_context(
        feature_dir,
        "WP01",
        "",
    )
    assert has_feedback is True
    assert ref == cycle.pointer
    assert path == cycle.artifact_path.resolve()
    assert source == "canonical"

    progress = _compute_wp_progress(feature_dir)
    assert _finalized_task_board_override_step(feature_dir, progress) == "implement"

    # Causal rework after the rejection: planned -> claimed -> in_progress ->
    # for_review, so the approval below extends the WP's actual history.
    for idx, (src, dst) in enumerate(
        [(Lane.PLANNED, Lane.CLAIMED), (Lane.CLAIMED, Lane.IN_PROGRESS), (Lane.IN_PROGRESS, Lane.FOR_REVIEW)],
        start=11,
    ):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-rework-{idx}",
                mission_slug=MISSION_SLUG,
                wp_id="WP01",
                from_lane=src,
                to_lane=dst,
                at=f"2026-01-01T00:00:{idx}+00:00",
                actor="fixture",
                force=False,
                execution_mode="worktree",
            ),
        )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-approved",
            mission_slug=MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.FOR_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:20+00:00",
            actor="codex",
            force=False,
            execution_mode="worktree",
        ),
    )

    resolved_mission = ResolvedMission(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MISSION_ID[:8],
        feature_dir=feature_dir,
    )
    with (
        patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=resolved_mission),
        patch("specify_cli.cli.commands.agent_retrospect.apply_proposals", return_value=_empty_result()),
    ):
        result = CliRunner().invoke(app, ["retrospect", "synthesize", "--mission", MISSION_ID[:8], "--json", "--fabricate-empty"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["outcome"] == "retrospective_record_created"
