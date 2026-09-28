"""Shared safe-commit recipe text (#5078 WP03, operator decision).

Operator decision (#5078): safe-commit is consumer doctrine. Every commit
recipe a spec-kitty CLI prints for an agent or operator to run -- a literal
command they are meant to copy and execute -- is rendered as
``spec-kitty safe-commit <files> -m "<msg>" --to-branch <branch>`` instead of
raw ``git add`` / ``git commit``. This module is the single place that
renders that text so every print site (``workflow_executor.py``,
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

from collections.abc import Sequence

PROTECTED_PRIMARY_HINT = (
    "Note: safe-commit refuses a protected destination. Plan on a topic branch, or configure `protection.protected_branches` in `.kittify/config.yaml`."
)


def safe_commit_recipe(
    files: Sequence[str],
    message: str,
    branch: str | None = None,
    *,
    protected_primary: bool = False,
) -> str:
    """Render a ``spec-kitty safe-commit`` recipe line.

    Args:
        files: File/path arguments to pass positionally to ``safe-commit``.
            May be literal paths or a placeholder token (e.g.
            ``"<your-implementation-files>"``) for a template recipe printed
            before the real paths are known.
        message: The commit message, rendered as the ``-m`` value.
        branch: The ``--to-branch`` target. Omitted from the rendered text
            when ``None`` -- the printed recipe then relies on
            ``safe-commit``'s HEAD-branch fallback (with its own deprecation
            notice) rather than naming one that was not available at print
            time.
        protected_primary: When True, appends :data:`PROTECTED_PRIMARY_HINT`
            on its own line.

    Returns:
        The recipe text, e.g.
        ``spec-kitty safe-commit foo.py -m "feat: x" --to-branch main``.
    """
    file_args = " ".join(files)
    recipe = f'spec-kitty safe-commit {file_args} -m "{message}"'
    if branch:
        recipe += f" --to-branch {branch}"
    if protected_primary:
        recipe += f"\n{PROTECTED_PRIMARY_HINT}"
    return recipe
