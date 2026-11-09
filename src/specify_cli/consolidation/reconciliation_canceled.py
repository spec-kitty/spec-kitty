"""The canceled pair of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP13).

One refusal stack for canceled work reaching an approved lane: the mixed-lane canceled-content
resolution (#5046: a lane that holds both an approved and a canceled-with-provenance work package) and
the fully-canceled dependency lane resolution (#5569, #5613, #6313: an approved lane that carries the
commits of a fully-canceled dependency lane), with the fail-closed check on a canceled dependency
lane whose tip cannot be read. Moved verbatim out of ``reconciliation.py``; no verdict changed.
That module re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from specify_cli.consolidation.canceled_attestation import OVERRIDABLE_REASONS, attestation_stamps
from specify_cli.consolidation.git_probes import GitProbeError, commits_in_range
from specify_cli.consolidation.reconciliation_claim_types import CanceledDependencyContent
from specify_cli.consolidation.reconciliation_kernel import (
    _ClaimEventLog,
    _closed_world_anchors,
    _dependency_lane_ids,
    _is_bookkeeping,
    _lane_branch_for,
    _lane_first_parent_spine,
    _lane_is_approved,
    _lane_tip_commits,
)
from specify_cli.consolidation.reconciliation_rendering import (
    _RECOVERY_TAIL,
    _attest_tail,
    _join_refusals,
)
from specify_cli.consolidation.wp_attribution import (
    Attributed,
    AttributionOutcome,
    CanceledPathState,
    Unattributable,
    UnattributableReason,
    canceled_spine_content,
    lacks_lane_head_stamps,
    lane_never_started,
    lane_own_commits,
    resolve_canceled_wp,
)
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_fully_canceled
from specify_cli.lanes.lane_tip import read_tip
from specify_cli.lanes.models import ExecutionLane, LanesManifest


def _mixed_lanes(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[ExecutionLane]:
    """Contract C2: every lane with ≥1 approved WP AND ≥1 canceled-with-
    provenance WP, sorted deterministically by lane id.

    ``not lane_fully_canceled(...)`` mirrors the same guard
    :func:`_unresolvable_approved_lane_branches` already applies (US1 AS-exempt
    shape): a lane whose EVERY WP is canceled-with-provenance is not "mixed" —
    there is no surviving WP to compare against — even when
    :func:`_lane_is_approved` alone still counts it true (a WP can be BOTH
    ``approved`` in the reduced snapshot AND canceled-with-provenance per the
    caller's *excluded_canceled_wp_ids*, the "provenance override" shape). Such
    a lane's created branch may legitimately not even exist.
    """

    def _is_mixed(lane: ExecutionLane) -> bool:
        has_approved = _lane_is_approved(lane, work_packages)
        has_canceled = any(wp in excluded_canceled_wp_ids for wp in lane.wp_ids)
        return has_approved and has_canceled and not lane_fully_canceled(lane, excluded_canceled_wp_ids)

    return sorted((lane for lane in lanes_manifest.lanes if _is_mixed(lane)), key=lambda lane: lane.lane_id)


def _mixed_lane_recovery(reason: UnattributableReason, wp_id: str) -> str:
    """Recovery for one mixed-lane REFUSE reason — never one that cannot succeed (FR-012)."""
    if reason is UnattributableReason.EVENTS_UNREADABLE:
        return f"Recovery: repair the mission's status event log (status.events.jsonl) so it reads cleanly, {_RECOVERY_TAIL}; this refusal cannot be overridden"
    if reason is UnattributableReason.SPINE_UNREADABLE:
        return f"Recovery: repair the lane branch so its git history reads from the coordination base, {_RECOVERY_TAIL}; this refusal cannot be overridden"
    if reason is UnattributableReason.CANCELED_LANE_CONTENT:
        return (
            "Re-running alone cannot clear this. "
            "Recovery: remove those commits from the dependent lane by reverting them on it "
            "(do not rebuild the lane: a rebuilt lane trips the resume lane-tip check), "
            f"{_RECOVERY_TAIL}; this refusal cannot be overridden"
        )
    if reason is UnattributableReason.COMMIT_OUTSIDE_WINDOWS:
        return (
            "No governed WP window will ever cover those commits, so re-running alone cannot clear this. "
            f"Recovery: verify by hand that they carry no canceled work and that {wp_id}'s canceled content is "
            f"absent or superseded, then {_attest_tail(wp_id)}"
        )
    return (
        "This attribution evidence cannot appear later (the event log is append-only), so re-running alone "
        f"cannot clear it. Recovery: verify by hand that {wp_id}'s canceled content is absent or superseded on "
        f"the lane, then {_attest_tail(wp_id)}"
    )


def _mixed_lane_unattributable_refusal(lane_id: str, wp_id: str, outcome: Unattributable) -> str:
    """T022's refusal text — names the mixed lane, the canceled WP, the resolver's
    own detail (which itself names lane/WP/evidence, NFR-003), and the recovery
    that works for THIS reason (FR-012)."""
    return f"mixed lane {lane_id}: canceled {wp_id} cannot be attributed — {outcome.detail}. {_mixed_lane_recovery(outcome.reason, wp_id)}."


@dataclass(frozen=True)
class _MixedLaneResolution:
    """Outcome of :func:`_resolve_mixed_lanes`: the claim's mixed-lane fields, plus each lane's attributed canceled commits.

    ``canceled_commits`` maps a mixed lane id to the commits the resolver attributed to its canceled
    work packages (:attr:`~specify_cli.consolidation.wp_attribution.Attributed.commits`): the lane
    window check exempts exactly these from tier 2 (operator ruling 2026-11-09). A canceled work
    package that cannot be attributed (``Unattributable``, attested or not) adds nothing. It is filled
    whether or not the resolution refuses, so a compound refusal reads the same exemption.
    """

    canceled_content: frozenset[CanceledPathState] = frozenset()
    attested_wp_ids: frozenset[str] = frozenset()
    refusal: str | None = None
    canceled_commits: Mapping[str, frozenset[str]] = field(default_factory=dict)


def _resolve_mixed_lane_canceled_content(*args: Any, **kwargs: Any) -> tuple[frozenset[CanceledPathState], frozenset[str], str | None]:
    """``(canceled_content, attested_wp_ids, refusal)`` of :func:`_resolve_mixed_lanes` (same arguments), for its tuple callers."""
    resolution = _resolve_mixed_lanes(*args, **kwargs)
    return resolution.canceled_content, resolution.attested_wp_ids, resolution.refusal


def _resolve_mixed_lanes(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    planning_prefix: str | None,
    target_base: str | None = None,
    sb_window: tuple[str, str] | None = None,
    *,
    canceled_lane_commits: frozenset[str],
    event_log: _ClaimEventLog | None = None,
    frozen_tips: Mapping[str, str] | None = None,
) -> _MixedLaneResolution:
    """Resolve every mixed lane's canceled-with-provenance WPs (T022/T023).

    Returns a :class:`_MixedLaneResolution`: ``canceled_content``, ``attested_wp_ids`` and
    ``refusal`` as the claim reads them, and every lane's attributed canceled commits (the lane
    window check's tier-2 exemption, operator ruling 2026-11-09; computed here once, never by a
    second spine walk). Events are read
    through :func:`specify_cli.status.read_events` exactly ONCE per claim
    (*event_log*, shared with :func:`_resolve_canceled_dependency_lanes` and the
    approved-bound check, :func:`_approved_bound_verdict`; a
    caller that passes none gets its own). This function itself reads only when
    at least one mixed lane exists (decided from ``lanes.json`` + the reduced
    snapshot + *excluded_canceled_wp_ids* alone); since #5668 every claim with a
    code lane reads the log once, through the approved-bound check, and its
    mixed-lane verdicts stay byte-identical to pre-#5046 behaviour. A
    ``StoreError`` reading them refuses with the ``events_unreadable`` reason
    (NFR-002; never overridable — the attestation lives in that same log).
    Every canceled WP in every mixed lane is handed to
    :func:`~specify_cli.consolidation.wp_attribution.resolve_canceled_wp`, and every
    one that refuses is named in the returned text (#5720), each refusal unchanged,
    joined in lane and WP order. An unreadable log refuses alone: nothing else can
    be computed without it.

    FR-012: an operator attestation
    (:func:`~specify_cli.consolidation.canceled_attestation.attestation_stamps`)
    adds its own ``lane_head`` stamp as a closed-world anchor for its lane (lane
    commits up to the attestation are exempt; a later straggler is still
    refused), and an attested WP's overridable Unattributable reason falls back
    to the pre-change whole-lane behaviour (no per-WP canceled content).
    Visible canceled content still FAILs.

    *canceled_lane_commits* (#5569/#5613,
    :attr:`_CanceledDependencyResolution.unapproved_commits`: the fully-canceled
    lanes' own commits, less only those a later approved commit fully superseded
    on every lane that carries them) are never exempt from the closed world,
    whichever anchor reaches them. No attestation takes a commit out of that set.

    *frozen_tips* (FR-015): a ``--resume``'s frozen dependency-lane tips, the closed-world anchors in
    place of the live dependency-lane branch names (:func:`_closed_world_anchors`); ``None`` reads live.
    """
    mixed_lanes = _mixed_lanes(lanes_manifest, work_packages, excluded_canceled_wp_ids)
    if not mixed_lanes:
        return _MixedLaneResolution()

    event_log = event_log or _ClaimEventLog(feature_dir)
    events = event_log.read()
    if events is None:
        lane = mixed_lanes[0]
        wp_id = next(wp for wp in sorted(lane.wp_ids) if wp in excluded_canceled_wp_ids)
        return _MixedLaneResolution(refusal=_mixed_lane_unattributable_refusal(lane.lane_id, wp_id, event_log.unreadable(lane.lane_id, wp_id)))

    stamps = attestation_stamps(events)
    scope = _MixedLaneScope(
        repo_root=repo_root,
        lanes_manifest=lanes_manifest,
        events=events,
        stamps=stamps,
        excluded_canceled_wp_ids=excluded_canceled_wp_ids,
        coord_base_ref=coord_base_ref,
        target_base=target_base,
        sb_window=sb_window,
        is_bookkeeping=functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix),
        canceled_lane_commits=canceled_lane_commits,
        frozen_tips=frozen_tips,
    )
    canceled_content: set[CanceledPathState] = set()
    refusals: list[str] = []
    canceled_commits: dict[str, frozenset[str]] = {}
    for lane in mixed_lanes:
        lane_content, lane_refusals, lane_commits = _resolve_mixed_lane(scope, lane)
        canceled_content |= lane_content
        refusals.extend(lane_refusals)
        canceled_commits[lane.lane_id] = lane_commits
    if refusals:
        # Every canceled WP that refuses is named in this one text (#5720), lanes and WPs in id order.
        return _MixedLaneResolution(refusal=_join_refusals(refusals), canceled_commits=canceled_commits)
    return _MixedLaneResolution(frozenset(canceled_content), frozenset(stamps), None, canceled_commits)


@dataclass(frozen=True)
class _MixedLaneScope:
    """What every mixed lane of one claim shares while its canceled work packages are resolved."""

    repo_root: Path
    lanes_manifest: LanesManifest
    events: Sequence[Any]
    stamps: Mapping[str, str | None]
    excluded_canceled_wp_ids: frozenset[str]
    coord_base_ref: str
    target_base: str | None
    sb_window: tuple[str, str] | None
    is_bookkeeping: Callable[[str], bool]
    canceled_lane_commits: frozenset[str]
    #: FR-015: a ``--resume``'s frozen dependency-lane tips (``None``: the live read).
    frozen_tips: Mapping[str, str] | None = None


def _resolve_mixed_lane(scope: _MixedLaneScope, lane: ExecutionLane) -> tuple[set[CanceledPathState], list[str], frozenset[str]]:
    """``(canceled content, refusals, attributed canceled commits)`` of one mixed lane: every canceled WP is resolved, none stops the others (#5720).

    An attested WP whose refusal is overridable (FR-012) falls back to the pre-change
    whole-lane behaviour and adds no refusal. Only an ``Attributed`` canceled WP adds its commits to
    the third item (the lane window check's tier-2 exemption, operator ruling 2026-11-09).
    """
    # #5100: a protected single_branch repo-root lane reads its authored
    # window ``fork_point..mission_branch`` (same source as the collectors).
    lane_base, branch = (
        scope.sb_window if scope.sb_window and is_planning_lane(lane) else (scope.coord_base_ref, _lane_branch_for(scope.lanes_manifest, lane.lane_id))
    )
    lane_canceled = sorted(wp for wp in lane.wp_ids if wp in scope.excluded_canceled_wp_ids)
    attestation_anchors = [stamp for wp in lane_canceled if (stamp := scope.stamps.get(wp))]
    anchors = [
        *_closed_world_anchors(
            scope.lanes_manifest, lane, scope.target_base, excluded_canceled_wp_ids=scope.excluded_canceled_wp_ids, frozen_tips=scope.frozen_tips
        ),
        *attestation_anchors,
    ]
    content: set[CanceledPathState] = set()
    refusals: list[str] = []
    attributed: set[str] = set()
    for wp_id in lane_canceled:
        outcome: AttributionOutcome = resolve_canceled_wp(
            scope.repo_root,
            events=scope.events,
            lane_id=lane.lane_id,
            lane_wp_ids=lane.wp_ids,
            canceled_wp_id=wp_id,
            lane_branch=branch,
            coord_base_ref=lane_base,
            is_bookkeeping=scope.is_bookkeeping,
            closed_world_anchors=anchors,
            never_exempt_commits=scope.canceled_lane_commits,
        )
        if isinstance(outcome, Attributed):
            content |= outcome.canceled_content
            attributed |= outcome.commits
        elif wp_id in scope.stamps and outcome.reason in OVERRIDABLE_REASONS:
            continue  # FR-012: operator-attested — pre-change whole-lane behaviour for this WP.
        else:
            refusals.append(_mixed_lane_unattributable_refusal(lane.lane_id, wp_id, outcome))
    return content, refusals, frozenset(attributed)


def _fully_canceled_lane_commits(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    target_base: str | None,
    *,
    frozen_tips: Mapping[str, str] | None = None,
) -> frozenset[str]:
    """Commits authored by FULLY-canceled lanes since their own base (#5569).

    A fully-canceled lane (every WP canceled-with-provenance) has no approved
    work, so nothing reachable from its tip after its base is authorship of any
    lane. The allocator merges a dependency lane into a dependent lane without
    ``--no-ff``, so a fresh dependent lane fast-forwards and these commits sit on
    the dependent lane's first-parent spine; this set is what
    :func:`_collect_authored` and the closed world subtract so they cannot be
    claimed as approved authorship. "After its base" is the shared
    :func:`~specify_cli.consolidation.wp_attribution.lane_own_commits` over the
    lane's own anchors, so ancestry the lane inherited from approved dependency
    lanes or the target is never counted. A canceled lane whose branch is gone
    yields nothing (claim building tolerates an unresolvable lane, as
    :func:`_lane_tip_commits` documents). A live lane's dependency on such a
    lane is refused by :func:`_unreadable_canceled_dependency_lanes` unless the
    event log proves the lane never started (no branch was ever created, so
    there is nothing to subtract; spec-kitty#5937); call this only after that check.
    *frozen_tips* (FR-015) anchors a ``--resume`` on the frozen dependency-lane tips.
    """
    by_lane = _fully_canceled_lane_own_commits(repo_root, lanes_manifest, excluded_canceled_wp_ids, coord_base_ref, target_base, frozen_tips=frozen_tips)
    return frozenset().union(*by_lane.values())


def _fully_canceled_lane_own_commits(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    target_base: str | None,
    *,
    frozen_tips: Mapping[str, str] | None = None,
) -> dict[str, frozenset[str]]:
    """:func:`_fully_canceled_lane_commits`, kept per fully-canceled lane id (#5613); *frozen_tips* as there (FR-015)."""
    by_lane: dict[str, frozenset[str]] = {}
    for lane in lanes_manifest.lanes:
        if is_planning_lane(lane) or not lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        tip_commits = _lane_tip_commits(repo_root, coord_base_ref, _lane_branch_for(lanes_manifest, lane.lane_id))
        anchors = _closed_world_anchors(lanes_manifest, lane, target_base, excluded_canceled_wp_ids=excluded_canceled_wp_ids, frozen_tips=frozen_tips)
        by_lane[lane.lane_id] = lane_own_commits(repo_root, coord_base_ref, tip_commits, anchors)
    return by_lane


@dataclass(frozen=True)
class _CanceledLaneQuery:
    """What the fully-canceled dependency lane resolution reads (#5613)."""

    repo_root: Path
    feature_dir: Path
    lanes_manifest: LanesManifest
    work_packages: Mapping[str, Any]
    excluded_ids: frozenset[str]
    coord_base_ref: str
    planning_prefix: str | None
    target_base: str | None
    sb_window: tuple[str, str] | None
    #: FR-015: a ``--resume``'s frozen dependency-lane tips (``None``: the live read).
    frozen_tips: Mapping[str, str] | None = None


@dataclass(frozen=True)
class _CanceledDependencyResolution:
    """Outcome of :func:`_resolve_canceled_dependency_lanes` (#5613).

    ``unapproved_commits`` is what :func:`_collect_authored` and the mixed-lane
    closed world subtract: the fully-canceled lanes' own commits, less the ones a
    later approved commit fully superseded on every lane that carries them.
    Nothing else leaves that set: an attestation lifts a refusal, never a commit.
    """

    unapproved_commits: frozenset[str] = frozenset()
    content: frozenset[CanceledDependencyContent] = frozenset()
    refusal: str | None = None


def _carrier_spines(query: _CanceledLaneQuery, canceled_commits: frozenset[str]) -> dict[str, list[str]]:
    """Approved, not fully-canceled lane id -> its first-parent spine, for lanes that carry a canceled-lane commit."""
    carriers: dict[str, list[str]] = {}
    for lane in query.lanes_manifest.lanes:
        if not _lane_is_approved(lane, query.work_packages) or lane_fully_canceled(lane, query.excluded_ids):
            continue
        lane_branch = _lane_branch_for(query.lanes_manifest, lane.lane_id)
        base, branch = query.sb_window if query.sb_window and is_planning_lane(lane) else (query.coord_base_ref, lane_branch)
        spine = _lane_first_parent_spine(query.repo_root, base, branch)
        if canceled_commits.intersection(spine):
            carriers[lane.lane_id] = spine
    return carriers


def _carried_unattributable_refusal(lane_id: str, wp_id: str, carrier_ids: Sequence[str], outcome: Unattributable) -> str:
    """The refusal for a canceled dependency WP whose carried work has no attribution evidence."""
    return (
        f"canceled {wp_id} (lane {lane_id}) is carried by approved lane(s) {', '.join(carrier_ids)} but cannot be attributed — "
        f"{outcome.detail}. {_mixed_lane_recovery(outcome.reason, wp_id)}."
    )


def _unstamped_carried_refusal(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    carriers: Mapping[str, list[str]],
    event_log: _ClaimEventLog,
) -> str | None:
    """The up-front REFUSE for a carried fully-canceled lane with an unstamped WP, or ``None`` (#5613).

    Every unstamped WP is named in the one text (#5720), lanes and WPs in id order.

    A canceled WP whose closed work window carries no ``lane_head`` stamp has no
    attribution evidence: the claim REFUSEs and names the override, exactly as a
    mixed lane does for ``no_stamp``. That covers a legacy mission (created before
    the stamps) and, identically, a modern mission whose best-effort stamp capture
    failed for that transition: the two cannot be told apart from the log, and the
    evidence cannot appear later in either.

    An operator attestation of that WP lifts THIS refusal and nothing else, and
    only while :data:`~specify_cli.consolidation.canceled_attestation.OVERRIDABLE_REASONS`
    (the one authority) lists ``no_stamp``. It is per WP: every unstamped WP of the
    lane must be attested itself. No commit is lifted with it -- neither the
    attested WP's nor a stamped sibling's -- so the lane's content is still
    resolved over all of its own commits (:func:`_carried_dependency_content`) and
    live content still FAILs with ``CANCELED_REACHABLE_VIA_DEPENDENCY``. An
    unreadable event log refuses and cannot be overridden.
    """
    carried = {lane_id: sorted(c for c, spine in carriers.items() if own.intersection(spine)) for lane_id, own in sorted(own_by_lane.items())}
    carried = {lane_id: carrier_ids for lane_id, carrier_ids in carried.items() if carrier_ids}
    wps_by_lane = {lane.lane_id: sorted(lane.wp_ids) for lane in query.lanes_manifest.lanes}
    events = event_log.read()
    if events is None:
        lane_id, carrier_ids = next(iter(carried.items()))
        wp_id = wps_by_lane[lane_id][0]
        return _carried_unattributable_refusal(lane_id, wp_id, carrier_ids, event_log.unreadable(lane_id, wp_id))
    liftable = frozenset(attestation_stamps(events)) if UnattributableReason.NO_STAMP in OVERRIDABLE_REASONS else frozenset()
    refusals = [
        _carried_unattributable_refusal(lane_id, wp_id, carrier_ids, Unattributable.for_reason(UnattributableReason.NO_STAMP, lane_id, wp_id))
        for lane_id, carrier_ids in carried.items()
        for wp_id in wps_by_lane[lane_id]
        if wp_id not in liftable and lacks_lane_head_stamps(events, wp_id)
    ]
    return _join_refusals(refusals) if refusals else None


def _unreadable_carrier_refusal(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    unreadable: Mapping[str, tuple[list[str], GitProbeError]],
) -> str | None:
    """The REFUSE for carrier lanes whose spine could not be read, or ``None`` (#6313).

    Every canceled WP of every fully-canceled lane an unreadable carrier holds is named
    once, with the unreadable carriers that hold it, lanes and WPs in id order. The
    reason is ``spine_unreadable``, as on a mixed lane, and the recovery names the
    carrier: ``OVERRIDABLE_REASONS`` omits the reason, so no attestation lifts it. A
    probe error is not always a broken branch: a path renamed to more than one target
    raises one too, so the recovery names that fix as well.
    """
    wps_by_lane = {lane.lane_id: sorted(lane.wp_ids) for lane in query.lanes_manifest.lanes}
    refusals: list[str] = []
    for lane_id, own in sorted(own_by_lane.items()):
        held_by = sorted(carrier_id for carrier_id, (spine, _error) in unreadable.items() if own.intersection(spine))
        if not held_by:
            continue
        carriers = ", ".join(held_by)
        errors = "; ".join(f"{carrier_id}: {unreadable[carrier_id][1]}" for carrier_id in held_by)
        refusals.extend(
            f"canceled {wp_id} (lane {lane_id}) is carried by approved lane(s) {carriers} "
            f"but cannot be attributed ({UnattributableReason.SPINE_UNREADABLE.value}) — "
            f"the git history of carrier lane(s) {carriers} could not be read to resolve which canceled content they still carry ({errors}). "
            f"Recovery: repair the branch of carrier lane(s) {carriers} so its history reads, or, when the error reports a path renamed to "
            f"more than one path, keep only one of those renames on the carrier, {_RECOVERY_TAIL}; this refusal cannot be overridden."
            for wp_id in wps_by_lane[lane_id]
        )
    return _join_refusals(refusals) if refusals else None


def _carried_dependency_content(
    query: _CanceledLaneQuery,
    own_by_lane: Mapping[str, frozenset[str]],
    carriers: Mapping[str, list[str]],
    canceled: frozenset[str],
) -> tuple[frozenset[str], frozenset[CanceledDependencyContent], str | None]:
    """``(superseded commits, carried content, refusal)`` over every carrier lane's spine (#5613).

    A canceled commit counts as superseded only when it is superseded on EVERY
    carrier that holds it; then it stays in that lane's authorship (its content is
    not the lane's final state) and consolidation is not refused for it. A carrier
    whose spine cannot be read REFUSEs (#6313, :func:`_unreadable_carrier_refusal`):
    subtracting its canceled commits is not enough, because the canceled lines stay in
    the carrier's authored blobs and would ship unnamed.
    """
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=query.lanes_manifest.mission_slug, planning_prefix=query.planning_prefix)
    lane_of = {sha: lane_id for lane_id, own in own_by_lane.items() for sha in own}
    wps_of = {lane.lane_id: tuple(sorted(lane.wp_ids)) for lane in query.lanes_manifest.lanes}
    superseded: set[str] = set()
    live_commits: set[str] = set()
    content: set[CanceledDependencyContent] = set()
    unreadable: dict[str, tuple[list[str], GitProbeError]] = {}
    for carrier_id, spine in carriers.items():
        on_spine = canceled.intersection(spine)
        try:
            lane_superseded, live = canceled_spine_content(query.repo_root, spine, canceled, is_bookkeeping)
        except GitProbeError as exc:
            live_commits |= on_spine
            unreadable[carrier_id] = (spine, exc)
            continue
        superseded |= lane_superseded
        live_commits |= on_spine - lane_superseded
        for path, entry in live.items():
            content.add(CanceledDependencyContent(wps_of[lane_of[entry.sha]], lane_of[entry.sha], carrier_id, path, entry.state, entry.renamed_from))
    return frozenset(superseded - live_commits), frozenset(content), _unreadable_carrier_refusal(query, own_by_lane, unreadable)


def _resolve_canceled_dependency_lanes(query: _CanceledLaneQuery, event_log: _ClaimEventLog | None = None) -> _CanceledDependencyResolution:
    """Resolve the fully-canceled lanes whose commits an approved lane carries (#5569, #5613).

    The base is :func:`_fully_canceled_lane_commits`: every such lane's own commits
    leave the approved claim. Four refinements, none of which runs (and no event
    log is read) for a mission where no approved lane carries such a commit:

    * a canceled WP without ``lane_head`` stamps REFUSEs with the override named,
      until the operator attests it (:func:`_unstamped_carried_refusal`). The
      attestation lifts that refusal only;
    * a canceled commit a later approved commit fully superseded on every carrier
      stays in the claim, so a superseded canceled dependency consolidates --
      whether its WP is stamped, or unstamped and attested;
    * the remaining live content is recorded so the verifier can name it with
      ``CANCELED_REACHABLE_VIA_DEPENDENCY``. It is computed over ALL of the lanes'
      own commits, attested or not: content that would ship always FAILs;
    * a carrier whose spine cannot be read REFUSEs (``spine_unreadable``, #6313),
      as the mixed-lane axis does; no attestation lifts it.
    """
    own_by_lane = _fully_canceled_lane_own_commits(
        query.repo_root, query.lanes_manifest, query.excluded_ids, query.coord_base_ref, query.target_base, frozen_tips=query.frozen_tips
    )
    own = frozenset().union(*own_by_lane.values())
    carriers = _carrier_spines(query, own) if own else {}
    if not carriers:
        return _CanceledDependencyResolution(unapproved_commits=own)
    refusal = _unstamped_carried_refusal(query, own_by_lane, carriers, event_log or _ClaimEventLog(query.feature_dir))
    if refusal is not None:
        return _CanceledDependencyResolution(refusal=refusal)
    superseded, content, unreadable_refusal = _carried_dependency_content(query, own_by_lane, carriers, own)
    if unreadable_refusal is not None:
        return _CanceledDependencyResolution(refusal=unreadable_refusal)
    return _CanceledDependencyResolution(unapproved_commits=own - superseded, content=content)


class _UnreadableCanceledLane(NamedTuple):
    """A fully-canceled dependency lane the claim refuses (#5569), and why.

    ``log_detail`` is set only when the status event log could not be read to
    prove the lane never started (spec-kitty#5937); it carries the store error.
    """

    lane_id: str
    branch: str
    log_detail: str | None = None

    @property
    def events_unreadable(self) -> bool:
        return self.log_detail is not None


def _missing_canceled_branch_refusal(
    repo_root: Path,
    lane: ExecutionLane,
    branch: str,
    event_log: _ClaimEventLog,
) -> _UnreadableCanceledLane | None:
    """Refuse a fully-canceled dependency lane whose branch is missing, unless it provably never started.

    In order: an unreadable event log refuses (with the store error); a log that
    does not prove :func:`~specify_cli.consolidation.wp_attribution.lane_never_started`
    refuses; a lane-tip ref still recorded for the branch refuses (it is positive
    evidence that the branch existed); otherwise the lane is tolerated (``None``).
    """
    events = event_log.read()
    if events is None:
        detail = event_log.unreadable(lane.lane_id, lane.wp_ids[0]).detail
        return _UnreadableCanceledLane(lane.lane_id, branch, detail)
    if not lane_never_started(events, lane.wp_ids):
        return _UnreadableCanceledLane(lane.lane_id, branch)
    # Lazy import, as phase_teardown does: only this rare arm needs the lane-tip refs.

    if read_tip(repo_root, branch) is not None:
        return _UnreadableCanceledLane(lane.lane_id, branch)
    return None


def _unreadable_canceled_dependency_lanes(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    excluded_canceled_wp_ids: frozenset[str],
    coord_base_ref: str,
    event_log: _ClaimEventLog,
) -> list[_UnreadableCanceledLane]:
    """Every fully-canceled lane a live lane depends on whose tip is unreadable (#5569).

    :func:`_fully_canceled_lane_commits` tolerates a canceled lane whose branch is gone
    (or whose range git cannot read) and yields nothing for it. That is only safe while
    nobody inherited the lane's commits: the allocator fast-forwards a dependency lane
    into its dependent, so the canceled commits sit on the dependent lane's first-parent
    spine, and an empty set for the canceled lane leaves nothing to subtract — the
    canceled content would be attributed as approved authorship and ship. For such a
    dependency lane the unreadable tip must therefore refuse. A canceled lane nobody
    depends on stays tolerated (its commits are on no live lane's spine).

    One exception (spec-kitty#5937): a missing branch is tolerated when the event log
    positively proves the lane never started
    (:func:`~specify_cli.consolidation.wp_attribution.lane_never_started`: every WP
    canceled from ``planned``/``blocked``, none ever moved into any lane other than
    ``planned``/``blocked``/``canceled``, migration seeds included). A lane branch is
    created only when a WP moves past those lanes (a claim, or ``agent action review``
    on a WP forced into ``for_review``), so such a lane never had a branch and nothing
    of it can be on a dependent's spine. Every
    other case keeps refusing: the log cannot be read, the log does not prove it
    (an empty or partial log is never proof), a lane-tip ref is still recorded for
    the branch, or the branch exists but its range cannot be read.

    *event_log* is the claim's one shared :class:`_ClaimEventLog`; it is read only
    when a canceled dependency's branch is missing. Its unreadable arm is defensive:
    :func:`build_approved_wp_set` materializes the snapshot first, which already
    refuses a malformed log, so it is reached only when the reader fails and the
    snapshot did not. The lane-tip arm (``read_tip``) is an extra fail-closed arm,
    not the proof: ``read_tip`` returns ``None`` on any git failure, and the ref is
    normally cleared when a lane becomes fully terminal.
    """
    live_dependencies = {
        dep
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane) and not lane_fully_canceled(lane, excluded_canceled_wp_ids)
        for dep in _dependency_lane_ids(lanes_manifest, lane)
    }
    unreadable: list[_UnreadableCanceledLane] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda candidate: candidate.lane_id):
        if lane.lane_id not in live_dependencies or is_planning_lane(lane) or not lane_fully_canceled(lane, excluded_canceled_wp_ids):
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        if not branch_exists(repo_root, branch):
            refused = _missing_canceled_branch_refusal(repo_root, lane, branch, event_log)
            if refused is not None:
                unreadable.append(refused)
            continue
        try:
            commits_in_range(repo_root, coord_base_ref, branch)
        except GitProbeError:
            unreadable.append(_UnreadableCanceledLane(lane.lane_id, branch))
    return unreadable


def _unreadable_canceled_dependency_clause(lane: _UnreadableCanceledLane) -> str:
    """One lane's clause of the #5569 refusal; the unreadable-log arm names the log, never a branch restore."""
    lane_id, branch = lane.lane_id, lane.branch
    if lane.events_unreadable:
        return (
            f"fully-canceled lane {lane_id} (branch '{branch}') is a dependency of a live lane but its branch is missing, "
            f"and the status event log could not be read to prove the lane never started ({lane.log_detail}). "
            "Recovery: repair or restore the Mission's status.events.jsonl (for example from git history), "
            "then re-run `spec-kitty consolidate`"
        )
    return (
        f"fully-canceled lane {lane_id} (branch '{branch}') is a dependency of a live lane but its commits cannot be read "
        "(the branch is missing or its history is unreadable): its canceled content, which the dependent lane inherited, "
        f"cannot be told apart from approved work. Recovery: restore '{branch}' (for example "
        f"`git branch {branch} refs/spec-kitty/lane-tip/{branch}` when a lane-tip ref was recorded, or from `git reflog`), "
        "then re-run `spec-kitty consolidate`; if the branch was rebuilt, run `spec-kitty consolidate --abort` before re-running"
    )


def _unreadable_canceled_dependency_refusal_text(unreadable: list[_UnreadableCanceledLane]) -> str:
    """The #5569 fail-closed refusal for a canceled dependency lane whose tip cannot be read."""
    return "; ".join(_unreadable_canceled_dependency_clause(lane) for lane in unreadable)


def _canceled_window_exemptions(query: _CanceledLaneQuery, event_log: _ClaimEventLog) -> Mapping[str, frozenset[str]]:
    """Each mixed lane's attributed canceled commits, resolved as the claim resolves them, for a caller that builds no claim.

    ``approved_bound_refusal`` (the ``orchestrator-api`` door) judges the lanes without the claim's
    mixed-lane resolution, so it asks here for the same tier-2 exemption (operator ruling 2026-11-09):
    the fully-canceled dependency lanes first (their unapproved commits are never exempt from the
    closed world), then :func:`_resolve_mixed_lanes` once. Anything that would refuse the claim
    before the mixed lanes are resolved exempts nothing, as the claim's own compound refusal does.
    """
    if not _mixed_lanes(query.lanes_manifest, query.work_packages, query.excluded_ids):
        return {}
    if _unreadable_canceled_dependency_lanes(query.repo_root, query.lanes_manifest, query.excluded_ids, query.coord_base_ref, event_log):
        return {}
    dependency = _resolve_canceled_dependency_lanes(query, event_log)
    if dependency.refusal is not None:
        return {}
    resolution = _resolve_mixed_lanes(
        query.repo_root,
        query.feature_dir,
        query.lanes_manifest,
        query.work_packages,
        query.excluded_ids,
        query.coord_base_ref,
        query.planning_prefix,
        query.target_base,
        query.sb_window,
        canceled_lane_commits=dependency.unapproved_commits,
        event_log=event_log,
        frozen_tips=query.frozen_tips,
    )
    return resolution.canceled_commits


__all__ = [
    "_CanceledDependencyResolution",
    "_CanceledLaneQuery",
    "_MixedLaneScope",
    "_UnreadableCanceledLane",
    "_carried_dependency_content",
    "_carried_unattributable_refusal",
    "_carrier_spines",
    "_fully_canceled_lane_commits",
    "_fully_canceled_lane_own_commits",
    "_missing_canceled_branch_refusal",
    "_mixed_lane_recovery",
    "_mixed_lane_unattributable_refusal",
    "_mixed_lanes",
    "_resolve_canceled_dependency_lanes",
    "_resolve_mixed_lane",
    "_resolve_mixed_lane_canceled_content",
    "_unreadable_canceled_dependency_clause",
    "_unreadable_canceled_dependency_lanes",
    "_unreadable_canceled_dependency_refusal_text",
    "_unreadable_carrier_refusal",
    "_unstamped_carried_refusal",
]
