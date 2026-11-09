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
  approved before it. Overlapping windows are accepted. A work package whose first claim carries no
  stamp (even if a later rework is stamped) degrades to ``(claim_base, S_k]`` and the degrade is logged (A-8). Merge commits,
  bookkeeping-only commits and commits reachable from an anchor are exempt, as in the lane check.

Reachability is batched: one ``git rev-list`` per window edge, then set membership (NFR-007).
Pure over a status event list and git probes; the claim builder calls it before any branch moves.

Lane missions use the same two tiers (Mission consolidation-window-provenance-01M6Y84D, WP19,
FR-007): :func:`check_lane_windows` judges one code lane whose windows open at the SHA the
status pipeline recorded (:func:`~specify_cli.consolidation.wp_attribution.window_open_of`,
bound to the one lane tip by :func:`bind_lane_predicates`); a work package with a window gap
opens at the claim base, exactly like a degraded ``single_branch`` window.
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
from .git_probes import commit_in_clone, commits_in_range, is_ancestor_strict
from .wp_attribution import GapEntry, WindowGap, WindowOpen, approval_window_open_stamp, lane_exempt_commits, window_open_of

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
        """True when the work package's first claim has no stamp: its window opens at the claim base (A-8)."""
        return self.open_stamp is None


@dataclass(frozen=True)
class _WindowReach:
    """What one window covers, and what its approval stamp reaches (to name the work package approved before a commit)."""

    window: ApprovalWindow
    reach: frozenset[str]
    covered: frozenset[str]


def approval_windows(
    events: Sequence[StatusEvent],
    stamps: Mapping[str, str],
    *,
    classes: Mapping[str, WindowOpen | WindowGap] | None = None,
) -> tuple[ApprovalWindow, ...]:
    """One :class:`ApprovalWindow` per work package of *stamps* (``{wp_id: approval stamp}``), in that order.

    A work package whose *classes* entry is a :class:`WindowOpen` opens at that recorded SHA
    (FR-011, the FR-021 cycle opener); every other one keeps today's derivation, the stamp on its
    first claim (:func:`~specify_cli.consolidation.wp_attribution.approval_window_open_stamp`).
    ``classes=None`` is exactly today's derivation. A work package whose claim carries no stamp
    yields a degraded window, which is logged.
    """
    windows: list[ApprovalWindow] = []
    for wp_id, stamp in stamps.items():
        recorded = (classes or {}).get(wp_id)
        open_stamp = recorded.sha if isinstance(recorded, WindowOpen) else approval_window_open_stamp(events, wp_id)
        window = ApprovalWindow(wp_id, open_stamp, stamp)
        if window.degraded:
            logger.info("%s has no stamped claim: its approval window opens at the claim base (A-8)", wp_id)
        windows.append(window)
    return tuple(windows)


def _window_reach(repo_root: Path, claim_base: str, window: ApprovalWindow) -> _WindowReach:
    reach = frozenset(commits_in_range(repo_root, claim_base, window.approval_stamp))
    opened = frozenset(commits_in_range(repo_root, claim_base, window.open_stamp)) if window.open_stamp else frozenset()
    return _WindowReach(window, reach, reach - opened)


def _preceding_wp(repo_root: Path, claim_base: str, sha: str, reaches: Sequence[_WindowReach]) -> tuple[str, bool]:
    """``(wp_id, precedes_approvals)``: the work package approved last before *sha*, or the first approved after it.

    The first case: the approval stamp *sha* reaches that reaches most, with ``precedes_approvals``
    False. When *sha* reaches no approval stamp (it predates every approval), the work package whose
    approval stamp reaches *sha* with the fewest commits is named instead, the first approval after
    it, with ``precedes_approvals`` True: the refusal text must not claim the commit came after it.

    Invariant: some approval stamp reaches *sha*, so that fallback is never empty. Tier 2 asks only
    after tier 1 passed, and a passing tier 1 means every content commit outside its exempt set is
    reachable from an approval stamp; tier 2's exempt set contains tier 1's (it only adds the
    canceled work packages' commits), so every commit it refuses is one of those. A change that
    lets tier 2 judge a commit tier 1 did not must keep this invariant or name the commit otherwise.
    """
    ancestors = frozenset(commits_in_range(repo_root, claim_base, sha))
    before = [entry for entry in reaches if entry.window.approval_stamp in ancestors]
    if before:
        return max(before, key=lambda entry: len(entry.reach)).window.wp_id, False
    after = [entry for entry in reaches if sha in entry.reach]
    return min(after, key=lambda entry: len(entry.reach)).window.wp_id, True


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
    refusals: list[BoundRefusal] = []
    for sha, path in content:
        wp_id, precedes = _preceding_wp(repo_root, claim_base, sha, reaches)
        refusals.append(
            BoundRefusal(
                BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
                lane_id,
                branch,
                (wp_id,),
                commits=(sha,),
                path=path,
                precedes_approvals=precedes,
            )
        )
    return tuple(refusals)


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
    classes: Mapping[str, WindowOpen | WindowGap] | None = None,
) -> tuple[BoundRefusal, ...]:
    """Refuse the Mission branch when it holds content no approval window covers, else ``()``.

    Tier 1 (:func:`~specify_cli.consolidation.approved_bound.check_lane`) first: a stamp refusal or
    content after every approval stamp is returned alone. Tier 2 then returns one
    ``LANE_MOVED_AFTER_APPROVAL`` refusal per content commit outside every approval window,
    each naming the work package approved before it. A probe error raises
    :class:`~specify_cli.consolidation.git_probes.GitProbeError` (every caller refuses on it).

    The windows open at *classes* (:func:`classify_windows`; classified here, bound to *tip* or
    *branch*, when ``None``): a recorded window-open SHA, else today's derivation (FR-011).
    :func:`check_write_branch_windows` also returns the window gaps.
    """
    branch_tip = tip or branch
    approved = tuple(sorted(approved_wp_ids))
    anchor_list = list(anchors)
    opened = classes if classes is not None else _write_branch_classes(repo_root, events, approved, branch_tip)
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
        windows=approval_windows(events, stamps, classes=opened),
        exempt=lane_exempt_commits(repo_root, claim_base, anchor_list),
        is_bookkeeping=is_bookkeeping,
    )


def check_write_branch_windows(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    claim_base: str,
    anchors: Iterable[str],
    is_bookkeeping: Callable[[str], bool],
    tip: str,
) -> tuple[tuple[BoundRefusal, ...], tuple[GapEntry, ...]]:
    """``(refusals, window gaps)`` of the Mission branch read at *tip* (S8, #7283; FR-011).

    The refusals are :func:`check_write_branch`'s, its windows classified once here, bound to *tip*
    (:func:`classify_windows`). A work package with a window gap keeps today's derived window and
    is reported in the gaps, sorted by work package, whatever the verdict.
    """
    approved = tuple(sorted(approved_wp_ids))
    classes = _write_branch_classes(repo_root, events, approved, tip)
    gaps = tuple(GapEntry.from_gap(wp_id, lane_id, opened) for wp_id, opened in classes.items() if isinstance(opened, WindowGap))
    refusals = check_write_branch(
        repo_root,
        events=events,
        lane_id=lane_id,
        branch=branch,
        approved_wp_ids=approved,
        claim_base=claim_base,
        anchors=anchors,
        is_bookkeeping=is_bookkeeping,
        tip=tip,
        classes=classes,
    )
    return refusals, gaps


def _write_branch_classes(repo_root: Path, events: Sequence[StatusEvent], approved: Sequence[str], tip: str) -> dict[str, WindowOpen | WindowGap]:
    on_lane, is_ancestor = bind_lane_predicates(repo_root, tip)
    return classify_windows(events, approved, on_lane=on_lane, is_ancestor=is_ancestor)


_LanePredicates = tuple[Callable[[str], bool], Callable[[str, str], bool]]


def bind_lane_predicates(repo_root: Path, tip: str) -> _LanePredicates:
    """``(on_lane, is_ancestor)`` bound to the one lane *tip* the approved bound resolved (FR-022).

    ``on_lane(sha)`` is true iff *sha* is a commit in this clone and *tip* reaches it;
    ``is_ancestor(a, b)`` is true iff both are commits in this clone and *a* is an ancestor of or
    equal to *b*. A SHA that is not in this clone reads as False, so a recorded SHA from another
    clone is ``not_on_lane`` (R-4). A git failure raises
    :class:`~specify_cli.consolidation.git_probes.GitProbeError`, which the approved bound refuses
    on: a broken probe never degrades a work package to its weaker window in silence.
    """
    present: dict[str, bool] = {}

    def in_clone(sha: str) -> bool:
        if sha not in present:
            present[sha] = commit_in_clone(repo_root, sha)
        return present[sha]

    def on_lane(sha: str) -> bool:
        return in_clone(sha) and is_ancestor_strict(repo_root, sha, tip)

    def is_ancestor(ancestor: str, descendant: str) -> bool:
        return in_clone(ancestor) and in_clone(descendant) and is_ancestor_strict(repo_root, ancestor, descendant)

    return on_lane, is_ancestor


def classify_windows(
    events: Sequence[StatusEvent],
    wp_ids: Iterable[str],
    *,
    on_lane: Callable[[str], bool],
    is_ancestor: Callable[[str, str], bool],
) -> dict[str, WindowOpen | WindowGap]:
    """``{wp_id: window open SHA or typed gap}`` for *wp_ids*, in that order (pure over the two predicates)."""
    return {wp_id: window_open_of(events, wp_id, on_lane=on_lane, is_ancestor=is_ancestor) for wp_id in wp_ids}


def lane_windows(classes: Mapping[str, WindowOpen | WindowGap], stamps: Mapping[str, str | None]) -> tuple[ApprovalWindow, ...]:
    """One :class:`ApprovalWindow` per stamped work package of *classes*: a gap opens at the claim base (``open_stamp=None``)."""
    windows: list[ApprovalWindow] = []
    for wp_id, opened in classes.items():
        stamp = stamps.get(wp_id)
        if stamp is not None:
            windows.append(ApprovalWindow(wp_id, opened.sha if isinstance(opened, WindowOpen) else None, stamp))
    return tuple(windows)


def check_lane_windows(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    branch: str,
    approved_wp_ids: Iterable[str],
    claim_base: str,
    exemption_anchors: Iterable[str],
    windows: Sequence[ApprovalWindow],
    is_bookkeeping: Callable[[str], bool],
    tip: str,
    canceled_exempt: frozenset[str] = frozenset(),
    dependency_exempt: frozenset[str] = frozenset(),
) -> tuple[tuple[BoundRefusal, ...], tuple[BoundRefusal, ...]]:
    """``(tier_one, tier_two)`` refusals of one code lane judged by its work-package windows (FR-007, WW-1, WW-2).

    The exempt set is computed ONCE from *exemption_anchors* (the closed-world anchors plus the
    approval stamps of OTHER bounded lanes, never this lane's own, WW-2a) and shared by both
    tiers (NFR-007). Tier 1 is :func:`~specify_cli.consolidation.approved_bound.check_lane`
    unchanged: dropping the own stamps from its exempt set changes none of its verdicts, because
    it already excludes everything its own stamps reach (``commits_beyond(tip, [claim_base,
    *own stamps])``). A tier-1 refusal is returned alone. Tier 2 then refuses, one refusal per
    commit, every content commit in ``claim_base..tip`` that no window covers and no exemption
    anchor reaches, naming the work package approved before it.

    *canceled_exempt* is the lane's canceled work packages' own attributed commits (the mixed-lane
    resolution's, never a second spine walk). Operator ruling 2026-11-09: they are exempt from tier 2
    only, so the mixed-lane and canceled-content rules stay their sole judge; tier 1 is not given
    them, so a canceled work package's commit after an approval stamp still refuses there (#5720).
    Adding to tier 2's exempt set keeps :func:`_preceding_wp`'s invariant (tier 2 judges only
    commits tier 1 did).

    *dependency_exempt* is the commits of the operator's declared, pinned external dependency refs
    (#6771, the set the closed world exempts). Tier 2 exempts them, so a declared ref merged before a
    work package's window keeps the pre-window verdict; tier 1 is not given them (the approval-stamp
    bound never read the declaration).
    """
    anchors = list(exemption_anchors)
    exempt = lane_exempt_commits(repo_root, claim_base, anchors)
    tier_one = check_lane(
        repo_root,
        events=events,
        lane_id=lane_id,
        branch=branch,
        approved_wp_ids=approved_wp_ids,
        claim_base=claim_base,
        anchors=anchors,
        is_bookkeeping=is_bookkeeping,
        tip=tip,
        exempt=exempt,
    )
    if tier_one is not None:
        return (tier_one,), ()
    if not windows:
        return (), ()
    tier_two = _window_refusals(
        repo_root,
        lane_id=lane_id,
        branch=branch,
        tip=tip,
        claim_base=claim_base,
        windows=windows,
        exempt=exempt | canceled_exempt | dependency_exempt,
        is_bookkeeping=is_bookkeeping,
    )
    return (), tier_two


def _window_finding(refusal: BoundRefusal) -> str:
    sha = refusal.commits[0][:_SHORT_SHA]
    where = f"commit {sha} ('{refusal.path}') on branch '{refusal.branch}' ({refusal.lane_id})"
    if refusal.precedes_approvals:
        return (
            f"{where} was committed before {refusal.wp_ids[0]}'s review window opened, and no work package's newest approval "
            f"comes before it, so it is in no work package's review window; see it with `git show {sha}`."
        )
    return f"{where} was committed after {refusal.wp_ids[0]}'s approval and is in no later work package's review window; see it with `git show {sha}`."


def _is_window_refusal(refusal: BoundRefusal) -> bool:
    return refusal.code is BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL and len(refusal.commits) == 1 and len(refusal.wp_ids) == 1


def render_write_branch_refusals(refusals: Sequence[BoundRefusal], mission_slug: str) -> str:
    """The operator text for :func:`check_write_branch`'s refusals; it starts with ``<CODE>: `` like every bound refusal.

    Tier-2 window refusals print one line per commit, then the recovery: send the named work
    package back for review and approve it again (a commit made before every approval gets its own
    recovery, see :func:`_window_block`). Tier-1 refusals render
    through :func:`~specify_cli.consolidation.approved_bound.render_refusals` unchanged.
    """
    windows = [refusal for refusal in refusals if _is_window_refusal(refusal)]
    if not windows or len(windows) != len(refusals):
        # Local annotation re-narrows to ``str`` (the narrow-file mypy override erases the callee's return type).
        lane_text: str = render_refusals(refusals, mission_slug)
        return lane_text
    return "\n".join([*_window_block(windows, mission_slug), _TOOL_COMMIT_HINT])


_PRE_WINDOW_RECOVERY = (
    "A commit made before a work package's review window opened is covered by no approval: approving again moves a window's end, "
    "never its start. Take the commit off the branch (for example rebuild the branch without it), then send the branch's work "
    "packages back for review and approve them again."
)


def _window_block(windows: Sequence[BoundRefusal], mission_slug: str) -> list[str]:
    """The window refusal lines: one finding per commit, then the recovery (no tool-commit hint).

    *windows* is never empty (both renderers pass only the window refusals they found). A commit
    made after a work package's approval is cleared by sending that work package back for review and
    approving it again: its window keeps its start and the new approval stamp moves its end past the
    commit. A revert never clears it (the revert is new content of its own), so none is advised. A
    commit that precedes every approval (``precedes_approvals``) gets its own recovery: no approval covers it.
    """
    assert windows, "a window block needs at least one window refusal"
    findings = [_window_finding(refusal) for refusal in windows]
    wp_ids = list(dict.fromkeys(refusal.wp_ids[0] for refusal in windows if not refusal.precedes_approvals))
    lines = [f"{BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL.value}: {findings[0]}", *findings[1:]]
    if wp_ids:
        lines.append(f"Recovery: Send {', '.join(wp_ids)} back for review and approve it again; the new approval then covers the commit:")
        lines.extend(f"{_COMMAND_INDENT}{move_back_command(wp_id, mission_slug)}" for wp_id in wp_ids)
    if any(refusal.precedes_approvals for refusal in windows):
        lines.append(f"Recovery: {_PRE_WINDOW_RECOVERY}")
    lines.append("Then re-run spec-kitty consolidate.")
    return lines


def render_lane_window_refusals(refusals: Sequence[BoundRefusal], mission_slug: str) -> str:
    """The operator text for :func:`check_lane_windows`' tier-2 refusals; it starts with ``LANE_MOVED_AFTER_APPROVAL: ``.

    One line per commit naming the commit, its lane and the work package approved before it,
    then the recovery. The ``single_branch`` tool-commit hint is not part of the lane text.
    """
    return "\n".join(_window_block(refusals, mission_slug))


__all__ = [
    "bind_lane_predicates",
    "check_lane_windows",
    "check_write_branch_windows",
    "classify_windows",
    "lane_windows",
    "render_lane_window_refusals",
    "render_write_branch_refusals",
]
