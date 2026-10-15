"""Short help flag coverage for the root CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = [pytest.mark.fast]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _bypass_startup_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.root_callback", lambda _ctx: None)
    monkeypatch.setattr("specify_cli._run_startup_project_gates", lambda _ctx: None)
    monkeypatch.setattr("specify_cli.runtime.agent_commands.ensure_global_agent_commands", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.agent_skills.ensure_global_agent_skills", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.bootstrap.ensure_runtime", lambda: None)


@pytest.mark.parametrize(
    ("path", "markers"),
    [
        ([], ["Usage:", "Options", "Commands"]),
        (["agent"], ["Usage:", "mission", "tasks"]),
        (["agent", "mission"], ["Usage:", "create", "finalize-tasks"]),
        (["agent", "tasks"], ["Usage:", "list-tasks", "mark-status"]),
    ],
)
def test_short_help_flag_matches_long_help(path: list[str], markers: list[str]) -> None:
    short_result = runner.invoke(cli_app, [*path, "-h"])
    long_result = runner.invoke(cli_app, [*path, "--help"])

    assert short_result.exit_code == 0
    assert long_result.exit_code == 0
    assert "-h" in long_result.output

    for marker in markers:
        assert marker in short_result.output
        assert marker in long_result.output


def test_unknown_short_option_still_fails() -> None:
    result = runner.invoke(cli_app, ["--definitely-not-a-real-option"])

    assert result.exit_code != 0
