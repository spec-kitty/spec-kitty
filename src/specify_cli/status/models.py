"""Canonical status models for spec-kitty work package lifecycle.

Defines the 9-lane state machine data types: Lane enum, StatusEvent,
DoneEvidence (with ReviewApproval, RepoEvidence, VerificationResult),
StatusSnapshot, AgentAssignment, and RetrospectiveSnapshot.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar, Literal, Optional, TypeAlias

from pydantic import BaseModel

from specify_cli.identity.aliases import with_tracked_mission_slug_aliases
from specify_cli.mission_metadata import mission_identity_fields
from specify_cli.retrospective.schema import Mode


class Lane(StrEnum):
    """Canonical work package lifecycle states.

    ``GENESIS`` is the pre-finalize state of a work package that has been
    created (``WPCreated``) but not yet seeded into the lane lifecycle. It is
    distinct from ``PLANNED`` so that ``finalize-tasks`` seeds a real
    ``genesis -> planned`` transition instead of a no-op ``planned -> planned``
    self-transition, and so the lane-state readers never silently default an
    unfinalized WP to ``planned``.

    ``GENESIS`` is a *non-display* lane: it is never the current lane of a
    materialized WP (an unseeded WP has no lane events and so is absent from the
    snapshot; once seeded it is ``planned``). It therefore does not appear on
    the kanban board or in the board summary. The nine post-genesis states
    (``PLANNED``..``CANCELED``) are the active, displayed lifecycle lanes.

    ``UNINITIALIZED`` is a *non-display, non-transitionable read sentinel*
    returned by the lane-reader surface (``lane_reader.get_wp_lane`` /
    ``get_all_wp_lanes``) when a WP is **absent from the reduced snapshot**
    (no events yet) or the event log **exists but is empty**. It is
    deliberately **distinct** from ``GENESIS``: ``GENESIS`` means "seeded WP
    on an unseeded lane" (has a ``WPCreated`` event, pre-finalize), while
    ``UNINITIALIZED`` means "no lane events exist for this WP at all" (a pure
    read-time absence marker). ``UNINITIALIZED`` is never persisted to the
    event log, never appears as a ``from_lane``/``to_lane`` in a transition,
    and never appears in a display summary — see ``NON_DISPLAY_LANES`` below,
    which is the single canonical authority for "which lanes never display."
    """

    GENESIS = "genesis"
    UNINITIALIZED = "uninitialized"
    PLANNED = "planned"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    FOR_REVIEW = "for_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    DONE = "done"
    BLOCKED = "blocked"
    CANCELED = "canceled"


# Single canonical authority for "which lanes never display" (charter
# single-canonical-authority principle). ``GENESIS`` (seeded-but-unfinalized)
# and ``UNINITIALIZED`` (absent-from-snapshot read sentinel) are both
# non-display: neither is ever the current lane of a materialized,
# board-visible WP. Every display-filter site (reducer summaries, board
# roster builders, kanban grouping) MUST consume this constant instead of
# inlining an ``is not Lane.GENESIS``-style check, so a future non-display
# lane cannot silently leak into a summary from a forgotten fifth site.
NON_DISPLAY_LANES: frozenset[Lane] = frozenset({Lane.GENESIS, Lane.UNINITIALIZED})


def get_all_lanes() -> tuple[Lane, ...]:
    """Return all Lane enum members as a tuple.

    Use this instead of hardcoding lane lists or counts.
    Tests and production code should derive lane-dependent values from this.
    """
    return tuple(Lane)


def get_all_lane_values() -> frozenset[str]:
    """Return all canonical lane string values as a frozenset.

    Convenience for validators and mapping checks that operate on strings.
    """
    return frozenset(lane.value for lane in Lane)


ULID_PATTERN = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")

#: A subtask's completion status reuses the canonical lane/status enum
#: vocabulary (``Lane``) rather than introducing a divergent string type
#: (data-model.md §WPInnerStateDelta). A subtask is "done" when its status is
#: ``Lane.DONE``.
Status = Lane


#: The ``actor`` on a ``StatusEvent`` / ``InnerStateChanged`` is EITHER a plain
#: ``str`` identity (the common case) OR a ``{role, profile, tool, model}``
#: structured *resolved binding* (FR-015 / IC-09). The dict form is the delivery
#: vehicle that lets the SaaS fan-out ride the transition's *resolved* identity;
#: ``spec_kitty_events`` 6.1.0 ``StatusTransitionPayload.actor`` already accepts
#: ``Union[str, Dict]``, so no shared-package change is needed to carry it.
ActorField: TypeAlias = str | dict[str, str | None]

_STRUCTURED_ACTOR_FIELDS = ("role", "profile", "tool", "model")


def decode_actor(value: Any) -> ActorField:
    """Decode a wire ``actor`` value, preserving a structured (dict) actor.

    A resolved-binding actor is a ``{role, profile, tool, model}`` dict that MUST
    survive the ``status.events.jsonl`` round-trip uncorrupted. The legacy
    ``from_dict`` decoders coerced *every* actor with ``str(...)`` — silently
    flattening such a dict to its ``repr`` (``"{'role': …}"``) with **no**
    exception (the load-bearing silent-corruption trap, FR-015). This decoder
    validates and copies the dict so only those four keys with ``str | None``
    values can cross the persistence/fan-out boundary. Every other value is
    coerced to ``str`` (the legacy string-actor contract).
    """
    if isinstance(value, dict):
        expected = set(_STRUCTURED_ACTOR_FIELDS)
        actual = set(value)
        if actual != expected:
            raise ValueError(
                "structured actor must contain exactly "
                f"{sorted(expected)!r}; got {sorted(actual)!r}"
            )
        decoded: dict[str, str | None] = {}
        for field_name in _STRUCTURED_ACTOR_FIELDS:
            field_value = value[field_name]
            if field_value is not None and not isinstance(field_value, str):
                raise ValueError(
                    "structured actor fields must be strings or null; "
                    f"{field_name!r} was {type(field_value).__name__}"
                )
            decoded[field_name] = field_value
        return decoded
    return str(value)


def actor_identity_str(actor: ActorField) -> str:
    """Project an actor to its plain-string identity for guard / snapshot / display.

    A structured (dict) resolved-binding actor projects to its ``tool`` (the agent
    identity a plain-string actor already carries), falling back to ``role`` then
    ``""``. A ``str`` actor is returned verbatim. This keeps guard inputs and the
    reduced-snapshot ``actor`` slot ``str``-typed for the ``.strip()``/display
    consumers, while the dict itself still rides ``StatusEvent.actor`` to the SaaS
    fan-out untouched (the snapshot slot is a display identity, not the binding).
    """
    if isinstance(actor, dict):
        identity = actor.get("tool") or actor.get("role") or ""
        return str(identity)
    return actor


@dataclass(frozen=True)
class CurrentWpState:
    """Current WP state resolved from a single in-transaction reduction.

    Returned by ``read_current_wp_state_transactional`` and derived by
    ``wp_lane_actor_from_events`` from the SAME reduction (C-002: no second
    reduce, no split-brain identity reader). ``role`` is the already-reduced
    resolved-binding ``role`` slot — carried, never re-derived by splitting the
    actor string (#2861). It may be blank/``None`` (a binding-less claim records
    no role, so collision detection downstream is best-effort).

    An unseeded WP (no events / absent from the snapshot) yields
    ``CurrentWpState(Lane.GENESIS, None, None)``.
    """

    lane: Lane
    actor: str | None
    role: str | None


@dataclass(frozen=True)
class RepoEvidence:
    """Evidence of code changes in a repository."""

    repo: str
    branch: str
    commit: str  # 7-40 hex chars
    files_touched: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "repo": self.repo,
            "branch": self.branch,
            "commit": self.commit,
        }
        if self.files_touched:
            d["files_touched"] = list(self.files_touched)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RepoEvidence:
        return cls(
            repo=data["repo"],
            branch=data["branch"],
            commit=data["commit"],
            files_touched=data.get("files_touched", []),
        )


@dataclass(frozen=True)
class VerificationResult:
    """Result of a verification command (test suite, linter, etc.)."""

    command: str
    result: str  # "pass", "fail", or "skip"
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "result": self.result,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VerificationResult:
        return cls(
            command=data["command"],
            result=data["result"],
            summary=data["summary"],
        )


@dataclass(frozen=True)
class ReviewApproval:
    """Reviewer approval or change request record."""

    reviewer: str
    verdict: str  # "approved" or "changes_requested"
    reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "reviewer": self.reviewer,
            "verdict": self.verdict,
            "reference": self.reference,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewApproval:
        return cls(
            reviewer=data["reviewer"],
            verdict=data["verdict"],
            reference=data["reference"],
        )


@dataclass(frozen=True)
class DoneEvidence:
    """Evidence payload required for done transitions."""

    review: ReviewApproval
    repos: list[RepoEvidence] = field(default_factory=list)
    verification: list[VerificationResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"review": self.review.to_dict()}
        if self.repos:
            d["repos"] = [r.to_dict() for r in self.repos]
        if self.verification:
            d["verification"] = [v.to_dict() for v in self.verification]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DoneEvidence:
        return cls(
            review=ReviewApproval.from_dict(data["review"]),
            repos=[RepoEvidence.from_dict(r) for r in data.get("repos", [])],
            verification=[VerificationResult.from_dict(v) for v in data.get("verification", [])],
        )


@dataclass(frozen=True)
class ReviewResult:
    """Structured review outcome required for all outbound in_review transitions.

    Unifies the currently asymmetric approval (DoneEvidence.review: ReviewApproval)
    and rejection (review_ref: str) recording paths into a single typed contract.
    """

    reviewer: str
    verdict: str  # "approved" or "changes_requested"
    reference: str  # Approval ref or feedback:// URI
    feedback_path: str | None = None  # Resolved path to feedback file (rejection only)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "reviewer": self.reviewer,
            "verdict": self.verdict,
            "reference": self.reference,
        }
        if self.feedback_path is not None:
            data["feedback_path"] = self.feedback_path
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewResult:
        return cls(
            reviewer=data["reviewer"],
            verdict=data["verdict"],
            reference=data["reference"],
            feedback_path=data.get("feedback_path"),
        )


@dataclass(frozen=True)
class StatusEvent:
    """Immutable record of a single lane transition.

    Each event is one line in status.events.jsonl.

    Wire-format evolution (FR-023, ADR 2026-04-09-1):
    - Legacy events: carry only ``mission_slug`` for mission identity.
    - New events (post-WP05): carry both ``mission_slug`` AND ``mission_id``
      (the ULID from meta.json).  ``mission_id`` is the canonical
      machine-facing identity; ``mission_slug`` is retained for human
      readability and backward compatibility.
    """

    event_id: str  # ULID
    mission_slug: str  # e.g. "034-feature-name"
    wp_id: str  # e.g. "WP01"
    from_lane: Lane
    to_lane: Lane
    at: str  # ISO 8601 UTC
    # ``str`` identity OR a ``{role, profile, tool, model}`` structured resolved
    # binding (FR-015 / IC-09). Widened from bare ``str`` so a dispatch-resolved
    # dict actor rides the transition to ``_saas_fan_out`` and round-trips the
    # JSONL uncorrupted; see :data:`ActorField` / :func:`decode_actor`.
    actor: ActorField
    force: bool
    execution_mode: str  # "worktree" or "direct_repo"
    reason: str | None = None
    # Provenance discriminator for the human ``reason`` (FR-001, mission
    # completion-terminal-state). ``"operator"`` iff the reason was authored by
    # the operator (a non-empty ``--note``); ``"synthetic"`` for the CLI's
    # auto-backfilled default (``"Force move to <lane>"`` / ``"move-task: …"``).
    # ``None`` for legacy events written before this field existed (NFR-002) and
    # for transitions where provenance is not tracked (only cancellations set it
    # today). Emitted to the wire only when populated so pre-existing event-log
    # lines stay byte-identical.
    reason_source: str | None = None
    review_ref: str | None = None
    # One-line, human-readable gist of the transition for the NOW view
    # (#4327). Producer-supplied and producer-validated at creation
    # (``status/moment_fields.validate_summary``); the Zeitgeist bridge
    # carries it on the ``WPStatusChanged`` moment as the bounded inline
    # ``summary`` attr once the installed events codec declares the field.
    # ``None`` for every transition recorded before the option existed.
    summary: str | None = None
    evidence: DoneEvidence | None = None
    review_result: ReviewResult | None = None
    policy_metadata: dict[str, Any] | None = None
    # mission_id (ULID) added in WP05; None for legacy events read from disk
    # before the migration, or for missions that pre-date mission_id minting.
    mission_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", decode_actor(self.actor))

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "event_id": self.event_id,
            "mission_slug": self.mission_slug,
            "wp_id": self.wp_id,
            "from_lane": str(self.from_lane),
            "to_lane": str(self.to_lane),
            "at": self.at,
            "actor": self.actor,
            "force": self.force,
            "execution_mode": self.execution_mode,
            "reason": self.reason,
            "review_ref": self.review_ref,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "policy_metadata": self.policy_metadata,
        }
        if self.review_result is not None:
            d["review_result"] = self.review_result.to_dict()
        # Emit only when populated so legacy event-log lines (and their golden
        # fixtures) stay byte-identical — mirrors mission_id / review_result.
        if self.reason_source is not None:
            d["reason_source"] = self.reason_source
        if self.summary is not None:
            d["summary"] = self.summary
        if self.mission_id is not None:
            d["mission_id"] = self.mission_id
        return d

    # Legacy lane name aliases from older event log formats.
    # Note: "in_review" was formerly aliased to "for_review" but is now a
    # first-class Lane member (promoted in mission 065 WP05).
    _LANE_ALIASES: ClassVar[dict[str, str]] = {}

    @classmethod
    def _coerce_lane(cls, value: str) -> Lane:
        return Lane(cls._LANE_ALIASES.get(value, value))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StatusEvent:
        evidence_data = data.get("evidence")
        review_result_data = data.get("review_result")
        return cls(
            event_id=data["event_id"],
            mission_slug=data.get("mission_slug") or data.get("feature_slug", ""),
            wp_id=data["wp_id"],
            from_lane=cls._coerce_lane(data["from_lane"]),
            to_lane=cls._coerce_lane(data["to_lane"]),
            at=data["at"],
            # Preserve a structured (dict) resolved-binding actor on read-back;
            # a scalar is coerced to ``str`` (decode_actor guards the trap).
            actor=decode_actor(data["actor"]),
            force=data["force"],
            execution_mode=data["execution_mode"],
            reason=data.get("reason"),
            # None for legacy events written before reason_source existed (NFR-002).
            reason_source=data.get("reason_source"),
            review_ref=data.get("review_ref"),
            # None for legacy events recorded before the inline summary attr
            # existed (#4327).
            summary=data.get("summary"),
            evidence=DoneEvidence.from_dict(evidence_data) if evidence_data else None,
            review_result=(
                ReviewResult.from_dict(review_result_data)
                if review_result_data
                else None
            ),
            policy_metadata=data.get("policy_metadata"),
            mission_id=data.get("mission_id"),  # None for legacy events
        )


@dataclass(frozen=True)
class ReviewOverride:
    """Review-cycle override slot carried by an ``InnerStateChanged`` delta.

    Pinned shape (do NOT reuse the review-result shape near
    ``wp_state._check_review_result`` and do NOT invent
    ``review_artifact_override_*`` fields): WP03/WP09 reference these exact
    four fields and the :meth:`complete` predicate verbatim.
    """

    at: str
    actor: str
    wp_id: str
    reason: str

    @property
    def complete(self) -> bool:
        """True only when all four fields are non-empty."""
        return bool(self.at and self.actor and self.wp_id and self.reason)

    @property
    def is_release_sentinel(self) -> bool:
        """True only when ALL four fields are empty.

        This is the narrow "release" shape ``_mt_emit_runtime_state`` emits on
        a ``--to planned`` rollback to explicitly clear a stale override (see
        the reducer's ``_apply_annotation_delta`` docstring). It is
        deliberately narrower than ``not complete``: a *partially*-filled
        override (e.g. ``at``/``actor``/``wp_id`` present but a blank
        ``reason``, #2684 WP09) is incomplete but NOT a release sentinel — it
        must still be persisted in the snapshot (so its non-completeness keeps
        blocking the merge gate) rather than silently discarded as if no
        override attempt had ever been recorded.
        """
        return not (self.at or self.actor or self.wp_id or self.reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.at,
            "actor": self.actor,
            "wp_id": self.wp_id,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ReviewOverride:
        # Actor audit (FR-015): the ``str(...)`` coercion is DELIBERATELY kept
        # here. ``ReviewOverride.actor`` is definitionally a scalar reviewer/agent
        # identity — the resolved-binding dict actor is routed ONLY through
        # ``StatusEvent.actor`` (the transition) and the ``role``/``agent_profile``/
        # ``model``/``provider`` delta slots, NEVER through a ``ReviewOverride``. A
        # dict therefore never reaches this decoder, so the coercion cannot flatten
        # one (unlike ``InnerStateChanged.from_dict`` / ``StatusEvent.from_dict``,
        # which are in-path and use :func:`decode_actor`).
        return cls(
            at=str(data["at"]),
            actor=str(data["actor"]),
            wp_id=str(data["wp_id"]),
            reason=str(data["reason"]),
        )


@dataclass(frozen=True)
class WPInnerStateDelta:
    """Typed partial runtime-state payload for an ``InnerStateChanged`` event.

    Every field is optional; an absent (``None``) field leaves the
    corresponding reduced-snapshot slot untouched. This is deliberately a
    typed dataclass rather than a free ``dict[str, Any]`` (C-002).

    ``tracker_refs`` is the *additive* channel (unions into the snapshot slot);
    ``tracker_refs_replace`` is the *replace* channel (wholesale-replaces the
    slot) that WP08's ``--replace`` needs so a replace does not resurrect stale
    refs. Both are delta inputs; the reduced snapshot exposes a single
    ``tracker_refs`` slot.

    **Resolved-binding group (FR-013, C-008)**: ``role``, ``agent_profile``,
    ``agent_profile_version``, ``model``, ``provider`` carry the *actual*
    runtime identity that resolved and ran a WP. They are event-sourced and
    folded latest-wins by the reducer — a later pick-up/reassign replaces them
    (INV-8). These are the **resolved actual**, deliberately distinct from the
    **authored recommendation** in frontmatter (C-008): never conflate "what
    ran" with "what was designed to run". The recorded value originates from
    ``resolve_profile``/``resolved_agent()`` / dispatch resolution, never a copy
    of the frontmatter ``agent_profile`` string (C-007). Absence is valid — a
    never-reclaimed WP leaves these slots ``None``.

    **Single-source-of-truth field list (D-14 tidy-first)**: the plain
    ``str | None`` scalar fields are enumerated **once** in
    :data:`_SCALAR_FIELDS`, which backs both ``to_dict`` and ``from_dict``;
    ``is_empty`` iterates the dataclass fields directly. Adding a scalar slot is
    one field declaration plus one ``_SCALAR_FIELDS`` entry — no method carries
    a hand-maintained field list. ``shell_pid`` (int coercion) and the
    container/typed fields (``subtasks``/``note``/``tracker_refs``/
    ``tracker_refs_replace``/``review``) are genuinely non-scalar and stay
    explicit.
    """

    shell_pid: int | None = None
    shell_pid_created_at: str | None = None
    subtasks: Mapping[str, Status] | None = None
    note: str | None = None
    tracker_refs: list[str] | None = None
    tracker_refs_replace: list[str] | None = None
    agent: str | None = None
    assignee: str | None = None
    review: ReviewOverride | None = None
    # Resolved-binding actuals (FR-013) — pure ``str | None`` scalar slots
    # folded latest-wins by the reducer. Declared after ``review`` per the WP09
    # contract; picked up automatically by _SCALAR_FIELDS / is_empty.
    role: str | None = None
    agent_profile: str | None = None
    agent_profile_version: str | None = None
    model: str | None = None
    provider: str | None = None
    # Explicit claim-release marker (WP: partition-authority residuals, #2960
    # follow-up). A bare ``agent=""`` (or any blank scalar) is, by design, a
    # NO-OP over the reducer's blank-protection guard (see __post_init__ /
    # _apply_annotation_delta) — it must never clobber a real recorded value.
    # But a legitimate claim RELEASE (e.g. ``move-task --to planned``) needs a
    # way to say "clear the claim triple for real", which a per-field string
    # sentinel cannot express cleanly because the group is mixed-type
    # (``shell_pid`` is ``int | None``, not ``str | None``). This single
    # explicit ``bool`` flag is that signal: when ``True`` the reducer clears
    # ``agent``/``shell_pid``/``shell_pid_created_at`` (the claim triple,
    # FR-004) to falsy, distinct from — and unaffected by — the bare
    # empty-string no-op guard. It is a first-class part of the delta
    # contract: any caller can emit it, and the reducer honors it regardless
    # of which transition (or no transition at all) accompanies the
    # annotation. Not a member of ``_SCALAR_FIELDS`` (it is not a ``str |
    # None`` scalar) and not folded through ``_REPLACE_SLOTS`` — it is applied
    # as its own explicit step in ``_apply_annotation_delta`` (reducer.py).
    release_runtime_claim: bool = False

    #: Single authoritative list of the pure ``str | None`` scalar fields that
    #: round-trip trivially on the wire. Backs ``to_dict``/``from_dict`` (one
    #: source of truth — D-14). A new scalar slot is added here once; the two
    #: serializers pick it up as data. NOT a dataclass field (``ClassVar``).
    #: ``release_runtime_claim`` is deliberately EXCLUDED: it is a ``bool``,
    #: not a ``str | None`` scalar, and it must never be routed through the
    #: ``""`` -> ``None`` blank-protection normalization below (a ``bool`` has
    #: no ``""`` state to normalize).
    _SCALAR_FIELDS: ClassVar[tuple[str, ...]] = (
        "shell_pid_created_at",
        "agent",
        "assignee",
        "role",
        "agent_profile",
        "agent_profile_version",
        "model",
        "provider",
    )

    def __post_init__(self) -> None:
        """Write-boundary normalization (#2960 / FR-014).

        An empty-string scalar runtime slot is meaningless — it carries no
        attribution. Normalize ``""`` -> ``None`` for every ``str | None`` scalar
        field so the append-only log **never records a blanking delta**: a stray
        ``agent: ""`` (or any blank scalar) can no longer clobber a real recorded
        value when the reducer folds it. This is the durable net; the reducer's
        empty-string no-op guard is the read-side belt-and-braces for logs that
        were written before this normalization existed.
        """
        for name in self._SCALAR_FIELDS:
            if getattr(self, name) == "":
                object.__setattr__(self, name, None)

    def is_empty(self) -> bool:
        """True when the delta touches no slot (all fields ``None``).

        Iterates the dataclass fields directly, so a newly-added optional field
        is covered automatically with no hand-maintained list to keep in sync.

        ``release_runtime_claim`` is the one field this scan does NOT apply the
        ``is None`` check to: it is a ``bool`` (default ``False``, never
        ``None``), so it is checked separately — ``True`` alone makes the delta
        non-empty (a real claim-release request must actually be emitted); the
        default ``False`` never manufactures a non-empty delta on its own.
        """
        if self.release_runtime_claim:
            return False
        return all(
            getattr(self, f.name) is None
            for f in fields(self)
            if f.name != "release_runtime_claim"
        )

    def to_dict(self) -> dict[str, Any]:
        """Emit only present fields so the reducer's "absent leaves slot
        untouched" rule is unambiguous on the wire.

        Scalar fields are emitted by iterating the single ``_SCALAR_FIELDS``
        list; the non-scalar fields (``shell_pid`` int, ``subtasks``, ``note``,
        ``tracker_refs*``, ``review``) are handled explicitly.
        """
        d: dict[str, Any] = {}
        if self.shell_pid is not None:
            d["shell_pid"] = self.shell_pid
        if self.subtasks is not None:
            d["subtasks"] = {sid: str(status) for sid, status in self.subtasks.items()}
        if self.note is not None:
            d["note"] = self.note
        if self.tracker_refs is not None:
            d["tracker_refs"] = list(self.tracker_refs)
        if self.tracker_refs_replace is not None:
            d["tracker_refs_replace"] = list(self.tracker_refs_replace)
        if self.review is not None:
            d["review"] = self.review.to_dict()
        for name in self._SCALAR_FIELDS:
            value = getattr(self, name)
            if value is not None:
                d[name] = value
        if self.release_runtime_claim:
            d["release_runtime_claim"] = True
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> WPInnerStateDelta:
        subtasks_raw = data.get("subtasks")
        subtasks: dict[str, Status] | None = None
        if subtasks_raw is not None:
            subtasks = {str(sid): Status(value) for sid, value in subtasks_raw.items()}
        review_raw = data.get("review")
        review = ReviewOverride.from_dict(review_raw) if review_raw is not None else None
        shell_pid_raw = data.get("shell_pid")
        tracker_refs_raw = data.get("tracker_refs")
        tracker_refs_replace_raw = data.get("tracker_refs_replace")
        scalars: dict[str, Any] = {name: data.get(name) for name in cls._SCALAR_FIELDS}
        return cls(
            shell_pid=int(shell_pid_raw) if shell_pid_raw is not None else None,
            subtasks=subtasks,
            note=data.get("note"),
            tracker_refs=list(tracker_refs_raw) if tracker_refs_raw is not None else None,
            tracker_refs_replace=(
                list(tracker_refs_replace_raw)
                if tracker_refs_replace_raw is not None
                else None
            ),
            review=review,
            release_runtime_claim=bool(data.get("release_runtime_claim", False)),
            **scalars,
        )


@dataclass(frozen=True)
class InnerStateChanged:
    """Off-axis (non-transition) runtime-state annotation event.

    Shares the append-only ``status.events.jsonl`` file with ``StatusEvent``
    but carries **no** ``from_lane``/``to_lane`` and can never traverse the
    FSM: it bypasses ``validate_transition`` and never increments
    ``force_count``. The reducer folds its typed :class:`WPInnerStateDelta`
    into the per-WP runtime slots in a dedicated post-transition pass.
    """

    event_id: str  # ULID
    wp_id: str
    at: str  # ISO 8601 UTC
    # Widened to accept a structured resolved-binding actor for parity with
    # ``StatusEvent.actor`` (FR-015 / IC-09); ``decode_actor`` guards the
    # ``from_dict`` round-trip against the ``str(dict)`` flattening trap.
    actor: ActorField
    delta: WPInnerStateDelta
    kind: str = "annotation"

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", decode_actor(self.actor))

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "kind": self.kind,
            "wp_id": self.wp_id,
            "at": self.at,
            "actor": self.actor,
            "delta": self.delta.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> InnerStateChanged:
        """Decode an annotation dict.

        Distinct from :meth:`StatusEvent.from_dict` (which hard-requires the
        ``from_lane``/``to_lane`` keys). Validates ``event_id`` against
        ``ULID_PATTERN`` and requires ``kind == "annotation"``.
        """
        event_id = data["event_id"]
        if not isinstance(event_id, str) or not ULID_PATTERN.match(event_id):
            raise ValueError(f"InnerStateChanged.event_id is not a valid ULID: {event_id!r}")
        kind = data.get("kind")
        if kind != "annotation":
            raise ValueError(f"InnerStateChanged requires kind == 'annotation', got {kind!r}")
        delta_raw = data["delta"]
        return cls(
            event_id=event_id,
            kind=kind,
            wp_id=str(data["wp_id"]),
            at=str(data["at"]),
            # decode_actor: a dict resolved-binding actor round-trips uncorrupted;
            # a scalar is ``str``-coerced (guards the models.py corruption trap).
            actor=decode_actor(data["actor"]),
            delta=WPInnerStateDelta.from_dict(delta_raw),
        )


@dataclass(frozen=True)
class EventStream:
    """Read-shape container partitioning the event log by kind.

    ``read_event_stream`` surfaces both lane ``transitions`` and off-axis
    ``annotations`` to the reducer without changing the on-disk file. Lane
    events continue to flow through the existing ``read_events`` list shape;
    this container is the reducer's annotation-aware read path.
    """

    transitions: list[StatusEvent] = field(default_factory=list)
    annotations: list[InnerStateChanged] = field(default_factory=list)


@dataclass
class StatusSnapshot:
    """Materialized current state of all WPs in a feature (status.json).

    Produced by the deterministic reducer from the canonical event log.
    """

    mission_slug: str
    materialized_at: str  # ISO 8601 UTC
    event_count: int
    last_event_id: str | None
    work_packages: dict[str, dict[str, Any]]  # WP ID -> WPState
    summary: dict[str, int]  # lane -> count
    mission_number: str | None = None
    mission_type: str | None = None
    # Additive WP03 field: retrospective state derived from retrospective.* events.
    # Default None → backwards-compatible; existing snapshot consumers see no change.
    retrospective: RetrospectiveSnapshot | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            **mission_identity_fields(
                self.mission_slug,
                self.mission_number,
                self.mission_type,
            ),
            "materialized_at": self.materialized_at,
            "event_count": self.event_count,
            "last_event_id": self.last_event_id,
            "work_packages": self.work_packages,
            "summary": self.summary,
        }
        if self.retrospective is not None:
            d["retrospective"] = self.retrospective.model_dump(mode="json")
        result: dict[str, Any] = with_tracked_mission_slug_aliases(d)
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StatusSnapshot:
        feature_slug = data.get("mission_slug") or data.get("feature_slug")
        if feature_slug is None:
            raise KeyError("mission_slug")
        retro_data = data.get("retrospective")
        retro: RetrospectiveSnapshot | None = None
        if retro_data is not None:
            retro = RetrospectiveSnapshot.model_validate(retro_data)
        return cls(
            mission_slug=feature_slug,
            materialized_at=data["materialized_at"],
            event_count=data["event_count"],
            last_event_id=data.get("last_event_id"),
            work_packages=data["work_packages"],
            summary=data["summary"],
            mission_number=data.get("mission_number"),
            mission_type=data.get("mission_type"),
            retrospective=retro,
        )


@dataclass(frozen=True)
class AgentAssignment:
    """Resolved agent assignment with complete context.

    Represents the fully-resolved agent assigned to a work package,
    including the tool (AI agent type), model, optional profile ID, and role.

    This value object is the output of legacy coercion and fallback resolution
    from WPMetadata.resolved_agent(). It provides a clean, typed interface for
    consumers to access agent assignment context.

    Attributes:
        tool: AI agent identifier (e.g., 'claude', 'copilot', 'gemini', 'cursor').
        model: Model identifier (e.g., 'claude-opus-4-6', 'gpt-4-turbo').
        profile_id: Optional profile identifier for agent configuration override.
        role: Optional role for this assignment (e.g., 'reviewer', 'implementer').

    Example:
        >>> assignment = wp_metadata.resolved_agent()
        >>> print(assignment.tool)  # 'claude'
        >>> print(assignment.model)  # 'claude-opus-4-6'
    """

    tool: str
    model: str
    profile_id: str | None = None
    role: str | None = None


@dataclass
class TransitionRequest:
    """All inputs for a single status transition.

    Consolidates the 19 parameters of ``emit_status_transition`` into one
    typed object so call sites are self-documenting and the function
    signature stays stable as new fields are added.
    """

    # Mission identity
    feature_dir: Path | None = None
    mission_dir: Path | None = None
    mission_slug: str | None = None
    _legacy_mission_slug: str | None = None
    repo_root: Path | None = None
    # Transition target
    wp_id: str | None = None
    to_lane: str | None = None
    force: bool = False
    reason: str | None = None
    # Provenance discriminator carried onto the emitted event's ``reason_source``
    # (FR-001). Set to ``"operator"`` / ``"synthetic"`` at the cancel emit site;
    # ``None`` (the default) for every transition that does not track provenance.
    reason_source: str | None = None
    # Actor
    actor: ActorField | None = None
    execution_mode: str = "worktree"
    # Evidence
    evidence: dict[str, Any] | None = None
    review_ref: str | None = None
    review_result: Any = None
    # One-line human gist of the transition for the NOW view (#4327);
    # validated at the CLI boundary (``status/moment_fields.validate_summary``)
    # before any artifact write, and again at the shared creation boundary
    # (``status/transition_pipeline._validated_inline_fields``) so no
    # programmatic caller can bypass it; threaded onto the emitted
    # ``StatusEvent``.
    summary: str | None = None
    # Guard hints (callers may pre-compute these; emit derives them otherwise)
    workspace_context: str | None = None
    subtasks_complete: bool | None = None
    implementation_evidence_present: bool | None = None
    current_actor: str | None = None
    policy_metadata: dict[str, Any] | None = None
    # Optional off-axis state change that belongs to the same logical claim as
    # this transition. Emitters persist it in the same atomic/transactional
    # unit as the lane event, so a resolved binding can never lag its claim.
    annotation_delta: WPInnerStateDelta | None = None
    effective_root: Path | None = None


@dataclass
class GuardContext:
    """Inputs required by guard condition evaluators.

    Consolidates the 10 keyword-only parameters shared between
    ``validate_transition`` and ``_run_guard`` so guard functions
    receive a single typed context object instead of an expanding
    keyword list.
    """

    actor: str | None = None
    workspace_context: str | None = None
    subtasks_complete: bool | None = None
    implementation_evidence_present: bool | None = None
    reason: str | None = None
    review_ref: str | None = None
    evidence: Any = None
    force: bool = False
    review_result: Any = None
    current_actor: str | None = None
    # Dependency readiness verdict (FR-012, tri-state). ``None`` = no verdict
    # supplied => the guard PASSES (fail-OPEN, C-004 / decision Q8
    # ``01M1V8HVDQH36X06JDK22SZV02``): the crash-recovery progression probe and
    # the FR-015 backward-edge probe build bare contexts on exactly the guarded
    # edges. ``False`` refuses ``planned -> claimed`` and
    # ``claimed -> in_progress`` (force with actor+reason bypasses at
    # ``check_transition``); ``True`` passes. The emit shells always supply a
    # verdict, resolved in-lock against their write surface (FR-013). Do NOT
    # copy ``subtasks_complete``'s fail-closed ``is not True`` polarity here.
    dependency_ready: bool | None = None


# ---------------------------------------------------------------------------
# RetrospectiveSnapshot (additive — WP03)
# ---------------------------------------------------------------------------


class RetrospectiveSnapshot(BaseModel):
    """Materialized retrospective state for a single mission.

    Computed by the status reducer from retrospective.* events in the
    mission's event log. Surfaced as an additive field on StatusSnapshot.

    status values:
      absent  — no retrospective.* events seen (legacy / in-flight / no-retro)
      pending — requested or started, but not yet completed/skipped/failed
      completed, skipped, failed — terminal states from the latest terminal event
    """

    status: Literal["completed", "skipped", "failed", "pending", "absent"]
    mode: Mode | None = None
    record_path: str | None = None
    proposals_total: int = 0
    proposals_applied: int = 0
    proposals_rejected: int = 0
    proposals_pending: int = 0
