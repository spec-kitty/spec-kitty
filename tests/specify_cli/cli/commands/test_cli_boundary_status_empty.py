"""Real zero-WP status regression for #4643 (FR-006/012)."""

from __future__ import annotations
import json
from pathlib import Path
import subprocess
import pytest
from typer.testing import CliRunner
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.agent_utils.status import show_kanban_status

pytestmark = [pytest.mark.regression, pytest.mark.git_repo]


@pytest.fixture
def empty_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("{}\n", encoding="utf-8")
    slug = "empty-status-01M2NQCB"
    mission = tmp_path / "kitty-specs" / slug
    (mission / "tasks").mkdir(parents=True)
    (mission / "meta.json").write_text(json.dumps({"mission_slug": slug, "mission_type": "software-dev", "target_branch": "main"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return slug


def test_issue_4643_real_empty_status_json(empty_mission: str) -> None:
    result = CliRunner().invoke(app, ["status", "--mission", empty_mission, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert "error" not in payload
    assert payload["total_wps"] == 0
    assert payload["work_packages"] == []
    assert payload["stale_verdicts"] == []
    assert result.stderr == ""


def test_empty_agent_status_is_success(empty_mission: str) -> None:
    result = show_kanban_status(empty_mission)
    assert "error" not in result
    assert result["work_packages"] == []
    assert result["total_wps"] == 0


def test_status_builder_is_silent(empty_mission: str, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.agent_utils.status import build_kanban_status

    payload = build_kanban_status(empty_mission)
    assert payload["total_wps"] == 0
    assert "error" not in payload
    assert capsys.readouterr().out == ""


def test_status_builder_failure_is_typed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    from specify_cli.agent_utils.status import build_kanban_status

    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Not in a spec-kitty project"):
        build_kanban_status("missing")
    assert capsys.readouterr().out == ""


def test_status_empty_human_message(empty_mission: str) -> None:
    result = CliRunner().invoke(app, ["status", "--mission", empty_mission])
    assert result.exit_code == 0, result.output
    assert "No work packages found" in result.stdout


def test_root_registered_empty_status_json(empty_mission: str) -> None:
    from specify_cli import app as root_app

    result = CliRunner().invoke(root_app, ["agent", "tasks", "status", "--mission", empty_mission, "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["work_packages"] == []
    assert "error" not in payload


@pytest.mark.parametrize(
    "handle,code,exit_code",
    [(None, "mission_required", 1), ("missing", "MISSION_NOT_FOUND", 2), ("01KV0S99", "MISSION_AMBIGUOUS_SELECTOR", 2)],
)
def test_status_selector_errors_use_canonical_shape_and_human_exit(empty_mission: str, handle: str | None, code: str, exit_code: int) -> None:
    for name, suffix in (("alpha", "A"), ("beta", "B")):
        slug = f"{name}-01KV0S99"
        directory = Path("kitty-specs") / slug
        directory.mkdir()
        (directory / "meta.json").write_text(json.dumps({"mission_id": "01KV0S99" + suffix * 18, "mission_slug": slug}), encoding="utf-8")
    args = ["status"] + (["--mission", handle] if handle is not None else [])
    human = CliRunner().invoke(app, args)
    machine = CliRunner().invoke(app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == exit_code
    assert isinstance(machine.exception, SystemExit), repr(machine.exception)
    payload = json.loads(machine.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == code
    assert payload["error"]["message"]
    assert machine.stderr == ""
    if handle is not None:
        assert payload["handle"] == handle
    if handle == "01KV0S99":
        assert sorted(payload["candidates"]) == ["alpha-01KV0S99", "beta-01KV0S99"]


@pytest.mark.parametrize("handle", [None, "missing"])
def test_shared_selector_default_keeps_existing_error_contract(empty_mission: str, handle: str | None, capsys: pytest.CaptureFixture[str]) -> None:
    import typer
    from specify_cli.cli.commands.agent.tasks_shared import _find_mission_slug

    with pytest.raises((SystemExit, typer.Exit)) as exc_info:
        _find_mission_slug(handle, json_output=True, repo_root=Path.cwd())
    exc = exc_info.value
    if isinstance(exc, SystemExit):
        assert exc.code == 1
    else:
        assert isinstance(exc, typer.Exit)
        assert exc.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload["error"], str)
    assert "ok" not in payload
    if handle is not None:
        assert payload["success"] is False
        assert payload["error_code"] == "MISSION_NOT_FOUND"
        assert payload["handle"] == handle
