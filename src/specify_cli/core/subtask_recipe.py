"""Shared completion advice for CLI and runtime callers (#7108).

Different WPs can reuse the same short subtask labels. Printed mark-status
commands therefore name the WP; the existing CLI remains the ownership
validator. This pure renderer lives in core because runtime callers cannot
import specify_cli.cli. It does not resolve a Mission or perform I/O.
"""

from __future__ import annotations

from collections.abc import Sequence


def mark_status_recipe(
    task_ids: Sequence[str],
    *,
    wp_id: str,
    mission_slug: str | None = None,
) -> str:
    """Render completion advice with its owning WP and available Mission context.

    Runtime callers omit the command for an empty roster. Legacy CLI runbooks
    instead pass their explicit ``<subtask-ids>`` placeholder; it remains advice
    to fill in, not an executable empty-roster command. Flag order is a display
    convention shared with adjacent move-task advice, not a parser requirement.
    Owned callers append their fact-derived suffix at the presentation boundary;
    this renderer never accepts or projects an owned root.
    """
    command = f"spec-kitty agent tasks mark-status {' '.join(task_ids)} --wp {wp_id} --status done"
    if mission_slug is not None:
        command += f" --mission {mission_slug}"
    return command
