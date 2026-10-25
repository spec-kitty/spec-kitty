"""Render an Op write refusal and exit (#6564), shared by the Op commands."""

from __future__ import annotations

import json
from typing import NoReturn

import typer
from rich.markup import escape

from specify_cli.cli.console import console
from specify_cli.invocation.op_custody import OpWriteRefused

__all__ = ["exit_op_write_refused"]


def exit_op_write_refused(refused: OpWriteRefused, *, json_output: bool) -> NoReturn:
    """Report the refusal on the command's error channel and exit 1."""
    if json_output:
        error = {
            "error": "op_write_refused",
            "error_code": refused.refusal.code,
            "message": str(refused),
            "record_root": str(refused.record_root),
        }
        typer.echo(json.dumps(error), err=True)
    else:
        console.print(f"[red]Error:[/red] {escape(str(refused))}")
    raise typer.Exit(1)
