"""Shared confirmation-prompt helper for CLI commands.

Kept as its own module (relocated by #4804, originally added by #4775) rather
than living inside a specifically-named gate module: ``safe_confirm`` is a
general-purpose prompt wrapper, not TeamSpace-mission-state-gate-specific,
and more than one command surface (``upgrade.py``'s migration-apply prompt,
the TeamSpace mission-state repair sub-gate) now imports it.
"""

from __future__ import annotations

import typer


def safe_confirm(prompt: str, *, default: bool) -> bool:
    """Prompt for confirmation, declining safely on abort or EOF (NFR-005).

    Wraps ``typer.confirm`` and explicitly catches ``typer.Abort`` (typer's
    public surface for the exception ``typer.confirm`` raises on Ctrl-C or
    when reading hits EOF — do not reference ``click.exceptions.Abort``
    directly; TID251 bans it because it is a distinct class from typer's own
    in typer>=0.26) and ``EOFError`` itself, folding either into a plain
    decline (``False``) rather than letting the exception crash an
    otherwise-successful upgrade run. Deliberately NOT a bare
    ``except Exception``: any other exception raised while prompting is a
    real bug and must propagate, not be silently swallowed as "declined".
    """
    try:
        return typer.confirm(prompt, default=default)
    except (typer.Abort, EOFError):
        return False
