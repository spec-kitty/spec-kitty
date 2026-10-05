"""Shared in-process ``finalize-tasks`` runner for the finalize guard tests.

One helper replaces the verbatim ``_run_finalize`` copies that swallowed the
exit code, so a refusal and a success were indistinguishable (#5573). It
records the exit code instead, mirroring the ``_run_real_finalize`` idiom in
``test_finalize_tasks_commit_surface.py``. ``add_owned_file`` is the
amendment edit the lane-identity guards share.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import typer

__all__ = ["add_owned_file", "run_finalize"]


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

    with ExitStack() as stack:
        for target, value in patches.items():
            stack.enter_context(patch(target, value))
        try:
            finalize_tasks(feature=mission_slug, json_output=True, validate_only=validate_only)
        except typer.Exit as exc:
            return exc.exit_code
        except SystemExit as exc:
            return int(exc.code or 0)
    return 0


def add_owned_file(wp_file: Path, path: str) -> None:
    """Append ``path`` to a WP file's ``owned_files`` through the frontmatter API.

    A textual ``str.replace`` on the frontmatter silently no-ops once a first
    finalize has re-serialised the block list (``- x`` instead of ``  - x``),
    which made earlier overlap amendments vacuous (#5573). This edit fails
    loudly instead.
    """
    from specify_cli.frontmatter import read_frontmatter, write_frontmatter

    meta, body = read_frontmatter(wp_file)
    owned = [str(item) for item in meta.get("owned_files") or []]
    if path in owned:
        raise AssertionError(f"{wp_file.name} already owns {path!r}; the amendment would be a no-op")
    meta["owned_files"] = [*owned, path]
    write_frontmatter(wp_file, meta, body)
