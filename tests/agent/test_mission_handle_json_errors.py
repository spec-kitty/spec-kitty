from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands.agent import app as agent_app
from specify_cli.cli.commands.doctor import app as doctor_app
from specify_cli.cli.commands.implement import implement as implement_command
from specify_cli.cli.selector_resolution import resolve_mission_handle

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.agent]


def _make_mission(repo_root: Path, slug: str) -> Path:
    mission_id = "01" + hashlib.sha1(slug.encode("utf-8")).hexdigest().upper()[:24]
    mission_dir = repo_root / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "mission_type": "software-dev",
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return mission_dir


def _make_repo(repo_root: Path) -> None:
    (repo_root / ".kittify").mkdir()
    (repo_root / ".kittify" / "config.yaml").write_text(
        "project:\n  uuid: 00000000-0000-0000-0000-000000000173\n",
        encoding="utf-8",
    )


def test_resolve_mission_handle_json_error_uses_stdout_exit_1(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _make_repo(tmp_path)
    _make_mission(tmp_path, "021-context-test")

    with pytest.raises(SystemExit) as exc_info:
        resolve_mission_handle("missing-mission", tmp_path, json_mode=True)

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_NOT_FOUND"
    assert payload["handle"] == "missing-mission"


def test_agent_tasks_status_json_bad_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _make_mission(tmp_path, "021-context-test")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        agent_app,
        ["tasks", "status", "--mission", "missing-mission", "--json"],
    )

    assert result.exit_code == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MISSION_NOT_FOUND"


def test_agent_issue_verdict_json_ambiguous_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _make_mission(tmp_path, "020-charter")
    _make_mission(tmp_path, "030-charter")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        agent_app,
        [
            "issue-verdict",
            "--mission",
            "charter",
            "--issue",
            "#173",
            "--verdict",
            "fixed",
            "--actor",
            "tester",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert len(payload["candidates"]) == 2


def test_agent_tasks_status_json_ambiguous_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ambiguous status selectors preserve candidates and the human exit code."""
    _make_repo(tmp_path)
    _make_mission(tmp_path, "020-charter")
    _make_mission(tmp_path, "030-charter")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        agent_app,
        ["tasks", "status", "--mission", "charter", "--json"],
    )

    assert result.exit_code == 2
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert payload["handle"] == "charter"
    assert payload["candidates"] == ["020-charter", "030-charter"]


def test_agent_status_materialize_json_ambiguous_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#241: ``agent status`` commands share the same
    ``status.py:_find_mission_slug`` read-path resolver as ``tasks_shared``'s
    copy — the squad's second reproduction (`agent status materialize
    --mission charter --json`) must resolve to the same shared envelope.
    """
    _make_repo(tmp_path)
    _make_mission(tmp_path, "020-charter")
    _make_mission(tmp_path, "030-charter")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        agent_app,
        ["status", "materialize", "--mission", "charter", "--json"],
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert payload["handle"] == "charter"
    assert payload["candidates"] == ["020-charter", "030-charter"]


def test_implement_json_ambiguous_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _make_mission(tmp_path, "020-charter")
    _make_mission(tmp_path, "030-charter")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)

    from specify_cli.charter_runtime.preflight import hook as preflight_hook

    monkeypatch.setattr(preflight_hook, "run_preflight_or_abort", lambda *_args, **_kwargs: None)

    app = typer.Typer()
    app.command()(implement_command)
    result = CliRunner().invoke(
        app,
        ["WP01", "--mission", "charter", "--json"],
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert len(payload["candidates"]) == 2


def test_doctor_review_cycle_reconcile_json_bad_mission_uses_stdout_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _make_repo(tmp_path)
    _make_mission(tmp_path, "021-context-test")
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "specify_cli.cli.commands.doctor.locate_project_root",
        lambda: tmp_path,
    )

    result = CliRunner().invoke(
        doctor_app,
        ["review-cycle-reconcile", "--mission", "missing-mission", "--json"],
    )

    assert result.exit_code == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_NOT_FOUND"
