"""ProfileInvocationExecutor: single execution primitive for profile-governed invocations.

IMPORTANT: mark_loaded=False is always passed to build_charter_context().
Failing to pass this flag would corrupt context-state.json and break the
specify/plan first-load detection — these commands use first_load as a
sentinel to decide whether to show the full charter vs a compact summary.
The invocation executor must NEVER claim a first-load token.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json as _json_mod
import logging
import subprocess as _subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Literal, Protocol

if TYPE_CHECKING:
    from charter.activation.context import CharterContextResult
    from charter.profiles import AgentProfile
    from charter.model_routing import RoutingRecommendation
    from glossary.chokepoint import (
        GlossaryChokepoint,
        GlossaryObservationBundle,
    )

import ulid as _ulid_mod  # matches codebase pattern: status/emit.py, core/mission_creation.py

from charter.activation.context import build_charter_context
from mission_runtime import CommitTarget
from specify_cli.core.commit_guard import GuardCapability
from kernel.clock import now_utc_iso
from specify_cli.git import safe_commit
from specify_cli.invocation.empty_charter import resolve_generic_fallback
from specify_cli.invocation.errors import (
    AlreadyClosedError,
    InvalidModeForEvidenceError,
    InvocationError,
    RouterAmbiguityError,
    UndeterminedModeForEvidenceError,
)
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.invocation.propagator import InvocationSaaSPropagator
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent, promote_to_evidence
from specify_cli.invocation.registry import ProfileRegistry
from specify_cli.invocation.router import ActionRouter, RouterDecision  # WP02: router implemented
from specify_cli.invocation.task_class_map import task_type_for_verb
from specify_cli.invocation.writer import (
    OP_CLOSURES_RELATIVE_PATH,
    InvocationWriter,
    append_op_closure,
    closed_invocation_ids,
    normalise_ref,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class OpCommitOutcome:
    """Result of one best-effort Op-record auto-commit (#4397).

    ``committed=False`` with a ``refusal`` carries the actionable reason (for
    example a protected-branch guard refusal) so callers can surface it — the
    doctor sweep reports it per entry and the CLI complete path prints it —
    instead of the outcome dying in a ``logger.warning``.
    """

    committed: bool
    refusal: str | None = None


def _compute_recommendation(profile: AgentProfile, action: str) -> RoutingRecommendation | None:
    """Advisory model-routing recommendation for ``(profile, action)`` (FR-004).

    This is the ONE seam that holds both the loader+evaluator call and the
    non-fatal envelope required by NFR-002/C-001, so ``invoke()`` can call it
    in a single line and stay within the complexity ceiling. Returns ``None``
    -- never raises -- when:

    - ``action`` has no ``task_class_map`` mapping (verb outside the
      maintained namespace);
    - the catalog is missing, whole-file-invalid, or fails schema validation
      (a malformed entry is allowed to raise ``pydantic.ValidationError`` per
      the loader's own contract -- caught here so dispatch never breaks);
    - the loaded catalog is stale per its own freshness policy; or
    - the evaluator finds no matching candidate for the resolved task_type
      (unmatched catalog -- no catalog pick and no profile-declared model).

    ``dispatch``/``invoke()`` always succeeds regardless of which branch
    fires -- this function only ever narrows the payload, never the outcome.
    """
    # Function-local charter-door imports keep model-routing lazy (no import-time
    # cost when routing is unused). The charter facade fronts
    # charter.offering.model_task_routing at symbol level (FR-004): import the callables
    # directly rather than the whole module.
    from charter.model_routing import evaluate, load

    task_type = task_type_for_verb(action)
    if task_type is None:
        return None
    try:
        catalog_result = load()
    except Exception:  # noqa: BLE001 - advisory envelope: never break dispatch (NFR-002/C-001)
        return None
    if catalog_result is None or catalog_result.is_stale:
        return None
    recommendation = evaluate(catalog_result.catalog, task_type, profile)
    if not recommendation.candidates:
        return None
    return recommendation


def _new_ulid() -> str:
    """Generate a new ULID string using the codebase's existing ulid library.

    Matches the pattern in src/specify_cli/status/emit.py lines 80-84.
    Handles both python-ulid API variants gracefully.
    """
    try:
        # python-ulid >= 1.0 API: _ulid_mod.new().str
        new_fn = getattr(_ulid_mod, "new", None)
        if new_fn is not None:
            return str(new_fn().str)
    except Exception:  # noqa: BLE001
        pass
    # Fallback: construct ULID directly
    return str(_ulid_mod.ULID())


class ActionRouterPlugin(Protocol):
    """No-op protocol stub — reserved for future hybrid routing extension (WP02)."""

    # No methods in v1. Fill in WP02's ActionRouterPlugin slot here.


@dataclasses.dataclass(frozen=True)
class _UndeterminedMode:
    """A recorded ``mode_of_work`` that maps to no :class:`ModeOfWork`.

    The third state, and the whole point of this type: a started record can
    declare **no** mode (a pre-v2 record — the field did not exist yet) or a
    mode nobody can read (a hand-edited or corrupted ``kitty-ops`` line). Those
    are different facts and collapsing them into one ``None`` made the second
    inherit the first's permissive default (#3030). ``raw`` carries the value
    verbatim so the refusal can name what it could not read.
    """

    raw: object


def classify_mode_of_work(raw: object) -> ModeOfWork | None | _UndeterminedMode:
    """Classify a recorded ``mode_of_work`` into absent / known / undetermined.

    - ``None`` → **absent**. Pre-v2 records legitimately carry no
      ``mode_of_work``; its documented legacy default is ``task_execution``
      (see the WP05 migration ``m_3_3_0_op_record_schema_v2``, which backfills
      exactly that, and ``propagator._projection_rule_for``). Absence must keep
      meaning absence — refusing on it would strand every legacy Op.
    - a :class:`ModeOfWork` value → that mode.
    - anything else → :class:`_UndeterminedMode`. Note the empty string is
      absence (a field written blank), while ``0`` / ``False`` / a list / an
      object are malformation: the old ``if not raw`` test read all of them as
      absence, which is how a JSON ``false`` bought a legacy default.
    """
    if raw is None or (isinstance(raw, str) and raw == ""):
        return None
    if isinstance(raw, ModeOfWork):
        return raw
    if not isinstance(raw, str):
        return _UndeterminedMode(raw)
    try:
        return ModeOfWork(raw)
    except ValueError:
        return _UndeterminedMode(raw)


def mode_permits_evidence(mode: ModeOfWork | None | _UndeterminedMode) -> bool:
    """Whether *mode* may carry a Tier 2 evidence artifact (FR-009).

    The single classification both the advertised close contract and the
    enforced gate read, so the two cannot drift into offering a flag the
    executor then refuses.
    """
    if isinstance(mode, _UndeterminedMode):
        return False  # undetermined is not permission
    if mode is None:
        return True  # absent → documented legacy default (task_execution)
    return mode not in (ModeOfWork.ADVISORY, ModeOfWork.QUERY)


def build_close_contract(invocation_id: str, mode_of_work: str | None = None) -> dict[str, object]:
    """Machine-readable close contract for an open Op (contracts/cli-do-output.md).

    Emitted in every invocation JSON payload so orchestrators know exactly how
    to close the Op with the real outcome.  ``evidence_flag`` is omitted for
            non-evidence-eligible modes because ``profile-invocation complete`` refuses
    ``--evidence`` there (InvalidModeForEvidenceError, FR-009) — including when
    the recorded mode cannot be read at all, which the gate now refuses too.
    """
    contract: dict[str, object] = {
        "command": (f"spec-kitty profile-invocation complete --invocation-id {invocation_id} --outcome <done|failed|abandoned>"),
        "outcomes": ["done", "failed", "abandoned"],
        "evidence_flag": "--evidence",
        "artifact_flag": "--artifact",
        "commit_flag": "--commit",
    }
    if not mode_permits_evidence(classify_mode_of_work(mode_of_work)):
        del contract["evidence_flag"]
    return contract


class InvocationPayload:
    """Ephemeral response returned to CLI callers."""

    # Typed instance attribute annotations alongside __slots__ so callers (and
    # mypy --strict) can see the payload shape. The class-level annotations
    # carry no value, so they do not conflict with __slots__ storage. Without
    # these, multi-file mypy --strict raises attr-defined on every payload
    # access (RISK-1 / mission-review.md follow-up).
    invocation_id: str
    profile_id: str
    profile_friendly_name: str
    action: str
    governance_context_text: str | None
    governance_context_hash: str | None
    governance_context_available: bool
    router_confidence: str | None
    glossary_observations: GlossaryObservationBundle | None
    mode_of_work: str | None
    recommendation: RoutingRecommendation | None
    empty_charter_fallback: bool
    # WP2/#3840 (FR-005): the already-computed losing candidates from
    # RouterDecision.alternatives, threaded onto both invoke() and dry_run()
    # payloads. Unlike RouterDecision (a real frozen dataclass), this class's
    # **kwargs __init__ enforces no required-constructor-argument guarantee
    # for this slot -- see to_dry_run_dict()'s explicit fail-fast guard below,
    # which is the real backstop at this layer.
    alternatives: list[dict[str, str]]

    __slots__ = (
        "invocation_id",
        "profile_id",
        "profile_friendly_name",
        "action",
        "governance_context_text",
        "governance_context_hash",
        "governance_context_available",
        "router_confidence",
        "glossary_observations",
        "mode_of_work",
        "recommendation",
        "empty_charter_fallback",
        "alternatives",
    )

    def __init__(self, **kwargs: object) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)

    def _serialize_slots(self, *, exclude: frozenset[str]) -> dict[str, object]:
        """Shared field-serialization walk used by both ``to_dict`` and
        ``to_dry_run_dict`` -- one branchy walk, two exclude sets, so the two
        JSON-shape builders can never drift on how a slot gets serialized.
        """
        result: dict[str, object] = {}
        for s in self.__slots__:
            if s in exclude:
                continue
            # Use getattr default so callers that omit glossary_observations
            # (e.g. tests constructing InvocationPayload directly) get None
            # instead of AttributeError. C-005 backward-compat fix.
            val = getattr(self, s, None)
            # Only serialise glossary_observations via its to_dict() — explicit,
            # not duck-typed, to avoid accidentally serialising future slots
            # that happen to carry objects with a to_dict() method. RISK-3 fix.
            if s == "glossary_observations" and val is not None:
                result[s] = val.to_dict()
            elif s == "recommendation" and val is not None:
                # RoutingRecommendation is a frozen dataclass (not a Pydantic
                # model / no to_dict of its own) -- dataclasses.asdict is the
                # explicit, non-duck-typed serialization for it (RISK-3 style
                # fix, matching the glossary_observations branch above).
                result[s] = dataclasses.asdict(val)
            else:
                result[s] = val
        return result

    def to_dict(self) -> dict[str, object]:
        # mode_of_work shapes the close contract below but is not part of
        # the serialized payload surface (contracts/cli-do-output.md).
        result = self._serialize_slots(exclude=frozenset({"mode_of_work"}))
        # FR-002 / contracts/cli-do-output.md: invoke() leaves the Op open;
        # every JSON payload carries the explicit close contract.
        result["status"] = "open"
        result["close_contract"] = build_close_contract(self.invocation_id, getattr(self, "mode_of_work", None))
        return result

    def to_dry_run_dict(self) -> dict[str, object]:
        """FR-004/Key-Entities: the dry-run success envelope.

        Reuses ``InvocationPayload``'s field set minus ``invocation_id`` (no
        Op was opened) and ``mode_of_work``/``close_contract`` (nothing to
        close), plus a terminal ``"status": "dry_run"``. ``alternatives`` is
        read directly off ``self`` (WP2/#3840) -- WP1's original signature
        took it as a parameter because the field did not exist yet on this
        class; now that it does, the parameter is redundant and has been
        dropped (``dispatch.py``'s sole call site updated to match).

        Fail-fast guard (WP2 Context/T009 step 5, required, not optional):
        unlike ``RouterDecision`` (a real frozen dataclass with no default,
        so ``mypy --strict`` catches a missed ``alternatives=`` kwarg at
        every production construction site), ``InvocationPayload.__init__``
        accepts arbitrary ``**kwargs`` and enforces nothing -- a construction
        site that omits ``alternatives=`` would otherwise silently serialize
        ``"alternatives": null`` here instead of failing loudly. This guard
        is intentionally scoped to THIS method only, never ``to_dict()``:
        ``to_dict()`` is the generic whole-``__slots__`` serializer that
        ``tests/invocation/test_dispatch_recommendation.py``'s
        ``_sample_payload()`` fixture depends on staying permissive for
        slots it omits (WP01-owned, not touched by this WP).
        """
        if getattr(self, "alternatives", None) is None:
            raise RuntimeError("InvocationPayload.alternatives was not set -- a construction site is missing alternatives=")
        result = self._serialize_slots(exclude=frozenset({"mode_of_work", "invocation_id"}))
        result["status"] = "dry_run"
        return result


def build_ambiguous_dry_run_payload(request_text: str, err: RouterAmbiguityError) -> dict[str, object]:  # noqa: ARG001
    """FR-009: the dedicated payload shape for the ``ROUTER_AMBIGUOUS`` dry-run
    branch -- a deliberate, narrow exception to reusing ``InvocationPayload``.

    No winner was resolved on this branch (``route()`` raised before returning
    a decision), so no governance context, no recommendation, no glossary scan
    tied to a winning profile exists to report. ``InvocationPayload``'s
    ``profile_id``/``action`` slots stay non-Optional (``mypy --strict``) for
    every other caller; forcing ``str | None`` through them to accommodate
    this one branch would ripple an ``Optional`` into the real-dispatch
    success contract for no benefit (plan.md "Two JSON shapes on the dry-run
    path"). This is colocated beside ``InvocationPayload.to_dry_run_dict``
    rather than living in ``dispatch.py`` so both dry-run shape sources stay
    visibly adjacent for the next maintainer -- it is not a second competing
    canonical payload type, just the one place the contract legitimately has
    no winner to describe.

    ``request_text`` is accepted for call-site symmetry with
    ``to_dry_run_dict`` (``dispatch.py`` calls both as
    ``builder(request, ...)``) and reserved for a future audit-trail echo;
    spec.md's Key Entities contract for this branch does not include it in
    the returned shape, so it is not read here.
    """
    return {
        "status": "dry_run",
        "profile_id": None,
        "action": None,
        "router_confidence": "ambiguous",
        "alternatives": [
            {
                "profile_id": c["profile_id"],
                "action": c["action"],
                # FR-009: router.py's ROUTER_AMBIGUOUS raise site now carries a
                # confidence key on every candidate dict -- guaranteed present,
                # not defensively .get()'d, so a future regression there is
                # loud (KeyError), not silently swallowed.
                "confidence": c["confidence"],
                "match_reason": c["match_reason"],
            }
            for c in err.candidates
        ],
    }


@dataclasses.dataclass(frozen=True)
class _RoutingResolution:
    """Read-only routing-resolution + governance-context result.

    Shared return shape for ``ProfileInvocationExecutor._resolve_routing_and_context``,
    the helper both ``invoke()`` and ``dry_run()`` call to eliminate their
    duplicated read-only wiring (PR-BOUNDARY-001). Carries ONLY the read
    half: resolved profile/action, the advisory model-routing recommendation,
    the assembled governance context, and the glossary chokepoint scan
    result. It carries NOTHING from the write half -- no started-record
    construction, no writer/propagator calls -- those stay in ``invoke()``
    only, entirely after the duplicated region this type replaces.
    """

    profile: AgentProfile
    action: str
    router_confidence: str | None
    empty_charter_fallback: bool
    alternatives: list[dict[str, str]]
    recommendation: RoutingRecommendation | None
    ctx_result: CharterContextResult
    ctx_hash: str
    ctx_available: bool
    bundle: GlossaryObservationBundle


class ProfileInvocationExecutor:
    """Single execution primitive for all profile-governed invocations.

    Does NOT spawn any LLM call. Returns synchronously.
    mark_loaded=False ensures first-load state for specify/plan/implement/review
    is NOT poisoned by invocation calls.
    """

    def __init__(
        self,
        repo_root: Path,
        router: ActionRouter | None = None,
        propagator: InvocationSaaSPropagator | None = None,
    ) -> None:
        self._repo_root = repo_root
        self._registry = ProfileRegistry(repo_root)
        self._writer = InvocationWriter(repo_root)
        self._router = router
        self._propagator = propagator
        self._chokepoint: GlossaryChokepoint | None = None  # lazy-loaded on first invoke
        #: Outcome of the most recent Op-record auto-commit performed by this
        #: executor (``None`` before the first close). Read by the doctor sweep
        #: and the CLI complete path to surface a refused commit (#4397).
        self.last_op_commit: OpCommitOutcome | None = None
        # Lazily populated only for doctor-sweep closes. One executor serves an
        # entire stale sweep, so keep the append-only spine's membership set in
        # memory and extend it after each successful append instead of reparsing
        # the ever-growing spine once per Op (#4424).
        self._doctor_sweep_closed_ids: set[str] | None = None

    def list_available_profiles(self) -> list[AgentProfile]:
        """Return the invocation catalog: profiles ``invoke`` can resolve.

        Read-only accessor over the same ``ProfileRegistry`` this executor's
        ``invoke()`` resolves ``profile_hint`` against, so a caller that
        picks a fallback profile from this list has a guarantee
        ``invoke(profile_hint=<that id>)`` cannot then fail with
        ``ProfileNotFoundError`` (#4115: the mission-step executor's
        role-based default-profile fallback consumes exactly this guarantee).
        """
        # Typed local: ``ProfileRegistry`` resolves to Any under a narrow
        # ``--strict`` check (the ``specify_cli.*`` follow-imports skip), and
        # this accessor's return type is the guarantee #4115 consumes, so it
        # must not silently widen to ``Any``.
        profiles: list[AgentProfile] = self._registry.list_all()
        return profiles

    def invoke(
        self,
        request_text: str,
        profile_hint: str | None = None,
        actor: str = "unknown",
        mode_of_work: ModeOfWork | None = None,
        *,
        action_hint: str | None = None,
        mission_id: str | None = None,
        wp_id: str | None = None,
    ) -> InvocationPayload:
        """Route the request, load governance context, write started record, return payload.

        IMPORTANT: Does NOT spawn any LLM call. Returns synchronously.
        mark_loaded=False ensures first-load state for specify/plan/implement/review
        is NOT poisoned by invocation calls.

        Args:
            action_hint: Optional caller-supplied action key. When supplied alongside
                ``profile_hint``, this value replaces the role-default-verb derivation.
                Empty strings are treated as if not supplied (legacy fallback per
                EDGE-005). Has no effect on the router-backed branch.
        """
        invocation_id = _new_ulid()  # uses codebase-standard ulid library

        # 1-2a. Resolve (profile_id, action), the advisory model-routing
        # recommendation, the governance context, and the glossary scan --
        # PR-BOUNDARY-001: shared read-only wiring, see
        # _resolve_routing_and_context()'s docstring for exactly what it
        # does and does not do.
        resolution = self._resolve_routing_and_context(
            request_text,
            profile_hint,
            actor,
            invocation_id=invocation_id,
            action_hint=action_hint,
            explicit_hint_router_confidence=None,  # invoke()'s explicit-hint branch leaves this None
        )
        profile = resolution.profile
        action = resolution.action
        router_confidence = resolution.router_confidence
        empty_charter_fallback = resolution.empty_charter_fallback
        alternatives = resolution.alternatives
        recommendation = resolution.recommendation
        ctx_result = resolution.ctx_result
        ctx_hash = resolution.ctx_hash
        ctx_available = resolution.ctx_available
        bundle = resolution.bundle

        catalog_candidate = recommendation.catalog_candidate if recommendation is not None else None
        durable_model_id = catalog_candidate.model_id if catalog_candidate is not None else None

        # 3. Write started record (raises InvocationWriteError on fs failure)
        started_at = now_utc_iso()
        record = OpStartedEvent(
            invocation_id=invocation_id,
            profile_id=profile.profile_id,
            action=action,
            request_text=request_text,
            governance_context_hash=ctx_hash,
            governance_context_available=ctx_available,
            actor=actor,
            router_confidence=router_confidence,
            started_at=started_at,
            # mode_of_work is required in schema v2; default legacy callers to
            # task_execution (matches the WP05 migration default).
            mode_of_work=mode_of_work.value if mode_of_work else ModeOfWork.TASK_EXECUTION.value,
            mission_id=mission_id,
            wp_id=wp_id,
            model_id=durable_model_id,
        )
        self._writer.write_started(record)  # raises InvocationWriteError → non-zero exit

        # Step 5: Write glossary observation to trail (best-effort)
        try:  # noqa: SIM105
            self._writer.write_glossary_observation(invocation_id, bundle)
        except Exception:  # noqa: BLE001
            pass

        # Propagate started event (non-blocking, best-effort)
        if self._propagator is not None:
            self._propagator.submit(record)

        return InvocationPayload(
            invocation_id=invocation_id,
            profile_id=profile.profile_id,
            profile_friendly_name=profile.name,  # AgentProfile.name (not friendly_name — that field does not exist)
            action=action,
            governance_context_text=ctx_result.text,
            governance_context_hash=ctx_hash,
            governance_context_available=ctx_available,
            router_confidence=router_confidence,
            glossary_observations=bundle,
            mode_of_work=record.mode_of_work,
            recommendation=recommendation,
            empty_charter_fallback=empty_charter_fallback,
            alternatives=alternatives,  # WP2/#3840 (FR-005)
        )

    def _resolve_routing_and_context(
        self,
        request_text: str,
        profile_hint: str | None,
        actor: str,
        *,
        invocation_id: str,
        action_hint: str | None = None,
        explicit_hint_router_confidence: str | None = None,
    ) -> _RoutingResolution:
        """Read-only routing-resolution + governance-context wiring shared by
        ``invoke()`` and ``dry_run()`` (PR-BOUNDARY-001).

        Resolves ``(profile, action)``, computes the FR-004 advisory
        model-routing recommendation, assembles the governance context
        (``mark_loaded=False`` — never poisons first-load state), and runs
        the glossary chokepoint scan. Returns a :class:`_RoutingResolution`.

        Deliberately does NOT: mint an ``invocation_id`` (the caller supplies
        one), construct an ``OpStartedEvent``, call
        ``self._writer.write_started``/``write_glossary_observation``, or
        call ``self._propagator.submit``. All of that write-side behaviour
        stays in ``invoke()`` only, entirely after this helper returns — so
        this extraction cannot couple the write path to ``dry_run()``.

        ``invocation_id`` is passed straight through to the glossary
        chokepoint call: ``invoke()`` passes its freshly-minted ULID;
        ``dry_run()`` passes ``""``, the explicit falsy value that
        structurally suppresses the persisted ``TermCandidateObserved``
        write via ``GlossaryChokepoint``'s own
        ``if not invocation_id: return None`` gate (chokepoint.py, untouched
        by this extraction) — FR-003's guarantee, not a runtime ``if`` added
        here.

        ``action_hint``/``explicit_hint_router_confidence`` capture the one
        real behavioural difference between the two callers' explicit-hint
        branches: ``invoke()`` accepts an optional caller-supplied
        ``action_hint`` (empty string treated as not supplied, EDGE-005) and
        leaves ``router_confidence`` at ``None``; ``dry_run()`` has no
        ``action_hint`` parameter of its own (so it always passes ``None``,
        and ``action_hint or self._derive_action_from_request(...)`` reduces
        to the plain derivation call) and pins ``router_confidence`` to
        ``"exact"`` (FR-008 / spec.md Acceptance Scenario 2) — a deliberate,
        pre-existing asymmetry this extraction preserves rather than resolves.
        """
        router_confidence: str | None = None
        empty_charter_fallback = False
        # WP2/#3840 (FR-005): the explicit-hint branch below never calls
        # route(), so there are no candidates to report -- [] unless the
        # router branch below overwrites it with RouterDecision.alternatives.
        alternatives: list[dict[str, str]] = []
        if profile_hint is not None:
            profile = self._registry.resolve(profile_hint)  # raises ProfileNotFoundError
            # FR-009/FR-010/FR-011/EDGE-005: when caller supplies a truthy action_hint,
            # use it verbatim; otherwise fall back to the legacy role-default-verb
            # derivation. Truthiness (not `is not None`) means empty-string falls back.
            action = action_hint or self._derive_action_from_request(request_text, profile.role)
            router_confidence = explicit_hint_router_confidence
        elif self._router is not None:
            # WP02/#3064: pre-check the composite empty-charter predicate BEFORE
            # routing. resolve_generic_fallback returns a RouterDecision only when
            # the charter is wholly empty (Decision 2/3, research.md); otherwise it
            # returns None and route() runs exactly as before. This does NOT touch
            # ProfileRegistry or the shared activation gate -- explicit --profile
            # (the branch above) is never affected by this pre-check.
            fallback_decision = resolve_generic_fallback(self._repo_root, request_text)
            # route() returns RouterDecision or raises RouterAmbiguityError (never returns error)
            result: RouterDecision = fallback_decision or self._router.route(request_text)
            profile = self._registry.resolve(result.profile_id)
            action = result.action
            router_confidence = result.confidence
            empty_charter_fallback = fallback_decision is not None
            alternatives = result.alternatives  # WP2/#3840 (FR-005)
        else:
            raise RuntimeError("No profile_hint and no router configured. Use 'spec-kitty dispatch \"<request>\" --profile <profile>' or supply a router.")

        # FR-004: advisory model-routing recommendation, non-fatal (NFR-002/C-001).
        recommendation = _compute_recommendation(profile, action)

        # 2. Assemble governance context (mark_loaded=False — critical)
        # NEVER pass mark_loaded=True here — would corrupt context-state.json
        # and break the specify/plan first-load detection.
        # WP03/#3064: thread the already-known empty-charter-fallback signal
        # through as suppress_project_resolver so the compact governance
        # block does not merge the project catalog-fallback directive canon
        # (research.md Decision 4 — see charter/compact.py:render_compact_view
        # for the full rationale). A declared, bounded, out-of-map coupled
        # edit to charter/context.py (owned by WP06) — no other caller of
        # build_charter_context passes this kwarg, so behaviour there is
        # unchanged.
        ctx_result = build_charter_context(
            self._repo_root,
            profile=profile.profile_id,
            action=action,
            mark_loaded=False,
            suppress_project_resolver=empty_charter_fallback,
        )
        ctx_hash = hashlib.sha256(ctx_result.text.encode()).hexdigest()[:16]  # noqa: TID251 - production raw SHA-256 owner
        ctx_available = ctx_result.mode != "missing"

        # 2a. Run glossary chokepoint scan (T016/T017)
        # Severity routing: bundle.high_severity = HIGH only; bundle.all_conflicts = all severities.
        # This routing is performed inside GlossaryChokepoint._run_inner() (WP02 code).
        # Exception guard: any failure returns an error-bundle; the invocation always continues.
        from glossary.chokepoint import GlossaryChokepoint, GlossaryObservationBundle

        try:
            if self._chokepoint is None:
                self._chokepoint = GlossaryChokepoint(self._repo_root)
            bundle = self._chokepoint.run(
                request_text,
                invocation_id=invocation_id,
                actor_id=actor,
            )
        except Exception as _exc:  # noqa: BLE001
            logger.warning("glossary chokepoint outer exception (invocation_id=%r): %r", invocation_id, _exc)
            bundle = GlossaryObservationBundle(matched_urns=(), high_severity=(), all_conflicts=(), tokens_checked=0, duration_ms=0.0, error_msg=repr(_exc))

        return _RoutingResolution(
            profile=profile,
            action=action,
            router_confidence=router_confidence,
            empty_charter_fallback=empty_charter_fallback,
            alternatives=alternatives,
            recommendation=recommendation,
            ctx_result=ctx_result,
            ctx_hash=ctx_hash,
            ctx_available=ctx_available,
            bundle=bundle,
        )

    def dry_run(
        self,
        request_text: str,
        profile_hint: str | None = None,
        actor: str = "unknown",
    ) -> InvocationPayload:
        """Route the request and assemble governance context; write NOTHING.

        A sibling of :meth:`invoke`, not a boolean flag threaded through it:
        calls the same read-only ``_resolve_routing_and_context()`` helper
        ``invoke()`` uses (routing resolution, the advisory model-routing
        recommendation, governance-context assembly, the glossary scan) and
        never reaches ``invoke()``'s write half at all. This method body
        never mints or passes a truthy ``invocation_id`` -- FR-003's
        structural guarantee, not a runtime ``if`` guard: it calls
        ``_resolve_routing_and_context(..., invocation_id="", ...)``, an
        explicit falsy value, so ``GlossaryChokepoint._build_event_context``'s
        existing ``if not invocation_id: return None`` gate (chokepoint.py,
        unchanged by this mission) suppresses the persisted
        ``TermCandidateObserved`` write before it is ever attempted. This
        method never calls ``self._writer.write_started``,
        ``self._writer.write_glossary_observation``, or
        ``self._propagator.submit`` anywhere in its body.

        ``RouterAmbiguityError`` propagates unchanged out of ``route()`` --
        no internal catch, exactly as ``invoke()`` does today -- covering all
        three of its error codes (``ROUTER_AMBIGUOUS``, ``ROUTER_NO_MATCH``,
        and, on the explicit-``profile_hint`` branch, ``PROFILE_NOT_FOUND``).
        A literal ``ProfileNotFoundError`` DOES reach this method's caller on
        the explicit-``profile_hint`` branch: the registry is resolved
        directly (not via ``route()``), so a bad ``--profile`` raises it here.
        Only the no-hint branch surfaces a miss as
        ``RouterAmbiguityError(error_code="PROFILE_NOT_FOUND")`` from ``route()``.
        """
        # FR-008 (spec.md Acceptance Scenario 2): the dry-run payload
        # contract pins "exact" for the explicit-hint branch, matching
        # ActionRouter.route()'s own Level-1 explicit-hint confidence value.
        # This intentionally does NOT mirror invoke()'s own explicit-hint
        # branch, which bypasses route() entirely at the executor level and
        # leaves router_confidence None there — a pre-existing invoke()-only
        # quirk this WP does not touch.
        resolution = self._resolve_routing_and_context(
            request_text,
            profile_hint,
            actor,
            invocation_id="",
            explicit_hint_router_confidence="exact",
        )

        # No write_started, no write_glossary_observation, no
        # propagator.submit, no invocation_id minted anywhere above -- this
        # is dry_run()'s entire reason to exist.
        return InvocationPayload(
            invocation_id="",
            profile_id=resolution.profile.profile_id,
            profile_friendly_name=resolution.profile.name,
            action=resolution.action,
            governance_context_text=resolution.ctx_result.text,
            governance_context_hash=resolution.ctx_hash,
            governance_context_available=resolution.ctx_available,
            router_confidence=resolution.router_confidence,
            glossary_observations=resolution.bundle,
            mode_of_work=None,
            recommendation=resolution.recommendation,
            empty_charter_fallback=resolution.empty_charter_fallback,
            alternatives=resolution.alternatives,  # WP2/#3840 (FR-005)
        )

    def complete_invocation(
        self,
        invocation_id: str,
        outcome: Literal["done", "failed", "abandoned"],
        evidence_ref: str | None = None,
        artifact_refs: list[str] | None = None,
        commit_sha: str | None = None,
        *,
        closed_by: Literal["agent", "doctor_sweep"],
    ) -> OpCompletedEvent:
        """Close an open invocation record and propagate the completed event.

        Wraps ``InvocationWriter.write_completed`` so that the completed record
        is also submitted to the SaaS propagator (non-blocking, best-effort).

        ``outcome`` is required (schema v2): callers must be explicit; a missing
        outcome is a usage error at the CLI boundary, never silently "done".
        ``closed_by`` is keyword-only and default-free (FR-003 / C-001): every
        close records the closing actor explicitly — a default of "agent" would
        let the doctor sweep silently misattribute closes.

        Raises ``AlreadyClosedError`` if already closed (idempotent guard).
        Raises ``InvocationError`` if invocation_id is not found.
        Raises ``InvocationWriteError`` on filesystem failure.
        Raises ``InvalidModeForEvidenceError`` if evidence_ref is supplied on an
            non-evidence-eligible invocation (FR-009), or its
            ``UndeterminedModeForEvidenceError`` subclass when the record's
            ``mode_of_work`` cannot be read at all (#3030). This is a pre-write
            check — no JSONL lines are written if this error is raised.

        Recording surface (#4397): an agent close appends the ``completed``
        event to the per-record file, which is legal because the record was
        minted this session (new archive history). A doctor-sweep close targets
        records that are pre-existing archive history — byte-frozen under the
        historical-preservation gate — so its closure is recorded on the
        append-only closure spine ``kitty-ops/op-closures.jsonl`` instead, and
        the per-record file is never touched. The sweep still closes through
        this executor (research R4): the spine append IS the canonical close
        path's write for the sweep caller.
        """
        # Step 1: Read started event for mode enforcement (FR-009).
        started_mode = self._read_started_mode(invocation_id)

        # Step 2: Enforce mode gate on evidence promotion BEFORE any write.
        # Scoped to the promotion: an Op whose mode cannot be read must still be
        # closable, or an unreadable field would strand the record forever.
        if evidence_ref is not None and not mode_permits_evidence(started_mode):
            if isinstance(started_mode, _UndeterminedMode):
                raise UndeterminedModeForEvidenceError(invocation_id, started_mode.raw)
            # mode_permits_evidence() only rejects ADVISORY / QUERY here; absence
            # (None) is permissive, so started_mode is a ModeOfWork by exhaustion.
            raise InvalidModeForEvidenceError(invocation_id, ModeOfWork(started_mode))

        # Both recording paths share the closure spine as an idempotency
        # authority. Without this guard, an agent close can append to a
        # byte-frozen record after the doctor sweep already closed it there.
        #
        # A doctor sweep closes many Ops through one executor; reading the
        # ever-growing spine per Op is quadratic (#4424). The sweep therefore
        # consults a per-executor snapshot read once here and extended after each
        # append (``_close_on_spine``). The snapshot is point-in-time: a closure
        # appended by another process mid-sweep is invisible to it, so a
        # duplicate spine line can be appended for an already-closed Op. That is
        # harmless — every closure consumer (``closed_invocation_ids``, this
        # guard) uses set membership and the sweep commits the spine once, so a
        # duplicate only inflates a *concurrent* sweep's reported ``swept`` count,
        # never corrupts state (#4467). An agent close is a single close, so it
        # reads the spine fresh.
        if closed_by == "doctor_sweep":
            if self._doctor_sweep_closed_ids is None:
                self._doctor_sweep_closed_ids = closed_invocation_ids(self._repo_root)
            already_closed = invocation_id in self._doctor_sweep_closed_ids
        else:
            already_closed = invocation_id in closed_invocation_ids(self._repo_root)
        if already_closed:
            raise AlreadyClosedError(invocation_id)

        # Step 3: Append the completed event to its recording surface.
        # Agent closes append to the per-record file (minted this session);
        # the doctor sweep records on the append-only closure spine because
        # its targets are pre-existing, byte-frozen archive records (#4397).
        completed = OpCompletedEvent(
            invocation_id=invocation_id,
            completed_at=now_utc_iso(),
            outcome=outcome,
            closed_by=closed_by,
            evidence_ref=evidence_ref,
        )
        if closed_by == "doctor_sweep":
            self._close_on_spine(completed)
        else:
            self._writer.write_completed(completed)

        # Step 4: Promote to Tier 2 evidence artifact if --evidence was supplied (existing behaviour).
        self._promote_evidence_if_requested(completed, evidence_ref)

        # Step 5 (NEW): Append artifact_link events (FR-007).
        self._append_artifact_links(invocation_id, artifact_refs)

        # Step 6 (NEW): Append commit_link event (FR-007).
        self._append_commit_link(invocation_id, commit_sha)

        # Step 7: Propagate completed event (non-blocking, best-effort; existing behaviour).
        # Correlation events (artifact_link, commit_link) are locally written by
        # append_correlation_link() above but are NOT submitted to the propagator in
        # this release. The policy gate in projection_policy.py is implemented (and
        # POLICY_TABLE assigns project=True for task_execution/mission_step correlation
        # events), but the dict-record submission path in _propagate_one is not yet
        # wired. SaaS projection of correlation events is deferred consistent with the
        # ADR-004 local-only stance for Tier 2 content in the 3.2.x line. See
        # propagator.py NOTE and docs/trail-model.md "Correlation Links" section.
        if self._propagator is not None:
            self._propagator.submit(completed)

        self._commit_op_record(invocation_id, closed_by=closed_by)
        return completed

    def _close_on_spine(self, completed: OpCompletedEvent) -> None:
        """Record a doctor-sweep closure on the append-only closure spine.

        The sweep's targets are pre-existing ``kitty-ops/`` records — byte-frozen
        archive history under the preservation gate — so the closure is appended
        to ``kitty-ops/op-closures.jsonl`` and the per-record file is never
        touched (#4397). Idempotent like ``write_completed``: raises
        ``AlreadyClosedError`` when the per-record file already carries a
        ``completed`` event (concurrent manual close) or the spine already
        carries a closure for this invocation.
        """
        invocation_id = completed.invocation_id
        path = self._writer.invocation_path(invocation_id)
        try:
            rows = [_json_mod.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, _json_mod.JSONDecodeError) as exc:
            raise InvocationError(f"Invocation record is unreadable: {invocation_id}") from exc
        if any(isinstance(row, dict) and row.get("event") == "completed" for row in rows):
            raise AlreadyClosedError(invocation_id)
        # The spine-membership idempotency check already ran once, snapshot-backed,
        # in ``complete_invocation`` (the shared #4397 guard); re-reading the spine
        # here would restore the per-Op quadratic cost this fix removes (#4424).
        # Extend the snapshot so a later close in the same sweep sees this id.
        append_op_closure(self._repo_root, completed)
        if self._doctor_sweep_closed_ids is not None:
            self._doctor_sweep_closed_ids.add(invocation_id)

    def _promote_evidence_if_requested(
        self,
        completed: OpCompletedEvent,
        evidence_ref: str | None,
    ) -> None:
        if evidence_ref is None:
            return
        content = self._resolve_evidence_content(evidence_ref)
        evidence_base_dir = self._repo_root / ".kittify" / "evidence"
        promote_to_evidence(completed, evidence_base_dir, content)

    def _resolve_evidence_content(self, evidence_ref: str) -> str:
        candidate_path = self._resolve_evidence_path(evidence_ref)
        try:
            return candidate_path.read_text(encoding="utf-8") if candidate_path is not None else evidence_ref
        except OSError:
            return evidence_ref

    def _resolve_evidence_path(self, evidence_ref: str) -> Path | None:
        evidence_path = Path(evidence_ref)
        if evidence_path.is_absolute():
            return evidence_path

        repo_root = self._repo_root.resolve()
        resolved_relative_path = (repo_root / evidence_path).resolve()
        if resolved_relative_path.is_relative_to(repo_root):
            return resolved_relative_path
        return None

    def _append_artifact_links(
        self,
        invocation_id: str,
        artifact_refs: list[str] | None,
    ) -> None:
        for raw_ref in artifact_refs or []:
            normalised = normalise_ref(raw_ref, self._repo_root)
            self._writer.append_correlation_link(
                invocation_id,
                kind="artifact",
                ref=normalised,
            )

    def _append_commit_link(self, invocation_id: str, commit_sha: str | None) -> None:
        if commit_sha is None:
            return
        self._writer.append_correlation_link(invocation_id, sha=commit_sha)

    def _read_started_mode(self, invocation_id: str) -> ModeOfWork | None | _UndeterminedMode:
        """Read ``mode_of_work`` from the started event, keeping three states apart.

        ``None`` means the record carries no mode (a pre-mission record) and
        keeps its documented legacy default; :class:`_UndeterminedMode` means
        the record declares something no reader can map to a ``ModeOfWork``.
        The two used to collapse into one ``None`` that skipped FR-009
        enforcement entirely, so a single mangled string bought evidence
        promotion on an advisory or query Op (#3030).
        """
        path = self._writer.invocation_path(invocation_id)
        if not path.exists():
            raise InvocationError(f"Invocation record not found: {invocation_id}")
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        first = _json_mod.loads(first_line)
        return classify_mode_of_work(first.get("mode_of_work"))

    def _read_started_event(self, invocation_id: str) -> dict[str, object]:
        path = self._writer.invocation_path(invocation_id)
        try:
            first_line = path.read_text(encoding="utf-8").splitlines()[0]
            data = _json_mod.loads(first_line)
        except (IndexError, OSError, _json_mod.JSONDecodeError) as exc:
            raise InvocationError(f"Invalid invocation record: {invocation_id}") from exc
        if not isinstance(data, dict):
            raise InvocationError(f"Invalid invocation record: {invocation_id}")
        return data

    def _current_branch(self) -> str | None:
        inside = _subprocess.run(
            ["git", "-C", str(self._repo_root), "rev-parse", "--is-inside-work-tree"],
            check=False,
            capture_output=True,
            text=True,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None

        symbolic = _subprocess.run(
            ["git", "-C", str(self._repo_root), "symbolic-ref", "--quiet", "--short", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if symbolic.returncode == 0:
            branch = symbolic.stdout.strip()
            if branch:
                return branch

        abbrev = _subprocess.run(
            ["git", "-C", str(self._repo_root), "rev-parse", "--abbrev-ref", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
        if abbrev.returncode == 0:
            branch = abbrev.stdout.strip()
            if branch and branch != "HEAD":
                return branch
        return None

    def _commit_op_record(self, invocation_id: str, *, closed_by: Literal["agent", "doctor_sweep"]) -> OpCommitOutcome:
        """Best-effort git commit for one completed Op record.

        Agent closes commit the per-record file; a doctor-sweep close commits
        only the append-only closure spine — committing a modified pre-existing
        per-record file is exactly what the historical-preservation gate
        forbids (#4397).

        Returns the outcome instead of only logging (#4397): a refused or
        failed auto-commit stays best-effort (the event is already durably on
        disk) but is now visible and actionable through ``self.last_op_commit``
        — the doctor sweep reports it per entry and the CLI complete path
        prints it — rather than dying in a ``logger.warning``.
        """
        try:
            started = self._read_started_event(invocation_id)
            profile_id = str(started.get("profile_id") or "unknown")
            action = str(started.get("action") or "unknown")
            if closed_by == "doctor_sweep":
                relative_path = OP_CLOSURES_RELATIVE_PATH
                message = f"op({profile_id}): {action} [{invocation_id[:8]}] (doctor sweep)"
            else:
                op_path = self._writer.invocation_path(invocation_id)
                relative_path = op_path.relative_to(self._repo_root)
                message = f"op({profile_id}): {action} [{invocation_id[:8]}]"

            current_branch = self._current_branch()
            if current_branch is None:
                return self._record_op_commit(OpCommitOutcome(committed=False, refusal="not a git worktree"))

            safe_commit(
                repo_root=self._repo_root,
                worktree_root=self._repo_root,
                target=CommitTarget(ref=current_branch),
                message=message,
                paths=(relative_path,),
                # Op-record auto-commit targets the operator's CURRENT branch,
                # which can be protected main; STANDARD asserts no
                # protected-branch flow, so the guard refuses there and the
                # outcome below carries the refusal (the Op record stays on
                # disk). The documented operator hatch
                # (SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS) lands it for
                # solo-fork operators who own main (FR-008).
                capability=GuardCapability.STANDARD,
            )
            return self._record_op_commit(OpCommitOutcome(committed=True))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Op record auto-commit failed for %s: %r", invocation_id, exc)
            return self._record_op_commit(OpCommitOutcome(committed=False, refusal=repr(exc)))

    def _record_op_commit(self, outcome: OpCommitOutcome) -> OpCommitOutcome:
        """Store the latest auto-commit outcome for caller visibility (#4397)."""
        self.last_op_commit = outcome
        return outcome

    def _derive_action_from_request(self, request_text: str, role: object) -> str:  # noqa: ARG002
        """Derive canonical action token from role when profile_hint is explicit."""
        from charter.profiles import DEFAULT_ROLE_CAPABILITIES, Role

        caps = DEFAULT_ROLE_CAPABILITIES.get(role) if isinstance(role, Role) else None
        if caps and caps.canonical_verbs:
            # charter.profiles is mypy-quarantined (follow_imports=skip), so
            # ``caps`` resolves to ``Any``; the verb is a str at runtime.
            return str(caps.canonical_verbs[0])
        return "review"  # default fallback
