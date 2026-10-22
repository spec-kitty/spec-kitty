"""Single home of the terminal-control sanitization seam tests (#5015).

``tests/specify_cli/cli/test_terminal_control_sanitization.py`` (out of matrix) and its always-on lift
``tests/architectural/test_lifted_cli_terminal_control_sanitization.py`` both import these, so the per-PR gate runs
exactly what the source suite runs and the two cannot drift apart.
"""

from __future__ import annotations

import io

from rich.table import Table

from specify_cli.cli.console import CliConsole

SAFE_TEXT = "Zoë Ölafsdóttir 日本語 🐱"


HOSTILE_SUFFIX = "\x1b[2J\x1b]0;x\x07\x1b"


HOSTILE_TEXT = f"{SAFE_TEXT}{HOSTILE_SUFFIX}"


def _console() -> tuple[CliConsole, io.StringIO]:
    buffer = io.StringIO()
    return CliConsole(
        file=buffer,
        width=160,
        no_color=True,
        highlight=False,
    ), buffer


def test_machine_json_output_remains_plain_and_round_trips() -> None:
    console, buffer = _console()
    console.emit_json({"value": HOSTILE_TEXT})
    emitted = buffer.getvalue().encode("utf-8")

    assert SAFE_TEXT.encode("utf-8") in emitted
    assert b"\\u001b[2J" in emitted
    assert b"\\u001b]0;x" in emitted
    assert b"\x1b" not in emitted


def test_render_str_and_segment_rendering_share_the_policy() -> None:
    console, _ = _console()
    rendered_text = console.render_str(f"[red]{HOSTILE_TEXT}[/red]")
    assert SAFE_TEXT in rendered_text.plain
    assert "\x1b" not in rendered_text.plain

    table = Table()
    table.add_column("Value")
    table.add_row(HOSTILE_TEXT)
    segments = list(console.render(table))
    rendered = "".join(segment.text for segment in segments)
    assert SAFE_TEXT in rendered
    assert "\x1b" not in rendered
