"""Pure per-WP commit attribution resolver (mixed-lane-authorship-soundness / #5046, WP04).

For ONE canceled WP in ONE mixed lane, :func:`resolve_canceled_wp` returns
either the WP's attributed commit set + unsuperseded canceled content
(:class:`Attributed`), or a typed reason the WP's commits could not be
bounded (:class:`Unattributable`). This is the ONLY place the window /
supersession rules live (plan.md D-2/D-3); ``reconciliation.py`` (WP05) only
wires this module's output into the claim and the verifier — it must not
duplicate any of this logic.

Pure except for git reads: every git probe used here (`git_probes.py`) is
fail-closed — a git error never reads as "no content" (see each probe's own
docstring). ``events`` is passed in already read (the caller reads it once
via the ``specify_cli.status`` facade and maps a ``StoreError`` onto
``UnattributableReason.EVENTS_UNREADABLE`` itself — this module never reads
the event log from disk).

Design references: plan.md D-2/D-3 (steps 2-4); data-model.md (``WorkWindow``,
``AttributionOutcome``, ``CanceledPathState``); research.md R-5, R-7, R-9
(R1, R3, R5-R8), R-10 (B3, B4); contracts/attribution-and-verdicts.md (C1-C4).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from specify_cli.status import LANE_HEAD_KEY, StatusEvent, actor_identity_str

from .git_probes import (
    GitProbeError,
    changed_paths_of,
    commits_in_range,
    first_parent_commits_in_range,
    is_merge_commit,
    path_state_at,
    sha_reachable_from,
)

# Lane values a WP transition can carry (status/models.py::Lane is a StrEnum;
# these plain-str sets compare/hash equal to its members).
_IMPLEMENTATION_LANES: frozenset[str] = frozenset({"claimed", "in_progress", "blocked"})
_REVIEW_LANES: frozenset[str] = frozenset({"for_review", "in_review"})
# Narrower than _IMPLEMENTATION_LANES: plan.md D-3 step 2 defines "entered
# implementation" as a transition into claimed/in_progress specifically —
# blocked still counts INSIDE an already-open window (R6), but reaching
# blocked without ever having been claimed/in_progress (planned -> blocked ->
# canceled) is not, by itself, entering implementation (review cycle 1,
# issue 4).
_ENTERED_IMPLEMENTATION_LANES: frozenset[str] = frozenset({"claimed", "in_progress"})

#: Actor prefix of every migration-synthesized lifecycle event (FR-011, spec.md).
#: Migrations record their provenance as ``migration:<module>`` (e.g. the
#: birth-cutover backfill's ``migration:backfill_runtime_state`` seed events,
#: ``specify_cli.migration.backfill_runtime_state.BACKFILL_ACTOR``). Such an
#: event reconstructs state; it never represents governed work, so it must not
#: open, close, or extend a work window, nor count as "entered implementation".
#: Without this, a FAILed consolidation's cutover appended unstamped seed
#: ``planned -> claimed`` events after the cancel and every re-run REFUSEd with
#: ``open_window`` — the FAIL's recovery could never succeed.
MIGRATION_ACTOR_PREFIX = "migration:"


class WindowKind(StrEnum):
    """Which class of lane state a :class:`WorkWindow` covers (data-model.md)."""

    IMPLEMENTATION = "implementation"
    REVIEW = "review"


@dataclass(frozen=True, slots=True)
class WorkWindow:
    """One contiguous interval a WP spent inside one :class:`WindowKind` (T016).

    ``open_head`` / ``close_head`` are the ``lane_head`` stamps
    (``policy_metadata[LANE_HEAD_KEY]``) on the transitions that entered and
    left the interval; either is ``None`` when that transition carried no
    stamp (pre-WP03 events, or a transition made outside the governed
    workflow). ``still_open`` is True for a window with NO closing transition
    at all (the WP was canceled — or the event stream ends — while still
    inside this window's class); it is kept as an explicit field, distinct
    from ``close_head is None``, because a CLOSED window whose closing
    transition simply lacked a stamp (``no_stamp``, T016) and a window that
    never closed at all (``open_window``, T016) are two different
    :class:`UnattributableReason`\\ s the data-model.md ``close_head``-only
    summary compresses into one ``None`` — this field is what lets
    :func:`_window_commits` tell them apart without re-scanning the event
    stream.
    """

    wp_id: str
    kind: WindowKind
    open_head: str | None
    close_head: str | None
    still_open: bool


class UnattributableReason(StrEnum):
    """Why a canceled WP's commit set could not be bounded (data-model.md)."""

    NO_STAMP = "no_stamp"
    OPEN_WINDOW = "open_window"
    STAMP_NOT_ANCESTOR_OF_LANE_TIP = "stamp_not_ancestor_of_lane_tip"
    CONTESTED_COMMIT = "contested_commit"
    EVENTS_UNREADABLE = "events_unreadable"
    SPINE_UNREADABLE = "spine_unreadable"
    #: FR-013 closed world: every WP window of the mixed lane resolved, yet a
    #: non-merge, non-bookkeeping first-parent commit lies in NO WP's window.
    COMMIT_OUTSIDE_WINDOWS = "commit_outside_windows"


@dataclass(frozen=True, slots=True)
class CanceledPathState:
    """One path whose newest on-spine state is the canceled WP's own, unsuperseded (T019).

    ``canceled_state`` / ``pre_state`` are blob shas, or ``None`` for
    "absent" (the path did not exist, or the canceled WP deleted it).
    ``pre_state_by_survivor`` is True when a non-canceled, non-merge lane
    commit touched ``path`` BEFORE the canceled WP's oldest touch — i.e. the
    pre-state was itself produced on the lane by a surviving WP, not merely
    inherited from the window base (R1; consumed by WP05 to tell "approved
    work undone" from "target already had it").

    ``pre_state_by_survivor`` counts ANY non-canceled, non-merge spine
    commit older than the canceled WP's oldest touch — not only a commit
    inside another WP's resolved window. That includes a commit that falls
    inside no WP's window at all, and a commit that belongs to a DIFFERENT
    canceled WP of the same lane (this resolver call only knows about ONE
    canceled WP at a time; a sibling canceled WP's own commits are
    "non-canceled" from THIS call's point of view). This is the safe
    direction for WP05: it can only ever make ``pre_state_by_survivor`` True
    when it should have been False, which biases the verifier toward FAIL
    (flagging as "approved work undone"), never toward a silent PASS.
    """

    wp_id: str
    lane_id: str
    path: str
    canceled_state: str | None
    pre_state: str | None
    pre_state_by_survivor: bool


@dataclass(frozen=True, slots=True)
class Attributed:
    """The canceled WP's commit set was resolved without contest (T020)."""

    commits: frozenset[str]
    canceled_content: frozenset[CanceledPathState]


@dataclass(frozen=True, slots=True)
class Unattributable:
    """The canceled WP's commit set could NOT be bounded; ``detail`` is operator-facing (NFR-003)."""

    reason: UnattributableReason
    detail: str

    @classmethod
    def for_reason(cls, reason: UnattributableReason, lane_id: str, wp_id: str) -> Unattributable:
        """The canonical outcome for *reason*, with its ``_DETAIL_TEMPLATES`` detail."""
        return cls(reason, _detail_for(reason, lane_id, wp_id))


AttributionOutcome = Attributed | Unattributable


#: How many offending commit shas a detail names before summarising the rest.
_DETAIL_COMMIT_SAMPLE = 3

#: Operator-facing detail per reason (NFR-003). TOTAL over
#: :class:`UnattributableReason` (a test iterates the enum): every template may
#: use ``{wp_id}``, ``{lane_id}``, ``{commits}`` (short shas) and ``{path}``.
_DETAIL_TEMPLATES: dict[UnattributableReason, str] = {
    UnattributableReason.NO_STAMP: (
        "{wp_id} in {lane_id} entered implementation but its lifecycle events carry no "
        "commit attribution (missions created before this change, or a transition made "
        "outside the governed workflow)"
    ),
    UnattributableReason.OPEN_WINDOW: ("{wp_id} in {lane_id} has a work window that never closed before it was canceled; its commit set cannot be bounded"),
    UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP: (
        "{wp_id} in {lane_id} carries a lane-head stamp that is not an ancestor of the "
        "lane's current tip (the lane's history was rewritten after the stamp was recorded)"
    ),
    UnattributableReason.CONTESTED_COMMIT: (
        "{wp_id} in {lane_id} shares commit(s) ({commits}) with another WP's work window in "
        "the same lane — lane WPs ran concurrently, so per-WP attribution cannot be resolved"
    ),
    UnattributableReason.EVENTS_UNREADABLE: ("{wp_id} in {lane_id}: the mission's lifecycle event log could not be read"),
    UnattributableReason.SPINE_UNREADABLE: ("{wp_id} in {lane_id}: the lane's git history could not be read to resolve commit attribution"),
    UnattributableReason.COMMIT_OUTSIDE_WINDOWS: (
        "{lane_id} carries commit(s) {commits} (touching '{path}') that lie outside every WP's "
        "recorded work window — no governed WP owns them, so canceled {wp_id}'s content "
        "cannot be told apart from approved work"
    ),
}


def _short_shas(commits: Sequence[str]) -> str:
    """Up to :data:`_DETAIL_COMMIT_SAMPLE` short shas, plus a count of the rest."""
    if not commits:
        return "(none recorded)"
    sample = ", ".join(sha[:10] for sha in commits[:_DETAIL_COMMIT_SAMPLE])
    rest = len(commits) - _DETAIL_COMMIT_SAMPLE
    return f"{sample} and {rest} more" if rest > 0 else sample


def _detail_for(
    reason: UnattributableReason,
    lane_id: str,
    wp_id: str,
    *,
    commits: Sequence[str] = (),
    path: str = "(unknown path)",
) -> str:
    """Operator-facing detail naming the lane, the WP, and what is missing (NFR-003)."""
    return _DETAIL_TEMPLATES[reason].format(wp_id=wp_id, lane_id=lane_id, commits=_short_shas(commits), path=path)


def _contested_detail(lane_id: str, wp_id: str, contested: frozenset[str]) -> str:
    return _detail_for(UnattributableReason.CONTESTED_COMMIT, lane_id, wp_id, commits=sorted(contested))


def _stamp_of(event: StatusEvent) -> str | None:
    metadata = event.policy_metadata
    if not metadata:
        return None
    value = metadata.get(LANE_HEAD_KEY)
    return value if isinstance(value, str) and value else None


def _is_migration_event(event: StatusEvent) -> bool:
    """True for a migration-synthesized event (:data:`MIGRATION_ACTOR_PREFIX`, FR-011)."""
    return bool(actor_identity_str(event.actor).startswith(MIGRATION_ACTOR_PREFIX))


def _classify(lane: str) -> WindowKind | None:
    if lane in _IMPLEMENTATION_LANES:
        return WindowKind.IMPLEMENTATION
    if lane in _REVIEW_LANES:
        return WindowKind.REVIEW
    return None


def _entered_implementation(events: Sequence[StatusEvent], wp_id: str) -> bool:
    """True iff *wp_id* has any transition INTO ``claimed``/``in_progress`` (T020, plan.md D-3 step 2).

    Uses :data:`_ENTERED_IMPLEMENTATION_LANES`, NOT :data:`_IMPLEMENTATION_LANES`
    — the latter also covers ``blocked`` for window membership (R6), but a WP
    that only ever reached ``blocked`` (e.g. ``planned`` -> ``blocked`` ->
    ``canceled``, never ``claimed``/``in_progress``) has done no
    implementation work to attribute, per the plan's own gate. A
    migration-synthesized event (FR-011) never counts: a backfill seed
    ``planned -> claimed`` for a WP canceled from ``planned`` is not work.
    """
    return any(event.wp_id == wp_id and event.to_lane in _ENTERED_IMPLEMENTATION_LANES and not _is_migration_event(event) for event in events)


def _windows(events: Sequence[StatusEvent], wp_ids: frozenset[str]) -> dict[str, list[WorkWindow]]:
    """Reconstruct each WP's :class:`WorkWindow` sequence from events in append order (T016).

    A transition among states of the SAME class (``claimed`` -> ``in_progress``,
    ``in_progress`` <-> ``blocked``) never opens a new window — "the batch
    shares one head". A transition that changes class closes the current
    window (if any) with THIS event's stamp and, if the new state is itself a
    window class, opens the next window with the SAME event's stamp (a
    ``for_review`` -> ``in_progress`` rework re-enters implementation as a
    NEW window, not a resumption of the earlier one). Migration-synthesized
    events (FR-011, :data:`MIGRATION_ACTOR_PREFIX`) are skipped entirely.
    """
    open_state: dict[str, tuple[WindowKind, str | None]] = {}
    result: dict[str, list[WorkWindow]] = {wp_id: [] for wp_id in wp_ids}
    for event in events:
        wp_id = event.wp_id
        if wp_id not in wp_ids or _is_migration_event(event):
            continue
        to_class = _classify(event.to_lane)
        stamp = _stamp_of(event)
        current = open_state.get(wp_id)
        if current is not None:
            current_kind, open_head = current
            if to_class == current_kind:
                continue  # same class — window stays open, no new entry
            result[wp_id].append(
                WorkWindow(
                    wp_id=wp_id,
                    kind=current_kind,
                    open_head=open_head,
                    close_head=stamp,
                    still_open=False,
                )
            )
            del open_state[wp_id]
        if to_class is not None:
            open_state[wp_id] = (to_class, stamp)
    for wp_id, (kind, open_head) in open_state.items():
        result[wp_id].append(WorkWindow(wp_id=wp_id, kind=kind, open_head=open_head, close_head=None, still_open=True))
    return result


def _window_commits(
    repo_root: Path,
    window: WorkWindow,
    lane_branch: str,
    spine_set: frozenset[str],
    merge_cache: dict[str, bool],
) -> tuple[frozenset[str], UnattributableReason | None]:
    """Resolve ONE window's non-merge, on-spine commits, or a failure reason (T017/T018 support).

    Stamp validity (R8): a stamp is valid iff it equals the lane tip or is an
    ancestor of it — :func:`sha_reachable_from` alone answers BOTH (a commit
    is its own ancestor under ``git merge-base --is-ancestor``), so a fork-point
    open stamp (the first WP's ``open_head``, which sits OUTSIDE the
    ``coord_base..lane`` range) is correctly valid without ever testing range
    membership.
    """
    if window.still_open:
        return frozenset(), UnattributableReason.OPEN_WINDOW
    if window.open_head is None or window.close_head is None:
        return frozenset(), UnattributableReason.NO_STAMP
    if not sha_reachable_from(repo_root, window.open_head, lane_branch):
        return frozenset(), UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP
    if not sha_reachable_from(repo_root, window.close_head, lane_branch):
        return frozenset(), UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP
    try:
        raw = first_parent_commits_in_range(repo_root, window.open_head, window.close_head)
    except GitProbeError:
        return frozenset(), UnattributableReason.SPINE_UNREADABLE
    commits: set[str] = set()
    for sha in raw:
        if sha not in spine_set:
            continue
        if sha not in merge_cache:
            try:
                merge_cache[sha] = is_merge_commit(repo_root, sha)
            except GitProbeError:
                return frozenset(), UnattributableReason.SPINE_UNREADABLE
        if merge_cache[sha]:
            continue  # R3/B4 — a merge commit never attributes to a WP
        commits.add(sha)
    return frozenset(commits), None


def _resolve_wp_windows(
    repo_root: Path,
    windows: list[WorkWindow],
    lane_branch: str,
    spine_set: frozenset[str],
    merge_cache: dict[str, bool],
) -> tuple[dict[WindowKind, frozenset[str]], UnattributableReason | None]:
    """Resolve every window of ONE WP, bucketed by :class:`WindowKind`.

    Fails the WHOLE resolution on the first window that cannot be bounded
    (missing/open/invalid stamp, or an unreadable spine range) — for BOTH the
    canceled WP and every sibling of its lane (review cycle 1, issue 1). C1
    legalizes a missing stamp (best-effort capture), so an unresolvable
    SIBLING window is a real, reachable state, not a corner case: treating it
    as "contributes no commits" would silently fold the sibling's own
    unattributed commits into the canceled WP's set with no contest, hiding a
    genuine R1 undo (a survivor commit the resolver could not see "wins" a
    self-revert check it should never have passed). There is therefore no
    lenient mode here any more — an unresolvable window anywhere in the
    lane's active WPs REFUSEs the whole attribution, never just silently
    narrows the canceled WP's own commit set.
    """
    by_kind: dict[WindowKind, set[str]] = {WindowKind.IMPLEMENTATION: set(), WindowKind.REVIEW: set()}
    for window in windows:
        commits, reason = _window_commits(repo_root, window, lane_branch, spine_set, merge_cache)
        if reason is not None:
            return {}, reason
        by_kind[window.kind].update(commits)
    return {kind: frozenset(members) for kind, members in by_kind.items()}, None


def _resolve_contested(
    canceled_by_kind: dict[WindowKind, frozenset[str]],
    sibling_impl: frozenset[str],
    sibling_review: frozenset[str],
) -> frozenset[str]:
    """T018: implementation-window overlap with any sibling implementation window,
    or review-window overlap with ANY sibling window (implementation or review) — R5/R7.
    """
    canceled_impl = canceled_by_kind.get(WindowKind.IMPLEMENTATION, frozenset())
    canceled_review = canceled_by_kind.get(WindowKind.REVIEW, frozenset())
    contested_impl = canceled_impl & sibling_impl
    contested_review = canceled_review & (sibling_impl | sibling_review)
    return frozenset(contested_impl | contested_review)


@dataclass(frozen=True, slots=True)
class _SpineWalk:
    """What ONE newest->oldest spine walk learned (T019 + FR-013)."""

    canceled_content: frozenset[CanceledPathState]
    #: ``(sha, first non-bookkeeping path)`` of every non-merge content commit
    #: in NO resolved window, newest first (FR-013 closed world).
    outside_windows: tuple[tuple[str, str], ...]


def _canceled_content_walk(
    repo_root: Path,
    spine: list[str],
    canceled_commits: frozenset[str],
    covered: frozenset[str],
    is_bookkeeping: Callable[[str], bool],
    wp_id: str,
    lane_id: str,
    merge_cache: dict[str, bool],
) -> _SpineWalk:
    """ONE newest->oldest spine walk producing the newest toucher, the
    canceled WP's oldest touch per path (T019, NFR-001 — never walk twice),
    AND the commits outside every resolved window (FR-013).

    For each non-merge, non-bookkeeping path touched on the spine: the FIRST
    commit seen (newest) is recorded as that path's ``newest_toucher``; every
    commit IN ``canceled_commits`` that touches the path OVERWRITES
    ``oldest_canceled_{idx,sha}`` for it, so after the full walk that holds
    the LAST (oldest) canceled touch. A path only produces a
    :class:`CanceledPathState` when its newest toucher IS a canceled commit
    (R7 supersession — a later survivor touch already dropped it before this
    point).  ``pre_state_by_survivor`` compares walk POSITIONS (index 0 =
    newest): a survivor's oldest recorded touch index strictly greater than
    the canceled WP's oldest touch index means some survivor commit is OLDER
    on the spine than the canceled WP's first change to that path (R1).

    A non-merge commit that is not in *covered* (the union of every resolved
    window of every lane WP that entered implementation) and touches at least
    one non-bookkeeping path is recorded in ``outside_windows`` — the same
    ``changed_paths_of`` read, no extra walk.
    """
    newest_toucher: dict[str, str] = {}
    oldest_canceled_idx: dict[str, int] = {}
    oldest_canceled_sha: dict[str, str] = {}
    oldest_survivor_idx: dict[str, int] = {}
    outside: list[tuple[str, str]] = []
    for idx, sha in enumerate(spine):
        if sha not in merge_cache:
            merge_cache[sha] = is_merge_commit(repo_root, sha)
        if merge_cache[sha]:
            continue  # R3/B4 — merges never attribute or supersede
        is_canceled = sha in canceled_commits
        content_paths = [path for path in changed_paths_of(repo_root, sha) if not is_bookkeeping(path)]
        if content_paths and sha not in covered:
            outside.append((sha, content_paths[0]))
        for path in content_paths:
            if path not in newest_toucher:
                newest_toucher[path] = sha
            if is_canceled:
                oldest_canceled_idx[path] = idx
                oldest_canceled_sha[path] = sha
            else:
                oldest_survivor_idx[path] = idx

    results: set[CanceledPathState] = set()
    for path, toucher in newest_toucher.items():
        if toucher not in canceled_commits:
            continue  # superseded by a later (newer) non-canceled toucher — R7
        oldest_c_sha = oldest_canceled_sha[path]
        canceled_state = path_state_at(repo_root, toucher, path)
        pre_state = path_state_at(repo_root, f"{oldest_c_sha}^", path)
        if canceled_state == pre_state:
            continue  # net-zero self-revert
        pre_state_by_survivor = oldest_survivor_idx.get(path, -1) > oldest_canceled_idx[path]
        results.add(
            CanceledPathState(
                wp_id=wp_id,
                lane_id=lane_id,
                path=path,
                canceled_state=canceled_state,
                pre_state=pre_state,
                pre_state_by_survivor=pre_state_by_survivor,
            )
        )
    return _SpineWalk(canceled_content=frozenset(results), outside_windows=tuple(outside))


def _resolve_sibling_windows(
    repo_root: Path,
    events: Sequence[StatusEvent],
    windows_by_wp: dict[str, list[WorkWindow]],
    siblings: Iterable[str],
    lane_branch: str,
    spine_set: frozenset[str],
    merge_cache: dict[str, bool],
) -> tuple[frozenset[str], frozenset[str], tuple[str, UnattributableReason] | None]:
    """Resolve every sibling that entered implementation; bucket impl/review commits.

    Returns ``(impl, review, failure)`` where *failure* names the
    first sibling whose windows could not be bounded, with the reason.

    A sibling that never entered implementation (T020, plan.md D-3 step 2) did
    no implementation work to attribute — the SAME gate the canceled WP itself
    gets. Skipping it BEFORE resolving its windows matters concretely:
    ``planned -> blocked`` is a legal transition and ``blocked`` opens an
    implementation window (R6), so a sibling that only ever reached
    ``blocked`` would otherwise have that window resolved — and either REFUSE
    the whole lane over a stamp it never needed, or silently claim overlap
    with the canceled WP's real commits (review cycle 2, issue 6).
    """
    impl: set[str] = set()
    review: set[str] = set()
    for wp_id in sorted(siblings):
        if not _entered_implementation(events, wp_id):
            continue
        by_kind, reason = _resolve_wp_windows(repo_root, windows_by_wp.get(wp_id, []), lane_branch, spine_set, merge_cache)
        if reason is not None:
            return frozenset(), frozenset(), (wp_id, reason)
        impl |= by_kind.get(WindowKind.IMPLEMENTATION, frozenset())
        review |= by_kind.get(WindowKind.REVIEW, frozenset())
    return frozenset(impl), frozenset(review), None


def _first_governed_open_stamp(events: Sequence[StatusEvent], wp_ids: frozenset[str]) -> str | None:
    """The lane head when the lane's FIRST governed work began (FR-013 anchor).

    The stamp on the first non-migration transition of any lane WP into an
    implementation-class lane. Everything reachable from it predates every WP
    window of this lane: the lane's creation, and whatever the allocator merged
    in before work started (dependency lanes fast-forwarded without ``--no-ff``,
    ``lanes/worktree_allocator.py``; the recorded planning-artifact commit merge,
    which can fast-forward target-branch commits). None of that is a straggler.
    """
    for event in events:
        if event.wp_id in wp_ids and not _is_migration_event(event) and _classify(event.to_lane) is WindowKind.IMPLEMENTATION:
            stamp = _stamp_of(event)
            if stamp is not None:
                return stamp
    return None


def lane_exempt_commits(repo_root: Path, coord_base_ref: str, anchors: Iterable[str]) -> frozenset[str]:
    """Commits after *coord_base_ref* that predate a lane's own work (the lane-base authority).

    The union of ``coord_base_ref..anchor`` over every anchor: the lane head at its
    first governed claim, each dependency-lane tip, the target's pre-consolidation
    tip, an operator attestation's own stamp. These name history that is NOT the
    lane's own new work. An anchor git cannot read is skipped: that exempts less,
    so it can only REFUSE/exclude more, never PASS more.

    The single answer to "what did this lane author since its base" for BOTH the
    FR-013 closed world (:func:`_outside_after_anchors`) and the authorship claim
    (:func:`lane_own_commits`, #5569) — no second copy of the anchor walk.
    """
    exempt: set[str] = set()
    for anchor in anchors:
        try:
            exempt.update(commits_in_range(repo_root, coord_base_ref, anchor))
        except GitProbeError:
            continue
    return frozenset(exempt)


def lane_own_commits(repo_root: Path, coord_base_ref: str, lane_commits: Iterable[str], anchors: Iterable[str]) -> frozenset[str]:
    """The subset of *lane_commits* the lane authored itself: not reachable from any anchor (#5569).

    Commits that precede the lane's base (shared ancestry reachable from an
    anchor) are never "own" — an approved lane that shares them keeps them.
    """
    return frozenset(lane_commits) - lane_exempt_commits(repo_root, coord_base_ref, anchors)


def _outside_after_anchors(
    repo_root: Path,
    coord_base_ref: str,
    outside: tuple[tuple[str, str], ...],
    anchors: Iterable[str],
    never_exempt: frozenset[str] = frozenset(),
) -> tuple[tuple[str, str], ...]:
    """Drop outside-window commits reachable from any anchor (FR-013 closed world).

    Anchors name history that is not this lane's own new work: the lane head at
    its first governed claim, each dependency-lane tip (later allocator merges
    of a dependency lane), the target's pre-consolidation tip (already shipped),
    and an operator attestation's own lane-head stamp (FR-012 — commits after
    the attestation stay checked). Only commits AFTER the lane's own base that
    lie in no own-WP window remain "outside". An anchor git cannot read is
    skipped: that exempts less, so it can only REFUSE more, never PASS more.

    *never_exempt* (#5569) are commits a fully-canceled lane authored: however an
    anchor reaches them (the dependent lane's first-claim stamp, a transitive
    dependency tip), they are canceled content, never "history that predates the
    lane", so they stay outside. This only shrinks the exempt set.
    """
    if not outside:
        return outside
    exempt = lane_exempt_commits(repo_root, coord_base_ref, anchors) - never_exempt
    return tuple(item for item in outside if item[0] not in exempt)


def _closed_world_refusal(walk: _SpineWalk, lane_id: str, wp_id: str) -> Unattributable:
    """FR-013: name the lane, up to three short shas and one offending path."""
    shas = [sha for sha, _path in walk.outside_windows]
    return Unattributable(
        UnattributableReason.COMMIT_OUTSIDE_WINDOWS,
        _detail_for(UnattributableReason.COMMIT_OUTSIDE_WINDOWS, lane_id, wp_id, commits=shas, path=walk.outside_windows[0][1]),
    )


def resolve_canceled_wp(
    repo_root: Path,
    *,
    events: Sequence[StatusEvent],
    lane_id: str,
    lane_wp_ids: Iterable[str],
    canceled_wp_id: str,
    lane_branch: str,
    coord_base_ref: str,
    is_bookkeeping: Callable[[str], bool],
    closed_world_anchors: Sequence[str] = (),
    never_exempt_commits: frozenset[str] = frozenset(),
) -> AttributionOutcome:
    """Resolve one canceled WP's attributed commits + unsuperseded canceled content.

    Pure except for git reads against *repo_root*. ``events`` must already be
    read (append/causal order — never sorted by wall clock, per CLAUDE.md's
    reducer-duality caveat); a caller that hit ``StoreError`` reading them
    should map that to ``Unattributable(EVENTS_UNREADABLE, ...)`` itself
    rather than calling this function.

    **Closed world (FR-013, ADR 2026-09-29-1).** When EVERY window of every lane WP that entered implementation resolved, a
    non-merge, non-bookkeeping first-parent commit of ``coord_base..lane``
    that lies in no WP's window, and is not reachable from the lane's first
    governed open stamp or from any of *closed_world_anchors* (dependency-lane
    tips, the target's pre-consolidation tip, an attestation stamp — see
    :func:`_outside_after_anchors`), returns
    ``Unattributable(COMMIT_OUTSIDE_WINDOWS)``. The check is computed in the
    same spine walk as the canceled content. For a canceled WP that never
    entered implementation it runs only when at least one sibling entered
    implementation and all sibling windows resolved; otherwise that WP keeps
    today's behaviour (an empty :class:`Attributed`, no git read). An operator
    attestation (FR-012) reaches this check only as one more anchor — its own
    ``lane_head`` stamp — so a straggler committed after it is still refused.

    *never_exempt_commits* (#5569) are a fully-canceled lane's own commits; no
    anchor may exempt them from the closed world (see :func:`_outside_after_anchors`).
    """
    wp_ids = frozenset(lane_wp_ids) | {canceled_wp_id}
    entered = _entered_implementation(events, canceled_wp_id)
    siblings = wp_ids - {canceled_wp_id}
    if not entered and not any(_entered_implementation(events, wp) for wp in siblings):
        return Attributed(commits=frozenset(), canceled_content=frozenset())

    try:
        spine = first_parent_commits_in_range(repo_root, coord_base_ref, lane_branch)
    except GitProbeError:
        return Unattributable(
            UnattributableReason.SPINE_UNREADABLE,
            _detail_for(UnattributableReason.SPINE_UNREADABLE, lane_id, canceled_wp_id),
        )
    spine_set = frozenset(spine)
    windows_by_wp = _windows(events, wp_ids)
    merge_cache: dict[str, bool] = {}

    canceled_by_kind: dict[WindowKind, frozenset[str]] = {WindowKind.IMPLEMENTATION: frozenset(), WindowKind.REVIEW: frozenset()}
    if entered:
        canceled_by_kind, reason = _resolve_wp_windows(repo_root, windows_by_wp.get(canceled_wp_id, []), lane_branch, spine_set, merge_cache)
        if reason is not None:
            return Unattributable(reason, _detail_for(reason, lane_id, canceled_wp_id))

    sibling_impl, sibling_review, failure = _resolve_sibling_windows(repo_root, events, windows_by_wp, siblings, lane_branch, spine_set, merge_cache)
    if failure is not None:
        if not entered:
            # Not every window resolved: the closed world cannot be evaluated,
            # and a never-implemented canceled WP has nothing of its own to
            # attribute — today's behaviour (FR-013 applies to resolved lanes).
            return Attributed(commits=frozenset(), canceled_content=frozenset())
        # A sibling's unresolvable window must not be read as "no overlap with
        # the canceled WP" (review cycle 1, issue 1) — name the sibling and the
        # lane (NFR-003), reusing the same reason vocabulary.
        failed_wp, sib_reason = failure
        return Unattributable(sib_reason, _detail_for(sib_reason, lane_id, failed_wp))

    contested = _resolve_contested(canceled_by_kind, sibling_impl, sibling_review)
    if contested:
        return Unattributable(
            UnattributableReason.CONTESTED_COMMIT,
            _contested_detail(lane_id, canceled_wp_id, contested),
        )

    canceled_commits = canceled_by_kind[WindowKind.IMPLEMENTATION] | canceled_by_kind[WindowKind.REVIEW]
    covered = canceled_commits | sibling_impl | sibling_review
    try:
        walk = _canceled_content_walk(repo_root, spine, canceled_commits, covered, is_bookkeeping, canceled_wp_id, lane_id, merge_cache)
    except GitProbeError:
        return Unattributable(
            UnattributableReason.SPINE_UNREADABLE,
            _detail_for(UnattributableReason.SPINE_UNREADABLE, lane_id, canceled_wp_id),
        )
    if walk.outside_windows:
        base_anchor = _first_governed_open_stamp(events, wp_ids)
        anchors = [*([base_anchor] if base_anchor else []), *closed_world_anchors]
        outside = _outside_after_anchors(repo_root, coord_base_ref, walk.outside_windows, anchors, never_exempt_commits)
        if outside:
            return _closed_world_refusal(replace(walk, outside_windows=outside), lane_id, canceled_wp_id)

    return Attributed(commits=canceled_commits, canceled_content=walk.canceled_content)


__all__ = [
    "MIGRATION_ACTOR_PREFIX",
    "AttributionOutcome",
    "Attributed",
    "Unattributable",
    "UnattributableReason",
    "CanceledPathState",
    "lane_exempt_commits",
    "lane_own_commits",
    "resolve_canceled_wp",
]
