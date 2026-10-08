"""`spec-kitty charter pack apply` is gone, with no alias (#3732 WP13, FR-005, C-001).

A preset is applied with `spec-kitty charter activate --preset <name>`; the old
spelling exits 2 through Typer's own unknown-command path and is not listed in
`charter pack --help`. The positive control applies `minimal` through the
replacement on a fresh project.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app

pytestmark = [pytest.mark.unit]

runner = CliRunner()

#: Typer/Click's unknown-command message (no "did you mean" hint is added by us).
_UNKNOWN_COMMAND = "No such command"


def test_charter_pack_apply_exits_2_as_an_unknown_command(tmp_path: Path) -> None:
    result = runner.invoke(cli_app, ["charter", "pack", "apply", "default", "--repo-root", str(tmp_path)])

    assert result.exit_code == 2, result.output
    assert _UNKNOWN_COMMAND in result.output
    assert "'apply'" in result.output
    assert not (tmp_path / ".kittify").exists(), "the removed command must not write anything"


def test_charter_pack_help_does_not_list_apply() -> None:
    result = runner.invoke(cli_app, ["charter", "pack", "--help"])

    assert result.exit_code == 0, result.output
    # Positive control: the help really lists the pack subcommands.
    assert "list" in result.output and "path" in result.output
    assert " apply " not in f" {' '.join(result.output.split())} "


def test_activate_preset_minimal_applies_on_a_fresh_project(tmp_path: Path) -> None:
    result = runner.invoke(
        cli_app,
        ["charter", "activate", "--preset", "minimal", "--no-compile", "--repo-root", str(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert _UNKNOWN_COMMAND not in result.output
