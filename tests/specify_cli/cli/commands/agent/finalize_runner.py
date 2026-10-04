"""Shared in-process ``finalize-tasks`` runner for the finalize guard tests.

One helper replaces the verbatim ``_run_finalize`` copies that swallowed the
exit code, so a refusal and a success were indistinguishable (#5573). It
records the exit code instead, mirroring the ``_run_real_finalize`` idiom in
``test_finalize_tasks_commit_surface.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from unittest.mock import patch

import typer

__all__ = ["run_finalize"]


def run_finalize(
    mission_slug: str,
    patches: Mapping[str, object],
    *,
    validate_only: bool = False,
) -> int | None:
    """Run the real ``finalize_tasks`` with ``patches`` applied; return its exit code.

    Each ``patches`` key is a dotted patch target and its value the
    replacement. Returns ``0`` on a normal return, ``exc.exit_code`` for a
    ``typer.Exit`` and ``int(exc.code or 0)`` for a ``SystemExit``.
    """
    from specify_cli.cli.commands.agent.mission import finalize_tasks

    ctx_patches = {target: patch(target, value) for target, value in patches.items()}
    for active in ctx_patches.values():
        active.start()
    try:
        finalize_tasks(feature=mission_slug, json_output=True, validate_only=validate_only)
    except typer.Exit as exc:
        return exc.exit_code
    except SystemExit as exc:
        return int(exc.code or 0)
    finally:
        for active in ctx_patches.values():
            active.stop()
    return 0
