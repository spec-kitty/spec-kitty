"""The hosted Team Kitty surfaces are removed from open-core (#6164).

``auth``, ``issue-search``, ``live-work``, ``moments``, ``routes`` and
``zeitgeist`` were the hidden hosted CLI entries. #6164 removed them outright:
they are no longer registered at all (not merely hidden), so they cannot be
invoked by name, and the visible commands that share the tracker surface
(``tracker`` for its local providers) stay registered.
"""

from __future__ import annotations

import sys

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import (
    _command_name,
    _top_level_group_name,
    register_commands,
)

# In-process Typer/CliRunner assertions; no subprocess, no filesystem.
pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REMOVED_HOSTED_NAMES = frozenset({"auth", "issue-search", "live-work", "moments", "routes", "zeitgeist"})


def _registered_root(monkeypatch: pytest.MonkeyPatch) -> typer.Typer:
    monkeypatch.setattr(sys, "argv", ["spec-kitty"])
    app = typer.Typer()
    register_commands(app)
    return app


def _registered_names(app: typer.Typer) -> set[str]:
    names = {_command_name(info) for info in app.registered_commands}
    names |= {str(_top_level_group_name(info)) for info in app.registered_groups}
    return names


def test_removed_hosted_surfaces_are_not_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    names = _registered_names(_registered_root(monkeypatch))
    assert _REMOVED_HOSTED_NAMES.isdisjoint(names), f"a removed hosted surface is still registered: {_REMOVED_HOSTED_NAMES & names}"


def test_non_hosted_commands_stay_registered(monkeypatch: pytest.MonkeyPatch) -> None:
    # tracker keeps its local providers (beads, fp); research/implement are unaffected.
    names = _registered_names(_registered_root(monkeypatch))
    assert "tracker" in names
    assert "implement" in names
    assert "research" in names


def test_removed_hosted_surface_cannot_be_invoked_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _registered_root(monkeypatch)
    # A removed top-level entry resolves to no command: Typer exits non-zero.
    result = CliRunner().invoke(app, ["moments", "--help"])
    assert result.exit_code != 0
