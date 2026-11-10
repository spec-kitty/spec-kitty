"""Shared safe-commit recipe text (#5078 WP03, operator decision).

Operator decision (#5078): safe-commit is consumer doctrine. Every commit
recipe a spec-kitty CLI prints for an agent or operator to run -- a literal
command they are meant to copy and execute -- is rendered as
``spec-kitty safe-commit <files> -m "<msg>" --to-branch <branch>`` instead of
raw ``git add`` / ``git commit``. This module is the single place that
renders that text (the renderer itself lives in ``specify_cli.core.commit_recipe``
so the runtime can share it, #7510; this module re-exports it) so every print site (``workflow_executor.py``,
``implement.py``, ``tasks_parsing_validation.py``,
``charter/_synthesis.py``, ``mission_setup_plan.py``) produces the identical
shape (Sonar S1192 -- the pattern was duplicated across all five before this
extraction).

``safe_commit_cmd.py`` (the ``spec-kitty safe-commit`` Typer command) and
``git/commit_helpers.py`` (``safe_commit``, ~994-1060) still do the actual
staging and committing; this module only builds the human-readable recipe
text printed for a human/agent to run. No executed git call changes.

Per the charter's "Agent Push Authorization" section, the protected-primary
hint below names the two supported paths for a refused protected-branch
commit -- a topic branch, or configuring
``protection.protected_branches`` -- and never suggests the
``SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS`` escape hatch.
"""

from __future__ import annotations

from specify_cli.core.commit_recipe import PROTECTED_PRIMARY_HINT, safe_commit_recipe

__all__ = ["PROTECTED_PRIMARY_HINT", "safe_commit_recipe"]
