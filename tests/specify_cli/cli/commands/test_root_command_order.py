"""Root command ordering tests."""

from __future__ import annotations

import sys

import pytest
from typer.main import get_command

from specify_cli import app as cli_app
from specify_cli.cli.helpers import callback as root_callback
from tests import _click_universe as typer_click

pytestmark = [pytest.mark.fast]


def _visible_root_command_names(command: typer_click.Group, ctx: typer_click.Context) -> list[str]:
    return [
        name
        for name in command.list_commands(ctx)
        if (subcommand := command.get_command(ctx, name)) is not None and not subcommand.hidden
    ]


def _command_names_from_simple_help(output: str) -> list[str]:
    names: list[str] = []
    in_commands = False
    for line in output.splitlines():
        if line == "Commands:":
            in_commands = True
            continue
        if not in_commands:
            continue
        if not line.strip():
            continue
        if not line.startswith("  "):
            if names:
                break
            continue
        if len(line) > 2 and not line[2].isspace():
            names.append(line.strip().split(maxsplit=1)[0])
    return names


def test_root_command_names_are_alphabetical() -> None:
    command = get_command(cli_app)
    ctx = typer_click.Context(command, info_name="spec-kitty")
    visible_names = _visible_root_command_names(command, ctx)

    assert visible_names == sorted(visible_names)


def test_bare_root_invocation_prints_alphabetical_command_list(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import specify_cli.readiness as readiness

    command = get_command(cli_app)
    ctx = typer_click.Context(command, info_name="spec-kitty", terminal_width=200)
    expected_names = _visible_root_command_names(command, ctx)

    monkeypatch.setattr(sys, "argv", ["spec-kitty"])
    monkeypatch.setattr(readiness, "evaluate_readiness", lambda _ctx: None)
    monkeypatch.setenv("CI", "1")
    monkeypatch.setenv("SPEC_KITTY_NO_BANNER", "1")
    monkeypatch.setenv("SPEC_KITTY_NO_NAG", "1")
    monkeypatch.setenv("SPEC_KITTY_SIMPLE_HELP", "1")

    root_callback(ctx)

    output = capsys.readouterr().out
    visible_names = _command_names_from_simple_help(output)

    assert visible_names == expected_names
    assert visible_names == sorted(visible_names)


def test_root_command_sorting_preserves_representative_commands() -> None:
    command = get_command(cli_app)
    visible_names = {name for name, subcommand in command.commands.items() if not subcommand.hidden}

    assert {"agent", "doctor", "mission", "tracker"}.issubset(visible_names)
