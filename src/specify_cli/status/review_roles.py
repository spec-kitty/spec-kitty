"""Pure latest-implementer projection for the move-task ownership guard.

Mission ``rework-is-not-an-override`` (#5196). The ownership guard compares the
slot occupant's *tool* with the requester's. After a review rejection the slot
holds the reviewer, so the implementer's ordinary rework resume (and the
reviewer's next claim) looked like an ownership conflict. The guard resolves
"who is the WP's latest implementer" from this projection instead of the slot.

This module is the single implementer-of-record authority: the ownership guard
and the consolidation hollow-review check both read it
(:func:`latest_implementer_event` is the one scan; :func:`latest_implementer_actor`
projects its actor). The reducer's ``implementer_of_record`` snapshot slot is
claim provenance (the ``planned -> claimed`` claimant), not an implementer
authority; do not read it to decide who implemented a WP. (#5340)

A migration seed (#6257) is never an implementing claim: its actor is a migration
identity, never a person, so a work package whose only implementing events are
seeds has no implementer authority and the guards fail closed.

This is a pure leaf: it performs no I/O and reads only the events it is given
(precedent: :mod:`specify_cli.status.review_claim_predicate`). Contract:
``kitty-specs/rework-is-not-an-override-01M3MQV6/contracts/ownership-role-allowance.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from specify_cli.status.actor import ActorRole
from specify_cli.status.models import (
    Lane,
    StatusEvent,
    actor_full_identity,
    actor_identities_independent,
    actor_identity_str,
    is_migration_actor,
    refine_actor_identity,
)
from specify_cli.status.work_package_lifecycle import GENERIC_IMPLEMENTATION_ACTORS, _actor_key

__all__ = [
    "implementer_identities",
    "IMPLEMENTER_RESUBMISSION_ROLE",
    "implementer_claim_target",
    "independent_of_implementers",
    "is_implementer_resubmission_hop",
    "is_latest_implementer",
    "latest_implementer_actor",
    "latest_implementer_event",
    "latest_implementer_identity",
    "latest_review_claimant",
    "profileless_claim_warning",
    "profileless_identity_warning",
    "resubmitter_may_be_implementer",
]

#: The actor role an ``in_review -> for_review`` re-submission records when the implementer
#: asserts it explicitly (``move-task --as-implementer``, #7712).
IMPLEMENTER_RESUBMISSION_ROLE: str = str(ActorRole.IMPLEMENTER)
_IMPLEMENTING_LANES: frozenset[str] = frozenset({Lane.CLAIMED.value, Lane.IN_PROGRESS.value})
_REVIEWER_SOURCE_LANES: frozenset[str] = frozenset({Lane.FOR_REVIEW.value, Lane.IN_REVIEW.value, Lane.APPROVED.value})


def _is_reviewer_rework_verdict(event: StatusEvent) -> bool:
    """A reviewer rework verdict: leaves a review lane with a ``review_ref`` set.

    Sibling predicate — keep in lockstep: ``review.arbiter._is_rejection_event``
    encodes the same "a reviewer verdict happened" concept for the arbiter-override
    check and so uses a deliberately NARROWER lane set (``to == planned`` only,
    sources ``for_review``/``in_review``). A future change to "what counts as a
    reviewer verdict" must be weighed against both. (#5196)
    The retrospective and hollow-review signal reads a third variant:
    ``review.rejection_signal.is_documented_review_rejection`` (#2267).

    The operator-rewind sentinel (``force-override``) is NOT a reviewer verdict
    (#6955): it means "an operator forced this rewind", so the actor *is* the
    implementer of record for the rework that follows. Reading it as a reviewer
    verdict made a forced ``approved -> in_progress`` reopen invisible to this
    projection, which in turn made a later approval by the same actor look like an
    independent review. The review-claim markers in the same sentinel set stay
    counted -- they are reviewer acts (``test_review_roles`` pins the legacy
    review-claim case).
    """
    from specify_cli.review.cycle import is_operator_rewind_sentinel

    if is_operator_rewind_sentinel(event.review_ref):
        return False
    return Lane(event.from_lane).value in _REVIEWER_SOURCE_LANES and bool(event.review_ref)


def _qualifies(event: StatusEvent) -> bool:
    """Whether ``event`` is an implementing claim by a real, non-generic actor.

    A migration seed (:func:`is_migration_actor`, #6257) never qualifies, however
    it is shaped: it restates history and is not governed work.
    """
    if is_migration_actor(event.actor):
        return False
    if Lane(event.to_lane).value not in _IMPLEMENTING_LANES:
        return False
    if _is_reviewer_rework_verdict(event):
        return False
    return _actor_key(event.actor) not in GENERIC_IMPLEMENTATION_ACTORS


def latest_implementer_event(events: Sequence[StatusEvent], wp_id: str) -> StatusEvent | None:
    """Return ``wp_id``'s latest qualifying implementing claim event, or ``None``.

    Scans newest-first (append order) for the first event into
    ``claimed``/``in_progress`` that is neither a reviewer rework verdict, nor
    made by a generic placeholder actor, nor a migration seed (#6257). Callers needing the full recorded
    identity (not the tool-scoped key) read it from the returned event.
    """
    for event in reversed(events):
        if event.wp_id == wp_id and _qualifies(event):
            return event
    return None


def _submission_actor_ok(event: StatusEvent) -> bool:
    """A real, non-generic, non-seed actor: the only kind whose identity may refine the record."""
    if is_migration_actor(event.actor):
        return False
    key = _actor_key(event.actor)
    return key is not None and key not in GENERIC_IMPLEMENTATION_ACTORS


def _recorded_role(actor: object) -> str | None:
    """The role a structured actor recorded, or ``None``.

    Only a structured (dict) actor counts: ``move-task`` writes one, and a compact string's
    role segment is discarded by every writer (ruling 1), so an older log's fourth segment
    never asserts an implementer act retroactively (#7712).
    """
    if not isinstance(actor, dict):
        return None
    role = actor.get("role")
    return str(role).strip() or None if role else None


def resubmitter_may_be_implementer(review_claimant: str | None, resubmitter: str | None) -> bool:
    """Whether an ``--as-implementer`` re-submission may be the implementer's act, given the review claim (#7712).

    ``False`` when the review claim recorded a model or profile and *resubmitter* is not
    provably another identity (ruling 7): the reviewer handing its own review back must not
    complete the implementer's identity with its own. A bare or unknown review claimant
    proves nothing either way, so the explicit assertion stands.
    """
    if not _records_more_than_tool(review_claimant):
        return True
    independent: bool = actor_identities_independent(review_claimant, resubmitter)
    return independent


def _is_implementer_submission(event: StatusEvent) -> bool:
    """A hand-over into ``for_review`` whose identity refines the implementer of record (#7159, #7712).

    Two hops qualify, each by a real, non-generic actor:

    * an unforced ``in_progress -> for_review`` submission (#7159); a forced one never does;
    * an ``in_review -> for_review`` re-submission whose actor is recorded with role
      ``implementer`` (#7712): the explicit act ``move-task --to for_review --as-implementer``.
      The hop's role is otherwise ``reviewer`` (``role_for_hop``): a reviewer handing a review
      back must never fill a bare claim with its own profile, which would make the real
      implementer look independent of it.
    """
    hop = (Lane(event.from_lane).value, Lane(event.to_lane).value)
    if hop == (Lane.IN_PROGRESS.value, Lane.FOR_REVIEW.value):
        return not event.force and _submission_actor_ok(event)
    if hop == (Lane.IN_REVIEW.value, Lane.FOR_REVIEW.value):
        return _recorded_role(event.actor) == IMPLEMENTER_RESUBMISSION_ROLE and _submission_actor_ok(event)
    return False


def is_implementer_resubmission_hop(from_lane: str | Lane | None, to_lane: str | Lane) -> bool:
    """Whether ``from_lane -> to_lane`` is the ``in_review -> for_review`` hop ``--as-implementer`` applies to (#7712)."""
    if from_lane is None:
        return False
    try:
        return (Lane(str(from_lane)), Lane(str(to_lane))) == (Lane.IN_REVIEW, Lane.FOR_REVIEW)
    except ValueError:
        return False


def _is_new_claim_cycle(event: StatusEvent) -> bool:
    """An unforced ``planned -> claimed``: the one explicit, recorded act that names a new implementer of record."""
    return not event.force and (Lane(event.from_lane).value, Lane(event.to_lane).value) == (Lane.PLANNED.value, Lane.CLAIMED.value)


def _is_placeholder_new_cycle(event: StatusEvent) -> bool:
    """An unforced ``planned -> claimed`` by a placeholder actor: a new cycle whose implementer is not yet known."""
    if not _is_new_claim_cycle(event) or is_migration_actor(event.actor):
        return False
    key = _actor_key(event.actor)
    return key is None or key in GENERIC_IMPLEMENTATION_ACTORS


def _adds_nothing(record: str, identity: str) -> bool:
    """Whether *identity* is the record or a less specific spelling of it (not independent, refines nothing)."""
    return not actor_identities_independent(record, identity) and refine_actor_identity(record, identity) == record


def _is_review_claim(event: StatusEvent) -> bool:
    """A move into ``in_review``: its actor is the review claimant."""
    return Lane(event.to_lane).value == Lane.IN_REVIEW.value and _submission_actor_ok(event)


def _records_more_than_tool(identity: str | None) -> bool:
    """Whether *identity* recorded a model or profile beside its tool."""
    if not identity:
        return False
    _tool, _, rest = identity.partition(":")
    return bool(rest.strip(":"))


def _review_claimant_may_be_record(record: str, review_claimant: str | None) -> bool:
    """Whether the cycle's review claimant, under a recorded model or profile, may be the implementer of record (#7712).

    A profiled review claimant not provably independent of the record (``claude::rev`` beside a
    bare ``claude`` claim) may hold the record itself: an ``--as-implementer`` re-submission that
    completed the record would then only make that claimant look independent of its own work,
    since the identity a re-submission declares is self-asserted. A bare review claimant
    proves nothing either way, so the explicit assertion stands for it.
    """
    return _records_more_than_tool(review_claimant) and not actor_identities_independent(record, review_claimant)


def _submission_may_refine(event: StatusEvent, submitter: str | None, others: Sequence[str], review_claimant: str | None, record: str) -> bool:
    """Whether a submission's identity may complete the implementer of record (#7712).

    Never when the submitter is not provably independent of an identity kept beside the record
    (whoever forced a rewind or took over must not fill the original claim with its own
    identity), nor, for an ``--as-implementer`` re-submission, when it may be the review claimant
    or the review claimant may be the implementer of record.
    """
    if any(not actor_identities_independent(other, submitter) for other in others):
        return False
    if Lane(event.from_lane).value == Lane.IN_REVIEW.value:
        if _review_claimant_may_be_record(record, review_claimant):
            return False
        return resubmitter_may_be_implementer(review_claimant, submitter)
    return True


def latest_review_claimant(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """Full identity of ``wp_id``'s latest review claim (a move into ``in_review``), or ``None``."""
    for event in reversed(events):
        if event.wp_id == wp_id and _is_review_claim(event):
            claimant: str | None = actor_full_identity(event.actor)
            return claimant
    return None


def implementer_identities(events: Sequence[StatusEvent], wp_id: str) -> tuple[str, ...]:
    """Every identity that implemented ``wp_id`` in its current claim cycle, implementer of record first (#7712).

    One forward pass over the work package's qualifying claims into ``claimed``/``in_progress``
    (:func:`_qualifies`) and its submissions into ``for_review`` (:func:`_is_implementer_submission`):

    * an unforced ``planned -> claimed`` claim starts a new cycle: its identity is the
      implementer of record and nobody else has implemented yet;
    * with no record yet, a claim is the record;
    * an unforced claim that agrees with the record (not provably independent of it, ruling 7),
      such as the claim's own ``claimed -> in_progress`` hop or a resume, refines it (fill only);
    * every other claim, forced or by another identity (a forced rewind, a takeover, an
      unblock), never changes the record: its identity is kept beside it as a further
      implementer, since whoever moved the work package into an implementing lane may have
      reworked it (#6955);
    * an unforced ``planned -> claimed`` by a placeholder actor starts a new cycle whose first
      unforced real claim names the implementer of record; until then the previous record stands;
    * a claim whose identity adds nothing to the record (the record itself, or a less specific
      spelling of it, such as the implementer's own forced pull-back) changes nothing;
    * a submission refines the record (#7159), unless its submitter may be an identity kept
      beside the record or, for an ``--as-implementer`` re-submission, the review claimant, or
      the review claimant may itself be the implementer of record (not provably independent of it).

    An approval must be independent of every identity returned
    (:func:`independent_of_implementers`). Empty when no qualifying claim exists.
    """
    record: str | None = None
    others: list[str] = []
    review_claimant: str | None = None
    cycle_pending = False
    for event in events:
        if event.wp_id != wp_id:
            continue
        if _is_placeholder_new_cycle(event):
            # The previous record stands until a real actor claims (#7712): emptying the set
            # would leave move-task with no implementer and accept with nobody to be independent of.
            cycle_pending = True
        elif _qualifies(event):
            identity = actor_full_identity(event.actor)
            if identity is None:
                continue
            if record is None or _is_new_claim_cycle(event) or (cycle_pending and not event.force):
                record, others, cycle_pending = identity, [], False
            elif _adds_nothing(record, identity):
                continue  # the recorded implementer moving its own work back: nothing new
            elif not event.force and not actor_identities_independent(record, identity):
                record = refine_actor_identity(record, identity)
            elif identity not in others:
                others.append(identity)
        elif _is_review_claim(event):
            review_claimant = actor_full_identity(event.actor)
        elif record is not None and _is_implementer_submission(event):
            submitter = actor_full_identity(event.actor)
            if _submission_may_refine(event, submitter, others, review_claimant, record):
                record = refine_actor_identity(record, submitter)
    if record is None:
        return ()
    return (record, *(other for other in others if other != record))


def latest_implementer_identity(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """Full ``tool:model:profile`` identity of ``wp_id``'s implementer of record, or ``None``.

    The identity of the claim that opened the work package's claim cycle, refined by every
    later submission into ``for_review`` (operator ruling on #7159; an explicit
    ``--as-implementer`` re-submission out of ``in_review`` since #7712) and by the claim's own
    unforced hops: a hop by the claim's tool fills the model or profile the claim did not
    record, and is ignored when it contradicts one. A forced claim or another identity's claim
    never replaces the implementer of record (#7712). A bare ``claude`` claim followed
    by a ``claude:<model>:implementer-ivan`` submission is therefore that full identity, while
    a ``claude::python-pedro`` claim keeps its profile whoever submits. The first element of
    :func:`implementer_identities`.
    """
    identities = implementer_identities(events, wp_id)
    return identities[0] if identities else None


#: The implementing lanes, in the order a repair should reach for them: a claim first.
_IMPLEMENTING_TARGETS: tuple[Lane, ...] = (Lane.CLAIMED, Lane.IN_PROGRESS)


def implementer_claim_target(lane: str | Lane) -> Lane | None:
    """The implementing lane a work package in *lane* can move into as an implementing claim, or ``None`` (#5781).

    Derived from the state machine: a target in ``wp_state_for(lane).allowed_targets()``
    among ``claimed`` / ``in_progress``, reached from a lane this projection does not read
    as a reviewer verdict (an exit from ``for_review`` / ``in_review`` / ``approved`` needs a
    ``review_ref`` and is a rework verdict, never a claim, :func:`_is_reviewer_rework_verdict`).
    ``None`` when no such move exists: ``in_progress`` (already implementing), the review
    lanes, and the terminal ``done`` / ``canceled``. The accept gate names a repair only when
    this returns a lane.
    """
    from specify_cli.status.transitions import resolve_lane_alias
    from specify_cli.status.wp_state import wp_state_for

    source = Lane(resolve_lane_alias(str(lane)))
    if source.value in _REVIEWER_SOURCE_LANES:
        return None
    allowed = wp_state_for(source).allowed_targets()
    return next((target for target in _IMPLEMENTING_TARGETS if target in allowed), None)


def independent_of_implementers(implementers: Sequence[str], approver: str | None) -> bool:
    """True only when *approver* is provably independent of every implementer identity (#6715 R1, #7712).

    *implementers* is :func:`implementer_identities`. No known implementer is independent of
    nothing, as :func:`~specify_cli.status.actor_identities_independent` treats an unknown identity.
    """
    return bool(implementers) and all(actor_identities_independent(implementer, approver) for implementer in implementers)


def profileless_claim_warning(event: StatusEvent | None) -> str | None:
    """The claim-time warning for a claim that recorded neither a profile nor a model (#7712).

    ``None`` unless *event* is a qualifying claim (:func:`_qualifies`); otherwise
    :func:`profileless_identity_warning` of its actor.
    """
    if event is None or not _qualifies(event):
        return None
    return profileless_identity_warning(event.wp_id, event.actor)


def profileless_identity_warning(wp_id: str, actor: object) -> str | None:
    """The warning for an implementer identity that is the tool alone, or ``None`` (#7712).

    Such an implementer is provably independent of no other identity of its tool (ruling R1),
    so ``accept`` and ``consolidate`` refuse every same-tool approval. The line names that
    refusal and the remedy. A placeholder or a migration seed names no implementer and gets none.
    """
    key = _actor_key(actor)
    if key is None or key in GENERIC_IMPLEMENTATION_ACTORS or is_migration_actor(actor):
        return None
    identity = actor_full_identity(actor)
    if identity is None or identity.count(":") != 2:
        return None
    tool, model, profile = identity.split(":")
    if not tool or model or profile:
        return None
    return (
        f"Warning: {wp_id} was claimed as '{tool}' with no profile or model recorded, so `spec-kitty accept` and "
        f"`spec-kitty consolidate` will refuse an approval by another '{tool}' identity with REVIEW_NOT_INDEPENDENT "
        "(SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT on a single_branch Mission). Record your identity: claim with "
        f"--agent {tool}:<model>:<profile> (or --profile <profile>), or submit with "
        f"`spec-kitty agent tasks move-task {wp_id} --to for_review --agent {tool}::<profile>`."
    )


def latest_implementer_actor(events: Sequence[StatusEvent], wp_id: str) -> str | None:
    """Return the actor of ``wp_id``'s latest implementing claim, or ``None``.

    A string actor is returned as recorded; a dict-shaped resolved-binding actor
    is returned as its identity string (bare tool), which ``_actor_key`` accepts.
    """
    event = latest_implementer_event(events, wp_id)
    if event is None:
        return None
    return actor_identity_str(event.actor) or None


def is_latest_implementer(latest: str | None, actor: object) -> bool:
    """Whether ``actor`` is the WP's implementer authority ``latest``.

    ``latest`` is the result of :func:`latest_implementer_actor`. ``None``, empty,
    or a generic placeholder ``latest`` names no implementer and admits nothing;
    otherwise the two are compared through the tool-scoped ``_actor_key``
    projection (compact and dict-shaped actors of one tool compare equal). A
    requester that projects to no key is never the implementer. (#5377)
    """
    if not latest:
        return False
    latest_key = _actor_key(latest)
    if latest_key is None or latest_key in GENERIC_IMPLEMENTATION_ACTORS:
        return False
    requester_key = _actor_key(actor)
    return requester_key is not None and requester_key == latest_key
