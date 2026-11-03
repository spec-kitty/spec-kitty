"""The single home for the subtask-completion recipe the CLI and runtime print (#7108).

Subtask ids are **mission-scoped**, not work-package-scoped: the normal case is
several work packages that each author their own short ``T001..T00n`` list.
``mark-status`` resolves that ambiguity with ``--wp`` and refuses an unscoped id
that more than one WP owns (``_resolve_task_owners``), so a printed recipe that
omits ``--wp`` is a dead end exactly when it is most needed — the operator is
then pushed to ``--force``, which is how a mis-attribution stays hidden.

This module renders that recipe once, following the ``_commit_recipes.py``
precedent ("one reviewed home for printed copy/paste advice"). Every emitter
calls it instead of hand-formatting the command: the ``move-task`` refusal
(``tasks_transition_core._guard_subtasks``), the implement prompt's WHEN DONE
block (``runtime.next.prompt_builder._completion_lines``) and the three
implement runbook sites in ``cli/commands/agent/workflow_executor.py``.

**Why ``specify_cli.core`` and not ``specify_cli.cli``.** The prompt builder
lives in the ``runtime`` layer, which ``tests/architectural/test_layer_rules.py``
forbids from importing ``specify_cli.cli``; ``specify_cli.core`` is already in
the ``runtime`` → ``specify_cli`` ledger. The module is pure text formatting so
that a decision core with no I/O (``tasks_transition_core``) can render it.
"""

from __future__ import annotations

import os
from collections.abc import Sequence


def mark_status_recipe(
    task_ids: Sequence[str],
    *,
    wp_id: str,
    mission_slug: str | None = None,
    owned_root: str | os.PathLike[str] | None = None,
) -> str:
    """Render a ``spec-kitty agent tasks mark-status`` completion recipe.

    The owning work package is always named: it is a required keyword argument
    so a caller cannot silently fall back to the ambiguous, unscoped form.

    Args:
        task_ids: The subtask ids to mark done, in the order they should be
            printed (e.g. ``["T001", "T002"]``). Callers only render this when
            the roster is non-empty.
        wp_id: The work package that authors ``task_ids`` (e.g. ``"WP02"``).
            On the ``move-task`` refusal path this is simply the WP being moved.
        mission_slug: The mission handle. Omitted from the rendered command when
            ``None`` — a directly constructed request may not know it, and
            ``--mission None`` would be a broken recipe.
        owned_root: The owned single-branch checkout root, for owned missions.
            Rendered as a trailing ``--owned-checkout`` flag.

    Returns:
        The recipe text, e.g.
        ``spec-kitty agent tasks mark-status T001 T002 --wp WP02 --status done --mission <slug>``.

    Note:
        The option order — ``--wp``, then ``--status``, then ``--mission``, then
        ``--owned-checkout`` — is asserted by
        ``tests/specify_cli/core/test_subtask_recipe.py`` and relied on as a
        suffix match by the owned-checkout prompt test. Do not reorder it.
    """
    command = f"spec-kitty agent tasks mark-status {' '.join(task_ids)} --wp {wp_id} --status done"
    if mission_slug is not None:
        command += f" --mission {mission_slug}"
    if owned_root is not None:
        command += f" --owned-checkout {owned_root}"
    return command
