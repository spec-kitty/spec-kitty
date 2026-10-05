"""Operator attestation for an approval that recorded no lane head (#5668, plan D-5).

``consolidate`` refuses a work package in the approved claim whose approval carries no
``lane_head`` stamp (``APPROVAL_STAMP_MISSING``): without the commit review saw, nothing
bounds the claim. ``spec-kitty consolidate --attest-approved-reviewed <WP> --attest-reason
"<text>"`` lets the operator state, after checking the lane by hand, that its content is
the reviewed content. It lifts that one refusal, for that work package; it never lifts
``LANE_MOVED_AFTER_APPROVAL`` or ``APPROVAL_STAMP_NOT_ON_LANE`` (no code path leads from
the flag to them).

**Record shape -- no event-schema change, one authority.** Like the canceled attestation
(:mod:`specify_cli.consolidation.canceled_attestation`), the attestation is a forced
operator transition appended through the canonical transactional status seam, never
hand-written: from and to the work package's CURRENT lane (``approved``, or ``done`` after
an interrupted run), ``reason_source = "operator"``, ``policy_metadata["attestation"] =
"approved_reviewed"`` and the ``lane_head`` the transition pipeline stamps itself. The
events contract requires evidence for a transition into ``approved`` or ``done``; it is the
operator as reviewer and the attestation as the reference. :func:`approval_stamp` reads the
attestation like an approval, so its own ``lane_head`` becomes the bound: a later commit
refuses, a later review approval replaces it, and the run's own ``approved -> done`` record
(not an approval) does not affect it.

An earlier attestation is not a review approval, and it bounds the lane exactly like one.
Attesting a work package whose newest approval is an earlier attestation is therefore
accepted only while its lane has not moved past that attestation's ``lane_head`` (no content
commit beyond it, and the stamp still on the lane): the
lane is checked through :func:`~specify_cli.consolidation.approved_bound.check_lane`, the
check the claim itself runs. When it holds, the attestation is **re-recorded** as a fresh
operator act with its own reason (like ``--attest-canceled-superseded``), so a run that
failed for an unrelated reason after attesting is repeatable with the same command; the new
bound is the lane's current tip, which the check just proved is the same content. When the
lane moved on (a commit made after the earlier attestation, or a rewritten lane), the
request is refused and nothing is recorded for any work package of it: re-attesting would
otherwise read as approving the new content, and review stays the only way to approve
content. A work package whose newest approval is a review approval that carries a stamp is
refused too: it already has one.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from specify_cli.lanes.models import LanesManifest
from specify_cli.status import Lane, StatusEvent, StoreError, TransitionRequest, materialize_snapshot, read_events
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

from .approved_bound import APPROVED_REVIEWED, ATTEST_APPROVED_FLAG, approval_is_attested, approval_stamp, check_lane, move_back_command
from .canceled_attestation import ATTEST_REASON_FLAG, ATTESTATION_KEY, AttestationError
from .git_probes import GitProbeError, resolve_commit
from .reconciliation import (
    _APPROVED_MEMBERSHIP_LANES,
    _bound_approved_wp_ids,
    _bound_lanes,
    _closed_world_anchors,
    _is_bookkeeping,
    _lane_branch_for,
    _planning_prefix,
    approval_stamp_anchors,
)

#: Prefix of the recorded ``reason`` so the status log says what the operator attested.
_REASON_PREFIX = "operator attests approved content reviewed: "
#: Evidence ``review.reference`` prefix: the attestation, not a review, is the reference.
_REFERENCE_PREFIX = "operator-attestation:"
_NOTHING_RECORDED = "Nothing was recorded."


def validate_approved_attestation_request(
    wp_ids: Iterable[str],
    reason: str | None,
    *,
    events: Sequence[StatusEvent],
    claim_lanes: Mapping[str, str],
) -> tuple[str, ...]:
    """Return the de-duplicated work package ids to attest, or raise :class:`AttestationError`.

    *claim_lanes* maps each work package of the approved claim to its current lane
    (``approved`` or ``done``). The reason is required and non-blank; every work package
    must be in the claim; a work package whose newest approval is a review approval that
    carries a stamp is refused. An earlier attestation (stamped or not) passes this
    validation; whether a STAMPED one may be repeated depends on its lane, which
    :func:`plan_approved_attestations` checks.
    """
    requested = tuple(dict.fromkeys(wp_ids))
    if not requested:
        return ()
    if not (reason and reason.strip()):
        raise AttestationError(f'{ATTEST_APPROVED_FLAG} requires {ATTEST_REASON_FLAG} "<why the lane content is the reviewed content>".')
    not_approved = [wp_id for wp_id in requested if wp_id not in claim_lanes]
    if not_approved:
        raise AttestationError(f"{ATTEST_APPROVED_FLAG} applies only to an approved work package; not approved: {', '.join(not_approved)}. {_NOTHING_RECORDED}")
    stamped = [wp_id for wp_id in requested if _has_review_approval_stamp(events, wp_id)]
    if stamped:
        raise AttestationError(
            f"{ATTEST_APPROVED_FLAG} applies only to an approval with no recorded lane head; {', '.join(stamped)} already has one. "
            f"Move it back for review instead. {_NOTHING_RECORDED}"
        )
    return requested


def _has_review_approval_stamp(events: Sequence[StatusEvent], wp_id: str) -> bool:
    return approval_stamp(events, wp_id) is not None and not approval_is_attested(events, wp_id)


def approved_claim_lanes(
    work_packages: Mapping[str, Mapping[str, object]], lanes_manifest: LanesManifest, excluded_canceled_wp_ids: Iterable[str]
) -> dict[str, str]:
    """Work package id -> current lane for every manifest work package in the approved claim.

    Membership is read the way the claim builder reads it: the Lamport snapshot's lane is
    ``approved`` or ``done``, and a work package canceled with provenance is not in it.
    """
    excluded = frozenset(excluded_canceled_wp_ids)
    lanes: dict[str, str] = {}
    for lane in lanes_manifest.lanes:
        for wp_id in lane.wp_ids:
            current = str((work_packages.get(wp_id) or {}).get("lane", ""))
            if wp_id not in excluded and current in _APPROVED_MEMBERSHIP_LANES:
                lanes[wp_id] = current
    return lanes


def plan_approved_attestations(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    wp_ids: Iterable[str],
    reason: str | None,
    *,
    excluded_canceled_wp_ids: Iterable[str],
) -> dict[str, str]:
    """Validate the request against the status log: work package id -> current lane, in request order.

    Raises :class:`AttestationError` (nothing recorded) for an invalid request, an
    unreadable status log, or a work package whose earlier attestation its lane has moved
    past (:func:`_refuse_moved_reattestations`). An empty request returns an empty mapping
    without reading.
    """
    requested = tuple(wp_ids)
    if not requested:
        return {}
    try:
        events = read_events(feature_dir)
        work_packages = materialize_snapshot(feature_dir).work_packages or {}
    except StoreError as exc:
        raise AttestationError(f"{ATTEST_APPROVED_FLAG} could not read the status log: {exc}. {_NOTHING_RECORDED}") from exc
    claim_lanes = approved_claim_lanes(work_packages, lanes_manifest, excluded_canceled_wp_ids)
    validated = validate_approved_attestation_request(requested, reason, events=events, claim_lanes=claim_lanes)
    _refuse_moved_reattestations(
        repo_root, feature_dir, lanes_manifest, validated, events=events, work_packages=work_packages, excluded_canceled_wp_ids=frozenset(excluded_canceled_wp_ids)
    )
    return {wp_id: claim_lanes[wp_id] for wp_id in validated}


def _refuse_moved_reattestations(
    repo_root: Path,
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    wp_ids: Iterable[str],
    *,
    events: Sequence[StatusEvent],
    work_packages: Mapping[str, Mapping[str, object]],
    excluded_canceled_wp_ids: frozenset[str],
) -> None:
    """Raise :class:`AttestationError` when a work package to re-attest has a lane beyond its earlier attestation.

    A work package is re-attested when its newest approval is a STAMPED attestation (an
    unstamped one bounded nothing, so attesting it is the ordinary first attestation). Its
    lane is run through :func:`~specify_cli.consolidation.approved_bound.check_lane` over
    every stamped approval of that lane, so the earlier attestation's ``lane_head`` bounds
    it exactly as the claim reads it: a commit of a canceled work package of the lane made
    after the earlier attestation counts like any other (#5720). Any lane refusal (commits
    after the stamp, or a stamp that is no longer on the lane), or a lane that cannot be
    read, refuses the request.
    """
    reattested = frozenset(wp_id for wp_id in wp_ids if approval_is_attested(events, wp_id) and approval_stamp(events, wp_id) is not None)
    if not reattested:
        return
    is_bookkeeping = functools.partial(_is_bookkeeping, mission_slug=lanes_manifest.mission_slug, planning_prefix=_planning_prefix(repo_root, feature_dir))
    lanes = _bound_lanes(lanes_manifest, work_packages, excluded_canceled_wp_ids)
    stamp_anchors = approval_stamp_anchors(events, lanes, work_packages, excluded_canceled_wp_ids)
    for lane in lanes:
        approved = _bound_approved_wp_ids(lane, work_packages, excluded_canceled_wp_ids)
        hit = sorted(reattested.intersection(approved))
        if not hit:
            continue
        branch = _lane_branch_for(lanes_manifest, lane.lane_id)
        try:
            refusal = check_lane(
                repo_root,
                events=events,
                lane_id=lane.lane_id,
                branch=branch,
                approved_wp_ids=[wp_id for wp_id in approved if approval_stamp(events, wp_id) is not None],
                claim_base=resolve_commit(repo_root, lanes_manifest.target_branch),
                anchors=[*_closed_world_anchors(lanes_manifest, lane, None, excluded_canceled_wp_ids=excluded_canceled_wp_ids), *stamp_anchors],
                is_bookkeeping=is_bookkeeping,
            )
        except GitProbeError as exc:
            raise AttestationError(
                f"{ATTEST_APPROVED_FLAG} could not read lane {lane.lane_id} to check the earlier attestation of {', '.join(hit)}: {exc}. {_NOTHING_RECORDED}"
            ) from exc
        if refusal is not None:
            raise AttestationError(
                f"{ATTEST_APPROVED_FLAG} cannot be repeated for {', '.join(hit)}: lane {lane.lane_id} (branch '{branch}') "
                f"moved past the earlier attestation, so its new content would otherwise read as approved. "
                f"Move {hit[0]} back for review ({move_back_command(hit[0], lanes_manifest.mission_slug)}) so the new content is reviewed, "
                f"approve it again, then re-run spec-kitty consolidate. {_NOTHING_RECORDED}"
            )


def record_approved_reviewed_attestation(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    current_lane: str,
    reason: str,
    actor: str,
) -> StatusEvent | None:
    """Append ONE attestation for *wp_id* through the canonical transactional seam.

    *feature_dir* is the PRIMARY, meta-bearing mission dir (the transactional shell
    resolves and commits to the coordination branch itself). *current_lane* is the work
    package's lane now: the transition is forced from it to itself. Returns the persisted
    event (``None`` only for the seam's alias-collapse no-op arm).
    """
    from specify_cli.coordination.status_transition import emit_status_transition_transactional

    request = TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        to_lane=Lane(current_lane),
        actor=actor,
        repo_root=repo_root,
        force=True,
        reason=f"{_REASON_PREFIX}{reason.strip()}",
        reason_source=OPERATOR_REASON_SOURCE,
        evidence={"review": {"reviewer": actor, "verdict": "approved", "reference": f"{_REFERENCE_PREFIX}{wp_id}"}},
        policy_metadata={ATTESTATION_KEY: APPROVED_REVIEWED},
    )
    return emit_status_transition_transactional(request)


__all__ = [
    "plan_approved_attestations",
    "record_approved_reviewed_attestation",
]
