"""The approved bound of the reconciliation gate (Mission consolidation-window-provenance-01M6Y84D, WP11).

The check that a code lane holds nothing beyond what review approved (#5668): the claim-time verdict,
the ``single_branch`` write-branch leg (S8, #7283), the public ``approved_bound_refusal`` entry point
and the gate-time lane-tip re-check. Moved verbatim out of ``reconciliation.py``; that module
re-exports every name, so no caller changes (C-005).
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from specify_cli.consolidation.approved_bound import (
    BoundRefusal,
    BoundRefusalCode,
    approval_stamp,
    check_lane,
    commits_beyond,
    content_commits,
    render_refusals,
    resolves_commit,
)
from specify_cli.consolidation.git_probes import GitProbeError, resolve_commit
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
    """The approved-bound outcome of one claim: a refusal, or the lane tips it validated."""

    refusal: str | None = None
    lane_tips: tuple[tuple[str, str], ...] = ()
    lane_branches: tuple[tuple[str, str], ...] = ()


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
) -> _BoundVerdict:
    """Check every covered code lane against its approval stamps (#5668); read the log once via *event_log*.

    A ``single_branch`` Mission that lands a minted Mission branch is checked through that
    branch against its per-WP approval windows instead (:func:`_write_branch_verdict`, S8, #7283).

    A lane that also holds a canceled work package is checked like any other: no commit,
    status event or attestation of a canceled work package covers a commit (#5720).

    The refused lanes render as one text (:func:`~specify_cli.consolidation.approved_bound.render_refusals`),
    a line per lane in lane order. A lane tip is resolved once and both checked and recorded, so the gate re-check asks about
    exactly the commit this check validated.
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
    stamp_anchors = approval_stamp_anchors(events, lanes, work_packages, excluded_canceled_wp_ids)
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=planning_prefix)
    refusals: list[BoundRefusal] = []
    tips: list[tuple[str, str]] = []
    for lane in lanes:
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        try:
            tip = resolve_commit(repo_root, branch)
        except GitProbeError:
            continue  # an unresolvable lane tip reads as an empty lane, as the collectors read it (:func:`_lane_tip_commits`)
        found = check_lane(
            repo_root,
            events=events,
            lane_id=lane.lane_id,
            branch=branch,
            approved_wp_ids=_bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids),
            claim_base=claim_base,
            anchors=[*_closed_world_anchors(lanes_manifest, lane, window_base, excluded_canceled_wp_ids=excluded_canceled_wp_ids), *stamp_anchors],
            is_bookkeeping=is_bookkeeping,
            tip=tip,
        )
        if found is not None:
            refusals.append(found)
        tips.append((branch, tip))
    if refusals:
        return _BoundVerdict(refusal=render_refusals(refusals, lanes_manifest.mission_slug))
    return _BoundVerdict(lane_tips=tuple(tips))


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
    resolves to the target) and asks about exactly the commit validated here.
    """
    from .write_branch_bound import check_write_branch, render_write_branch_refusals

    events = event_log.read()
    if events is None:
        return _BoundVerdict(refusal=_bound_events_unreadable_text(scope.lane_id))
    claim_base = _bound_claim_base(repo_root, window_base, coord_base_ref)
    if not resolves_commit(repo_root, claim_base):
        return _BoundVerdict(refusal=_bound_claim_base_unresolved_text(claim_base))
    tip = resolve_commit(repo_root, scope.branch)
    refusals = check_write_branch(
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
        return _BoundVerdict(refusal=render_write_branch_refusals(refusals, lanes_manifest.mission_slug))
    return _BoundVerdict(lane_tips=((scope.branch, tip),), lane_branches=((scope.lane_id, scope.branch),))


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
    """
    from specify_cli.status import materialize_snapshot

    snapshot = materialize_snapshot(feature_dir)
    verdict = _approved_bound_verdict(
        repo_root,
        lanes_manifest,
        snapshot.work_packages or {},
        frozenset(excluded_canceled_wp_ids),
        coord_base_ref=coord_base_ref,
        window_base=excluded_window_base,
        planning_prefix=_planning_prefix(repo_root, feature_dir),
        event_log=event_log or _ClaimEventLog(feature_dir),
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
