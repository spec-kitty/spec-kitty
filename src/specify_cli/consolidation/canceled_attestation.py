"""Operator-attested override for an unresolvable mixed lane (FR-012, #5046).

A mixed-lane REFUSE from attribution evidence (a missing stamp, a window that
never closed, a rewritten history, a contested commit, a commit outside every
window) can never clear on its own: the event log is append-only, so the
evidence cannot appear later. ``spec-kitty consolidate
--attest-canceled-superseded <WP> --attest-reason "<text>"`` lets the operator
state, after checking by hand, that the canceled WP's content is absent or
superseded. The gate then lifts that WP's attribution-evidence REFUSEs and
exempts the lane commits up to the attestation's own ``lane_head`` stamp from
the closed-world check (operator decision
``01M3NR7QRXJBZXQR1B91XKY3JQ``).

**Record shape — no event-schema change (C-001), one authority (C-002).** The
attestation is a forced ``canceled -> canceled`` lane transition of the
canceled WP, appended through the canonical transactional status seam
(:func:`specify_cli.coordination.status_transition.emit_status_transition_transactional`),
never hand-written. It carries:

* ``actor`` — the operator identity (the merge-time actor resolver);
* ``reason`` — the operator's ``--attest-reason`` text (a forced transition
  requires actor and reason, so both are enforced by the FSM itself);
* ``reason_source = "operator"`` — keeps the WP an acceptable, operator-provenance
  ending (``status_lanes.has_operator_provenance``);
* ``at`` — the seam's own timestamp;
* ``policy_metadata[ATTESTATION_KEY] = CANCELED_SUPERSEDED`` — the machine
  marker, in the CLI-local ``policy_metadata`` sidecar that already carries the
  ``lane_head`` stamp (the external ``StatusTransitionPayload`` never carries it).

The gate reads it back from the same event log it already reads for
attribution (:func:`attestation_stamps`); the latest attestation of a WP wins, so
each re-attestation advances the stamp. An attestation is valid only
while the WP stays in the same canceled stint: any later governed transition of
that WP (reopened, re-canceled) voids it. Migration-synthesized events
(``wp_attribution.MIGRATION_ACTOR_PREFIX``, FR-011) never void it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path

from specify_cli.status import LANE_HEAD_KEY, Lane, StatusEvent, TransitionRequest, actor_identity_str
from specify_cli.status_lanes import OPERATOR_REASON_SOURCE

from .wp_attribution import MIGRATION_ACTOR_PREFIX, UnattributableReason

#: ``policy_metadata`` key of the attestation marker.
ATTESTATION_KEY = "attestation"
#: ``policy_metadata[ATTESTATION_KEY]`` value: the canceled WP's content is
#: absent or superseded, verified by hand by the operator.
CANCELED_SUPERSEDED = "canceled_superseded"
#: The CLI flags, named in every REFUSE message that the override can lift.
ATTEST_FLAG = "--attest-canceled-superseded"
ATTEST_REASON_FLAG = "--attest-reason"
#: Attribution-evidence reasons an attestation lifts (FR-012). The evidence can
#: never appear later, so only the operator can resolve them. NOT here:
#: ``EVENTS_UNREADABLE`` / ``SPINE_UNREADABLE`` (infrastructure — repair, never
#: override), ``CANCELED_LANE_CONTENT`` (a fully-canceled lane's inherited
#: commits: no anchor may exempt them, #5569) and ``COMMIT_OUTSIDE_WINDOWS``: for the closed world the
#: attestation is bounded in time instead — its ``lane_head`` stamp becomes an
#: anchor, so only commits made up to the attestation are exempt. The
#: verify-time "merged with an independent change" REFUSE is lifted in
#: ``reconciliation`` by WP id; a canceled-content FAIL never is.
#:
#: This set is also the authority for a fully-canceled DEPENDENCY lane (#5613):
#: ``NO_STAMP`` being listed is what lets an attestation lift the up-front
#: refusal of an unstamped canceled WP whose commits an approved lane carries.
#: It lifts that refusal only, per attested WP. No commit of the lane becomes
#: approved authorship through it, so content still live on the carrying lane
#: FAILs with ``CANCELED_REACHABLE_VIA_DEPENDENCY`` exactly as for a stamped WP.
OVERRIDABLE_REASONS: frozenset[UnattributableReason] = frozenset(
    {
        UnattributableReason.NO_STAMP,
        UnattributableReason.OPEN_WINDOW,
        UnattributableReason.STAMP_NOT_ANCESTOR_OF_LANE_TIP,
        UnattributableReason.CONTESTED_COMMIT,
    }
)
#: Prefix of the recorded ``reason`` so the snapshot's cancellation reason says what it is.
_REASON_PREFIX = "operator attests canceled content absent or superseded: "


class AttestationError(ValueError):
    """An attestation request that cannot be recorded (operator-facing message)."""


def is_canceled_superseded_attestation(event: StatusEvent) -> bool:
    """True iff *event* is a valid FR-012 attestation record (see module docstring)."""
    metadata = event.policy_metadata or {}
    return (
        str(event.from_lane) == Lane.CANCELED
        and str(event.to_lane) == Lane.CANCELED
        and event.reason_source == OPERATOR_REASON_SOURCE
        and metadata.get(ATTESTATION_KEY) == CANCELED_SUPERSEDED
        and not actor_identity_str(event.actor).startswith(MIGRATION_ACTOR_PREFIX)
    )


def attestation_stamps(events: Sequence[StatusEvent]) -> dict[str, str | None]:
    """Still-valid attestations, from events in append order: WP id -> its ``lane_head`` stamp.

    A later non-migration transition of the same WP (reopened, re-canceled)
    voids the attestation: it covered the canceled stint the operator checked.
    The stamp (the lane head when the attestation was recorded) bounds the
    closed-world exemption in time: only lane commits reachable from it are
    covered; a straggler committed afterwards is still checked. ``None`` when
    no stamp could be taken — then nothing is exempted from the closed world.
    """
    attested: dict[str, str | None] = {}
    for event in events:
        if is_canceled_superseded_attestation(event):
            stamp = (event.policy_metadata or {}).get(LANE_HEAD_KEY)
            attested[event.wp_id] = stamp if isinstance(stamp, str) and stamp else None
        elif event.wp_id in attested and not actor_identity_str(event.actor).startswith(MIGRATION_ACTOR_PREFIX):
            del attested[event.wp_id]
    return attested


def validate_attestation_request(
    wp_ids: Iterable[str],
    reason: str | None,
    *,
    acceptably_canceled: frozenset[str],
) -> tuple[str, ...]:
    """Return the de-duplicated WP ids to attest, or raise :class:`AttestationError`.

    The reason is required and non-blank; every WP must be canceled with
    operator provenance (the merge-side acceptable-cancel authority) — an
    attestation for any other WP would override nothing and is refused.
    """
    requested = tuple(dict.fromkeys(wp_ids))
    if not requested:
        return ()
    if not (reason and reason.strip()):
        raise AttestationError(f'{ATTEST_FLAG} requires {ATTEST_REASON_FLAG} "<why the canceled content is absent or superseded>".')
    not_canceled = [wp_id for wp_id in requested if wp_id not in acceptably_canceled]
    if not_canceled:
        raise AttestationError(
            f"{ATTEST_FLAG} applies only to a WP canceled with operator provenance; not canceled: {', '.join(not_canceled)}. Nothing was recorded."
        )
    return requested


def record_canceled_superseded_attestation(
    *,
    repo_root: Path,
    feature_dir: Path,
    mission_slug: str,
    wp_id: str,
    reason: str,
    actor: str,
) -> StatusEvent | None:
    """Append ONE attestation for *wp_id* through the canonical transactional seam.

    *feature_dir* is the PRIMARY, meta-bearing mission dir (the transactional
    shell resolves and commits to the coordination branch itself). Returns the
    persisted event (``None`` only for the seam's alias-collapse no-op arm).
    """
    from specify_cli.coordination.status_transition import emit_status_transition_transactional

    request = TransitionRequest(
        feature_dir=feature_dir,
        mission_slug=mission_slug,
        wp_id=wp_id,
        to_lane=Lane.CANCELED,
        actor=actor,
        repo_root=repo_root,
        force=True,
        reason=f"{_REASON_PREFIX}{reason.strip()}",
        reason_source=OPERATOR_REASON_SOURCE,
        policy_metadata={ATTESTATION_KEY: CANCELED_SUPERSEDED},
    )
    return emit_status_transition_transactional(request)


__all__ = [
    "ATTEST_FLAG",
    "ATTEST_REASON_FLAG",
    "OVERRIDABLE_REASONS",
    "AttestationError",
    "attestation_stamps",
    "record_canceled_superseded_attestation",
    "validate_attestation_request",
]
