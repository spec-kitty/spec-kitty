"""The claim commit of a work package: one fail-closed authority for every review path.

A work package's **claim commit** is the commit that recorded the WP's last
``to_lane == "claimed"`` status event. It is never identified by matching
commit subjects: the event-only ``move-task`` commit carries no stable subject,
which is why the three subject matchers this module replaced were broken for
every mission after the event-only cutover (R-05, R-16).

Algorithm (:func:`claim_commit_for_wp`):

1. take the LAST ``claimed`` event of the WP from ``status.events.jsonl``;
2. ask git for the commits on ``HEAD`` whose diff to ``status.events.jsonl``
   introduced that ``event_id`` (``git log -S<event_id>``);
3. exactly one such commit is the claim commit. Zero or several fail closed.

The helper is topology-agnostic: it takes the directory that holds
``status.events.jsonl`` in the checkout whose ``HEAD`` is being reviewed, and
never an ownership fact (it is deliberately not a consumer of
``OwnedCheckout``).

Known limitation, not detectable here: squash-rebasing a branch folds the claim
commit into an implementation commit. ``-S`` then returns that combined commit
and the diff ``claim..HEAD`` silently omits the work inside it. Rewriting
history before review is out of contract.

Layering: the ``specify_cli.status`` import is lazy (inside the function) so
that importing the package root stays cold (``test_package_root_cold_imports``)
and the ``mission_runtime`` -> ``specify_cli`` ledger does not grow. Git is
called directly, following ``lifecycle_phase.py``, because no general-purpose
git seam exists below ``specify_cli`` and ``specify_cli.git`` is not an allowed
subpackage for this layer.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

__all__ = ["ClaimCommitUnresolved", "claim_commit_for_wp"]

_EVENTS_FILENAME = "status.events.jsonl"
_GIT_TIMEOUT_SECONDS = 30

ClaimCommitReason = Literal["no_claim_event", "no_commit", "ambiguous", "git_unavailable"]


class ClaimCommitUnresolved(Exception):
    """No single claim commit could be determined for a work package.

    Deliberately NOT an ``ActionContextError``: repository-root callers must
    never see an ``OWNED_*`` code. Owned callers translate it themselves.
    """

    def __init__(self, wp_id: str, reason: ClaimCommitReason, detail: str = "") -> None:
        self.wp_id = wp_id
        self.reason: ClaimCommitReason = reason
        message = f"{wp_id}: no deterministic claim commit ({reason})"
        super().__init__(f"{message}: {detail}" if detail else message)


def _last_claim_event_id(mission_dir: Path, wp_id: str) -> str:
    from specify_cli.status import Lane, read_events

    claimed = [event for event in read_events(mission_dir) if event.wp_id == wp_id and event.to_lane == Lane.CLAIMED]
    if not claimed:
        raise ClaimCommitUnresolved(wp_id, "no_claim_event")
    return str(claimed[-1].event_id)


def _commits_introducing(mission_dir: Path, wp_id: str, event_id: str) -> list[str]:
    command = ["git", "log", "--format=%H", "--no-show-signature", f"-S{event_id}", "HEAD", "--", _EVENTS_FILENAME]
    try:
        result = subprocess.run(
            command,
            cwd=mission_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ClaimCommitUnresolved(wp_id, "git_unavailable", str(exc)) from exc
    if result.returncode != 0:
        raise ClaimCommitUnresolved(wp_id, "git_unavailable", result.stderr.strip())
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_ancestor_of_head(mission_dir: Path, wp_id: str, commit: str) -> bool:
    """Whether ``commit`` is reachable from the consuming checkout's ``HEAD``.

    A RACE GUARD, not a second lookup: ``git log -S<id> HEAD`` (see
    :func:`_commits_introducing`) already yields only ancestors of the ``HEAD``
    it ran against, so on a quiescent checkout this is always true. It is
    re-checked because ``HEAD`` may move between that ``git log`` and the
    return (a concurrent checkout, reset or rebase in the reviewed worktree):
    a SHA that stopped being an ancestor must fail closed as ``no_commit``
    rather than become a review base the reviewed ``HEAD`` no longer contains.
    """
    try:
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=mission_dir,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ClaimCommitUnresolved(wp_id, "git_unavailable", str(exc)) from exc
    if result.returncode not in (0, 1):
        raise ClaimCommitUnresolved(wp_id, "git_unavailable", result.stderr.strip())
    return result.returncode == 0


def claim_commit_for_wp(mission_dir: Path, wp_id: str) -> str:
    """Return the SHA of the unique commit on ``HEAD`` that claimed ``wp_id``.

    ``mission_dir`` holds ``status.events.jsonl`` in the checkout whose ``HEAD``
    is being reviewed; git runs there and the pathspec is relative to it.

    Raises:
        ClaimCommitUnresolved: ``no_claim_event`` (the log has no ``claimed``
            event for the WP), ``no_commit`` (the event is on no commit of
            ``HEAD``, or the found commit is not an ancestor of it), ``ambiguous`` (several commits introduced it) or
            ``git_unavailable`` (git failed or timed out).
    """
    event_id = _last_claim_event_id(mission_dir, wp_id)
    commits = _commits_introducing(mission_dir, wp_id, event_id)
    if not commits:
        raise ClaimCommitUnresolved(wp_id, "no_commit", event_id)
    if len(commits) > 1:
        raise ClaimCommitUnresolved(wp_id, "ambiguous", f"{event_id} introduced by {len(commits)} commits")
    # Race guard: ``HEAD`` may have moved since the ``git log`` above (see the helper's docstring).
    if not _is_ancestor_of_head(mission_dir, wp_id, commits[0]):
        raise ClaimCommitUnresolved(wp_id, "no_commit", f"{commits[0]} is not an ancestor of HEAD")
    return commits[0]
