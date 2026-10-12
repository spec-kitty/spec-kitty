"""`spec-kitty charter sync` is gone, with no alias (#5828, ADR 2026-10-06-2 §7).

`charter sync` was a permanent no-op kept only for compatibility: the prose->triad
extraction it once ran was retired (IC-04 / #2773), so it existed only to announce it
did nothing. Per the full-cutover rule (no aliases, no shims) it is removed. The old
spelling now exits 2 through Typer's own unknown-command path and is not listed in
`charter --help`. The load-bearing `charter.activation.sync` module is untouched; the
positive control exercises a sibling `charter` subcommand to prove the group still works.
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


def test_charter_sync_exits_2_as_an_unknown_command(tmp_path: Path) -> None:
    result = runner.invoke(cli_app, ["charter", "sync"])

    assert result.exit_code == 2, result.output
    assert _UNKNOWN_COMMAND in result.output
    assert "'sync'" in result.output
    assert not (tmp_path / ".kittify").exists(), "the removed command must not write anything"


def test_charter_sync_force_and_json_also_unknown(tmp_path: Path) -> None:
    """The removed command took `--force`/`--json`; neither resurrects it."""
    for extra in (["--force"], ["--json"], ["--force", "--json"]):
        result = runner.invoke(cli_app, ["charter", "sync", *extra])

        assert result.exit_code == 2, result.output
        assert _UNKNOWN_COMMAND in result.output


def test_charter_sync_help_is_also_unknown() -> None:
    """A real subcommand answers `--help` with exit 0; the removed `sync`
    errors the same way as a bare invocation.

    (The ``charter status`` description legitimately contains the phrase
    "charter sync status" -- the charter's freshness state -- so a substring
    scan of ``charter --help`` is not a sound absence check; invoking the
    name is.)
    """
    result = runner.invoke(cli_app, ["charter", "sync", "--help"])

    assert result.exit_code == 2, result.output
    assert _UNKNOWN_COMMAND in result.output

    # Positive control: a surviving sibling subcommand DOES answer --help.
    ok = runner.invoke(cli_app, ["charter", "status", "--help"])
    assert ok.exit_code == 0, ok.output
