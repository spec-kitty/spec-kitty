"""The click context of the running command, whichever click built it."""

from __future__ import annotations

from typing import Any

import click
from typer._click.globals import get_current_context as _typer_current_context


def current_click_context() -> Any:
    """Return the active click context, or ``None`` outside an invocation.

    ``typer>=0.26`` vendors its own click (``typer._click``) with its own context
    stack, so ``click.get_current_context`` sees nothing while a typer command
    runs. The vendored stack is read first; the real one still covers plain
    click commands.
    """
    ctx = _typer_current_context(silent=True)
    if ctx is not None:
        return ctx
    return click.get_current_context(silent=True)
