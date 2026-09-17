"""Adopted glossary error and empty-success contract."""

from __future__ import annotations
import json
from pathlib import Path
import pytest
from typer.testing import CliRunner
from specify_cli.cli.commands.glossary import app


@pytest.mark.parametrize("args", [["list"], ["list", "--scope", "bad"], ["list", "--status", "bad"], ["conflicts", "--strictness", "bad"]])
def test_glossary_errors_are_json(args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, [*args, "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] and payload["error"]["message"]
    assert result.stderr == ""


@pytest.mark.parametrize("directory", [False, True])
@pytest.mark.parametrize("content", ["bad: [", "terms: invalid"])
def test_glossary_invalid_validation_envelope(directory: bool, content: str, tmp_path: Path) -> None:
    seed = tmp_path / "team_domain.yaml"
    seed.write_text(content, encoding="utf-8")
    result = CliRunner().invoke(app, ["validate", str(tmp_path if directory else seed), "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["message"]


@pytest.mark.parametrize("command", ["list", "conflicts"])
def test_glossary_empty_success_unchanged(command: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".kittify/glossaries").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, [command, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == []


def test_glossary_corrupt_seed_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / ".kittify/glossaries"
    directory.mkdir(parents=True)
    (directory / "team_domain.yaml").write_text("bad: [", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(app, ["list", "--json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["error"]["message"]


def test_glossary_missing_validation_path(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["validate", str(tmp_path / "missing.yaml"), "--json"])
    assert result.exit_code == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "invalid_path"
