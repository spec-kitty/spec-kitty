from __future__ import annotations

import pytest
import typer
from typer.core import TyperGroup
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands import (
    _TOP_LEVEL_GROUP_EMPTY_INVOCATION_EXCEPTIONS,
    _enforce_top_level_empty_group_help,
    _top_level_group_invokes_without_command,
    _top_level_group_name,
    register_commands,
)

# In-process Typer/CliRunner assertions; no subprocess, no filesystem.
pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _registered_root() -> typer.Typer:
    app = typer.Typer()
    register_commands(app)
    return app


def test_registered_top_level_groups_default_to_help(monkeypatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    app = _registered_root()
    command = get_command(app)

    for group_info in app.registered_groups:
        name = _top_level_group_name(group_info)
        if name in _TOP_LEVEL_GROUP_EMPTY_INVOCATION_EXCEPTIONS:
            continue
        if _top_level_group_invokes_without_command(group_info):
            continue

        assert command.commands[str(name)].no_args_is_help is True, name


def test_empty_doctor_invocation_runs_the_default_checks(monkeypatch) -> None:
    """#6969: bare ``doctor`` runs the default checks instead of refusing with exit 2.

    #4678 made the bare group print its help and exit 2 so an empty run could
    not be mistaken for a passing check. #6969 keeps that intent -- a bare run
    reports a real verdict -- but runs the default check set instead of a usage
    error, so exit 2 (which reads as a failure or a misuse to a wrapper) is gone.
    """
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    result = CliRunner().invoke(_registered_root(), ["doctor"])

    assert result.exit_code in {0, 1}, result.output
    assert "Default checks" in result.output
    assert "no diagnostic ran" not in result.output
    assert "Missing command" not in result.output


def test_doctor_subcommand_help_is_unaffected(monkeypatch) -> None:
    """The bare-invocation guard must not intercept real subcommands (#4678)."""
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")
    result = CliRunner().invoke(_registered_root(), ["doctor", "channel", "--help"])

    assert result.exit_code == 0
    assert "no diagnostic ran" not in result.output


def test_future_top_level_groups_are_covered_by_registration_guard() -> None:
    app = typer.Typer()
    future_app = typer.Typer(help="Future command group")
    future_app.command("ping")(lambda: None)
    app.add_typer(future_app, name="future")

    _enforce_top_level_empty_group_help(app)
    result = CliRunner().invoke(app, ["future"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Future command group" in result.output
    assert "Missing command" not in result.output


def test_future_custom_top_level_group_classes_are_preserved() -> None:
    class CustomGroup(TyperGroup):
        pass

    app = typer.Typer()
    future_app = typer.Typer(help="Future custom group", cls=CustomGroup)
    future_app.command("ping")(lambda: None)
    app.add_typer(future_app, name="future")

    _enforce_top_level_empty_group_help(app)
    command = get_command(app).commands["future"]
    result = CliRunner().invoke(app, ["future"])

    assert isinstance(command, CustomGroup)
    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "Future custom group" in result.output
    assert "Missing command" not in result.output
