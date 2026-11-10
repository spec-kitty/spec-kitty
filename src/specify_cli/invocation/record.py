"""Op event Pydantic v2 models (schema v2) and MinimalViableTrailPolicy.

Schema v2 (contracts/op-record-events.md) splits the old dual-purpose
``InvocationRecord`` into two frozen models so invalid blank-default states
are unrepresentable:

- ``OpStartedEvent`` — first JSONL line, write-once (exclusive create)
- ``OpCompletedEvent`` — appended at most once; requires ``outcome`` and
  ``closed_by`` and carries NO started-only fields

Validation rules:
- invocation_id must be a valid ULID (26 chars, Crockford base32)
- started_at / completed_at must be non-empty ISO-8601 UTC strings
- legacy (pre-v2) lines raise ``LegacyRecordError`` from ``parse_op_event``
"""

from __future__ import annotations

from kernel.clock import UTC, datetime, parse_iso
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, ValidationError, field_validator

from specify_cli.invocation.errors import LegacyRecordError

_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def validate_invocation_id(value: str) -> str:
    """Return *value* when it is an exact Crockford-base32 ULID.

    This is the canonical validation boundary for both event models and any
    filesystem lookup keyed by an invocation ID. Callers must invoke it before
    composing an ID into a path.
    """
    if not _ULID_RE.fullmatch(value):
        raise ValueError(f"invocation_id must be a 26-char ULID, got {value!r}")
    return value


class OpStartedEvent(BaseModel):
    """v2 ``started`` event — required fields make blank records unrepresentable."""

    event: Literal["started"] = "started"
    invocation_id: str  # ULID (26 chars)
    profile_id: str = Field(min_length=1)
    action: str = Field(min_length=1)  # canonical action token; non-empty
    request_text: str  # may be empty only in query mode (executor enforces)
    actor: str = Field(min_length=1)  # "claude" | "codex" | "operator" | …
    mode_of_work: Literal["task_execution", "advisory", "mission_step", "query"]  # task_execution | advisory | mission_step | query
    governance_context_hash: str  # first 16 hex chars of SHA-256
    governance_context_available: bool
    router_confidence: str | None = None  # exact | canonical_verb | domain_keyword
    started_at: str = Field(min_length=1)  # ISO-8601 UTC
    mission_id: str | None = None
    wp_id: str | None = None
    # No model identifier is recorded here (#7013): ``actor`` is the harness key
    # and the only runtime identity a committed record carries.

    model_config = {"frozen": True}

    _ulid = field_validator("invocation_id")(validate_invocation_id)

    def to_jsonl_line(self) -> str:
        """Serialise to a single JSON line, omitting None fields."""
        return json.dumps(self.model_dump(exclude_none=True))


class OpCompletedEvent(BaseModel):
    """v2 ``completed`` event — meaningful in isolation, no started-only fields."""

    event: Literal["completed"] = "completed"
    invocation_id: str  # ULID (26 chars); must match file
    completed_at: str = Field(min_length=1)  # ISO-8601 UTC
    outcome: Literal["done", "failed", "abandoned"]  # required, no default
    closed_by: Literal["agent", "doctor_sweep"]  # required, no default
    evidence_ref: str | None = None

    model_config = {"frozen": True}

    _ulid = field_validator("invocation_id")(validate_invocation_id)

    def to_jsonl_line(self) -> str:
        """Serialise to a single JSON line, omitting None fields."""
        return json.dumps(self.model_dump(exclude_none=True))


def parse_op_event(data: dict[str, Any]) -> OpStartedEvent | OpCompletedEvent:
    """Dispatch a parsed JSONL dict to the right v2 event model.

    Raises:
        LegacyRecordError: the dict is a pre-v2 (legacy) record — e.g. a
            completed event without ``closed_by``, or a started event missing
            required v2 fields. Catchable so readers and the WP05 migration
            can identify legacy lines deliberately rather than crash.
        ValueError: ``event`` is not a lifecycle event (started/completed).
    """
    event = data.get("event")
    invocation_id = data.get("invocation_id")
    inv_id = invocation_id if isinstance(invocation_id, str) else None
    if event == "completed":
        if "closed_by" not in data:
            raise LegacyRecordError(inv_id, "completed event lacks 'closed_by'")
        try:
            return OpCompletedEvent.model_validate(data)
        except ValidationError as exc:
            raise LegacyRecordError(inv_id, f"completed event not v2-parseable: {exc}") from exc
    if event == "started":
        try:
            return OpStartedEvent.model_validate(data)
        except ValidationError as exc:
            raise LegacyRecordError(inv_id, f"started event not v2-parseable: {exc}") from exc
    raise ValueError(f"not an Op lifecycle event: {event!r}")


# ---------------------------------------------------------------------------
# Tier policy dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TierPolicy:
    """Configuration for a single trail tier."""

    name: str
    mandatory: bool
    description: str
    storage_path: str
    promotion_trigger: str = ""


@dataclass(frozen=True)
class MinimalViableTrailPolicy:
    """
    The three-tier minimal viable trail contract.
    Every Spec Kitty action's audit trail requirements.

    Tier 1 (every_invocation): mandatory. One InvocationRecord in local JSONL before executor returns.
    Tier 2 (evidence_artifact): optional. EvidenceArtifact when invocation produces checkable output.
    Tier 3 (durable_project_state): optional. kitty-specs/ / doctrine artifact only for domain-state changes.
    """

    tier_1: TierPolicy
    tier_2: TierPolicy
    tier_3: TierPolicy


MINIMAL_VIABLE_TRAIL_POLICY = MinimalViableTrailPolicy(
    tier_1=TierPolicy(
        name="every_invocation",
        mandatory=True,
        description=("One InvocationRecord written locally before executor returns. Applies to all standalone dispatch invocations."),
        storage_path="kitty-ops/{invocation_id}.jsonl",
    ),
    tier_2=TierPolicy(
        name="evidence_artifact",
        mandatory=False,
        description=(
            "Optional EvidenceArtifact for invocations that produce checkable output. Created when caller passes --evidence to profile-invocation complete."
        ),
        storage_path=".kittify/evidence/{invocation_id}/",
        promotion_trigger="caller sets evidence_ref on profile-invocation complete",
    ),
    tier_3=TierPolicy(
        name="durable_project_state",
        mandatory=False,
        description=(
            "Promotion to kitty-specs/ or doctrine artifacts only when invocation "
            "changes project-domain state. Applies to specify, plan, tasks, merge, accept only."
        ),
        storage_path="kitty-specs/{mission_slug}/",
        promotion_trigger="spec, plan, tasks, merge, accept commands only",
    ),
)


# ---------------------------------------------------------------------------
# Tier eligibility
# ---------------------------------------------------------------------------

# Actions that qualify for Tier 3 (durable project state changes)
TIER_3_ACTIONS: frozenset[str] = frozenset(
    {
        "specify",
        "plan",
        "tasks",
        "merge",
        "accept",
    }
)


@dataclass(frozen=True)
class TierEligibility:
    """Which trail tiers apply to a given invocation."""

    tier_1: bool = True  # always True — every invocation has Tier 1
    tier_2: bool = False  # True if evidence_ref is set on completed event
    tier_3: bool = False  # True if action is in TIER_3_ACTIONS


def tier_eligible(
    started: OpStartedEvent,
    completed: OpCompletedEvent | None = None,
) -> TierEligibility:
    """Determine which trail tiers apply to an Op.

    ``action`` lives on the started event (v2); ``evidence_ref`` on the
    completed event. Pass ``completed=None`` for still-open Ops.
    """
    return TierEligibility(
        tier_1=True,
        tier_2=completed is not None and completed.evidence_ref is not None,
        tier_3=started.action in TIER_3_ACTIONS,
    )


# ---------------------------------------------------------------------------
# Evidence artifact promotion (Tier 2)
# ---------------------------------------------------------------------------


@dataclass
class EvidenceArtifact:
    """A Tier 2 evidence artifact written to the evidence base directory."""

    invocation_id: str
    directory: Path
    evidence_file: Path
    record_snapshot: Path


# ---------------------------------------------------------------------------
# Profile-invocation lifecycle pair (WP05 / data-model.md §4)
# ---------------------------------------------------------------------------


#: ``abandoned`` (#7346): closed by ``doctor ops --close-stale``, not by the action's result.
ProfileInvocationPhase = Literal["started", "completed", "failed", "abandoned"]
#: Derived from the Literal so a new phase is declared in one place (WP01 review L1).
_PROFILE_INVOCATION_PHASES: frozenset[str] = frozenset(get_args(ProfileInvocationPhase))


@dataclass(frozen=True)
class ProfileInvocationRecord:
    """Paired profile-invocation lifecycle record (WP05).

    Captures one phase of a public action `next` issued. For every `started`
    record there should eventually be exactly one paired `completed`, `failed`
    or `abandoned` record sharing the same ``canonical_action_id``. An
    `abandoned` record is written by ``doctor ops --close-stale`` for a stale
    `started` record; it says nothing about the action's result (#7346).

    See data-model.md §4 and contracts/invocation-lifecycle.md.
    """

    canonical_action_id: str
    phase: ProfileInvocationPhase
    at: datetime
    agent: str
    mission_id: str
    wp_id: str | None = None
    reason: str | None = None
    # Optional tag set by the writer for ergonomic filtering. Not part of the
    # canonical schema; ignored by readers that don't recognise it.
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialise to the on-disk JSON shape (sorted-key stable).

        Optional fields are omitted when None for line-stability with the
        contract example. ``metadata`` is omitted when empty.
        """
        payload: dict[str, Any] = {
            "canonical_action_id": self.canonical_action_id,
            "phase": self.phase,
            "at": _ensure_iso_utc(self.at),
            "agent": self.agent,
            "mission_id": self.mission_id,
            "wp_id": self.wp_id,
            "reason": self.reason,
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileInvocationRecord:
        """Parse from the on-disk JSON shape.

        Tolerates missing optional fields. Coerces ``at`` from ISO string.
        """
        at_raw = data.get("at")
        if isinstance(at_raw, datetime):
            at_value = at_raw
        elif isinstance(at_raw, str) and at_raw:
            at_value = parse_iso(at_raw)
        else:
            raise ValueError("ProfileInvocationRecord requires 'at' (ISO-8601 string or datetime)")

        metadata_raw = data.get("metadata") or {}
        metadata: dict[str, str] = {}
        if isinstance(metadata_raw, dict):
            for k, v in metadata_raw.items():
                metadata[str(k)] = str(v)

        phase_raw = data.get("phase")
        if phase_raw not in _PROFILE_INVOCATION_PHASES:
            raise ValueError(f"ProfileInvocationRecord.phase must be started|completed|failed|abandoned, got {phase_raw!r}")

        return cls(
            canonical_action_id=str(data["canonical_action_id"]),
            phase=phase_raw,
            at=at_value,
            agent=str(data["agent"]),
            mission_id=str(data["mission_id"]),
            wp_id=(str(data["wp_id"]) if data.get("wp_id") is not None else None),
            reason=(str(data["reason"]) if data.get("reason") is not None else None),
            metadata=metadata,
        )

    def to_json_line(self) -> str:
        """Serialise to a single JSON line (sorted keys for stability)."""
        return json.dumps(self.to_dict(), sort_keys=True)


def _ensure_iso_utc(dt: datetime) -> str:
    """Return ISO-8601 string. Naive datetimes are assumed UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


def promote_to_evidence(
    record: OpCompletedEvent,
    evidence_base_dir: Path,
    content: str,
) -> EvidenceArtifact:
    """
    Create a Tier 2 EvidenceArtifact at evidence_base_dir/<invocation_id>/.

    Creates:
      - evidence_base_dir/<invocation_id>/evidence.md  (caller-supplied content)
      - evidence_base_dir/<invocation_id>/record.json  (snapshot of invocation record)
    """
    artifact_dir = evidence_base_dir / record.invocation_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    evidence_file = artifact_dir / "evidence.md"
    record_file = artifact_dir / "record.json"
    evidence_file.write_text(content, encoding="utf-8")
    record_file.write_text(json.dumps(record.model_dump(), indent=2), encoding="utf-8")
    return EvidenceArtifact(
        invocation_id=record.invocation_id,
        directory=artifact_dir,
        evidence_file=evidence_file,
        record_snapshot=record_file,
    )
