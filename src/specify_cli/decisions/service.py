"""Decision Moment service layer — open/resolve/defer/cancel orchestration.

Public API:
    open_decision(repo_root, mission_slug, *, ...)  -> DecisionOpenResponse
    resolve_decision(repo_root, mission_slug, decision_id, *, ...) -> DecisionTerminalResponse
    defer_decision(repo_root, mission_slug, decision_id, *, ...)   -> DecisionTerminalResponse
    cancel_decision(repo_root, mission_slug, decision_id, *, ...)  -> DecisionTerminalResponse

Also exports:
    DecisionError(Exception) — structured error with ``code`` and ``details``.

mission_id resolution:
    Reads ``<repo_root>/kitty-specs/<mission_slug>/meta.json`` → ``mission_id`` field.
    Raises ``DecisionError(MISSION_NOT_FOUND)`` if meta.json is missing or has no
    ``mission_id``.
"""

from __future__ import annotations

from mission_runtime import MissionArtifactKind, placement_seam
import json
from collections.abc import Callable
from pathlib import Path

import ulid as _ulid_mod

from kernel.clock import now_utc
from specify_cli.decisions import emit as _emit
from specify_cli.decisions import ledger_commit as _ledger_commit
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import (
    DecisionErrorCode,
    DecisionOpenResponse,
    DecisionStatus,
    DecisionTerminalResponse,
    IndexEntry,
    OriginFlow,
)
from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED

__all__ = [
    "DecisionError",
    "open_decision",
    "resolve_decision",
    "defer_decision",
    "cancel_decision",
]


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


class DecisionError(Exception):
    """Structured error raised by the decisions service.

    Attributes:
        code: Machine-readable DecisionErrorCode.
        details: Optional dict with context (decision_id, status, etc.).
    """

    def __init__(
        self,
        code: DecisionErrorCode,
        details: dict | None = None,  # type: ignore[type-arg]
        message: str | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        msg = message or f"Decision error: {code.value}"
        super().__init__(msg)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mint_decision_id() -> str:
    """Mint a new ULID-based decision_id."""
    return str(_ulid_mod.ULID())


_TERMINAL_STATUSES = {
    DecisionStatus.RESOLVED,
    DecisionStatus.DEFERRED,
    DecisionStatus.CANCELED,
}


def _is_terminal(status: DecisionStatus) -> bool:
    return status in _TERMINAL_STATUSES


def _is_allowed_terminal_reopen(
    current_status: DecisionStatus,
    target_status: DecisionStatus,
) -> bool:
    """Return True for terminal states that may be explicitly closed later."""
    return current_status == DecisionStatus.DEFERRED and target_status == DecisionStatus.RESOLVED


def _resolve_mission_id(repo_root: Path, mission_slug: str) -> str:
    """Read mission_id from kitty-specs/<slug>/meta.json.

    Raises:
        DecisionError(MISSION_NOT_FOUND): if meta.json is missing or has no mission_id.
    """
    # FR-001: route through the SAME kind-routed seam as ``_mission_dir`` (the
    # decisions ledger's own directory authority) rather than a fresh
    # PRIMARY_METADATA lookup. WP04's pre-existing single-read-path-authority
    # regression test (test_decision_single_authority.py) pins this mission_id
    # read as coord-aware: a materialized ``-coord`` worktree carries its own
    # ``meta.json`` copy and IS the resolvable surface (unlike the #2453 husk
    # class, which shadows a stale PRIMARY copy). Reusing ``_mission_dir`` keeps
    # the mission_id lookup and the decisions-ledger location in agreement — a
    # separate PRIMARY-only resolution here could disagree with where the
    # ledger itself resolves under coord topology (C-001: no over-claiming a
    # funnel beyond what each site's own contract needs).
    feature_dir = _mission_dir(repo_root, mission_slug)
    # FR-005 / post-#2091 + FR-007 / #3162: this site hard-fails on a missing
    # meta.json (DecisionError(MISSION_NOT_FOUND)) -- allow_missing=True would
    # MASK that guard and silently re-introduce the removed legacy tolerance.
    # Routed through the ONE fail-closed reader: a missing file returns None
    # (same MISSION_NOT_FOUND diagnostic as before), and a corrupt/unreadable
    # one raises the typed MissionMetaReadError, wrapped here into the same
    # MISSION_NOT_FOUND DecisionError the pre-#2091 local try/except produced.
    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        # The fail-closed reader wraps both a JSON syntax error and a
        # read/decode (OSError) failure into MissionMetaReadError -- the same
        # two failure modes the pre-#2091 local try/except caught as ValueError.
        raise DecisionError(
            code=DecisionErrorCode.MISSION_NOT_FOUND,
            details={"mission_slug": mission_slug},
            message=f"Failed to read meta.json for mission {mission_slug!r}: {exc}",
        ) from exc
    if meta is None:
        raise DecisionError(
            code=DecisionErrorCode.MISSION_NOT_FOUND,
            details={"mission_slug": mission_slug},
            message=f"meta.json not found for mission {mission_slug!r}",
        )
    mission_id = meta.get("mission_id")
    if not mission_id:
        raise DecisionError(
            code=DecisionErrorCode.MISSION_NOT_FOUND,
            details={"mission_slug": mission_slug},
            message=f"meta.json for {mission_slug!r} has no mission_id field",
        )
    return str(mission_id)


def _mission_dir(repo_root: Path, mission_slug: str) -> Path:
    """Return kitty-specs/<mission_slug>/.

    The decisions ledger (``decisions/index.json`` / ``DM-<id>.md``) and its
    companion ``status.events.jsonl`` entries are coord-authority-owned
    STATUS-partition state -- the SAME directory ``decisions/emit.py``'s
    permanent kind-blind write target resolves to (data-model.md:31, the 2
    permanent-by-design coord_authority writes). Routed through
    ``placement_seam(...).read_dir(STATUS_STATE)`` so this read stays
    topology-aware and agrees with where emit.py writes; splitting reads onto
    PRIMARY here would read/write split-brain the ledger under coord topology.
    """
    mission_dir: Path = placement_seam(repo_root, mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)
    return mission_dir


def _events_path(repo_root: Path, mission_slug: str) -> Path:
    """Return kitty-specs/<mission_slug>/status.events.jsonl."""
    return _mission_dir(repo_root, mission_slug) / "status.events.jsonl"


def _opened_event_exists(repo_root: Path, mission_slug: str, decision_id: str) -> bool:
    """Return True when the canonical opened event already exists."""
    path = _events_path(repo_root, mission_slug)
    if not path.exists():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DecisionError(
            code=DecisionErrorCode.EVENT_REPAIR_FAILED,
            details={"decision_id": decision_id, "events_path": str(path)},
            message=f"Failed to read decision event log for {decision_id!r}: {exc}",
        ) from exc

    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DecisionError(
                code=DecisionErrorCode.EVENT_REPAIR_FAILED,
                details={
                    "decision_id": decision_id,
                    "events_path": str(path),
                    "line": line_number,
                    "parse_error": str(exc),
                },
                message=(f"Cannot verify opened event for {decision_id!r}: malformed event log line {line_number}"),
            ) from exc
        payload = event.get("payload")
        if event.get("event_type") == DECISION_POINT_OPENED and isinstance(payload, dict) and payload.get("decision_point_id") == decision_id:
            return True
    return False


def _repair_missing_opened_event(
    repo_root: Path,
    mission_slug: str,
    *,
    entry: IndexEntry,
) -> int | None:
    """Re-emit a missing opened event for an already-persisted open decision."""
    if _opened_event_exists(repo_root, mission_slug, entry.decision_id):
        return None
    if entry.opened_by is None:
        raise DecisionError(
            code=DecisionErrorCode.EVENT_REPAIR_FAILED,
            details={"decision_id": entry.decision_id, "mission_slug": mission_slug},
            message=(f"Cannot repair opened event for decision {entry.decision_id!r}: opening actor was not persisted"),
        )
    try:
        return _emit.emit_decision_opened(
            repo_root,
            mission_slug,
            decision_id=entry.decision_id,
            entry=entry,
            actor=entry.opened_by,
        )
    except Exception as exc:
        raise DecisionError(
            code=DecisionErrorCode.EVENT_REPAIR_FAILED,
            details={"decision_id": entry.decision_id, "mission_slug": mission_slug},
            message=f"Failed to repair opened event for decision {entry.decision_id!r}: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# open_decision
# ---------------------------------------------------------------------------


def open_decision(
    repo_root: Path,
    mission_slug: str,
    *,
    origin_flow: OriginFlow,
    input_key: str,
    question: str,
    options: tuple[str, ...] = (),
    step_id: str | None = None,
    slot_key: str | None = None,
    actor: str,
    dry_run: bool = False,
    decision_id: str | None = None,
    on_minted: Callable[[str], None] | None = None,
) -> DecisionOpenResponse:
    """Open a new decision or return idempotently if already open.

    Args:
        repo_root:    Repository root (parent of kitty-specs/).
        mission_slug: The mission slug.
        origin_flow:  Which CLI flow is creating this decision.
        input_key:    The specific input this decision governs.
        question:     Human-readable question text.
        options:      Ordered tuple of candidate answers.
        step_id:      Interview step identifier (supply step_id OR slot_key).
        slot_key:     Slot key (used when step_id is not available).
        actor:        Identity of the opening actor.
        dry_run:      If True, validate and look up without writing.
        decision_id:  Pre-minted ULID to use as the decision_id.  If None, a
                      new ULID is minted inside this function.
        on_minted:    Optional callback invoked with the recoverable
                      decision_id after an existing open decision is found or a
                      fresh open has been persisted. Machine callers should
                      prefer the returned response; if a process exits before
                      receiving it, rerun the same logical open command to
                      recover the same idempotent decision_id.

    Returns:
        DecisionOpenResponse

    Raises:
        DecisionError(MISSING_STEP_OR_SLOT): if both step_id and slot_key are None.
        DecisionError(ALREADY_CLOSED): if a matching entry exists in terminal state.
        DecisionError(MISSION_NOT_FOUND): if meta.json is missing or invalid.
    """
    if step_id is None and slot_key is None:
        raise DecisionError(
            code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
            message="Either step_id or slot_key must be provided",
        )

    mission_id = _resolve_mission_id(repo_root, mission_slug)
    mission_dir = _mission_dir(repo_root, mission_slug)

    if dry_run:
        if on_minted is not None:
            on_minted("DRY_RUN")
        return DecisionOpenResponse(
            decision_id="DRY_RUN",
            idempotent=False,
            mission_id=mission_id,
            artifact_path="",
            event_lamport=None,
        )

    # Look up existing entry by logical key
    index = _store.load_index(mission_dir)
    existing = _store.find_by_logical_key(
        index,
        origin_flow,
        step_id,
        slot_key,
        input_key,
    )

    if existing is not None:
        if not _is_terminal(existing.status):
            # Idempotent return — already open. The re-record itself is a
            # no-op (issue #4311: never a duplicate row, never an event), but
            # the commit is still ATTEMPTED: the seam's own idempotence makes
            # an already-committed ledger a byte-identical "unchanged" no-op,
            # so this costs nothing on the happy path — while a first record
            # whose commit failed (refused/error, e.g. an operator who has
            # since created the feature branch) converges to committed on
            # the rerun instead of staying uncommitted forever. A repaired
            # opened event names the repair in the commit message.
            repaired_lamport = _repair_missing_opened_event(
                repo_root,
                mission_slug,
                entry=existing,
            )
            ledger_commit = _ledger_commit.commit_ledger_change(
                repo_root,
                mission_slug,
                mission_dir,
                existing.decision_id,
                action="repaired" if repaired_lamport is not None else "open",
            )
            if on_minted is not None:
                on_minted(existing.decision_id)
            return DecisionOpenResponse(
                decision_id=existing.decision_id,
                idempotent=True,
                mission_id=mission_id,
                artifact_path=str(_store.artifact_path(mission_dir, existing.decision_id)),
                event_lamport=repaired_lamport,
                ledger_commit=ledger_commit,
            )
        else:
            # Already closed — reject
            raise DecisionError(
                code=DecisionErrorCode.ALREADY_CLOSED,
                details={
                    "decision_id": existing.decision_id,
                    "status": existing.status.value,
                },
                message=(f"Decision {existing.decision_id!r} is already in terminal state {existing.status.value!r}"),
            )

    # Mint new decision (use caller-supplied id if provided, else mint fresh)
    decision_id = decision_id if decision_id is not None else _mint_decision_id()
    created_at = now_utc()
    entry = IndexEntry(
        decision_id=decision_id,
        origin_flow=origin_flow,
        step_id=step_id,
        slot_key=slot_key,
        input_key=input_key,
        question=question,
        options=tuple(options),
        status=DecisionStatus.OPEN,
        created_at=created_at,
        opened_by=actor,
        mission_id=mission_id,
        mission_slug=mission_slug,
    )

    _store.append_entry(mission_dir, entry)
    artifact = _store.write_artifact(mission_dir, entry)
    lamport = _emit.emit_decision_opened(
        repo_root,
        mission_slug,
        decision_id=decision_id,
        entry=entry,
        actor=actor,
    )
    if on_minted is not None:
        on_minted(decision_id)
    # Commit-on-record (#4311): the ledger change (index + DM artifact + the
    # event row just appended) lands as one local commit through the write
    # seam in the same operation that recorded it. Never an empty commit —
    # the seam returns "unchanged" for a byte-identical already-committed
    # artifact — and never a push (GOAL.md defers auto-push permanently).
    # After the minted-id callback, so a crash mid-commit still leaves the
    # machine caller's recovery id recorded and the rerun idempotent.
    ledger_commit = _ledger_commit.commit_ledger_change(
        repo_root,
        mission_slug,
        mission_dir,
        decision_id,
        action="open",
    )

    return DecisionOpenResponse(
        decision_id=decision_id,
        idempotent=False,
        mission_id=mission_id,
        artifact_path=str(artifact),
        event_lamport=lamport,
        ledger_commit=ledger_commit,
    )


# ---------------------------------------------------------------------------
# _terminal_command — shared logic for resolve/defer/cancel
# ---------------------------------------------------------------------------


def _terminal_command(
    repo_root: Path,
    mission_slug: str,
    decision_id: str,
    *,
    target_status: DecisionStatus,
    terminal_outcome: str,
    final_answer: str | None = None,
    other_answer: bool = False,
    rationale: str | None = None,
    summary_json: dict[str, str] | None = None,
    resolved_by: str | None = None,
    actor: str,
    dry_run: bool = False,
) -> DecisionTerminalResponse:
    """Shared implementation for resolve, defer, and cancel.

    Raises:
        DecisionError(NOT_FOUND): if decision_id is not in the index.
        DecisionError(TERMINAL_CONFLICT): if already terminal with different payload.
    """
    if dry_run:
        return DecisionTerminalResponse(
            decision_id=decision_id,
            status=target_status,
            terminal_outcome=terminal_outcome,
            idempotent=False,
            event_lamport=None,
        )

    mission_dir = _mission_dir(repo_root, mission_slug)
    index = _store.load_index(mission_dir)
    entry = next(
        (e for e in index.entries if e.decision_id == decision_id),
        None,
    )
    if entry is None:
        raise DecisionError(
            code=DecisionErrorCode.NOT_FOUND,
            details={"decision_id": decision_id},
            message=f"Decision {decision_id!r} not found in index",
        )

    if _is_terminal(entry.status) and not _is_allowed_terminal_reopen(
        entry.status,
        target_status,
    ):
        # Already terminal — check for idempotency or conflict
        if entry.status == target_status:
            # Same outcome — check payload identity
            payload_matches = entry.final_answer == final_answer and entry.other_answer == other_answer and entry.rationale == rationale
            if payload_matches:
                # Idempotent re-record: the ledger itself changes nothing, but
                # the commit is still ATTEMPTED (#4311) — the seam's own
                # idempotence makes an already-committed ledger "unchanged"
                # (never an empty commit), while a first record whose commit
                # failed converges to committed on the rerun instead of
                # staying uncommitted forever.
                ledger_commit = _ledger_commit.commit_ledger_change(
                    repo_root,
                    mission_slug,
                    mission_dir,
                    decision_id,
                    action=terminal_outcome,
                )
                return DecisionTerminalResponse(
                    decision_id=decision_id,
                    status=target_status,
                    terminal_outcome=terminal_outcome,
                    idempotent=True,
                    event_lamport=None,
                    ledger_commit=ledger_commit,
                )
        # Different outcome or different payload — conflict
        raise DecisionError(
            code=DecisionErrorCode.TERMINAL_CONFLICT,
            details={
                "decision_id": decision_id,
                "existing_status": entry.status.value,
                "requested_status": target_status.value,
            },
            message=(f"Decision {decision_id!r} is already in terminal state {entry.status.value!r}; cannot transition to {target_status.value!r}"),
        )

    # Apply the terminal transition
    resolved_at = now_utc()
    updated_index = _store.update_entry(
        mission_dir,
        decision_id,
        status=target_status,
        final_answer=final_answer,
        other_answer=other_answer,
        rationale=rationale,
        summary_json=summary_json,
        resolved_by=resolved_by,
        resolved_at=resolved_at,
    )

    # Get the updated entry for artifact + event
    updated_entry = next(e for e in updated_index.entries if e.decision_id == decision_id)
    _store.write_artifact(mission_dir, updated_entry)
    lamport = _emit.emit_decision_resolved(
        repo_root,
        mission_slug,
        decision_id=decision_id,
        entry=updated_entry,
        actor=actor,
    )
    # Commit-on-record (#4311): a resolved/deferred/canceled decision is never
    # left uncommitted in the working tree — the terminal ledger change lands
    # as one local commit through the write seam in the same operation. The
    # early idempotent return above (same outcome, same payload) also
    # re-attempts the commit, a "unchanged" no-op when it already landed.
    ledger_commit = _ledger_commit.commit_ledger_change(
        repo_root,
        mission_slug,
        mission_dir,
        decision_id,
        action=terminal_outcome,
    )

    return DecisionTerminalResponse(
        decision_id=decision_id,
        status=target_status,
        terminal_outcome=terminal_outcome,
        idempotent=False,
        event_lamport=lamport,
        ledger_commit=ledger_commit,
    )


# ---------------------------------------------------------------------------
# resolve_decision / defer_decision / cancel_decision
# ---------------------------------------------------------------------------


def resolve_decision(
    repo_root: Path,
    mission_slug: str,
    decision_id: str,
    *,
    final_answer: str,
    other_answer: bool = False,
    rationale: str | None = None,
    summary_json: dict[str, str] | None = None,
    resolved_by: str | None = None,
    actor: str,
    dry_run: bool = False,
) -> DecisionTerminalResponse:
    """Resolve a decision with a concrete answer.

    Args:
        repo_root:    Repository root (parent of kitty-specs/).
        mission_slug: The mission slug.
        decision_id:  The ULID identifier of the decision to resolve.
        final_answer: The chosen answer text (required, non-empty).
        other_answer: True if the answer is "other" (write-in).
        rationale:    Optional explanation of the choice.
        summary_json: Optional provenance payload; persisted as C-005 requires.
                      Expected shape: ``{"text": <str>, "source": <SummarySource.value>}``.
        resolved_by:  Identity of the resolver (falls back to actor).
        actor:        Identity of the acting agent.
        dry_run:      If True, validate without writing.

    Returns:
        DecisionTerminalResponse

    Raises:
        DecisionError(MISSING_STEP_OR_SLOT): if ``final_answer`` is empty or
            whitespace-only. Rejected here, in the ONE shared authority both
            the host CLI's ``cmd_resolve`` (``cli/commands/decision.py``) and
            the orchestrator-api's ``resolve-decision`` verb
            (``orchestrator_api/commands.py``) call directly -- so this check
            cannot drift between callers the way the analogous ``rationale``
            emptiness check (duplicated per-caller for defer/cancel) can.
    """
    if not final_answer.strip():
        raise DecisionError(
            code=DecisionErrorCode.MISSING_STEP_OR_SLOT,
            details={"field": "final_answer"},
            message="final_answer must be a non-empty string",
        )
    return _terminal_command(
        repo_root,
        mission_slug,
        decision_id,
        target_status=DecisionStatus.RESOLVED,
        terminal_outcome="resolved",
        final_answer=final_answer,
        other_answer=other_answer,
        rationale=rationale,
        summary_json=summary_json,
        resolved_by=resolved_by,
        actor=actor,
        dry_run=dry_run,
    )


def defer_decision(
    repo_root: Path,
    mission_slug: str,
    decision_id: str,
    *,
    rationale: str,
    resolved_by: str | None = None,
    actor: str,
    dry_run: bool = False,
) -> DecisionTerminalResponse:
    """Defer a decision for later resolution.

    Args:
        repo_root:    Repository root (parent of kitty-specs/).
        mission_slug: The mission slug.
        decision_id:  The ULID identifier of the decision to defer.
        rationale:    Explanation of why it's being deferred (required).
        resolved_by:  Identity of the deferring party (falls back to actor).
        actor:        Identity of the acting agent.
        dry_run:      If True, validate without writing.

    Returns:
        DecisionTerminalResponse
    """
    return _terminal_command(
        repo_root,
        mission_slug,
        decision_id,
        target_status=DecisionStatus.DEFERRED,
        terminal_outcome="deferred",
        rationale=rationale,
        resolved_by=resolved_by,
        actor=actor,
        dry_run=dry_run,
    )


def cancel_decision(
    repo_root: Path,
    mission_slug: str,
    decision_id: str,
    *,
    rationale: str,
    resolved_by: str | None = None,
    actor: str,
    dry_run: bool = False,
) -> DecisionTerminalResponse:
    """Cancel a decision (deemed no longer relevant).

    Args:
        repo_root:    Repository root (parent of kitty-specs/).
        mission_slug: The mission slug.
        decision_id:  The ULID identifier of the decision to cancel.
        rationale:    Explanation of why it's being canceled (required).
        resolved_by:  Identity of the canceling party (falls back to actor).
        actor:        Identity of the acting agent.
        dry_run:      If True, validate without writing.

    Returns:
        DecisionTerminalResponse
    """
    return _terminal_command(
        repo_root,
        mission_slug,
        decision_id,
        target_status=DecisionStatus.CANCELED,
        terminal_outcome="canceled",
        rationale=rationale,
        resolved_by=resolved_by,
        actor=actor,
        dry_run=dry_run,
    )
