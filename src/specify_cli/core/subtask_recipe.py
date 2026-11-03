"""Shared completion advice for CLI and runtime callers (#7108).

Different WPs can reuse the same short subtask labels. Printed mark-status
commands therefore name the WP; the existing CLI remains the ownership
validator. This pure renderer lives in core because runtime callers cannot
import specify_cli.cli. It does not resolve a Mission or perform I/O.
"""

from __future__ import annotations

import os
import shlex
from collections.abc import Sequence


def owned_checkout_suffix(owned_root: str | os.PathLike[str] | None) -> str:
    """Keep a supplied checkout path in one shell argument, without validating it."""
    return f" --owned-checkout {shlex.quote(os.fspath(owned_root))}" if owned_root is not None else ""


def mark_status_recipe(
    task_ids: Sequence[str],
    *,
    wp_id: str,
    mission_slug: str | None = None,
    owned_root: str | os.PathLike[str] | None = None,
) -> str:
    """Render completion advice with its owning WP and available Mission context.

    Runtime callers omit the command for an empty roster. Legacy CLI runbooks
    instead pass their explicit ``<subtask-ids>`` placeholder; it remains advice
    to fill in, not an executable empty-roster command. Flag order is a display
    convention shared with adjacent move-task advice, not a parser requirement.
    """
    command = f"spec-kitty agent tasks mark-status {' '.join(task_ids)} --wp {wp_id} --status done"
    if mission_slug is not None:
        command += f" --mission {mission_slug}"
    return command + owned_checkout_suffix(owned_root)
