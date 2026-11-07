"""The approval bound of a ``single_branch`` Mission branch: per-WP approval windows (S8, #7283).

ADR ``2026-10-04-5`` Amendment 2026-11-06. A ``single_branch`` Mission that lands a minted
Mission branch has no lanes: every work package commits to the one Mission branch, one after
the other. Its approvals bound it in two tiers:

* **Tier 1** -- :func:`~specify_cli.consolidation.approved_bound.check_lane` runs unchanged on
  the Mission branch: an approval stamp that is missing or not on the branch refuses, and
  content committed after every approval stamp refuses ``LANE_MOVED_AFTER_APPROVAL``.
* **Tier 2** -- every content commit in ``claim_base..mission_branch`` must lie in some approved
  work package's window ``(O_k, S_k]``: reachable from ``S_k`` (the stamp on its newest
  approval) and not from ``O_k`` (the stamp on its first claim,
  :func:`~specify_cli.consolidation.wp_attribution.approval_window_open_stamp`). A commit slipped
  in between two approvals is reachable from the later approval stamp, but also from the later
  work package's claim stamp, so tier 1 misses it and tier 2 refuses it, naming the work package
  approved before it. Overlapping windows are accepted. A work package with no claim stamp
  degrades to ``(claim_base, S_k]`` and the degrade is logged (A-8). Merge commits,
  bookkeeping-only commits and commits reachable from an anchor are exempt, as in the lane check.

Reachability is batched: one ``git rev-list`` per window edge, then set membership (NFR-007).
Pure over a status event list and git probes; the claim builder calls it before any branch moves.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from specify_cli.status import StatusEvent

from .approved_bound import (
    BoundRefusal,
    BoundRefusalCode,
    approval_stamps,
    check_lane,
    content_commits,
    move_back_command,
    render_refusals,
)
from .git_probes import commits_in_range
from .wp_attribution import approval_window_open_stamp, lane_exempt_commits

logger = logging.getLogger(__name__)

_SHORT_SHA = 7
_COMMAND_INDENT = "  "
_TOOL_COMMIT_HINT = (
    "A commit a tool made on the Mission branch (for example `spec-kitty upgrade` committing agent directories) is content too: recover from it the same way."
)


@dataclass(frozen=True)
class ApprovalWindow:
    """One approved work package's review window ``(open_stamp, approval_stamp]`` on the Mission branch."""

    wp_id: str
    open_stamp: str | None
    approval_stamp: str

    @property
    def degraded(self) -> bool:
        """True when the work package has no claim stamp: its window opens at the claim base (A-8)."""
        return self.open_stamp is None


@dataclass(frozen=True)
class _WindowReach:
    """What one window covers, and what its approval stamp reaches (to name the work package approved before a commit)."""

    window: ApprovalWindow
    reach: frozenset[str]
    covered: frozenset[str]


def approval_windows(events: Sequence[StatusEvent], stamps: Mapping[str, str]) -> tuple[ApprovalWindow, ...]:
    """One :class:`ApprovalWindow` per work package of *stamps* (``{wp_id: approval stamp}``), in that order.

    A work package whose claim carries no stamp yields a degraded window, which is logged.
    """
    windows: list[ApprovalWindow] = []
    for wp_id, stamp in stamps.items():
        window = ApprovalWindow(wp_id, approval_window_open_stamp(events, wp_id), stamp)
        if window.degraded:
            logger.info("%s has no stamped claim: its approval window opens at the claim base (A-8)", wp_id)
        windows.append(window)
    return tuple(windows)


def _window_reach(repo_root: Path, claim_base: str, window: ApprovalWindow) -> _WindowReach:
    reach = frozenset(commits_in_range(repo_root, claim_base, window.approval_stamp))
    opened = frozenset(commits_in_range(repo_root, claim_base, window.open_stamp)) if window.open_stamp else frozenset()
    return _WindowReach(window, reach, reach - opened)


def _preceding_wp(repo_root: Path, claim_base: str, sha: str, reaches: Sequence[_WindowReach]) -> str:
    """The work package approved last before *sha*: the approval stamp *sha* reaches that reaches most.

    When *sha* reaches no approval stamp (it predates every approval), the work package whose
    approval stamp reaches *sha* with the fewest commits is named instead: the first approval after it.
    """
    ancestors = frozenset(commits_in_range(repo_root, claim_base, sha))
    before = [entry for entry in reaches if entry.window.approval_stamp in ancestors]
    if before:
        return max(before, key=lambda entry: len(entry.reach)).window.wp_id
    after = [entry for entry in reaches if sha in entry.reach]
    return min(after, key=lambda entry: len(entry.reach)).window.wp_id


def _outside(repo_root: Path, claim_base: str, tip: str, reaches: Sequence[_WindowReach], exempt: frozenset[str]) -> list[str]:
    skipped = exempt.union(*(entry.covered for entry in reaches))
    return [sha for sha in commits_in_range(repo_root, claim_base, tip) if sha not in skipped]


def _window_refusals(
    repo_root: Path,
    *,
    lane_id: str,
    branch: str,
    tip: str,
    claim_base: str,
    windows: Sequence[ApprovalWindow],
    exempt: frozenset[str],
    is_bookkeeping: Callable[[str], bool],
) -> tuple[BoundRefusal, ...]:
    reaches = [_window_reach(repo_root, claim_base, window) for window in windows]
    content = content_commits(repo_root, _outside(repo_root, claim_base, tip, reaches, exempt), is_bookkeeping)
    return tuple(
        BoundRefusal(
            BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
            lane_id,
            branch,
            (_preceding_wp(repo_root, claim_base, sha, reaches),),
            commits=(sha,),
            path=path,
        )
        for sha, path in content
    )


def check_write_branch(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    claim_base: str,
    anchors: Iterable[str],
    is_bookkeeping: Callable[[str], bool],
    tip: str | None = None,
) -> tuple[BoundRefusal, ...]:
    """Refuse the Mission branch when it holds content no approval window covers, else ``()``.

    Tier 1 (:func:`~specify_cli.consolidation.approved_bound.check_lane`) first: a stamp refusal or
    content after every approval stamp is returned alone. Tier 2 then returns one
    ``LANE_MOVED_AFTER_APPROVAL`` refusal per content commit outside every approval window,
    each naming the work package approved before it. A probe error raises
    :class:`~specify_cli.consolidation.git_probes.GitProbeError` (every caller refuses on it).
    """
    branch_tip = tip or branch
    approved = tuple(sorted(approved_wp_ids))
    anchor_list = list(anchors)
    tier_one = check_lane(
        repo_root,
        events=events,
        lane_id=lane_id,
        branch=branch,
        approved_wp_ids=approved,
        claim_base=claim_base,
        anchors=anchor_list,
        is_bookkeeping=is_bookkeeping,
        tip=branch_tip,
    )
    if tier_one is not None:
        return (tier_one,)
    stamps = {wp_id: stamp for wp_id, stamp in approval_stamps(events, approved).items() if stamp is not None}
    if not stamps:
        return ()
    return _window_refusals(
        repo_root,
        lane_id=lane_id,
        branch=branch,
        tip=branch_tip,
        claim_base=claim_base,
        windows=approval_windows(events, stamps),
        exempt=lane_exempt_commits(repo_root, claim_base, anchor_list),
        is_bookkeeping=is_bookkeeping,
    )


def _window_finding(refusal: BoundRefusal) -> str:
    sha = refusal.commits[0][:_SHORT_SHA]
    return (
        f"commit {sha} ('{refusal.path}') on branch '{refusal.branch}' ({refusal.lane_id}) was committed after "
        f"{refusal.wp_ids[0]}'s approval and is in no later work package's review window; see it with `git show {sha}`."
    )


def _is_window_refusal(refusal: BoundRefusal) -> bool:
    return refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL and len(refusal.commits) == 1 and len(refusal.wp_ids) == 1


def render_write_branch_refusals(refusals: Sequence[BoundRefusal], mission_slug: str) -> str:
    """The operator text for :func:`check_write_branch`'s refusals; it starts with ``<CODE>: `` like every bound refusal.

    Tier-2 window refusals print one line per commit, then the recovery: send the named work
    package back for review and approve it again, or revert the commit. Tier-1 refusals render
    through :func:`~specify_cli.consolidation.approved_bound.render_refusals` unchanged.
    """
    windows = [refusal for refusal in refusals if _is_window_refusal(refusal)]
    if not windows or len(windows) != len(refusals):
        # Local annotation re-narrows to ``str`` (the narrow-file mypy override erases the callee's return type).
        lane_text: str = render_refusals(refusals, mission_slug)
        return lane_text
    findings = [_window_finding(refusal) for refusal in windows]
    wp_ids = list(dict.fromkeys(refusal.wp_ids[0] for refusal in windows))
    named = ", ".join(wp_ids)
    return "\n".join(
        [
            f"{BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL.value}: {findings[0]}",
            *findings[1:],
            f"Recovery: Send {named} back for review and approve it again, or revert the commit:",
            *(f"{_COMMAND_INDENT}{move_back_command(wp_id, mission_slug)}" for wp_id in wp_ids),
            "Then re-run spec-kitty consolidate.",
            _TOOL_COMMIT_HINT,
        ]
    )


__all__ = [
    "check_write_branch",
    "render_write_branch_refusals",
]
