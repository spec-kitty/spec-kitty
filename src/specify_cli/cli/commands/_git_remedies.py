"""Shared renderers for the destructive git remedies the CLI prints (#3931).

Following the #5078 precedent for commit recipes (``_commit_recipes.py``),
this module is the single place that builds the text of any *destructive* git
command the CLI prints for an agent or operator to run as a copy/paste
command line -- ``git restore``, ``git reset --hard``, ``git clean`` and
friends. Centralising the text means one reviewed home for advice that can
delete user-authored files, and lets the AST gate
(``tests/specify_cli/cli/commands/test_git_remedies.py``) enforce that no
other module prints such a command line inline.

The release-blocking defect (#3931 F-30, escalated to P0 after a real
data-loss repro in mission ``verdict-matrix-rmw-preservation``, PR #4881)
was the move-task lane gate printing:

    git restore --source <planning-branch> --staged --worktree -- kitty-specs/

Following that advice restored the *whole* ``kitty-specs/`` tree from the
planning tip, which (a) pulled every other mission's advanced planning
content into the lane and (b) DELETED lane-local files the planning branch
did not carry (``issue-matrix.json``, ``acceptance-matrix.json``).
:func:`restore_recipe` closes both holes structurally: it refuses a
directory-scoped restore (every path must name a file) and it takes the
restore source as an explicit argument so callers pass the *merge-base*, not
the planning tip. See #2555 (the same remedy for coord topology) and epic
#4915 (mutating flows must never silently destroy user-authored files).
"""

from __future__ import annotations

import shlex
from collections.abc import Sequence

# Standard git alternatives the ``spec-kitty ops undo`` command prints when it
# explains that git has no reversible operation history. These are educational
# alternatives the operator runs by choice (not a spec-kitty remedy that
# mutates their tree behind a workflow), but they are still printed destructive
# command lines, so they live here rather than inline in ``ops.py`` (#3931,
# empty-allowlist ratchet). Kept in sync with ``ops.undo``'s docstring, which
# feeds the shell-completion manifest.
GIT_UNDO_ALTERNATIVES: tuple[str, ...] = (
    "git reset --soft HEAD~1  (undo last commit, keep changes)",
    "git reset --hard HEAD~1  (undo last commit, discard changes)",
    "git revert <commit>      (create reverting commit)",
    "git reflog               (find previous states)",
)


def restore_recipe(paths: Sequence[str], *, source: str) -> str:
    """Render a file-scoped ``git restore`` recipe line.

    The rendered command restores the *named* files (both the index and the
    working tree) from ``source``. It never restores a directory, so it can
    only ever touch the files it is handed -- never a lane-local sibling the
    caller did not name (#3931 F-30 data-loss).

    Args:
        paths: The files to restore. Must be non-empty, and every entry must
            name a file, not a directory -- a trailing ``/`` is refused so a
            directory-scoped restore (the original defect) is impossible to
            render.
        source: The ``--source`` ref the files are restored from. Callers pass
            the merge-base of the lane and its planning branch (the point the
            lane diverged), NEVER the planning tip -- restoring from the tip is
            what pulled in unrelated, advanced content.

    Returns:
        ``git restore --source <source> --staged --worktree -- <path>...``.

    Raises:
        ValueError: if ``paths`` is empty, if any path is blank, or if any
            path names a directory (trailing ``/``).
    """
    cleaned = [p.strip() for p in paths]
    if not cleaned or any(not p for p in cleaned):
        raise ValueError("restore_recipe requires at least one non-empty file path")
    directoryish = [p for p in cleaned if p.endswith("/")]
    if directoryish:
        raise ValueError(f"restore_recipe refuses a directory-scoped restore (name the offending files): {directoryish}")
    # Shell-quote each path: the rendered line is pasted into a shell (and run
    # via ``subprocess ... shell=True`` in the shipped regression test), and
    # ``git diff --name-only`` can return a path with a space, which would
    # otherwise split into two pathspecs and silently fail to clean. The
    # ``--source`` ref is intentionally NOT quoted -- callers may pass the
    # ``$(git merge-base ...)`` command-substitution fallback, which quoting
    # would neutralise.
    path_args = " ".join(shlex.quote(p) for p in cleaned)
    return f"git restore --source {source} --staged --worktree -- {path_args}"
