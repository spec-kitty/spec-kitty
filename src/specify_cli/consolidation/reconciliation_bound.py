"""The approved bound of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP11).

The check that a code lane holds nothing beyond what review approved (#5668): the claim-time verdict,
the ``single_branch`` write-branch leg (S8, #7283), the public ``approved_bound_refusal`` entry point
and the gate-time lane-tip re-check. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.consolidation.approved_bound import (
    BoundRefusal,
    BoundRefusalCode,
    approval_stamp,
    approval_stamps,
    check_lane,
    commits_beyond,
    content_commits,
    render_refusals,
    resolves_commit,
)
from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit
from specify_cli.consolidation.wp_attribution import GapEntry, WindowGap, WindowOpen
from specify_cli.consolidation.write_branch_bound import (
    bind_lane_predicates,
    check_lane_windows,
    classify_windows,
    lane_windows,
    render_lane_window_refusals,
)
from specify_cli.consolidation.reconciliation_kernel import (
    _APPROVED_MEMBERSHIP_LANES,
    _ClaimEventLog,
    _closed_world_anchors,
    _is_bookkeeping,
    _lane_branch_for,
    _planning_prefix,
)
from specify_cli.lanes._git import branch_exists
from specify_cli.lanes.compute import is_planning_lane, lane_fully_canceled
from specify_cli.lanes.models import ExecutionLane, LanesManifest


@dataclass(frozen=True)
class _BoundVerdict:
    """The approved-bound outcome of one claim: a refusal, or the lane tips it validated.

    ``window_gaps`` names every approved work package of a code lane judged by its degraded
    window (FR-009), sorted by ``(lane_id, wp_id)``; it rides on a passing and a refused verdict.
    """

    refusal: str | None = None
    lane_tips: tuple[tuple[str, str], ...] = ()
    lane_branches: tuple[tuple[str, str], ...] = ()
    window_gaps: tuple[GapEntry, ...] = ()


@dataclass(frozen=True)
class _LaneVerdict:
    """One code lane's approved-bound outcome: tier-1 refusals (today's text), tier-2 window refusals, and its gaps."""

    tier_one: tuple[BoundRefusal, ...] = ()
    tier_two: tuple[BoundRefusal, ...] = ()
    gaps: tuple[GapEntry, ...] = ()


@dataclass(frozen=True)
class _LaneScope:
    """What every lane of one claim is judged against, computed once per claim."""

    repo_root: Path
    lanes_manifest: LanesManifest
    work_packages: Mapping[str, Any]
    excluded: frozenset[str]
    events: Sequence[Any]
    claim_base: str
    window_base: str | None
    frozen_tips: Mapping[str, str] | None
    stamps_by_lane: Mapping[str, tuple[str, ...]]
    is_bookkeeping: Callable[[str], bool]
    #: ``{lane_id: the canceled work packages' attributed commits}`` (the mixed-lane resolution's), tier-2 exempt.
    canceled_commits: Mapping[str, frozenset[str]]


def _bound_events_unreadable_text(lane_id: str) -> str:
    return (
        f"the status event log could not be read, so the approvals of lane {lane_id} cannot be bounded to what was reviewed. "
        "Recovery: repair or restore status.events.jsonl, then re-run"
    )


def _bound_claim_base_unresolved_text(claim_base: str) -> str:
    return (
        f"the commit the approved lanes are measured from ('{claim_base}') does not resolve, so their approvals cannot be bounded to what was reviewed. "
        "Recovery: restore that branch or commit, then re-run"
    )


def _bound_approved_wp_ids(
    lane: ExecutionLane,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[str]:
    """The work package ids of *lane* whose approval bounds it: approved membership, not canceled-with-provenance."""
    return [wp for wp in lane.wp_ids if wp not in excluded_canceled_wp_ids and str((work_packages.get(wp) or {}).get("lane", "")) in _APPROVED_MEMBERSHIP_LANES]


def _bound_lanes(
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> list[ExecutionLane]:
    """The code lanes the approved bound covers, by lane id: not planning, not fully canceled, with an approved work package."""
    covered = [
        lane
        for lane in lanes_manifest.lanes
        if not is_planning_lane(lane)
        and not lane_fully_canceled(lane, excluded_canceled_wp_ids)
        and _bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids)
    ]
    return sorted(covered, key=lambda lane: lane.lane_id)


def _bound_claim_base(repo_root: Path, window_base: str | None, coord_base_ref: str) -> str:
    """What a lane's own range is measured from: the target's pre-mutation tip when it resolves, else *coord_base_ref*.

    The target's pre-mutation tip (persisted on a resume, the live tip on a fresh run)
    predates every commit this run merges, so a post-approval commit that the mission
    branch already carries is not reachable from it. A live mission-branch (or
    coordination) tip is not: on a resume it already holds what the interrupted run merged.
    """
    return window_base if window_base and resolves_commit(repo_root, window_base) else coord_base_ref


def approval_stamp_anchors(events: Sequence[Any], lanes: Sequence[ExecutionLane], work_packages: Mapping[str, Any], excluded: frozenset[str]) -> list[str]:
    """The approval stamps of every bounded lane: reviewed content the tool's own mission-branch merges bring into another lane."""
    stamps = (approval_stamp(events, wp_id) for lane in lanes for wp_id in _bound_approved_wp_ids(lane, work_packages, excluded))
    return [stamp for stamp in stamps if stamp is not None]


def _approved_bound_verdict(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
    *,
    coord_base_ref: str,
    window_base: str | None,
    planning_prefix: str | None,
    event_log: _ClaimEventLog,
    frozen_tips: Mapping[str, str] | None = None,
    canceled_commits: Mapping[str, frozenset[str]] | None = None,
) -> _BoundVerdict:
    """Check every covered code lane against its approval stamps (#5668); read the log once via *event_log*.

    *frozen_tips* (FR-015): a ``--resume``'s frozen dependency-lane tips anchor each lane in place of the
    live dependency-lane branch names (:func:`_closed_world_anchors`); ``None`` reads live.

    A ``single_branch`` Mission that lands a minted Mission branch is checked through that
    branch against its per-WP approval windows instead (:func:`_write_branch_verdict`, S8, #7283).

    A lane that also holds a canceled work package is checked like any other: no commit,
    status event or attestation of a canceled work package covers a commit (#5720).

    The refused lanes render as one text (:func:`~specify_cli.consolidation.approved_bound.render_refusals`),
    a line per lane in lane order. A lane tip is resolved once and both checked and recorded, so the gate re-check asks about
    exactly the commit this check validated.

    A lane with at least one recorded work-package window is judged by those windows (FR-007, WP19,
    :func:`_lane_verdict`): a content commit outside every window and every exemption anchor refuses,
    after the tier-1 text of every lane. A lane whose every window is a gap keeps today's check and
    text (FR-023). ``window_gaps`` names every work package judged by its degraded window (FR-009).

    *canceled_commits* (``{lane_id: commits}``, the mixed-lane resolution's
    :attr:`~specify_cli.consolidation.reconciliation_canceled._MixedLaneResolution.canceled_commits`)
    are a canceled work package's own attributed commits: the window check (tier 2) exempts them, and
    the mixed-lane and canceled-content rules stay their sole judge (operator ruling 2026-11-09). Tier 1
    does not: a canceled work package's commit after an approval stamp still refuses (#5720). ``None``
    exempts nothing.
    """
    write_branch = _bound_write_branch(repo_root, lanes_manifest, work_packages, excluded_canceled_wp_ids)
    if write_branch is not None:
        return _write_branch_verdict(
            repo_root,
            lanes_manifest,
            write_branch,
            coord_base_ref=coord_base_ref,
            window_base=window_base,
            planning_prefix=planning_prefix,
            event_log=event_log,
        )
    lanes = _bound_lanes(lanes_manifest, work_packages, excluded_canceled_wp_ids)
    if not lanes:
        return _BoundVerdict()
    events = event_log.read()
    if events is None:
        return _BoundVerdict(refusal=_bound_events_unreadable_text(lanes[0].lane_id))
    claim_base = _bound_claim_base(repo_root, window_base, coord_base_ref)
    if not resolves_commit(repo_root, claim_base):
        return _BoundVerdict(refusal=_bound_claim_base_unresolved_text(claim_base))
    scope = _LaneScope(
        repo_root=repo_root,
        lanes_manifest=lanes_manifest,
        work_packages=work_packages,
        excluded=excluded_canceled_wp_ids,
        events=events,
        claim_base=claim_base,
        window_base=window_base,
        frozen_tips=frozen_tips,
        stamps_by_lane=_stamps_by_lane(events, lanes, work_packages, excluded_canceled_wp_ids),
        is_bookkeeping=functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix),
        canceled_commits=canceled_commits or {},
    )
    verdicts: list[_LaneVerdict] = []
    tips: list[tuple[str, str]] = []
    for lane in lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        try:
            tip = resolve_commit(repo_root, branch)
        except GitProbeError:
            continue  # an unresolvable lane tip reads as an empty lane, as the collectors read it (:func:`_lane_tip_commits`)
        verdicts.append(_lane_verdict(scope, lane, branch=branch, tip=tip))
        tips.append((branch, tip))
    gaps = tuple(sorted((gap for verdict in verdicts for gap in verdict.gaps), key=lambda gap: (gap.lane_id, gap.wp_id)))
    refusal = _render_lane_verdicts(verdicts, lanes_manifest.mission_slug)
    if refusal is not None:
        return _BoundVerdict(refusal=refusal, window_gaps=gaps)
    return _BoundVerdict(lane_tips=tuple(tips), window_gaps=gaps)


def _stamps_by_lane(
    events: Sequence[Any], lanes: Sequence[ExecutionLane], work_packages: Mapping[str, Any], excluded: frozenset[str]
) -> dict[str, tuple[str, ...]]:
    """``{lane_id: approval stamps of its bound work packages}``, lanes and stamps in :func:`approval_stamp_anchors` order."""
    return {lane.lane_id: tuple(approval_stamp_anchors(events, [lane], work_packages, excluded)) for lane in lanes}


def _canceled_window_exempt(scope: _LaneScope, lane: ExecutionLane) -> frozenset[str]:
    """The commits attributed to *lane*'s canceled work packages: exempt from its window check (tier 2) only.

    Operator ruling 2026-11-09: a canceled work package's own commits are judged by the mixed-lane
    and canceled-content rules alone; a canceled work package with no usable attribution exempts nothing.
    """
    return frozenset(scope.canceled_commits.get(lane.lane_id, frozenset()))


def _lane_verdict(scope: _LaneScope, lane: ExecutionLane, *, branch: str, tip: str) -> _LaneVerdict:
    """Judge one code lane by its work-package windows (FR-007), or by today's stamp bound when every window is a gap.

    The window predicates are bound to *tip*, the lane tip the caller resolved once and records,
    so the classifier reads exactly the commit this check validates (FR-022). An all-gap lane is
    checked by :func:`~specify_cli.consolidation.approved_bound.check_lane` with today's anchors,
    every bounded lane's stamps included, so its verdict and text are today's (FR-023, WW-3). A
    lane with a recorded window drops its OWN stamps from the anchors (WW-2a): other lanes are
    selected by lane id, never by SHA, so a dependent lane's stamp equal to this lane's tip stays one.
    The lane's canceled work packages' attributed commits (:func:`_canceled_window_exempt`) are exempt
    from tier 2 only: tier 1 keeps refusing a canceled work package's commit after an approval stamp (#5720).
    """
    approved = _bound_approved_wp_ids(lane, scope.work_packages, scope.excluded)
    closed_world = _closed_world_anchors(scope.lanes_manifest, lane, scope.window_base, excluded_canceled_wp_ids=scope.excluded, frozen_tips=scope.frozen_tips)
    on_lane, is_ancestor = bind_lane_predicates(scope.repo_root, tip)
    classes = classify_windows(scope.events, approved, on_lane=on_lane, is_ancestor=is_ancestor)
    gaps = tuple(GapEntry.from_gap(wp_id, lane.lane_id, opened) for wp_id, opened in classes.items() if isinstance(opened, WindowGap))
    if not any(isinstance(opened, WindowOpen) for opened in classes.values()):
        every_stamp = [stamp for stamps in scope.stamps_by_lane.values() for stamp in stamps]
        found = check_lane(
            scope.repo_root,
            events=scope.events,
            lane_id=lane.lane_id,
            branch=branch,
            approved_wp_ids=approved,
            claim_base=scope.claim_base,
            anchors=[*closed_world, *every_stamp],
            is_bookkeeping=scope.is_bookkeeping,
            tip=tip,
        )
        return _LaneVerdict(tier_one=() if found is None else (found,), gaps=gaps)
    others = [stamp for lane_id, stamps in scope.stamps_by_lane.items() if lane_id != lane.lane_id for stamp in stamps]
    tier_one, tier_two = check_lane_windows(
        scope.repo_root,
        events=scope.events,
        lane_id=lane.lane_id,
        branch=branch,
        approved_wp_ids=approved,
        claim_base=scope.claim_base,
        exemption_anchors=[*closed_world, *others],
        windows=lane_windows(classes, approval_stamps(scope.events, approved)),
        is_bookkeeping=scope.is_bookkeeping,
        tip=tip,
        canceled_exempt=_canceled_window_exempt(scope, lane),
    )
    return _LaneVerdict(tier_one=tier_one, tier_two=tier_two, gaps=gaps)


def _render_lane_verdicts(verdicts: Sequence[_LaneVerdict], mission_slug: str) -> str | None:
    """Tier-1 refusals of every lane in today's text, then the tier-2 window block; ``None`` when nothing refused."""
    tier_one = [refusal for verdict in verdicts for refusal in verdict.tier_one]
    tier_two = [refusal for verdict in verdicts for refusal in verdict.tier_two]
    parts: list[str] = []
    if tier_one:
        parts.append(render_refusals(tier_one, mission_slug))
    if tier_two:
        parts.append(render_lane_window_refusals(tier_two, mission_slug))
    return "\n".join(parts) if parts else None


@dataclass(frozen=True)
class _WriteBranchScope:
    """The one ``single_branch`` lane the S8 bound reads, the Mission branch it reads it through, and its approved work packages."""

    lane_id: str
    branch: str
    approved_wp_ids: tuple[str, ...]


def _bound_write_branch(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    work_packages: Mapping[str, Any],
    excluded_canceled_wp_ids: frozenset[str],
) -> _WriteBranchScope | None:
    """The S8 scope (#7283) when the Mission lands a minted Mission branch, else ``None``.

    Only a STORED ``single_branch`` Mission whose write branch differs from its target
    (``lands_mission_branch``) is bounded this way; a commit-to-target Mission stays unbounded
    (FR-078). Its approved work packages are those of its planning lane(s), canceled-with-provenance excluded.
    """
    from specify_cli.lanes.single_branch_landing import minted_mission_branch

    branch = minted_mission_branch(repo_root, lanes_manifest.mission_slug, lanes_manifest.target_branch)
    if branch is None:
        return None
    planning = [lane for lane in lanes_manifest.lanes if is_planning_lane(lane)]
    approved = tuple(sorted(wp for lane in planning for wp in _bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids)))
    if not planning or not approved:
        return None
    return _WriteBranchScope(planning[0].lane_id, branch, approved)


def _write_branch_verdict(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    scope: _WriteBranchScope,
    *,
    coord_base_ref: str,
    window_base: str | None,
    planning_prefix: str | None,
    event_log: _ClaimEventLog,
) -> _BoundVerdict:
    """Check a ``single_branch`` Mission branch against its approval windows (S8, #7283; tiers 1 and 2).

    The Mission branch tip is resolved once, checked and recorded with the lane's branch, so the
    gate re-check reads the Mission branch (never ``lane-planning``'s created-branch alias, which
    resolves to the target) and asks about exactly the commit validated here. A work package whose
    window-open SHA was not recorded keeps today's derived window and rides on the verdict as a
    window gap, on a refusal and on a pass (FR-011).
    """
    from .write_branch_bound import check_write_branch_windows, render_write_branch_refusals

    events = event_log.read()
    if events is None:
        return _BoundVerdict(refusal=_bound_events_unreadable_text(scope.lane_id))
    claim_base = _bound_claim_base(repo_root, window_base, coord_base_ref)
    if not resolves_commit(repo_root, claim_base):
        return _BoundVerdict(refusal=_bound_claim_base_unresolved_text(claim_base))
    tip = resolve_commit(repo_root, scope.branch)
    refusals, gaps = check_write_branch_windows(
        repo_root,
        events=events,
        lane_id=scope.lane_id,
        branch=scope.branch,
        approved_wp_ids=scope.approved_wp_ids,
        claim_base=claim_base,
        anchors=[window_base] if window_base else [],
        is_bookkeeping=functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix),
        tip=tip,
    )
    if refusals:
        return _BoundVerdict(refusal=render_write_branch_refusals(refusals, lanes_manifest.mission_slug), window_gaps=gaps)
    return _BoundVerdict(lane_tips=((scope.branch, tip),), lane_branches=((scope.lane_id, scope.branch),), window_gaps=gaps)


def approved_bound_refusal(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    *,
    coord_base_ref: str,
    excluded_canceled_wp_ids: Iterable[str] = (),
    excluded_window_base: str | None = None,
    event_log: _ClaimEventLog | None = None,
) -> str | None:
    """Refusal text when a code lane holds content beyond what review approved, else ``None`` (#5668).

    The claim builder's approved-bound check as a public entry point for the one other
    caller, ``orchestrator-api consolidate-mission`` (``consolidate`` runs the same check
    inside :func:`build_approved_wp_set`, on a fresh run and on ``--resume``): the reduced
    snapshot gives membership exactly as :func:`build_approved_wp_set` reads it, the
    status events come from *event_log* (one read per claim; a caller that passes none
    gets its own), and the refusal codes are rendered by
    :func:`~specify_cli.consolidation.approved_bound.render_refusals`. A snapshot
    that cannot be materialized raises, as it does for the claim builder's own caller.
    The canceled work packages' attributed commits are resolved as the claim resolves them
    (:func:`~specify_cli.consolidation.reconciliation_canceled._canceled_window_exemptions`) and exempt
    from the window check (tier 2) only, so this door and the claim give the same verdict (FR-022).
    """
    from specify_cli.lanes.single_branch_landing import authorship_window
    from specify_cli.status import materialize_snapshot

    from .reconciliation_canceled import _CanceledLaneQuery, _canceled_window_exemptions

    snapshot = materialize_snapshot(feature_dir)
    work_packages = snapshot.work_packages or {}
    excluded = frozenset(excluded_canceled_wp_ids)
    planning_prefix = _planning_prefix(repo_root, feature_dir)
    log = event_log or _ClaimEventLog(feature_dir)
    sb_window = authorship_window(repo_root, lanes_manifest.mission_slug, lanes_manifest.mission_branch, lanes_manifest.target_branch)
    query = _CanceledLaneQuery(repo_root, feature_dir, lanes_manifest, work_packages, excluded, coord_base_ref, planning_prefix, excluded_window_base, sb_window)
    verdict = _approved_bound_verdict(
        repo_root,
        lanes_manifest,
        work_packages,
        excluded,
        coord_base_ref=coord_base_ref,
        window_base=excluded_window_base,
        planning_prefix=planning_prefix,
        event_log=log,
        canceled_commits=_canceled_window_exemptions(query, log),
    )
    return verdict.refusal


def lane_tips_moved_refusal(
    repo_root: Path,
    lanes_manifest: LanesManifest,
    *,
    validated_tips: Mapping[str, str],
    anchor_shas: Sequence[str],
    planning_prefix: str | None,
    approved_wp_ids: Mapping[str, Sequence[str]] | None = None,
    lane_branches: Mapping[str, str] | None = None,
) -> str | None:
    """Refusal text when content arrived on a lane after the claim-time check validated it, else ``None`` (#5668).

    For each lane branch in *validated_tips* that still exists: the commits reachable from
    the live tip and from none of the lane's own validated tip, any other lane's validated
    tip or any of *anchor_shas*, less merge commits and bookkeeping-only commits. Reads no
    status events: the stamps were checked at claim time and this asks only whether
    content arrived since. Every reference it excludes is a SHA captured before the run
    mutated anything, never a live branch name: at gate time the live mission branch
    already reaches every merged lane commit and would exempt the commit this exists to
    find. A lane is named with its manifest work packages, or with *approved_wp_ids*
    (lane id -> approved work package ids) for the lanes it lists, so the recovery
    command never names a canceled work package. *lane_branches* (lane id -> branch, the claim's
    :attr:`ApprovedWpCommitSet.bound_lane_branches`) names the branch a lane was checked through
    when it is not the lane's created branch: a ``single_branch`` Mission's ``lane-planning`` is
    read through its Mission branch, never through its alias, which resolves to the target (S8, #7283).
    """
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix)
    refusals: list[BoundRefusal] = []
    for lane in sorted(lanes_manifest.lanes, key=lambda candidate: candidate.lane_id):
        branch = (lane_branches or {}).get(lane.lane_id) or _lane_branch_for(lanes_manifest, lane.lane_id)
        validated = validated_tips.get(branch)
        if validated is None or not branch_exists(repo_root, branch):
            continue
        others = [sha for other, sha in validated_tips.items() if other != branch]
        beyond = commits_beyond(repo_root, branch, [validated, *others, *anchor_shas])
        content = content_commits(repo_root, beyond, is_bookkeeping)
        if content:
            refusals.append(
                BoundRefusal(
                    BoundRefusalCode.LANE_MOVED_AFTER_APPROVAL,
                    lane.lane_id,
                    branch,
                    tuple(sorted((approved_wp_ids or {}).get(lane.lane_id) or lane.wp_ids)),
                    commits=tuple(sha for sha, _path in content),
                    path=content[0][1],
                )
            )
    return render_refusals(refusals, lanes_manifest.mission_slug) if refusals else None


__all__ = [
    "_BoundVerdict",
    "_WriteBranchScope",
    "_approved_bound_verdict",
    "_bound_approved_wp_ids",
    "_bound_claim_base",
    "_bound_claim_base_unresolved_text",
    "_bound_events_unreadable_text",
    "_bound_lanes",
    "_bound_write_branch",
    "_write_branch_verdict",
    "approval_stamp_anchors",
    "approved_bound_refusal",
    "lane_tips_moved_refusal",
]
