"""The hosted Team Kitty surfaces are hidden unless hosted drain is on (ADR 2026-10-06-1).

``register_commands`` always registers ``auth``, ``issue-search``,
``live-work``, ``moments``, ``routes`` and ``zeitgeist`` hidden, so the
generated completion manifest and CLI reference describe the default
consumer posture. ``reveal_hosted_surfaces`` lists them again in the root
``--help`` only when the checkout's drain posture is on, and still runs each
one when it is invoked by name.
"""

from __future__ import annotations

import sys
import warnings

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import (
    _HOSTED_SURFACE_NAMES,
    _command_name,
    _top_level_group_name,
    register_commands,
    reveal_hosted_surfaces,
)
from specify_cli.core import hosted_posture

# In-process Typer/CliRunner assertions; no subprocess, no filesystem.
pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ROOT_HELP_ARGV = ["spec-kitty", "--help"]


def _registered_root(monkeypatch: pytest.MonkeyPatch) -> typer.Typer:
    monkeypatch.setattr(sys, "argv", ["spec-kitty"])
    app = typer.Typer()
    register_commands(app)
    return app


def _hidden_by_name(app: typer.Typer) -> dict[str, bool]:
    flags = {_command_name(info): bool(info.hidden) for info in app.registered_commands}
    for info in app.registered_groups:
        flags[str(_top_level_group_name(info))] = info.hidden is True
    return flags


def _root_listing(app: typer.Typer) -> str:
    result = CliRunner().invoke(app, ["--help"], env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    return result.output


def _listed(output: str, name: str) -> bool:
    return any(line.strip("│ ").startswith(f"{name} ") for line in output.splitlines())


def test_every_hosted_surface_registers_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    flags = _hidden_by_name(_registered_root(monkeypatch))

    assert set(_HOSTED_SURFACE_NAMES) <= flags.keys(), "a hosted surface name no longer matches a registered command"
    assert {name for name in _HOSTED_SURFACE_NAMES if not flags[name]} == set()


def test_non_hosted_commands_stay_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    # tracker keeps its local providers (beads, fp), so it is not a hosted surface.
    flags = _hidden_by_name(_registered_root(monkeypatch))

    assert flags["tracker"] is False
    assert flags["implement"] is False


@pytest.mark.usefixtures("drain_off")
def test_drain_off_keeps_hosted_surfaces_out_of_root_help(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _registered_root(monkeypatch)

    reveal_hosted_surfaces(app, _ROOT_HELP_ARGV)
    output = _root_listing(app)

    assert [name for name in sorted(_HOSTED_SURFACE_NAMES) if _listed(output, name)] == []
    assert _listed(output, "tracker")


def test_drain_on_lists_hosted_surfaces_in_root_help(monkeypatch: pytest.MonkeyPatch) -> None:
    # The root autouse fixture pins the drain posture on.
    app = _registered_root(monkeypatch)

    reveal_hosted_surfaces(app, _ROOT_HELP_ARGV)
    output = _root_listing(app)

    assert [name for name in sorted(_HOSTED_SURFACE_NAMES) if not _listed(output, name)] == []


def test_single_command_invocation_does_not_read_the_posture(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _registered_root(monkeypatch)

    def _must_not_run(*_args: object, **_kwargs: object) -> hosted_posture.DrainPosture:
        raise AssertionError("drain posture read for a single-command invocation")

    monkeypatch.setattr(hosted_posture, "drain_posture", _must_not_run)

    reveal_hosted_surfaces(app, ["spec-kitty", "implement", "WP01"])

    assert _hidden_by_name(app)["moments"] is True


@pytest.mark.usefixtures("drain_off")
def test_hidden_surface_still_runs_when_invoked_by_name(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _registered_root(monkeypatch)
    reveal_hosted_surfaces(app, _ROOT_HELP_ARGV)

    result = CliRunner().invoke(app, ["moments", "--help"])

    assert result.exit_code == 0, result.output
    assert "Usage:" in result.output


def test_unparseable_posture_warning_does_not_reach_root_help(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _registered_root(monkeypatch)
    off = hosted_posture.DrainPosture(
        enabled=False,
        repo_value=None,
        repo_source="test",
        personal_value=None,
        personal_source="test",
        narrowed_by=None,
        reason="unparseable",
    )

    def _warning_posture(*_args: object, **_kwargs: object) -> hosted_posture.DrainPosture:
        warnings.warn("config.toml is not valid TOML", UserWarning, stacklevel=2)
        return off

    monkeypatch.setattr(hosted_posture, "drain_posture", _warning_posture)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        reveal_hosted_surfaces(app, _ROOT_HELP_ARGV)

    assert caught == []
    assert _hidden_by_name(app)["zeitgeist"] is True
