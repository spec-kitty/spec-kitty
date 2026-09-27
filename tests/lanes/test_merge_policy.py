"""Tests for the lane-only merge contract."""

from __future__ import annotations

import json
import pytest

from typer.testing import CliRunner

from specify_cli import app as cli_app
from tests.lane_test_utils import write_single_lane_manifest

pytestmark = pytest.mark.git_repo


runner = CliRunner()


def test_merge_dry_run_loads_lane_manifest(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    feature_dir = repo_root / "kitty-specs" / "010-feat"
    feature_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01", "WP02"), target_branch="main")

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr("specify_cli.cli.commands.consolidate.find_repo_root", lambda: repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.consolidate._enforce_git_preflight", lambda *_a, **_k: None)
    monkeypatch.setattr("specify_cli.consolidation.preflight.run_command", fake_run_command)
    monkeypatch.setattr("specify_cli.consolidation.resolve.run_command", fake_run_command)

    result = runner.invoke(cli_app, ["consolidate", "--json", "--dry-run", "--mission", "010-feat", "--target", "main"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout.strip())
    assert payload["mission_branch"] == "kitty/mission-010-feat"
    assert payload["lanes"][0]["wp_ids"] == ["WP01", "WP02"]


def test_merge_dry_run_refuses_missing_lanes_manifest(monkeypatch, tmp_path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    (repo_root / "kitty-specs" / "010-feat").mkdir(parents=True)

    def fake_run_command(cmd, capture=False, **_kwargs):
        if cmd[:4] == ["git", "rev-parse", "--verify", "refs/heads/main"]:
            return 0, "main", ""
        return 0, "", ""

    monkeypatch.setattr("specify_cli.cli.commands.consolidate.find_repo_root", lambda: repo_root)
    monkeypatch.setattr("specify_cli.cli.commands.consolidate._enforce_git_preflight", lambda *_a, **_k: None)
    monkeypatch.setattr("specify_cli.consolidation.preflight.run_command", fake_run_command)
    monkeypatch.setattr("specify_cli.consolidation.resolve.run_command", fake_run_command)

    result = runner.invoke(cli_app, ["consolidate", "--json", "--dry-run", "--mission", "010-feat", "--target", "main"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout.strip())
    assert "lanes.json is required" in payload["error"]
