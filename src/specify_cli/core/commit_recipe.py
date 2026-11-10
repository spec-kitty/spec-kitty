"""Commit-recipe text shared by CLI and runtime callers (#5078, #7510).

The renderer behind every printed ``spec-kitty safe-commit`` recipe. It lives
in core, like ``subtask_recipe``, because runtime callers cannot import
``specify_cli.cli``: the ``spec-kitty next`` implement prompt has to print the
same post-implementation commit step the claim output prints (#7510). CLI
callers keep importing it through ``specify_cli.cli.commands._commit_recipes``,
which documents the #5078 operator decision. Pure text: no I/O, no git call.
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


def implementation_commit_step(wp_id: str, branch: str | None) -> str:
    """Render the commit-your-work step that precedes ``move-task --to for_review``.

    One wording for both places an implementing agent reads it: the claim
    output's "After implementation, run" list and the ``spec-kitty next``
    implement prompt's WHEN DONE block (#7510).
    """
    return "git status && " + safe_commit_recipe(["<your-files>"], f"feat({wp_id}): <description>", branch)
