"""CLI contract tests for ``spec-kitty agent status emit``."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.status import app

pytestmark = pytest.mark.fast

runner = CliRunner()


@pytest.fixture(autouse=True)
def _disable_emit_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep status emit CLI tests focused on local persistence output."""
    import specify_cli.status.emit as status_emit

    monkeypatch.setattr(status_emit, "_status_fan_out", lambda *args, **kwargs: None)
from tests.status.conftest import seed_wp_to_planned as _seed_wp


def _seed_planned_event(feature_dir: Path, slug: str, wp_id: str = "WP01") -> None:
    """Seed a WP out of the non-display 'genesis' state into 'planned'."""
    _seed_wp(feature_dir, wp_id, slug=slug)


@pytest.fixture
def repo_with_mission(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    feature_dir = repo / "kitty-specs" / "017-test-feature"
    feature_dir.mkdir(parents=True)
    (repo / ".kittify").mkdir()
    _seed_planned_event(feature_dir, "017-test-feature")
    return repo


@patch("specify_cli.cli.commands.agent.status.locate_project_root")
@patch("specify_cli.cli.commands.agent.status._find_mission_slug")
def test_status_emit_success_includes_contract_fields(
    mock_slug,
    mock_root,
    repo_with_mission: Path,
) -> None:
    mock_root.return_value = repo_with_mission
    mock_slug.return_value = "017-test-feature"

    result = runner.invoke(
        app,
        [
            "emit",
            "WP01",
            "--to",
            "claimed",
            "--actor",
            "codex",
            "--mission",
            "017-test-feature",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    output = json.loads(result.stdout)
    assert output["event_id"]
    assert output["wp_id"] == "WP01"
    assert output["work_package_id"] == "WP01"
    assert output["to_lane"] == "claimed"
    assert output["status_events_path"] == str(
        repo_with_mission / "kitty-specs" / "017-test-feature" / "status.events.jsonl"
    )


@patch("specify_cli.cli.commands.agent.status.locate_project_root")
@patch("specify_cli.cli.commands.agent.status._find_mission_slug")
def test_status_emit_readback_failure_uses_structured_diagnostic(
    mock_slug,
    mock_root,
    repo_with_mission: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_root.return_value = repo_with_mission
    mock_slug.return_value = "017-test-feature"

    import specify_cli.status.store as status_store

    monkeypatch.setattr(
        status_store,
        "_append_serialized_atomic",
        lambda _feature_dir, _events: None,
    )

    result = runner.invoke(
        app,
        [
            "emit",
            "WP01",
            "--to",
            "claimed",
            "--actor",
            "codex",
            "--mission",
            "017-test-feature",
            "--json",
        ],
    )

    assert result.exit_code == 1
    output = json.loads(result.stdout)
    assert output["diagnostic_code"] == "STATUS_EVENT_PERSISTENCE_VERIFICATION_FAILED"
    assert output["violated_invariant"] == "STA-002"
    assert output["remediation"]
    assert output["mission_slug"] == "017-test-feature"
    assert output["work_package_id"] == "WP01"
    assert output["wp_id"] == "WP01"
    assert output["to_lane"] == "claimed"
    assert output["status_events_path"] == str(
        repo_with_mission / "kitty-specs" / "017-test-feature" / "status.events.jsonl"
    )
    assert "persistence verification failed" in output["error"]
