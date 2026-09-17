"""Registered mission CLI boundaries: config, activation and JSON failures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.doctrine import app as doctrine_app
from specify_cli.cli.commands.mission import app as mission_app
from specify_cli.cli.commands.mission_type import app as mission_type_app

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()
ROUTES = [
    (mission_app, ["list"]),
    (mission_type_app, ["list"]),
    (charter_app, ["mission-type", "list"]),
    (mission_type_app, ["show", "software-dev"]),
    (doctrine_app, ["mission-type", "list"]),
]


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Real config loader and roster; isolate project state from the checkout."""
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("mission_type_activations:\n  - software-dev\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def error_payload(result: Result, code: str | None = None) -> dict[str, Any]:
    assert result.exit_code != 0, result.output
    assert isinstance(result.exception, SystemExit), repr(result.exception)
    assert "Traceback" not in result.output
    value: dict[str, Any] = json.loads(result.stdout)
    assert value["ok"] is False
    assert isinstance(value["error"]["message"], str) and value["error"]["message"]
    assert isinstance(value["error"]["code"], str) and value["error"]["code"]
    if code is not None:
        assert value["error"]["code"] == code
    return value


@pytest.mark.regression
@pytest.mark.parametrize("app,args", ROUTES)
@pytest.mark.parametrize("contents", [b"- invalid-root\n", b"\xff\xfe"])
def test_issue_4600_content_load_names_config_without_traceback(project: Path, app: Any, args: list[str], contents: bytes) -> None:
    (project / ".kittify" / "config.yaml").write_bytes(contents)
    human = runner.invoke(app, args)
    machine = runner.invoke(app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    assert isinstance(human.exception, SystemExit), repr(human.exception)
    assert "config.yaml" in human.stdout
    payload = error_payload(machine)
    assert "config.yaml" in payload["error"]["message"]
    if contents == b"\xff\xfe":
        assert "decode" in payload["error"]["message"]


@pytest.mark.regression
@pytest.mark.parametrize("app,args", ROUTES[:3])
def test_issue_4598_aliases_keep_activation_subset(project: Path, app: Any, args: list[str]) -> None:
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, repr(result.exception)
    assert [row["id"] for row in json.loads(result.stdout)] == ["software-dev"]
    assert "OptionInfo" not in result.output


def test_inactive_discovery_and_doctrine_success_schema(project: Path) -> None:
    canonical = runner.invoke(charter_app, ["mission-type", "list", "--include-inactive", "--json"])
    doctrine = runner.invoke(doctrine_app, ["mission-type", "list", "--json"])
    assert canonical.exit_code == doctrine.exit_code == 0
    rows = json.loads(doctrine.stdout)
    assert len(rows) > 1
    assert {row["id"] for row in rows} == {row["id"] for row in json.loads(canonical.stdout)}
    assert all(set(row) == {"id", "source_layer", "display_name"} for row in rows)


@pytest.mark.regression
def test_issue_4601_unknown_type_json(project: Path) -> None:
    human = runner.invoke(mission_type_app, ["show", "missing-type"])
    machine = runner.invoke(mission_type_app, ["show", "missing-type", "--json"])
    assert human.exit_code == machine.exit_code == 1
    assert "missing-type" in error_payload(machine)["error"]["message"]


@pytest.mark.parametrize("app,args", ROUTES[:3])
def test_empty_activated_roster_is_json_success(project: Path, app: Any, args: list[str]) -> None:
    (project / ".kittify" / "config.yaml").write_text("mission_type_activations: []\n", encoding="utf-8")
    result = runner.invoke(app, [*args, "--json"])
    assert result.exit_code == 0, repr(result.exception)
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize(
    "args",
    [
        ["run", "missing-definition", "--mission", "missing-mission"],
        ["reopen", "missing-mission", "--reason", "repair"],
        ["follow-up", "missing-mission", "--pr", "1"],
    ],
)
def test_mutating_siblings_outside_project_are_json_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    monkeypatch.chdir(tmp_path)
    human = runner.invoke(mission_type_app, args)
    machine = runner.invoke(mission_type_app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    error_payload(machine, "not_in_project")


@pytest.mark.parametrize(
    "args",
    [
        ["run", "missing-definition", "--mission", "missing-mission"],
        ["reopen", "missing-mission", "--reason", "repair"],
        ["follow-up", "missing-mission"],
        ["follow-up", "missing-mission", "--commit", "invalid"],
        ["follow-up", "missing-mission", "--pr", "1"],
    ],
)
def test_mutating_siblings_reject_invalid_input_without_prose(project: Path, args: list[str]) -> None:
    human = runner.invoke(mission_type_app, args)
    machine = runner.invoke(mission_type_app, [*args, "--json"])
    assert human.exit_code == machine.exit_code
    error_payload(machine)


@pytest.mark.parametrize("app,args", ROUTES)
def test_malformed_roster_is_a_named_json_error(project: Path, app: Any, args: list[str]) -> None:
    org_root = project / "org"
    (org_root / "mission_types").mkdir(parents=True)
    (org_root / "mission_types" / "broken.yaml").write_text("id: [unterminated\n", encoding="utf-8")
    (project / ".kittify" / "config.yaml").write_text(
        f"mission_type_activations: [software-dev]\ncharter_packs:\n  org:\n    packs:\n      - name: test\n        local_path: {org_root}\n",
        encoding="utf-8",
    )
    human = runner.invoke(app, args)
    machine = runner.invoke(app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    assert "broken.yaml" in error_payload(machine)["error"]["message"]


@pytest.mark.parametrize(
    "command,args,branch,code",
    [
        ("reopen", ["--reason", "repair"], "unavailable-branch", "mission_branch_unavailable"),
        ("reopen", ["--reason", "repair"], None, "mission_not_completed"),
        ("follow-up", ["--pr", "1"], None, "mission_not_completed"),
    ],
)
def test_lifecycle_json_rejection_preserves_metadata(project: Path, command: str, args: list[str], branch: str | None, code: str) -> None:
    directory = project / "kitty-specs" / "demo-01KV0S99"
    directory.mkdir(parents=True)
    meta_path = directory / "meta.json"
    meta_path.write_text(
        json.dumps(
            {
                "mission_id": "01KV0S99ABCDEFGHJKMNPQRSTV",
                "mission_slug": directory.name,
                "mission_branch": branch,
            }
        ),
        encoding="utf-8",
    )
    before = meta_path.read_bytes()
    human = runner.invoke(mission_app, [command, directory.name, *args])
    machine = runner.invoke(mission_app, [command, directory.name, *args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    error_payload(machine, code)
    assert meta_path.read_bytes() == before
    assert list(directory.iterdir()) == [meta_path]


def test_root_registration_reaches_activated_aliases(project: Path) -> None:
    from click.testing import CliRunner as ClickRunner
    from typer.main import get_command

    from specify_cli import app

    cli = get_command(app)
    # Root global asset repair is outside the content-load boundary under test.
    # Keep the real registration tree, option binding and every child callback.
    cli.callback = None
    for route in (["mission", "list"], ["mission-type", "list"], ["charter", "mission-type", "list"]):
        result = ClickRunner().invoke(cli, [*route, "--json"])
        assert result.exit_code == 0, repr(result.exception)
        assert [row["id"] for row in json.loads(result.stdout)] == ["software-dev"]


def test_run_ambiguous_handle_emits_selector_error_before_runtime_start(project: Path) -> None:
    for slug, suffix in (("alpha", "AAAAAAAAAAAAAAAAAA"), ("beta", "BBBBBBBBBBBBBBBBBB")):
        directory = project / "kitty-specs" / f"{slug}-01KV0S99"
        directory.mkdir(parents=True)
        (directory / "meta.json").write_text(
            json.dumps({"mission_id": "01KV0S99" + suffix, "mission_slug": directory.name}),
            encoding="utf-8",
        )
    args = ["run", "unused-definition", "--mission", "01KV0S99"]
    human = runner.invoke(mission_app, args)
    machine = runner.invoke(mission_app, [*args, "--json"])
    assert human.exit_code == machine.exit_code == 1
    payload = error_payload(machine, "MISSION_AMBIGUOUS_SELECTOR")
    assert len(payload["candidates"]) == 2
    assert not (project / ".kittify" / "runtime").exists()
