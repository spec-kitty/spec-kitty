"""Pydantic v2 models and enums for the Decision Moment ledger.

Defines OriginFlow, DecisionStatus, DecisionErrorCode enums and
the frozen IndexEntry / DecisionIndex models used by both the store
and the service layer.  Also defines DecisionOpenResponse and
DecisionTerminalResponse for CLI output contracts.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kernel.clock import datetime


__all__ = [
    "OriginFlow",
    "DecisionStatus",
    "DecisionErrorCode",
    "IndexEntry",
    "DecisionIndex",
    "DecisionOpenResponse",
    "DecisionTerminalResponse",
    "LedgerCommitReport",
    "logical_key",
]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class OriginFlow(StrEnum):
    """The CLI workflow that opened this decision."""

    CHARTER = "charter"
    SPECIFY = "specify"
    PLAN = "plan"


class DecisionStatus(StrEnum):
    """Lifecycle state of a decision moment."""

    OPEN = "open"
    RESOLVED = "resolved"
    DEFERRED = "deferred"
    CANCELED = "canceled"


class DecisionErrorCode(StrEnum):
    """Machine-readable error codes for decision service failures."""

    MISSING_STEP_OR_SLOT = "DECISION_MISSING_STEP_OR_SLOT"
    ALREADY_CLOSED = "DECISION_ALREADY_CLOSED"
    EVENT_REPAIR_FAILED = "DECISION_EVENT_REPAIR_FAILED"
    TERMINAL_CONFLICT = "DECISION_TERMINAL_CONFLICT"
    NOT_FOUND = "DECISION_NOT_FOUND"
    MISSION_NOT_FOUND = "MISSION_NOT_FOUND"
    # PR-CONTRACT-002 (design-phase-orchestrator-api-01M1HE6M pre-merge
    # review): reserved-but-unused -- ``decisions/service.py`` never raises
    # this member today (its only other reference is the value-only unit
    # test in ``tests/specify_cli/decisions/test_models.py``), and it is
    # deliberately NOT in ``upstream_contract.json``'s ``allowed_error_codes``
    # (unlike the six members above, which all ARE registered). If a future
    # verify/drift check starts raising it, orchestrator-api's
    # ``_fail_from_decision_error`` guard (``orchestrator_api/commands.py``)
    # degrades an unregistered code to a safe, contract-registered fallback
    # rather than leaking it onto the public API -- so this stays reserved
    # here without also needing a matching contract entry.
    VERIFY_DRIFT = "DECISION_VERIFY_DRIFT"


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class IndexEntry(BaseModel):
    """A single decision moment record as stored in index.json."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    origin_flow: OriginFlow
    step_id: str | None = None
    slot_key: str | None = None
    input_key: Annotated[str, Field(min_length=1)]
    question: Annotated[str, Field(min_length=1)]
    options: tuple[str, ...] = ()
    status: DecisionStatus
    final_answer: str | None = None
    rationale: str | None = None
    other_answer: bool = False
    summary_json: dict[str, str] | None = None
    created_at: datetime
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    opened_by: str | None = None
    mission_id: str
    mission_slug: str

    @model_validator(mode="after")
    def _step_or_slot(self) -> IndexEntry:
        """Require at least one of step_id or slot_key."""
        if not self.step_id and not self.slot_key:
            raise ValueError("step_id or slot_key required")
        return self


class DecisionIndex(BaseModel):
    """Container for all IndexEntry records; serializes to index.json."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1] = 1
    mission_id: str
    entries: tuple[IndexEntry, ...] = ()


# ---------------------------------------------------------------------------
# Response models (wire contracts for CLI output)
# ---------------------------------------------------------------------------


class LedgerCommitReport(BaseModel):
    """Outcome of the commit-on-record step (#4311).

    ``status`` mirrors :class:`~specify_cli.coordination.write_seam.
    WriteSeamResult.status` for the routable outcomes (``committed`` /
    ``unchanged``), plus the aggregated refusal/error outcomes. ``surface``
    is the resolved placement ref on committed/unchanged, ``None`` when the
    seam refused (nothing was resolved). The commit is LOCAL by design:
    pushing stays under the repo's normal policy (GOAL.md defers auto-push
    permanently), so "permanent" means committed in the checkout, visible to
    the team on the next normal push.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["committed", "unchanged", "refused", "error"]
    surface: str | None = None
    commit_hash: str | None = None
    diagnostic: str | None = None


class DecisionOpenResponse(BaseModel):
    """Response returned when a decision is opened (or idempotently found)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    idempotent: bool
    mission_id: str
    artifact_path: str
    event_lamport: int | None = None
    ledger_commit: LedgerCommitReport | None = None


class DecisionTerminalResponse(BaseModel):
    """Response returned when a decision reaches a terminal state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str
    status: DecisionStatus
    terminal_outcome: str
    idempotent: bool
    event_lamport: int | None = None
    ledger_commit: LedgerCommitReport | None = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def logical_key(entry: IndexEntry) -> tuple[str, str, str | None, str]:
    """Return the idempotency key tuple for an IndexEntry.

    Returns ``(mission_id, origin_flow, step_id_or_slot_key, input_key)``.
    ``step_id`` takes precedence over ``slot_key`` when both are set.
    """
    step_or_slot: str | None = entry.step_id if entry.step_id is not None else entry.slot_key
    return (entry.mission_id, entry.origin_flow, step_or_slot, entry.input_key)
