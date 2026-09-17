"""Remaining adopted command error streams and success compatibility."""

from __future__ import annotations
import json
from collections.abc import Callable
from typing import Any
from pathlib import Path
import pytest
import typer
from typer.testing import CliRunner
from specify_cli.cli.commands import archive, dashboard, materialize, verify


@pytest.mark.parametrize("name", ["archive-create", "archive-list", "materialize", "dashboard", "verify"])
def test_missing_project_json(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    if name.startswith("archive"):
        app = archive.app
        args = ["create", "missing", "--by", "test", "--reason", "test"] if name == "archive-create" else ["list"]
    else:
        app = typer.Typer()
        commands: dict[str, Callable[..., Any]] = {"materialize": materialize.materialize, "dashboard": dashboard.dashboard, "verify": verify.verify_setup}
        app.command()(commands[name])
        args = []
    result = CliRunner().invoke(app, [*args, "--json"])
    assert result.exit_code == (2 if name.startswith("archive") else 1), result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] and payload["error"]["message"]
    assert result.stderr == ""


@pytest.mark.parametrize("name", ["archive", "materialize"])
def test_missing_mission_json(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    monkeypatch.chdir(tmp_path)
    if name == "archive":
        app = archive.app
        args = ["create", "missing", "--by", "test", "--reason", "test"]
    else:
        app = typer.Typer()
        app.command()(materialize.materialize)
        args = ["--mission", "missing"]
    result = CliRunner().invoke(app, [*args, "--json"])
    assert result.exit_code == (2 if name == "archive" else 1)
    assert json.loads(result.stdout)["error"]["code"] == "mission_not_found"


def test_dashboard_empty_registry_keeps_success_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    monkeypatch.chdir(tmp_path)
    app = typer.Typer()
    app.command()(dashboard.dashboard)
    result = CliRunner().invoke(app, ["--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"missions": {}, "display_order": []}


def test_archive_nonterminal_refusal_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    mission = tmp_path / "kitty-specs" / "not-terminal"
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(json.dumps({"mission_slug": "not-terminal", "mission_type": "software-dev"}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(archive.app, ["create", "not-terminal", "--by", "test", "--reason", "test", "--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "AM-1"


def test_materialize_partial_failure_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    mission = tmp_path / "kitty-specs" / "broken"
    mission.mkdir(parents=True)
    (mission / "status.events.jsonl").write_text("not json\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    app = typer.Typer()
    app.command()(materialize.materialize)
    result = CliRunner().invoke(app, ["--json"])
    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "materialize_failed"
    assert payload["errors"]


@pytest.mark.regression
@pytest.mark.parametrize("name", ["archive", "materialize", "verify", "verify-diagnostics"])
def test_ambiguous_selector_is_controlled_json(name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify/config.yaml").write_text("{}\n", encoding="utf-8")
    candidates = ["alpha-01KV0S99", "beta-01KV0S99"]
    for slug, suffix in zip(candidates, ("A", "B"), strict=True):
        directory = tmp_path / "kitty-specs" / slug
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(json.dumps({"mission_id": "01KV0S99" + suffix * 18, "mission_slug": slug}), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    if name == "archive":
        app = archive.app
        args = ["create", "01KV0S99", "--by", "test", "--reason", "test"]
    else:
        app = typer.Typer()
        app.command()(materialize.materialize if name == "materialize" else verify.verify_setup)
        args = ["--mission", "01KV0S99"]
        if name == "verify-diagnostics":
            args.append("--diagnostics")
    before = {p: p.read_bytes() for p in (tmp_path / "kitty-specs").rglob("*") if p.is_file()}
    human = CliRunner().invoke(app, args)
    machine = CliRunner().invoke(app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    assert isinstance(human.exception, SystemExit), repr(human.exception)
    assert isinstance(machine.exception, SystemExit), repr(machine.exception)
    payload = json.loads(machine.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "MISSION_AMBIGUOUS_SELECTOR"
    assert payload["error"]["message"]
    assert payload["handle"] == "01KV0S99"
    assert sorted(payload["candidates"]) == candidates
    assert machine.stderr == ""
    assert "Traceback" not in human.output + machine.output
    assert before == {p: p.read_bytes() for p in (tmp_path / "kitty-specs").rglob("*") if p.is_file()}
