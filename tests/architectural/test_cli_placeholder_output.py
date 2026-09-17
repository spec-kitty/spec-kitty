"""G2: execute every no-subcommand callback and reject Typer object reprs."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner
from typer.main import get_command

from tests.architectural.test_json_contract_enumeration import walk_commands

pytestmark = pytest.mark.architectural
CALLBACK_PATHS = {"", "context", "migrate", "charter list"}


def assert_no_placeholders(output: str) -> None:
    for marker in ("OptionInfo", "ArgumentInfo", "typer.models.OptionInfo"):
        assert marker not in output, output


def isolate_global_io(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep root/default binding real; replace only unrelated external services."""
    # On Windows migrate performs this before checking the project root.
    monkeypatch.setattr("specify_cli.paths.windows_migrate.migrate_windows_state", lambda **_kwargs: [])
    monkeypatch.setattr("specify_cli.runtime.bootstrap.ensure_runtime", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.agent_skills.ensure_global_agent_skills", lambda: None)
    monkeypatch.setattr("specify_cli.runtime.agent_commands.ensure_global_agent_commands", lambda: None)
    monkeypatch.setattr("specify_cli.readiness.evaluate_readiness", lambda _ctx: None)
    monkeypatch.setattr("specify_cli.core.version_checker.maybe_emit_no_upgrade_notice", lambda _command: None)


@pytest.fixture(scope="module")
def callback_graph() -> click.Command:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["spec-kitty"])
        import specify_cli

        return get_command(specify_cli.app)


def test_callback_inventory(callback_graph: click.Command) -> None:
    actual = {path for path, cmd in walk_commands(callback_graph) if isinstance(cmd, click.Group) and cmd.invoke_without_command}
    assert actual == CALLBACK_PATHS, f"Classify newly registered callbacks: {actual ^ CALLBACK_PATHS}"


@pytest.mark.parametrize("path", sorted(CALLBACK_PATHS))
def test_no_subcommand_callback_output(callback_graph: click.Command, path: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *path.split()])
    isolate_global_io(monkeypatch)
    command = dict(walk_commands(callback_graph))[path]
    callback = command.callback
    assert callback is not None
    calls: list[bool] = []

    def observed(*args: Any, **kwargs: Any) -> Any:
        calls.append(True)
        return callback(*args, **kwargs)

    monkeypatch.setattr(command, "callback", observed)
    result = CliRunner().invoke(command, [])
    assert calls == [True], "Guard must actually execute callback, not help-only dispatch"
    assert result.exception is None or isinstance(result.exception, SystemExit), repr(result.exception)
    assert_no_placeholders(result.stdout + result.stderr)
    assert result.output, "Callback fixture must produce observable output"


@pytest.mark.parametrize("marker", ["OptionInfo", "ArgumentInfo", "typer.models.OptionInfo"])
def test_placeholder_mutation_is_rejected(callback_graph: click.Command, marker: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    command = dict(walk_commands(callback_graph))["context"]
    callback: Callable[..., Any] | None = command.callback
    assert callback is not None

    def contaminated(*args: Any, **kwargs: Any) -> Any:
        click.echo(f"<{marker} object at 0x1234>")
        return callback(*args, **kwargs)

    monkeypatch.setattr(command, "callback", contaminated)
    result = CliRunner().invoke(command, [])
    with pytest.raises(AssertionError, match=marker):
        assert_no_placeholders(result.stdout + result.stderr)
