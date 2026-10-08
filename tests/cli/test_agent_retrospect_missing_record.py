from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app
from specify_cli.context.mission_resolver import ResolvedMission
from specify_cli.charter_pack_synthesizer import SynthesisResult
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
MISSION_ID = "01KQ6YEG000000000000000000"
MISSION_SLUG = "001-retro-missing"


def _resolved(feature_dir: Path) -> ResolvedMission:
    return ResolvedMission(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        mid8=MISSION_ID[:8],
        feature_dir=feature_dir,
    )


def _empty_result() -> SynthesisResult:
    return SynthesisResult(
        dry_run=True,
        planned=[],
        applied=[],
        conflicts=[],
        rejected=[],
        events_emitted=[],
    )


def _completed_mission(repo: Path) -> Path:
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ndependencies: []\ntitle: WP01\n---\n# WP01\n",
        encoding="utf-8",
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="seed-WP01-done",
            mission_slug=MISSION_SLUG,
            wp_id="WP01",
            from_lane=Lane.APPROVED,
            to_lane=Lane.DONE,
            at="2026-01-01T00:00:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )
    return feature_dir


def test_missing_record_completed_mission_blocks_and_points_to_create(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    feature_dir = _completed_mission(repo)

    with (
        patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=_resolved(feature_dir)),
        patch("specify_cli.cli.commands.agent_retrospect.apply_proposals", return_value=_empty_result()),
    ):
        result = runner.invoke(app, ["retrospect", "synthesize", "--mission", MISSION_ID[:8], "--json"])

    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert payload["result"] == "blocked"
    assert payload["code"] == "RETROSPECTIVE_RECORD_MISSING"
    assert payload["mission_id"] == MISSION_ID
    assert payload["mission_slug"] == MISSION_SLUG
    assert "spec-kitty retrospect create" in payload["blocked_reason"]
    assert not (repo / ".kittify" / "missions" / MISSION_ID / "retrospective.yaml").exists()


def test_missing_record_insufficient_artifacts_returns_parseable_json(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)

    with (
        patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent_retrospect.resolve_mission_handle", return_value=_resolved(feature_dir)),
    ):
        result = runner.invoke(
            app,
            ["retrospect", "synthesize", "--mission", MISSION_ID[:8], "--fabricate-empty", "--json"],
        )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["outcome"] == "insufficient_mission_artifacts"
    assert payload["mission_id"] == MISSION_ID
    assert payload["mission_slug"] == MISSION_SLUG
    assert payload["error"] == "record_not_found"
    assert payload["next_action"]


def test_missing_mission_returns_parseable_json_outcome(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify").mkdir()
    (repo / "kitty-specs").mkdir()

    with patch("specify_cli.cli.commands.agent_retrospect.locate_project_root", return_value=repo):
        result = runner.invoke(app, ["retrospect", "synthesize", "--mission", "does-not-exist", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["status"] == "error"
    assert payload["outcome"] == "MISSION_NOT_FOUND"
    assert payload["error"] == "MISSION_NOT_FOUND"
    assert payload["next_action"]
