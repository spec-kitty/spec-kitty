"""``upgrade`` intent parsing raises the usage errors of the command's own click.

typer 0.26+ vendors click (``typer._click``). ``parse_upgrade_intent`` runs inside
the root group's ``parse_args``, so a real-click ``UsageError`` raised there escapes
the vendored dispatch as a traceback (exit 1) instead of a clean usage error
(exit 2). The lockfile pins typer 0.24, so these tests stand in a second click
universe instead of depending on the installed typer.
"""

from __future__ import annotations

import sys
import types

import click
import pytest

from specify_cli.upgrade.intent import _click_of, _parse_values

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _ForeignUsageError(Exception):
    def __init__(self, message: str, ctx: object = None) -> None:
        super().__init__(message)


def _install_foreign_click(monkeypatch: pytest.MonkeyPatch) -> type[click.Command]:
    core = types.ModuleType("foreignclick.core")
    exceptions = types.ModuleType("foreignclick.exceptions")
    exceptions.UsageError = _ForeignUsageError  # type: ignore[attr-defined]
    core.Context = click.Context  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "foreignclick.core", core)
    monkeypatch.setitem(sys.modules, "foreignclick.exceptions", exceptions)
    foreign_command = type("Command", (click.Command,), {"__module__": "foreignclick.core"})
    return type("ForeignUpgradeCommand", (foreign_command,), {})


def test_real_click_command_resolves_to_real_click() -> None:
    assert _click_of(click.Command("upgrade")) == (click.core, click.exceptions)


def test_extra_arguments_raise_the_commands_own_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    command_class = _install_foreign_click(monkeypatch)
    command = command_class("upgrade", params=[click.Option(["--dry-run"], is_flag=True)])
    with pytest.raises(_ForeignUsageError, match=r"unexpected extra arguments \(extra\)"):
        _parse_values(command, ["--dry-run", "extra"])
