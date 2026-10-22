"""Regression coverage for task status progress semantics."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

runner = CliRunner()


def _create_project(tmp_path: Path, mission_slug: str, lanes: dict[str, str]) -> Path:
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": mission_slug,
                "mission_number": "099",
                "mission_type": "software-dev",
            }
        ),
        encoding="utf-8",
    )

    for wp_id, lane in lanes.items():
        task_file = tasks_dir / f"{wp_id}-test.md"
        task_file.write_text(
            textwrap.dedent(
                f"""\
                ---
                work_package_id: {wp_id}
                title: Test {wp_id}
                execution_mode: code_change
                ---
                # {wp_id}
                """
            ),
            encoding="utf-8",
        )
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"test-{wp_id}-{lane}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane),
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )

    return feature_dir


def _invoke_status(tmp_path: Path, mission_slug: str, *args: str) -> object:
    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    with setup_mocked_env(tmp_path, workspace_resolution=workspace):
        return runner.invoke(app, ["status", "--mission", mission_slug, *args])


def test_status_json_separates_done_and_weighted_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission_slug = "099-progress-semantics"
    _create_project(tmp_path, mission_slug, {"WP01": "approved", "WP02": "approved"})
    monkeypatch.chdir(tmp_path)

    result = _invoke_status(tmp_path, mission_slug, "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["done_count"] == 0
    assert payload["total_wps"] == 2
    assert payload["done_percentage"] == pytest.approx(0.0)
    assert payload["progress_percentage"] == pytest.approx(80.0)
    assert payload["weighted_percentage"] == pytest.approx(80.0)
    assert payload["progress_semantics"] == "weighted_readiness"


def test_status_human_output_separates_done_and_weighted_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mission_slug = "099-progress-semantics"
    _create_project(tmp_path, mission_slug, {"WP01": "approved", "WP02": "approved"})
    monkeypatch.chdir(tmp_path)

    result = _invoke_status(tmp_path, mission_slug)

    assert result.exit_code == 0, result.output
    assert "Done progress:" in result.output
    assert "0/2 (0.0%)" in result.output
    assert "Weighted readiness:" in result.output
    assert "80.0%" in result.output
    assert "Progress: 0/2 (80.0%)" not in result.output
