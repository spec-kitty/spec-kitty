"""End-to-end guard: a real ``--json`` command stays machine-parseable (#2632).

The canonical console seam (:mod:`specify_cli.cli.console`) emits ``--json``
payloads through :meth:`CliConsole.print_json` / :meth:`CliConsole.emit_json`,
which bypass Rich's syntax highlighter entirely. So a ``--json`` payload never
carries ANSI escapes — not even when the console is rendering in *styled* mode
(the failure mode the Claude Code harness triggers by exporting
``FORCE_COLOR=3``, which would otherwise splice ``\x1b[...`` into the JSON and
raise ``json.loads`` ``Expecting value``).

This exercises the whole CLI stack through ``CliRunner`` — flag parsing, the
command body, and the seam's stdout sink — rather than the seam in isolation.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app as app
from specify_cli.cli.console import console

pytestmark = [pytest.mark.unit, pytest.mark.fast]

runner = CliRunner()

_ESC = "\x1b["


def test_json_command_output_is_loadable() -> None:
    """A real ``--json`` command produces output ``json.loads`` accepts."""
    result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"])

    assert result.exit_code == 0, result.output
    # Parse `.stdout` (stdout only), not `.output` (Click 8.2+'s
    # stdout+stderr merge): the JSON sink under test is the stdout sink.
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)


def test_json_stays_plain_even_when_console_is_styled() -> None:
    """The ``--json`` sink is intrinsically plain, independent of colour mode.

    The suite-level autouse fixture pins the seam colourless; here we deliberately
    re-enable styled rendering (simulating a ``FORCE_COLOR`` harness) *on the
    shared object* and prove the machine-output path still never emits ANSI, so
    ``json.loads`` succeeds. This is the object-level determinism contract, not an
    ``os.environ`` toggle.
    """
    console.set_plain(False)
    try:
        result = runner.invoke(app, ["mission-type", "list", "--include-inactive", "--json"], color=True)
    finally:
        console.set_plain(True)

    assert result.exit_code == 0, result.output
    # Checked against `.stdout` (the JSON sink this test's own docstring
    # names): stderr has no "must stay plain" contract of its own.
    assert _ESC not in result.stdout
    assert isinstance(json.loads(result.stdout), list)
