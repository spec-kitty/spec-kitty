"""Coded-error rendering shared by ``charter activate --preset`` and ``charter pack`` (#3732 WP08).

Text mode prints ``Error (<CODE>): <message>`` followed by any detail lines;
``--json`` emits :func:`specify_cli.cli.json_contract.json_error` with the
error's payload merged into the ``error`` object (contracts/cli.md "Error text
format").
"""

from __future__ import annotations

from rich.markup import escape

from charter.packs import PresetFormatError
from specify_cli.cli.console import console
from specify_cli.cli.json_contract import json_error

__all__ = ["render_coded_error", "render_preset_format_error"]

#: A preset file that does not load (unknown key, bad name, unreadable YAML);
#: contracts/errors.md.
PRESET_INVALID = "PRESET_INVALID"


def render_coded_error(code: str, message: str, *, details: list[str] | None = None, payload: dict[str, object] | None = None, json_output: bool) -> None:
    """Render one coded error in text or ``--json`` mode."""
    if json_output:
        body = json_error(code, message)
        error = body["error"]
        if isinstance(error, dict) and payload:
            error.update(payload)
        console.emit_json(body)
        return
    console.print(f"[red]Error[/red] ({code}): {escape(message)}")
    for line in details or ():
        console.print(escape(line))


def render_preset_format_error(exc: PresetFormatError, *, json_output: bool) -> None:
    """Render a malformed preset file as ``PRESET_INVALID`` naming the file and field."""
    render_coded_error(PRESET_INVALID, str(exc), payload={"preset_file": str(exc.path), "field": exc.field}, json_output=json_output)
