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
from typing import Any

import ulid as _ulid_mod

from kernel.clock import datetime, now_utc
from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded
from kernel.locks import machine_file_lock
from specify_cli.decisions import emit as _emit
from specify_cli.decisions import index_fold as _index_fold
from specify_cli.decisions import store as _store
from specify_cli.decisions.models import (
    DecisionErrorCode,
    DecisionIndex,
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
    "DecisionEventLogReadError",
    "open_decision",
    "resolve_decision",
    "defer_decision",
    "cancel_decision",
]


# ---------------------------------------------------------------------------
# Error class
# ---------------------------------------------------------------------------


class DecisionEventLogReadError(GuardedReadError, RuntimeError):
    """Raised when ``status.events.jsonl`` exists but cannot be decoded while
    checking whether a decision's opened event was already recorded.

    Mirrors :class:`specify_cli.decisions.store.DecisionIndexReadError`
    (mission cli-error-surface-seam, WP07/#4746): a fail-closed signal
    distinguishing a genuine *read failure* (non-UTF-8 bytes or a malformed
    JSON line) from the benign *missing-file* case, which
    :func:`_opened_event_exists` still resolves to ``False`` (D5 — never
    routed through the guard).

    Not caught by ``cmd_open``'s existing ``except DecisionError`` /
    ``except DecisionIndexReadError`` clauses (``decision.py``) — it
    propagates to the global CLI error-presentation hook
    (``contracts/error-envelope.md``) like every other
    :class:`kernel.errors.GuardedReadError` subclass, rather than gaining a
    bespoke per-command presentation.
    """


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


#: T010 (D4, FR-004): the sidecar lock-only path guarding the decisions index
#: RMW. Never the payload path (``index.json`` itself) -- see
#: ``kernel.locks`` G1: the caller supplies a DEDICATED lock-only path.
_LOCK_FILENAME = "index.json.lock"

#: Bounded wait matching the NFR-002 10s hold ceiling -- a stuck holder fails
#: loudly (``LockAcquireTimeout``) rather than hanging a caller forever.
_LOCK_ACQUIRE_TIMEOUT_S = 10.0


def _decisions_lock_path(mission_dir: Path) -> Path:
    """Return the sidecar lock path guarding ``decisions/index.json``.

    Shared by the forward write path below and the reconciler
    (``cli/commands/_decisions_doctor.py``, T012, I8) -- both serialize
    against the SAME lock so a concurrent open/resolve cannot race a repair.
    """
    return _store.decisions_dir(mission_dir) / _LOCK_FILENAME


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


def _parse_opened_events(content: bytes | str) -> list[dict[str, Any]]:
    """Parse every non-blank line of *content* as a JSON event object.

    A malformed line's :class:`json.JSONDecodeError` is re-raised carrying
    the 1-based line number in its message, then collapsed by
    :func:`kernel.guarded_read.read_guarded` into
    :class:`DecisionEventLogReadError` (D5: called only after the caller has
    confirmed the events file exists — never for the absent-file case).
    """
    events: list[dict[str, Any]] = []
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(f"malformed event log line {line_number}: {exc.msg}", exc.doc, exc.pos) from exc
    return events


def _opened_event_exists(repo_root: Path, mission_slug: str, decision_id: str) -> bool:
    """Return True when the canonical opened event already exists.

    Raises:
        DecisionEventLogReadError: when ``status.events.jsonl`` exists but
            cannot be decoded (non-UTF-8 bytes or a malformed JSON line) —
            fail-closed (FR-012). Never raised when the file is simply
            absent (D5); that case returns ``False``.
    """
    path = _events_path(repo_root, mission_slug)
    if not path.exists():
        return False

    events = read_guarded(
        path,
        _parse_opened_events,
        errors=(json.JSONDecodeError,),
        error_cls=DecisionEventLogReadError,
    )
    for event in events:
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


def _locate_or_create_open_entry(
    mission_dir: Path,
    *,
    origin_flow: OriginFlow,
    step_id: str | None,
    slot_key: str | None,
    input_key: str,
    question: str,
    options: tuple[str, ...],
    actor: str,
    mission_id: str,
    mission_slug: str,
    decision_id: str | None,
) -> tuple[IndexEntry | None, IndexEntry | None, bool]:
    """T010's service-level RMW critical section for ``open_decision``.

    Runs the dedup lookup (check) and, when nothing matches, the mint +
    append (act) under ONE lock acquisition on the dedicated sidecar
    ``decisions/index.json.lock`` (D4/FR-004) -- closing the check-then-act
    window a lock scoped to ``store.save_index`` alone would leave open.

    Returns ``(existing_entry, new_entry, is_new)``: exactly one of
    ``existing_entry``/``new_entry`` is non-``None``, selected by ``is_new``.
    Entry construction routes through
    :func:`specify_cli.decisions.index_fold.build_opened_entry` -- the same
    assembler the reconciler's fold consumes (T008, "one canonical
    constructor, no second interpretation").
    """
    lock_path = _decisions_lock_path(mission_dir)
    with machine_file_lock(lock_path, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):
        index = _store.load_index(mission_dir)
        existing = _store.find_by_logical_key(
            index,
            origin_flow,
            step_id,
            slot_key,
            input_key,
        )
        if existing is not None:
            return existing, None, False

        minted_id = decision_id if decision_id is not None else _mint_decision_id()
        entry = _index_fold.build_opened_entry(
            decision_id=minted_id,
            origin_flow=origin_flow,
            step_id=step_id,
            slot_key=slot_key,
            input_key=input_key,
            question=question,
            options=options,
            created_at=now_utc(),
            opened_by=actor,
            mission_id=mission_id,
            mission_slug=mission_slug,
        )
        _store.append_entry(mission_dir, entry)
        return None, entry, True


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

    # T010 (D4/FR-004): the dedup lookup (check) and the mint-and-append
    # (act) run under ONE lock acquisition -- the service-level
    # check-then-act window this WP closes. ``store.append_entry`` still
    # does its own internal load->save, but that redundant internal read is
    # harmless here: it happens while THIS lock is held, so no other
    # open/resolve call can interleave between the dedup check and the
    # write that follows it.
    existing, entry, is_new = _locate_or_create_open_entry(
        mission_dir,
        origin_flow=origin_flow,
        step_id=step_id,
        slot_key=slot_key,
        input_key=input_key,
        question=question,
        options=options,
        actor=actor,
        mission_id=mission_id,
        mission_slug=mission_slug,
        decision_id=decision_id,
    )

    if not is_new:
        assert existing is not None  # narrows for mypy: is_new=False implies existing
        if not _is_terminal(existing.status):
            # Idempotent return — already open
            repaired_lamport = _repair_missing_opened_event(
                repo_root,
                mission_slug,
                entry=existing,
            )
            if on_minted is not None:
                on_minted(existing.decision_id)
            return DecisionOpenResponse(
                decision_id=existing.decision_id,
                idempotent=True,
                mission_id=mission_id,
                artifact_path=str(_store.artifact_path(mission_dir, existing.decision_id)),
                event_lamport=repaired_lamport,
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

    assert entry is not None  # narrows for mypy: is_new=True implies entry
    artifact = _store.write_artifact(mission_dir, entry)
    lamport = _emit.emit_decision_opened(
        repo_root,
        mission_slug,
        decision_id=entry.decision_id,
        entry=entry,
        actor=actor,
    )
    if on_minted is not None:
        on_minted(entry.decision_id)

    return DecisionOpenResponse(
        decision_id=entry.decision_id,
        idempotent=False,
        mission_id=mission_id,
        artifact_path=str(artifact),
        event_lamport=lamport,
    )


def _apply_terminal_under_lock(
    mission_dir: Path,
    decision_id: str,
    *,
    target_status: DecisionStatus,
    final_answer: str | None,
    other_answer: bool,
    rationale: str | None,
    summary_json: dict[str, str] | None,
    resolved_by: str | None,
    resolved_at: datetime,
) -> tuple[IndexEntry, bool]:
    """T010's service-level RMW critical section for resolve/defer/cancel.

    Mirrors :func:`_locate_or_create_open_entry`'s span: load -> find ->
    idempotency/conflict check -> mutate -> save, all under ONE acquisition
    of the SAME sidecar lock ``open_decision`` uses (D4/FR-004) -- a
    concurrent open and a concurrent terminal transition can never interleave
    a stale read against each other's write.

    Returns ``(entry, idempotent)``. Raises :class:`DecisionError`
    (``NOT_FOUND`` / ``TERMINAL_CONFLICT``) from inside the lock -- the lock
    is released via the context manager's own ``finally`` regardless.
    """
    lock_path = _decisions_lock_path(mission_dir)
    with machine_file_lock(lock_path, blocking=True, timeout_s=_LOCK_ACQUIRE_TIMEOUT_S):
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
                    return entry, True
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

        # Apply the terminal transition via the SAME assembler the
        # reconciler's fold uses (T008, "one canonical mapping").
        updated_entry = _index_fold.apply_terminal(
            entry,
            status=target_status,
            final_answer=final_answer,
            other_answer=other_answer,
            rationale=rationale,
            resolved_at=resolved_at,
            resolved_by=resolved_by,
            summary_json=summary_json,
        )
        new_entries = tuple(updated_entry if e.decision_id == decision_id else e for e in index.entries)
        new_index = DecisionIndex(
            version=index.version,
            mission_id=index.mission_id,
            entries=new_entries,
        )
        _store.save_index(mission_dir, new_index)
        return updated_entry, False


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
    # T010 (D4/FR-004): load -> find -> idempotency/conflict-check -> mutate
    # -> save all run under ONE lock acquisition (see
    # ``_apply_terminal_under_lock``) instead of the prior lock-free
    # load-then-separately-locked-``store.update_entry`` pattern, which left
    # the check-then-act window between them open to a concurrent writer.
    updated_entry, idempotent = _apply_terminal_under_lock(
        mission_dir,
        decision_id,
        target_status=target_status,
        final_answer=final_answer,
        other_answer=other_answer,
        rationale=rationale,
        summary_json=summary_json,
        resolved_by=resolved_by,
        resolved_at=now_utc(),
    )
    if idempotent:
        return DecisionTerminalResponse(
            decision_id=decision_id,
            status=target_status,
            terminal_outcome=terminal_outcome,
            idempotent=True,
            event_lamport=None,
        )

    _store.write_artifact(mission_dir, updated_entry)
    lamport = _emit.emit_decision_resolved(
        repo_root,
        mission_slug,
        decision_id=decision_id,
        entry=updated_entry,
        actor=actor,
    )

    return DecisionTerminalResponse(
        decision_id=decision_id,
        status=target_status,
        terminal_outcome=terminal_outcome,
        idempotent=False,
        event_lamport=lamport,
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
