"""Shared classifier for a recorded ``planning_commit_sha`` (issue #4827).

Before #4827 the "is the recorded planning pin still good?" question was asked
in three places with different, partial logic — now unified here:

* ``mission_finalize.py::_recorded_planning_sha_is_ancestor_of_tip`` (**removed**
  in #4827, folded into this module) — ``merge-base --is-ancestor recorded tip``,
  collapsed "rewritten" and "unknown object" into a single ``False``.
* ``worktree_allocator.py::_merge_recorded_planning_commit`` —
  ``is-ancestor pin <lane HEAD>`` (a **different** ref; see the C-006 note
  below — never conflate this with the target-branch-tip question below).
* ``implement_support.py::_is_git_ancestor``.

None of them distinguish a pin that is *orphaned* (present in the object
store but no longer reachable from the target-branch tip — the mid-mission
rebase shape) from one that is *foreign* (the object is simply absent). This
module is the single shared authority for that distinction so finalize
(re-pin) and the lane consumers stop duplicating ad-hoc ancestor checks and
stop collapsing "orphaned" and "foreign" into one undifferentiated refusal
(research.md D1/D5).

**C-006 — classify against the target-branch tip, never a lane HEAD.** The
allocator's own no-op gate (``is-ancestor pin <lane HEAD>``) answers a
different question — it short-circuits when the pin is reachable from a
*lane worktree's* HEAD, which is the normal healthy state of a fresh coord
lane. Passing a lane HEAD as ``target_tip`` here would misfire on every
healthy allocation (#2993). Callers must always pass the planning
target-branch tip (e.g. ``capture_branch_tip(repo_root,
target_branch)``), never a worktree's ``HEAD``.

This module is deliberately pure: no Typer, no console output, no
``sys.exit``. Both the finalize re-pin path (WP02) and the lane-allocation /
reconcile / claim-ancestry / owned-review consumers (WP03) call
:func:`classify_recorded_pin` and decide what to do with the result
themselves.
"""

from __future__ import annotations

import subprocess
from enum import StrEnum
from pathlib import Path


class PinClass(StrEnum):
    """Classification of a recorded ``planning_commit_sha`` vs. a target tip.

    * ``ADVANCED`` — the recorded SHA is an ancestor of (or equal to) the
      target tip: the normal, healthy state.
    * ``ORPHANED`` — the recorded SHA's commit object is present in the
      repository but is NOT an ancestor of the target tip: the mid-mission
      rebase/rewrite shape. The object still exists, so it can be inspected,
      but merging against it produces a dead base.
    * ``FOREIGN`` — the recorded SHA's commit object is absent from the
      repository entirely (never existed here, or was garbage-collected).
    * ``INDETERMINATE`` — the question cannot be answered at all: the target
      tip is uncapturable (non-git workspace, or the branch tip itself could
      not be resolved) or there is no recorded SHA to classify. Callers
      degrade to their own historical preserve behavior in this case; this
      classifier never guesses and never aborts.
    """

    ADVANCED = "advanced"
    ORPHANED = "orphaned"
    FOREIGN = "foreign"
    INDETERMINATE = "indeterminate"


def _object_present(repo_root: Path, sha: str) -> bool:
    """Return True iff ``sha`` resolves to a commit object in ``repo_root``.

    Runs ``git cat-file -e <sha>^{commit}``, which succeeds (rc 0) only when
    the object exists and peels to a commit. Absent, foreign, and
    garbage-collected SHAs all return False. Never raises: a missing ``git``
    binary, a non-existent ``repo_root``, or any other ``OSError`` from the
    subprocess call is treated the same as "not present".
    """
    try:
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def _is_ancestor(repo_root: Path, sha: str, tip: str) -> bool:
    """Return True iff ``sha`` is an ancestor of (or equal to) ``tip``.

    Runs ``git merge-base --is-ancestor <sha> <tip>``. Any nonzero exit —
    not-an-ancestor, an unknown object on either side, or ``repo_root`` not
    being a git repository at all — returns False. Never raises.
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, tip],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def classify_recorded_pin(
    repo_root: Path,
    recorded_sha: str | None,
    target_tip: str | None,
) -> PinClass:
    """Classify a recorded ``planning_commit_sha`` against ``target_tip``.

    ``target_tip`` MUST be the planning target-branch tip (e.g. from
    ``capture_branch_tip``), never a lane worktree's ``HEAD`` — see
    the C-006 note on the module docstring.

    Does not compute the pre-execution "captured" case (execution-not-begun
    short-circuit) — that stays with the finalize caller, which knows
    whether execution has begun. This function only ever sees an already
    recorded SHA to classify.
    """
    if target_tip is None:
        return PinClass.INDETERMINATE
    if recorded_sha is None:
        return PinClass.INDETERMINATE
    if _is_ancestor(repo_root, recorded_sha, target_tip):
        return PinClass.ADVANCED
    if _object_present(repo_root, recorded_sha):
        return PinClass.ORPHANED
    return PinClass.FOREIGN
