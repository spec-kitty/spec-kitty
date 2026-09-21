"""The canonical ``event -> IndexEntry`` fold for the Decision Moment ledger (T008).

Single source of truth for interpreting ``DecisionPointOpened`` /
``DecisionPointResolved`` event envelopes (``status.events.jsonl``, the
``spec_kitty_events.decisionpoint`` 4.0.0 contract) as
:class:`~specify_cli.decisions.models.IndexEntry` records. Two consumers
share it so they cannot drift into two independent interpretations of what a
decision event means (``contracts/decisions-doctor.md``, "Single fold, no
second reducer"):

- the forward write path (:mod:`specify_cli.decisions.service`) builds the
  OPEN-state entry via :func:`build_opened_entry` and terminal transitions
  via :func:`apply_terminal` -- the exact same assembly the reconciler uses;
- the reconciler (``cli/commands/_decisions_doctor.py``) rebuilds
  ``index.json`` from the authoritative event log via :func:`fold_events`,
  which is built from the SAME two functions.

Deliberately NOT a rewrite of :func:`specify_cli.status.reducer.reduce` --
that reduces a different (status-lane) ``spec_kitty_events`` schema and
cannot be reused here.

**Known wire-schema limitation (documented, not silently dropped):** the
``DecisionPointOpenedInterviewPayload`` wire schema (``spec_kitty_events``,
owned upstream) carries a single ``step_id`` string -- :mod:`specify_cli.
decisions.emit` collapses ``IndexEntry.step_id``/``IndexEntry.slot_key`` into
that one field before emission (``entry.step_id if entry.step_id is not None
else entry.slot_key``). An entry opened via ``slot_key`` therefore reconstructs
with the value in ``step_id`` and ``slot_key=None`` -- the origin-field
distinction does not round-trip through the current wire schema. A
step_id-opened entry (the common path) round-trips exactly (I9 proof in
``tests/decisions/test_decisions_reconciler.py`` uses that path). Fixing the
wire schema itself is out of this module's surface (``decisions/emit.py`` is
not owned by mission local-write-safety-01M2ZPZD WP03).

Similarly, ``IndexEntry.summary_json`` is never placed on the wire
(``emit.emit_decision_resolved`` always emits ``summary=None`` -- "SaaS
concern; slot reserved in V1", its own docstring) -- :func:`_fold_resolved`
therefore always folds ``summary_json=None``, matching what the forward path
persists whenever a caller does not supply it (the common case).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from kernel.clock import datetime, parse_iso
from spec_kitty_events.decision_moment import TerminalOutcome
from spec_kitty_events.decisionpoint import (
    DECISION_POINT_OPENED,
    DECISION_POINT_RESOLVED,
)

from specify_cli.decisions.models import (
    DecisionStatus,
    IndexEntry,
    OriginFlow,
)

__all__ = [
    "FoldError",
    "build_opened_entry",
    "apply_terminal",
    "fold_events",
]


class FoldError(ValueError):
    """Raised when an event sequence cannot be folded into an ``IndexEntry``."""


_OUTCOME_TO_STATUS: dict[TerminalOutcome, DecisionStatus] = {
    TerminalOutcome.RESOLVED: DecisionStatus.RESOLVED,
    TerminalOutcome.DEFERRED: DecisionStatus.DEFERRED,
    TerminalOutcome.CANCELED: DecisionStatus.CANCELED,
}


# ---------------------------------------------------------------------------
# Shared assemblers (used by BOTH the forward path and the fold below)
# ---------------------------------------------------------------------------


def build_opened_entry(
    *,
    decision_id: str,
    origin_flow: OriginFlow,
    step_id: str | None,
    slot_key: str | None,
    input_key: str,
    question: str,
    options: tuple[str, ...],
    created_at: datetime,
    opened_by: str,
    mission_id: str,
    mission_slug: str,
) -> IndexEntry:
    """Canonical constructor for a freshly-opened (``OPEN``) ``IndexEntry``.

    The forward write path (:func:`specify_cli.decisions.service.
    open_decision`) calls this directly with the caller's own
    ``step_id``/``slot_key`` (preserving whichever the caller supplied,
    losslessly); :func:`_fold_opened` below calls it with the wire's
    collapsed ``step_id`` and ``slot_key=None`` (see module docstring).
    """
    return IndexEntry(
        decision_id=decision_id,
        origin_flow=origin_flow,
        step_id=step_id,
        slot_key=slot_key,
        input_key=input_key,
        question=question,
        options=tuple(options),
        status=DecisionStatus.OPEN,
        created_at=created_at,
        opened_by=opened_by,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )


def apply_terminal(
    entry: IndexEntry,
    *,
    status: DecisionStatus,
    final_answer: str | None,
    other_answer: bool,
    rationale: str | None,
    resolved_at: datetime,
    resolved_by: str | None,
    summary_json: dict[str, str] | None,
) -> IndexEntry:
    """Canonical terminal-state transition, shared by
    :func:`specify_cli.decisions.service._terminal_command` and
    :func:`_fold_resolved` below.

    ``summary_json`` is never available on the wire (module docstring), so
    the fold path always passes ``None`` here -- identical to what the
    forward path persists when a caller does not supply one.
    """
    return entry.model_copy(
        update={
            "status": status,
            "final_answer": final_answer,
            "other_answer": other_answer,
            "rationale": rationale,
            "resolved_at": resolved_at,
            "resolved_by": resolved_by,
            "summary_json": summary_json,
        }
    )


# ---------------------------------------------------------------------------
# event -> IndexEntry fold
# ---------------------------------------------------------------------------


def _fold_opened(payload: Mapping[str, Any]) -> IndexEntry:
    return build_opened_entry(
        decision_id=str(payload["decision_point_id"]),
        origin_flow=OriginFlow(payload["origin_flow"]),
        step_id=str(payload["step_id"]),
        slot_key=None,
        input_key=str(payload["input_key"]),
        question=str(payload["question"]),
        options=tuple(payload.get("options", ())),
        created_at=parse_iso(str(payload["state_entered_at"])),
        opened_by=str(payload["actor_id"]),
        mission_id=str(payload["mission_id"]),
        mission_slug=str(payload["mission_slug"]),
    )


def _fold_resolved(entry: IndexEntry, payload: Mapping[str, Any]) -> IndexEntry:
    outcome = TerminalOutcome(payload["terminal_outcome"])
    try:
        status = _OUTCOME_TO_STATUS[outcome]
    except KeyError as exc:  # pragma: no cover - defensive, outcome is an enum
        raise FoldError(f"unknown terminal_outcome {outcome!r}") from exc
    return apply_terminal(
        entry,
        status=status,
        final_answer=payload.get("final_answer"),
        other_answer=bool(payload.get("other_answer", False)),
        rationale=payload.get("rationale"),
        resolved_at=parse_iso(str(payload["state_entered_at"])),
        resolved_by=str(payload["resolved_by"]),
        summary_json=None,
    )


def fold_events(events: Iterable[Mapping[str, Any]]) -> IndexEntry:
    """Fold one decision's ordered event envelopes into an ``IndexEntry``.

    Args:
        events: Envelopes (``{"event_id", "at", "event_type", "payload"}``)
            for exactly ONE ``decision_point_id``, in any order. Must contain
            exactly one ``DecisionPointOpened`` event; a
            ``DecisionPointResolved`` event, if present, is folded on top of
            the opened state.

    Returns:
        The reconstructed :class:`~specify_cli.decisions.models.IndexEntry`.

    Raises:
        FoldError: no ``DecisionPointOpened`` event is present, more than one
            ``DecisionPointOpened``/``DecisionPointResolved`` event is
            present, or an event of an unrecognized type is present.
    """
    materialized = list(events)

    opened = [e for e in materialized if e.get("event_type") == DECISION_POINT_OPENED]
    if not opened:
        raise FoldError("no DecisionPointOpened event in the fold input")
    if len(opened) > 1:
        raise FoldError("more than one DecisionPointOpened event for one decision_point_id")

    resolved = [e for e in materialized if e.get("event_type") == DECISION_POINT_RESOLVED]
    if len(resolved) > 1:
        raise FoldError("more than one DecisionPointResolved event for one decision_point_id")

    unknown = {str(e.get("event_type")) for e in materialized} - {DECISION_POINT_OPENED, DECISION_POINT_RESOLVED}
    if unknown:
        raise FoldError(f"unknown event type(s) in fold input: {sorted(unknown)}")

    entry = _fold_opened(opened[0]["payload"])
    if resolved:
        entry = _fold_resolved(entry, resolved[0]["payload"])
    return entry
