"""Issue #4597/#4601: context commands honor real defaults and JSON boundaries."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.context import app
from specify_cli.workspace.context import WorkspaceContext, save_context

pytestmark = [pytest.mark.fast, pytest.mark.unit]
runner = CliRunner()


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / ".kittify").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_4597_default_invocation_matches_info(project: Path) -> None:
    implicit = runner.invoke(app, [])
    explicit = runner.invoke(app, ["info"])
    assert implicit.exit_code == explicit.exit_code == 1
    assert implicit.stdout == explicit.stdout
    assert "OptionInfo" not in implicit.output


@pytest.mark.parametrize(
    "args,code,exit_code",
    [
        (["info"], "no_worktree", 1),
        (["info", "--workspace", "missing"], "workspace_not_found", 1),
        (["mission-show", "--context", "ctx-missing"], "context_not_found", 1),
        (["mission-resolve", "--wp", "WP01"], "missing_mission", 2),
        (["mission-resolve", "--wp", "WP01", "--mission", "missing"], "context_resolution_failed", 1),
    ],
)
def test_4601_context_errors_are_json(project: Path, args: list[str], code: str, exit_code: int) -> None:
    human = runner.invoke(app, args)
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == human.exit_code == exit_code
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == code
    assert payload["error"]["message"]
    assert result.stderr == ""


@pytest.mark.parametrize(
    "args",
    [
        ["info"],
        ["list"],
        ["mission-show", "--context", "ctx-missing"],
        ["mission-resolve", "--wp", "WP01", "--mission", "missing"],
    ],
)
def test_non_project_context_errors_are_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "not_in_project"
    assert result.stderr == ""


@pytest.mark.parametrize("args", [["list"], ["list", "--orphaned"]])
def test_empty_context_lists_are_success(project: Path, args: list[str]) -> None:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == []
    assert result.stderr == ""


def test_workspace_success_preserves_payload_and_default_detection(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = "demo-lane-a"
    worktree = project / ".worktrees" / workspace
    worktree.mkdir(parents=True)
    context = WorkspaceContext(
        wp_id="WP01",
        mission_slug="demo",
        worktree_path=f".worktrees/{workspace}",
        branch_name="kitty/mission-demo-lane-a",
        base_branch="main",
        base_commit=None,
        dependencies=[],
        created_at="2026-09-16T00:00:00Z",
        created_by="test",
        vcs_backend="git",
        lane_id="lane-a",
        lane_wp_ids=["WP01"],
        current_wp="WP01",
    )
    save_context(project, context)
    monkeypatch.chdir(worktree)
    assert runner.invoke(app, []).stdout == runner.invoke(app, ["info"]).stdout
    result = runner.invoke(app, ["info", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == context.to_dict()
    assert result.stderr == ""


def test_corrupt_token_emits_canonical_json(project: Path) -> None:
    contexts = project / ".kittify" / "runtime" / "contexts"
    contexts.mkdir(parents=True)
    (contexts / "ctx-broken.json").write_text("{bad", encoding="utf-8")
    result = runner.invoke(app, ["mission-show", "--context", "ctx-broken", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "context_corrupted"
    assert result.stderr == ""


def test_main_cli_registration_reaches_context_json_boundary(project: Path) -> None:
    from specify_cli import app as root_app

    result = runner.invoke(root_app, ["context", "info", "--workspace", "missing", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "workspace_not_found"
    assert result.stderr == ""


@pytest.mark.parametrize("json_output", [False, True])
@pytest.mark.parametrize("unreadable", [False, True], ids=["non-utf8", "directory"])
def test_corrupt_token_read_failure_is_controlled(project: Path, json_output: bool, unreadable: bool) -> None:
    """R1: real decoding/OS failures reach the registered command boundary."""
    contexts = project / ".kittify" / "runtime" / "contexts"
    contexts.mkdir(parents=True)
    token_file = contexts / "ctx-broken.json"
    if unreadable:
        token_file.mkdir()
    else:
        token_file.write_bytes(b"\xff\xfe")
    args = ["mission-show", "--context", "ctx-broken"]
    if json_output:
        args.append("--json")
    result = runner.invoke(app, args)
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), result.exception
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "context_corrupted"
        assert "ctx-broken" in payload["error"]["message"]
        assert result.stderr == ""
    else:
        assert "ctx-broken" in result.stdout
    assert "Traceback" not in result.output


@pytest.mark.parametrize("args", [["info", "--workspace", "broken"], ["list"], ["list", "--orphaned"]])
@pytest.mark.parametrize("json_output", [False, True])
def test_workspace_read_failure_is_controlled(project: Path, args: list[str], json_output: bool) -> None:
    """A directory at a workspace-file path is a failed read, never empty data."""
    workspace_file = project / ".kittify" / "workspaces" / "broken.json"
    workspace_file.mkdir(parents=True)
    result = runner.invoke(app, [*args, *(["--json"] if json_output else [])])
    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    if json_output:
        payload = json.loads(result.stdout)
        assert payload["ok"] is False
        assert payload["error"]["code"] == "workspace_read_failed"
        assert "broken.json" in payload["error"]["message"]
        assert result.stderr == ""
    else:
        assert "broken.json" in result.stdout
    assert "Traceback" not in result.output
    assert workspace_file.is_dir()
