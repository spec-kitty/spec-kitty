"""session-start — emit spec-kitty orientation for the Claude Code SessionStart hook.

This command is invoked automatically by Claude Code's ``SessionStart`` lifecycle
hook on every new session.  It prints the orientation block to stdout when the
cwd is inside a spec-kitty project, and silently exits 0 in all other cases.

Exit 0 guarantee: the outermost ``except Exception: pass`` is intentional.
This command MUST never cause a Claude Code session to fail to start, regardless
of any error in the spec-kitty stack.  All exceptions are swallowed.

Performance (NFR-001): the command must complete in <200ms on a warm filesystem.
Unless ``SPEC_KITTY_NO_UPGRADE_CHECK`` is set, the upgrade check fires a
background subprocess (``check_in_background()``) that returns immediately;
``get_available_version()`` reads only the local cache file — no network calls
on the hot path.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from kernel.ancestor_walk import find_ancestor

_logger = logging.getLogger(__name__)


def _find_project_root(start: Path | None = None) -> Path | None:
    """Walk up from *start* looking for a ``.kittify/`` directory.

    Returns the nearest directory at or above *start* that contains a
    ``.kittify/`` subdirectory, or ``None`` when no such directory is found
    (i.e. *start* is not inside a spec-kitty project). *start* defaults to the
    cwd.

    The walk is the one ceiling-aware ancestor walk
    (:func:`kernel.ancestor_walk.find_ancestor`), so ``GIT_CEILING_DIRECTORIES``
    bounds it exactly as it bounds git and every other root walk, and it always
    terminates — at a listed ceiling or at the filesystem root (#7122). The
    test-only ``stop=`` bound this function used to carry is gone; tests narrow
    the walk with ``GIT_CEILING_DIRECTORIES``, the production mechanism.
    """
    return find_ancestor(
        start if start is not None else Path.cwd(),
        lambda candidate: (candidate / ".kittify").is_dir(),
    )


def session_start() -> None:
    """Emit spec-kitty orientation for the Claude Code SessionStart hook."""
    try:
        project_root = _find_project_root()
        if project_root is None:
            return
        from specify_cli.core.agent_config import load_agent_config
        from specify_cli.session_presence.manager import SessionPresenceManager

        agent_config = load_agent_config(project_root)
        content = SessionPresenceManager(project_root, agent_config)._build_content()
        typer.echo(content.render())
        from specify_cli.session_presence.open_ops import render_open_ops_section

        open_ops_section = render_open_ops_section(project_root)
        if open_ops_section:
            typer.echo(open_ops_section)
    except Exception:
        pass  # Always exit 0 — never fail the Claude Code session
