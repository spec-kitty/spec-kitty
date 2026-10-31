"""WPState ABC, 10 concrete lane state classes, and wp_state_for() factory.

Implements the State Pattern for work-package lane behavior. Each lane
has a frozen dataclass subclass that owns its allowed transitions,
guard conditions, progress bucket, and display category.

Single-ownership (WP01, DM-01KTH03G): the WPState objects are the SOLE
authority for BOTH the transition edge graph AND the act of transitioning
(structural edge + guards + force-override). ``transitions.validate_transition``
is a thin delegator over :meth:`WPState.transition_to`; no edge/guard/force
logic lives outside these state objects, and no production code consults a
parallel ``(from, to)`` table as a gate.

See ADR: docs/adr/3.x/2026-04-06-1-wp-state-pattern-for-lane-behavior.md
See also: docs/adr/3.x/2026-06-07-1-wp-lane-fsm-genesis-and-finalize-clobber.md
(genesis lane, guard/force migration into the state objects, finalize clobber fix)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from specify_cli.status.models import ActorField, InnerStateChanged, Lane, WPInnerStateDelta, is_migration_actor

# Shared error message constants (single source for parity with the historical
# ``transitions.py`` implementation these guards were migrated from).
_FORCE_REQUIRES_ACTOR_AND_REASON = "Force transitions require actor and reason"
_REVIEWER_APPROVAL_REQUIRED = "Transition to approved/done requires evidence (reviewer identity and approval reference)"
_DEPENDENCIES_UNSATISFIED = "Transition {source} -> {target} blocked: unsatisfied dependencies (force with reason to override)"

#: Edges whose persisted events the status schema validator refuses without a
#: ``review_ref`` (#6514). ONE owning definition, consumed by the write path
#: (:meth:`WPState.check_transition`) and by the auditor
#: (``status.validate.validate_event_schema``) -- see
#: :func:`requires_review_ref`. Force may bridge a missing structural edge;
#: it may not produce an event this tool's own auditor calls malformed.
REVIEW_REF_REQUIRED_EDGES: frozenset[tuple[Lane, Lane]] = frozenset(
    {(Lane.FOR_REVIEW, Lane.IN_PROGRESS)},
)


def requires_review_ref(from_lane: Lane | str, to_lane: Lane | str) -> bool:
    """True when an event on this edge must carry a ``review_ref`` (#6514).

    A plain membership test over :data:`REVIEW_REF_REQUIRED_EDGES`, tolerant of
    raw lane strings (the auditor reads decoded event dicts). It answers only
    *which* edges carry the requirement; *whether a given request satisfies it*
    is :func:`has_review_ref`, which the writer (:meth:`WPState.check_transition`)
    and the auditor (``status.validate.validate_event_schema``) both read.

    An unknown lane string is not a member (``Lane(...)`` raises ``ValueError``),
    so a malformed lane never makes this predicate raise; the schema validator's
    canonical-lane finding already covers that case.
    """
    try:
        return (Lane(from_lane), Lane(to_lane)) in REVIEW_REF_REQUIRED_EDGES
    except ValueError:
        return False


def has_review_ref(review_ref: object) -> bool:
    """True when *review_ref* is a usable pointer: a non-blank string.

    The single definition of "the requirement is satisfied", so the writer and the
    auditor cannot disagree on whitespace or on a non-string that a corrupt log may
    carry. A value that is not a string is not a pointer.
    """
    return isinstance(review_ref, str) and bool(review_ref.strip())


def review_ref_required_message(source: Lane, target: Lane) -> str:
    """The refusal for a review rewind that cites no review feedback (#6514).

    Kept as a plain interpolated sentence rather than a ``str.format`` template keyed on
    lane operands: the worktree-name gate reads a ``.format(...)`` whose arguments are
    lane-shaped as a hand-rolled lane-name compose, and this is a human-facing refusal,
    not a name.
    """
    return (
        f"Transition {source.value} -> {target.value} requires review_ref: a forced rewind out of review "
        "must cite the review feedback it is rewinding (pass `--review-ref <ref>`)."
    )


class TransitionInputs(Protocol):
    """Structural protocol over the guard inputs a transition consults.

    Both :class:`specify_cli.status.transition_context.TransitionContext` and
    :class:`specify_cli.status.models.GuardContext` satisfy this protocol, so
    the FSM can own guard + force evaluation for callers of either context
    without coupling to a single concrete type.
    """

    actor: str | None
    workspace_context: str | None
    subtasks_complete: bool | None
    implementation_evidence_present: bool | None
    reason: str | None
    review_ref: str | None
    evidence: object
    force: bool
    review_result: object
    current_actor: str | None
    dependency_ready: bool | None


class InvalidTransitionError(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, source: Lane, target: Lane, reason: str | None = None) -> None:
        self.source = source
        self.target = target
        self.reason = reason
        message = f"Cannot transition from {source!r} to {target!r}"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message)


@dataclass(frozen=True)
class WPState(ABC):
    """Abstract base for lane-specific work package behaviour."""

    @property
    @abstractmethod
    def lane(self) -> Lane: ...

    @property
    def is_terminal(self) -> bool:
        """Return True for terminal lanes (done, canceled).

        Terminal lanes require ``force=True`` to leave. Note that merge
        validation uses an explicit ``approved|done`` check, NOT this property.
        """
        return False

    @property
    def is_blocked(self) -> bool:
        return False

    @property
    def is_run_affecting(self) -> bool:
        """Return True if this WP affects execution progress.

        A WP is "run-affecting" if it is active (planned through approved).
        Does not include terminal lanes (done, canceled) or the blocked lane.

        Distinction from related properties:
        - ``is_run_affecting``: True for active lanes (planned through approved)
        - ``is_terminal``:      True for cleanup-only lanes (done, canceled)
        - ``is_blocked``:       True only for the blocked lane

        Returns:
            True  if lane in {planned, claimed, in_progress, for_review, in_review, approved}
            False if lane in {genesis, done, blocked, canceled}

        Usage::

            if state.is_run_affecting:
                # Route to implementation or review
        """
        return self.lane in {
            Lane.PLANNED,
            Lane.CLAIMED,
            Lane.IN_PROGRESS,
            Lane.FOR_REVIEW,
            Lane.IN_REVIEW,
            Lane.APPROVED,
        }

    @abstractmethod
    def allowed_targets(self) -> frozenset[Lane]: ...

    @property
    def current_lane(self) -> Lane:
        """The lane this state represents (State-pattern FSM accessor).

        Alias of :attr:`lane` using the canonical FSM vocabulary.
        """
        return self.lane

    def may_transition_to(self, target: Lane) -> bool:
        """Structural edge check only (guard-free, force-free).

        This is the single authority for the lane-adjacency graph: a target is
        reachable iff it is in this state's ``allowed_targets()``. Production
        edge-legality questions route here instead of consulting any parallel
        ``(from, to)`` table.
        """
        return target in self.allowed_targets()

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:  # noqa: ARG002 -- target/ctx are the contract every override consumes; the default hook is unguarded
        """Evaluate this state's entry guard for ``target``.

        Subclasses with guarded outbound edges override this. The default is
        unguarded (any structurally-allowed target is permitted). Returns the
        ``(ok, error_message)`` decision; ``error_message`` is the parity
        message the historical ``transitions._run_guard`` produced.
        """
        return True, None

    def can_transition_to(self, target: Lane, ctx: TransitionInputs) -> bool:
        """Guard-aware boolean edge check (no force-override).

        Returns True iff the structural edge exists AND this state's entry
        guard for ``target`` is satisfied by ``ctx``. Force is NOT consulted
        here — use :meth:`check_transition` / :meth:`transition_to` for the
        full force-aware decision.
        """
        if not self.may_transition_to(target):
            return False
        ok, _ = self.guard_for(target, ctx)
        return ok

    def check_transition(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        """Full transition decision: structural edge + guard + force-override.

        Returns ``(ok, error_message)`` with the exact parity messages of the
        historical ``validate_transition``. ``force`` (with actor + reason)
        overrides both the edge check and the guards — including terminal
        force-exit from ``done``/``canceled`` to any display lane. ``genesis``
        remains a non-display seed source and is never a valid target.

        Two refusals are deliberately NOT force-overridable: a ``genesis`` target,
        and the ``review_ref`` requirement of an edge in
        :data:`REVIEW_REF_REQUIRED_EDGES` (#6514) — force may bridge a missing edge
        or a guard, never the status schema validator's own invariants.
        """
        if target == Lane.GENESIS:
            # Genesis is a seed source, not a persisted/display target. Force may
            # bypass edges and guards, but it must not create a current genesis WP.
            return False, f"Illegal transition: {self.lane.value} -> {target.value}"
        if not self.may_transition_to(target) and not ctx.force:
            # Edge does not exist: only force (with actor + reason) can override.
            # This early return keeps the historical refusal text for an unforced
            # attempt on a force-only edge (#6514 contract C-5).
            return False, f"Illegal transition: {self.lane.value} -> {target.value}"

        # Force bypasses the guard but still requires actor + reason for audit. The
        # audit requirement is checked FIRST so a reasonless force keeps its historical
        # message instead of being reported as a missing review_ref.
        if ctx.force:
            ok, error = self._check_force(ctx)
            if not ok:
                return ok, error

        # A review_ref requirement is FORCE-INSURMOUNTABLE (#6514): force's contract is
        # to override a missing edge or a guard with actor + reason for audit, not to
        # persist an event the status schema validator refuses. Evaluated here, never
        # in ``guard_for``: force bypasses guards entirely, so a guard-side rule would
        # be dead on the only route this edge has.
        # A ``migration:`` actor reconstructs state rather than acting (the #5446
        # precedent in ``transition_pipeline._refuse_unnoted_review_exit``), so it is
        # exempt; the validator still reports such a row, as it does for legacy rows.
        if (
            requires_review_ref(self.lane, target)
            and not has_review_ref(ctx.review_ref)
            and not is_migration_actor(ctx.actor)
        ):
            return False, review_ref_required_message(self.lane, target)

        if ctx.force:
            return True, None
        return self.guard_for(target, ctx)

    @staticmethod
    def _check_force(ctx: TransitionInputs) -> tuple[bool, str | None]:
        """Force-override gate: requires a non-empty actor AND reason."""
        if not ctx.actor or not ctx.actor.strip():
            return False, _FORCE_REQUIRES_ACTOR_AND_REASON
        if not ctx.reason or not ctx.reason.strip():
            return False, _FORCE_REQUIRES_ACTOR_AND_REASON
        return True, None

    def transition_to(self, target: Lane, ctx: TransitionInputs) -> WPState:
        """Return the new state after a full edge + guard + force transition.

        Canonical FSM name. Honours ``ctx.force`` (requires actor + reason)
        exactly where the historical ``validate_transition`` force branch
        permitted it, including terminal force-exit. Raises
        :class:`InvalidTransitionError` on rejection.
        """
        ok, error = self.check_transition(target, ctx)
        if not ok:
            raise InvalidTransitionError(self.lane, target, error)
        return wp_state_for(target)

    @abstractmethod
    def progress_bucket(self) -> str:
        """One of: 'not_started', 'in_flight', 'review', 'terminal'."""
        ...

    @abstractmethod
    def display_category(self) -> str:
        """Kanban column label (e.g., 'Planned', 'In Progress', 'Done')."""
        ...


# ---------------------------------------------------------------------------
# Guard helpers (used by concrete classes)
# ---------------------------------------------------------------------------


def _has_actor(ctx: TransitionInputs) -> bool:
    return bool(ctx.actor and ctx.actor.strip())


# ---------------------------------------------------------------------------
# Concrete state classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenesisState(WPState):
    """Work package created but not yet seeded into the lane lifecycle.

    Pre-finalize, non-display state. ``finalize-tasks`` performs the explicit
    ``genesis -> planned`` seed. A genesis WP has no lane events and so never
    materializes into a snapshot or onto the board; this state exists to make
    the seed transition explicit rather than an implied ``planned -> planned``.
    """

    @property
    def lane(self) -> Lane:
        return Lane.GENESIS

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset({Lane.PLANNED, Lane.CANCELED})

    def progress_bucket(self) -> str:
        return "not_started"

    def display_category(self) -> str:
        # Non-display lane: group under Planned so no separate board column is
        # ever introduced for the transient genesis state.
        return "Planned"


@dataclass(frozen=True)
class UninitializedState(WPState):
    """Read sentinel for a WP with no lane events at all.

    Distinct from ``GenesisState``: genesis means a WP was created and
    seeded (has a ``WPCreated`` event) but not yet finalized into the lane
    lifecycle; uninitialized means the lane-reader found NO events for the
    WP whatsoever (empty event log, or WP absent from the reduced
    snapshot). ``allowed_targets()`` is deliberately EMPTY — not a copy of
    ``GenesisState``'s ``{PLANNED, CANCELED}`` — because this state must add
    zero edges to the transition-matrix projection derived in
    ``transitions.py`` and must be genuinely non-transitionable (never a
    valid ``from_lane`` or ``to_lane`` in a real transition). Do not
    "simplify" this into an alias of ``GenesisState``: that would inject
    transition edges and make ``UNINITIALIZED`` transitionable, both of
    which are contract violations (see ``docs/adr/3.x`` lane-uninitialized
    notes / #2675).
    """

    @property
    def lane(self) -> Lane:
        return Lane.UNINITIALIZED

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset()

    def progress_bucket(self) -> str:
        return "not_started"

    def display_category(self) -> str:
        # Non-display lane: never a board column. Grouped under Planned for
        # parity with GenesisState's placeholder, though this value is not
        # expected to be consulted in practice (uninitialized WPs never
        # materialize onto the board).
        return "Planned"


@dataclass(frozen=True)
class PlannedState(WPState):
    """Work package is planned but not yet started."""

    @property
    def lane(self) -> Lane:
        return Lane.PLANNED

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset({Lane.CLAIMED, Lane.BLOCKED, Lane.CANCELED})

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        if target == Lane.CLAIMED and not _has_actor(ctx):
            return False, "Transition requires actor identity"
        # FR-012 dependency gate, tri-state and fail-OPEN on ``None`` (C-004,
        # decision Q8): only an explicit ``False`` verdict refuses. ``None`` means
        # no verdict was supplied (the two direct probe callers) and passes. Do
        # NOT copy ``subtasks_complete``'s ``is not True`` polarity. Force is not
        # consulted here -- ``check_transition._check_force`` bypasses the guard.
        if target == Lane.CLAIMED and ctx.dependency_ready is False:
            return False, _DEPENDENCIES_UNSATISFIED.format(source=Lane.PLANNED.value, target=Lane.CLAIMED.value)
        return True, None

    def progress_bucket(self) -> str:
        return "not_started"

    def display_category(self) -> str:
        return "Planned"


@dataclass(frozen=True)
class ClaimedState(WPState):
    """Work package has been claimed by an agent/actor."""

    @property
    def lane(self) -> Lane:
        return Lane.CLAIMED

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset({Lane.IN_PROGRESS, Lane.BLOCKED, Lane.CANCELED})

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        if target == Lane.IN_PROGRESS and not (ctx.workspace_context and ctx.workspace_context.strip()):
            return False, "Transition claimed -> in_progress requires workspace context"
        # FR-012 dependency gate: same tri-state, fail-OPEN-on-``None`` polarity
        # as ``PlannedState.guard_for`` (C-004, decision Q8).
        if target == Lane.IN_PROGRESS and ctx.dependency_ready is False:
            return False, _DEPENDENCIES_UNSATISFIED.format(source=Lane.CLAIMED.value, target=Lane.IN_PROGRESS.value)
        return True, None

    def progress_bucket(self) -> str:
        return "in_flight"

    def display_category(self) -> str:
        return "In Progress"


@dataclass(frozen=True)
class InProgressState(WPState):
    """Work package is actively being implemented."""

    @property
    def lane(self) -> Lane:
        return Lane.IN_PROGRESS

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset(
            {
                Lane.FOR_REVIEW,
                Lane.APPROVED,
                Lane.PLANNED,
                Lane.BLOCKED,
                Lane.CANCELED,
            }
        )

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        # NB: guards must NOT consult ``ctx.force`` — force is handled once, at the
        # caller (``check_transition._check_force``), which bypasses the guard
        # entirely. A force branch here is dead on the canonical path and breaks
        # the ``can_transition_to`` contract ("Force is NOT consulted here"), making
        # ``can_transition_to(FOR_REVIEW, force=True)`` disagree with
        # ``check_transition`` (#1775 review M2).
        if target == Lane.FOR_REVIEW:
            if ctx.subtasks_complete is not True:
                return (
                    False,
                    "Transition in_progress -> for_review requires completed subtasks or force with reason",
                )
            if ctx.implementation_evidence_present is not True:
                return (
                    False,
                    "Transition in_progress -> for_review requires implementation evidence or force with reason",
                )
            return True, None
        if target == Lane.APPROVED:
            return _check_reviewer_approval(ctx)
        if target == Lane.PLANNED:
            if not (ctx.reason and ctx.reason.strip()):
                return False, "Transition in_progress -> planned requires reason"
            return True, None
        return True, None

    def progress_bucket(self) -> str:
        return "in_flight"

    def display_category(self) -> str:
        return "In Progress"


@dataclass(frozen=True)
class ForReviewState(WPState):
    """Work package is queued for review (not yet claimed by a reviewer)."""

    @property
    def lane(self) -> Lane:
        return Lane.FOR_REVIEW

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset({Lane.IN_REVIEW, Lane.BLOCKED, Lane.CANCELED})

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        if target == Lane.IN_REVIEW:
            if not _has_actor(ctx):
                return False, "Transition requires actor identity"
            return _check_no_review_conflict(ctx)
        return True, None

    def progress_bucket(self) -> str:
        return "review"

    def display_category(self) -> str:
        return "Review"


@dataclass(frozen=True)
class InReviewState(WPState):
    """Work package is actively being reviewed by a specific reviewer."""

    @property
    def lane(self) -> Lane:
        return Lane.IN_REVIEW

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset(
            {
                Lane.APPROVED,
                Lane.DONE,
                Lane.IN_PROGRESS,
                Lane.PLANNED,
                Lane.BLOCKED,
                Lane.CANCELED,
            }
        )

    def guard_for(self, _target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        # FR-012c: ALL outbound transitions from in_review require ReviewResult.
        ok, error = _check_review_result(ctx)
        if not ok:
            return ok, error
        if _target in {Lane.APPROVED, Lane.DONE}:
            ok, error = _check_in_review_approval(ctx)
            if not ok:
                return ok, error
        return _check_review_result_consistency(ctx)

    def progress_bucket(self) -> str:
        return "review"

    def display_category(self) -> str:
        return "In Progress"


@dataclass(frozen=True)
class ApprovedState(WPState):
    """Work package review is approved, pending completion."""

    @property
    def lane(self) -> Lane:
        return Lane.APPROVED

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset(
            {
                Lane.DONE,
                Lane.IN_PROGRESS,
                Lane.PLANNED,
                Lane.BLOCKED,
                Lane.CANCELED,
            }
        )

    def guard_for(self, target: Lane, ctx: TransitionInputs) -> tuple[bool, str | None]:
        if target == Lane.DONE:
            return _check_reviewer_approval(ctx)
        if target in (Lane.IN_PROGRESS, Lane.PLANNED):
            if not (ctx.review_ref and ctx.review_ref.strip()):
                return False, "Transition requires review_ref (review feedback reference)"
            return True, None
        return True, None

    def progress_bucket(self) -> str:
        return "review"

    def display_category(self) -> str:
        return "Approved"


@dataclass(frozen=True)
class DoneState(WPState):
    """Work package is complete (terminal)."""

    @property
    def lane(self) -> Lane:
        return Lane.DONE

    @property
    def is_terminal(self) -> bool:
        return True

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset()

    def progress_bucket(self) -> str:
        return "terminal"

    def display_category(self) -> str:
        return "Done"


@dataclass(frozen=True)
class BlockedState(WPState):
    """Work package is blocked on an external dependency."""

    @property
    def lane(self) -> Lane:
        return Lane.BLOCKED

    @property
    def is_blocked(self) -> bool:
        return True

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset({Lane.IN_PROGRESS, Lane.CANCELED})

    def progress_bucket(self) -> str:
        return "in_flight"

    def display_category(self) -> str:
        return "Blocked"


@dataclass(frozen=True)
class CanceledState(WPState):
    """Work package has been canceled (terminal)."""

    @property
    def lane(self) -> Lane:
        return Lane.CANCELED

    @property
    def is_terminal(self) -> bool:
        return True

    def allowed_targets(self) -> frozenset[Lane]:
        return frozenset()

    def progress_bucket(self) -> str:
        return "terminal"

    def display_category(self) -> str:
        return "Canceled"


# ---------------------------------------------------------------------------
# Guard helpers (evidence / review-result / conflict) — own the parity messages
# ---------------------------------------------------------------------------


def _check_reviewer_approval(ctx: TransitionInputs) -> tuple[bool, str | None]:
    """Guard: approval/done transitions require reviewer approval evidence."""
    evidence = ctx.evidence
    if evidence is None:
        return False, _REVIEWER_APPROVAL_REQUIRED
    review = getattr(evidence, "review", None)
    reviewer = getattr(review, "reviewer", None) if review is not None else None
    verdict = getattr(review, "verdict", None) if review is not None else None
    reference = getattr(review, "reference", None) if review is not None else None
    if not reviewer or not str(reviewer).strip():
        return False, _REVIEWER_APPROVAL_REQUIRED
    if not reference or not str(reference).strip():
        return False, _REVIEWER_APPROVAL_REQUIRED
    if verdict != "approved":
        return False, _REVIEWER_APPROVAL_REQUIRED
    return True, None


def _check_in_review_approval(ctx: TransitionInputs) -> tuple[bool, str | None]:
    """Accept review-result approval when no separate done evidence is needed."""
    if ctx.evidence is not None:
        return _check_reviewer_approval(ctx)
    review_result = ctx.review_result
    if (
        getattr(review_result, "reviewer", None)
        and getattr(review_result, "verdict", None) == "approved"
        and getattr(review_result, "reference", None)
    ):
        return True, None
    return False, _REVIEWER_APPROVAL_REQUIRED


def _check_no_review_conflict(ctx: TransitionInputs) -> tuple[bool, str | None]:
    """Guard: for_review -> in_review is HARD allow-only (never blocks).

    This guard consults actor-presence only (already enforced upstream by
    :meth:`ForReviewState.guard_for` via ``_has_actor``) and ALWAYS allows. It
    deliberately has NO reject / ``return False`` branch: the ``for_review``
    holder is structurally the implementer (or a *stale* reviewer after a rework
    cycle), so any block-on-actor/role here is either the original
    cross-profile false-positive ("WP already claimed for review by
    <implementer>") or the stale-role false-positive. The genuine
    reviewer-vs-reviewer collision lives solely at the ``in_review`` re-claim
    (:func:`work_package_lifecycle.start_review_status`, via
    ``review_claim_decision``); this guard MUST NOT import or evaluate that
    predicate. A stale reviewer role at ``for_review`` therefore still ALLOWs by
    construction, not by input shape.
    """
    del ctx  # allow-only: inputs are intentionally never consulted for a block
    return True, None


def _check_review_result(ctx: TransitionInputs) -> tuple[bool, str | None]:
    """Guard: all outbound in_review transitions require a ReviewResult."""
    rr = ctx.review_result
    if rr is None:
        return (
            False,
            "Transition from in_review requires review_result (structured review outcome)",
        )
    reviewer = getattr(rr, "reviewer", None)
    verdict = getattr(rr, "verdict", None)
    reference = getattr(rr, "reference", None)
    if not reviewer or not str(reviewer).strip():
        return False, "Transition from in_review requires review_result with reviewer"
    if not verdict or not str(verdict).strip():
        return False, "Transition from in_review requires review_result with verdict"
    if not reference or not str(reference).strip():
        return False, "Transition from in_review requires review_result with reference"
    return True, None


def _check_review_result_consistency(
    ctx: TransitionInputs,
) -> tuple[bool, str | None]:
    """Reject contradictory structured, evidence, and legacy review fields."""
    rr = ctx.review_result
    if rr is None:
        return False, "Transition from in_review requires review_result"

    if ctx.review_ref is not None and ctx.review_ref != getattr(rr, "reference", None):
        return False, "review_ref must match review_result.reference"

    evidence = ctx.evidence
    if evidence is None:
        return True, None
    review = getattr(evidence, "review", None)
    expected = (
        getattr(rr, "reviewer", None),
        getattr(rr, "verdict", None),
        getattr(rr, "reference", None),
    )
    actual = (
        getattr(review, "reviewer", None),
        getattr(review, "verdict", None),
        getattr(review, "reference", None),
    )
    if actual != expected:
        return False, "Review evidence must match review_result"
    return True, None


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_STATE_MAP: dict[str, type[WPState]] = {
    "genesis": GenesisState,
    "uninitialized": UninitializedState,
    "planned": PlannedState,
    "claimed": ClaimedState,
    "in_progress": InProgressState,
    "for_review": ForReviewState,
    "in_review": InReviewState,
    "approved": ApprovedState,
    "done": DoneState,
    "blocked": BlockedState,
    "canceled": CanceledState,
}

# Alias resolution for the factory (only "doing" remains; "in_review" is first-class)
_FACTORY_ALIASES: dict[str, str] = {
    "doing": "in_progress",
}


def wp_state_for(lane: Lane | str) -> WPState:
    """Instantiate the correct concrete WPState for a given lane value."""
    lane_str = str(lane)
    lane_str = _FACTORY_ALIASES.get(lane_str, lane_str)
    cls = _STATE_MAP.get(lane_str)
    if cls is None:
        raise ValueError(f"Unknown lane: {lane_str!r}")
    return cls()


# ---------------------------------------------------------------------------
# Sanctioned non-transition annotation seam (C-004)
# ---------------------------------------------------------------------------


def annotate(
    wp_id: str,
    delta: WPInnerStateDelta,
    *,
    actor: ActorField,
    at: str,
    event_id: str,
) -> InnerStateChanged:
    """Construct a validated off-axis :class:`InnerStateChanged` annotation.

    This is the sanctioned NON-transition seam: it assembles the typed event
    WITHOUT consulting ``validate_transition`` and WITHOUT adding any lane
    self-edge to the FSM matrix. It is modelled on
    :meth:`UninitializedState.allowed_targets` (which returns ``frozenset()``
    — it adds zero edges): the annotation path traverses zero FSM edges.

    Validation here is delta-shape validation, not FSM validation:

    - ``wp_id`` must match the canonical WP-id pattern (``store._WP_ID_PATTERN``).
    - the delta must not be empty (an empty delta folds to a no-op and is
      refused at this seam).

    Args:
        wp_id: Target work-package id (e.g. ``"WP01"``).
        delta: The typed partial runtime-state payload to record.
        actor: Identity of the actor causing the change.
        at: ISO-8601 occurrence timestamp.
        event_id: ULID event id (minted by the caller / emit seam).

    Returns:
        A fully-typed :class:`InnerStateChanged` ready to persist.

    Raises:
        ValueError: for a malformed ``wp_id`` or an empty delta.
    """
    # Lazy import keeps the FSM module free of a store-layer import at module
    # load and reuses the single canonical WP-id pattern. ``store`` never
    # exposes ``validate_transition``, so the annotate path stays FSM-free.
    from specify_cli.status.store import _WP_ID_PATTERN  # noqa: PLC0415

    if not _WP_ID_PATTERN.match(wp_id):
        raise ValueError(f"annotate() refuses wp_id not matching the WP-id pattern: {wp_id!r}")
    if delta.is_empty():
        raise ValueError("annotate() refuses an empty delta (it folds to a no-op)")
    return InnerStateChanged(
        event_id=event_id,
        wp_id=wp_id,
        at=at,
        actor=actor,
        delta=delta,
    )
