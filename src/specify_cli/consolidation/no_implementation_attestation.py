"""Operator attestation that an approved work package owes no implementation (#6715).

The implementation-evidence axis (:mod:`specify_cli.consolidation.wp_evidence`) refuses an approved
work package whose evidence window holds no change to its ``owned_files``
(``IMPLEMENTATION_MISSING``). Some work packages legitimately owe none: the deliverable already
exists, or it landed elsewhere. ``--attest-no-implementation <WP> --attest-reason "<why>"`` (on
``spec-kitty consolidate``, and on ``spec-kitty accept``) records why, and the axis then lifts
that one code for that one work package.

**What it never does.** It lifts no other refusal: ``REVIEW_NOT_INDEPENDENT``,
``IMPLEMENTATION_UNREADABLE`` and ``EVIDENCE_WINDOW_UNCOMPUTABLE`` stand (only ``wp_evidence``
reads the record, and only for ``IMPLEMENTATION_MISSING``). It is never a review: the #5939
independence comparison skips it when it looks for the approving actor
(``preflight._latest_actor_for_transition``), it is not an approval for the approval bound
(``approved_bound._is_approval`` reads a forced move outside ``in_review`` as no approval), and
the hollow-review force count discounts it (``preflight._review_force_counts``).

**Record shape -- no event-schema change, one authority.** Like the other operator attestations
(:mod:`~specify_cli.consolidation.approved_attestation`,
:mod:`~specify_cli.consolidation.canceled_attestation`), it is a forced operator transition
appended through the canonical transactional status seam, from and to the work package's CURRENT
lane (``approved``, or ``done`` after an interrupted run), with ``reason_source = "operator"`` and
``policy_metadata["attestation"] = "no_implementation"``. The events contract requires evidence
for a transition into ``approved`` or ``done``; it names the operator and the attestation as the
reference. Every request records a fresh attestation (a new operator act with its own reason).

**Scope -- it speaks about the current approval only.** An attestation counts only while the work
package has stayed in ``{approved, done}`` since it was recorded (operator ruling 2026-10-27). A
later non-migration transition to any other lane (a reopen, a rejection, a re-claim) voids it, so
a re-approval needs a fresh attestation. Consolidate's own ``approved -> done``, forced
self-transitions and a resume keep it. The log is read in append order. The one reader is
:func:`~specify_cli.consolidation.wp_evidence.in_force_no_implementation_attestation`;
:func:`_attested_reason` cites only the attestation it returns.

**Atomicity residual.** Every request is validated before any is recorded, but the records are
separate appends: if a later write fails (a seam refusal or an I/O error), the attestations
recorded before it stay recorded. An attestation recorded before a claim that then refuses for
another reason (for example ``REVIEW_NOT_INDEPENDENT``) also stays, by design, and is honoured by
the next run while the work package stays approved. This matches the other operator attestations.

The public functions here carry no CLI dependency, so ``consolidate`` and ``accept`` share them:
:func:`plan_no_implementation_attestations` validates a request against the status log (nothing is
recorded on a refusal) and :func:`record_no_implementation_attestation` records one.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from specify_cli.lanes.models import LanesManifest
from specify_cli.status import Lane, StatusEvent, StoreError, TransitionRequest, materialize_snapshot
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

from .canceled_attestation import ATTEST_REASON_FLAG, ATTESTATION_KEY, AttestationError
from .wp_evidence import ATTEST_NO_IMPLEMENTATION_FLAG, IMPLEMENTATION_MISSING, NO_IMPLEMENTATION, in_force_no_implementation_attestation

#: Prefix of the recorded ``reason`` so the status log says what the operator attested.
_REASON_PREFIX = "operator attests no implementation is owed: "
#: Evidence ``review.reference`` prefix: the attestation, not a review, is the reference.
_REFERENCE_PREFIX = "operator-attestation:"
_NOTHING_RECORDED = "Nothing was recorded."


def is_no_implementation_attestation(policy_metadata: Mapping[str, object] | None) -> bool:
    """True iff *policy_metadata* marks a no-implementation attestation."""
    return bool(policy_metadata) and (policy_metadata or {}).get(ATTESTATION_KEY) == NO_IMPLEMENTATION


def _validate_no_implementation_request(wp_ids: Iterable[str], reason: str | None, *, claim_lanes: Mapping[str, str]) -> tuple[str, ...]:
    """Return the de-duplicated work package ids to attest, or raise :class:`AttestationError`.

    *claim_lanes* maps each work package of the approved claim to its current lane (``approved``
    or ``done``). The reason is required and non-blank, and every work package must be in the claim.
    """
    requested = tuple(dict.fromkeys(wp_ids))
    if not requested:
        return ()
    if not (reason and reason.strip()):
        raise AttestationError(f'{ATTEST_NO_IMPLEMENTATION_FLAG} requires {ATTEST_REASON_FLAG} "<why no implementation is owed>". {_NOTHING_RECORDED}')
    not_approved = [wp_id for wp_id in requested if wp_id not in claim_lanes]
    if not_approved:
        raise AttestationError(
            f"{ATTEST_NO_IMPLEMENTATION_FLAG} applies only to an approved work package; not approved: {', '.join(not_approved)}. {_NOTHING_RECORDED}"
        )
    return requested


def plan_no_implementation_attestations(
    feature_dir: Path,
    lanes_manifest: LanesManifest,
    wp_ids: Iterable[str],
    reason: str | None,
    *,
    excluded_canceled_wp_ids: Iterable[str],
) -> dict[str, str]:
    """Validate the request against the status snapshot: work package id -> current lane, in request order.

    *feature_dir* is the status-bearing mission dir. Raises :class:`AttestationError` (nothing
    recorded) for an invalid request or an unreadable status log. An empty request returns an
    empty mapping without reading.
    """
    from .approved_attestation import approved_claim_lanes

    requested = tuple(wp_ids)
    if not requested:
        return {}
    try:
        work_packages = materialize_snapshot(feature_dir).work_packages or {}
    except StoreError as exc:
        raise AttestationError(f"{ATTEST_NO_IMPLEMENTATION_FLAG} could not read the status log: {exc}. {_NOTHING_RECORDED}") from exc
    claim_lanes = approved_claim_lanes(work_packages, lanes_manifest, excluded_canceled_wp_ids)
    validated = _validate_no_implementation_request(requested, reason, claim_lanes=claim_lanes)
    return {wp_id: claim_lanes[wp_id] for wp_id in validated}


def record_no_implementation_attestation(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    current_lane: str,
    reason: str,
    actor: str,
) -> StatusEvent | None:
    """Append ONE no-implementation attestation for *wp_id* through the canonical transactional seam.

    *feature_dir* is the PRIMARY, meta-bearing mission dir (the transactional shell resolves and
    commits to the coordination branch itself). *current_lane* is the work package's lane now:
    the transition is forced from it to itself. Returns the persisted event (``None`` only for the
    seam's alias-collapse no-op arm).
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
        policy_metadata={ATTESTATION_KEY: NO_IMPLEMENTATION},
    )
    return emit_status_transition_transactional(request)


def _attested_reason(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """The reason of *wp_id*'s no-implementation attestation IN FORCE (prefix stripped), or ``None``.

    Scoped by the one reader (:func:`~specify_cli.consolidation.wp_evidence.in_force_no_implementation_attestation`),
    so a voided attestation (the work package left ``{approved, done}`` after it) is never cited.
    """
    event = in_force_no_implementation_attestation(events, wp_id)
    if event is None:
        return None
    return (event.reason or "").removeprefix(_REASON_PREFIX).strip()


def lifted_notices(events: Sequence[StatusEvent], wp_ids: Iterable[str]) -> list[str]:
    """One line per work package whose ``IMPLEMENTATION_MISSING`` an attestation lifted, sorted by id."""
    return [f"⚠️  {wp_id}: {IMPLEMENTATION_MISSING} lifted by operator attestation ({_attested_reason(events, wp_id) or ''})" for wp_id in sorted(wp_ids)]


__all__ = [
    "is_no_implementation_attestation",
    "lifted_notices",
    "plan_no_implementation_attestations",
    "record_no_implementation_attestation",
]
