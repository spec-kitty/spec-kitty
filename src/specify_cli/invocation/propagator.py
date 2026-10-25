# CONTRACT VERIFICATION
# Verified 2026-04-21: The spec-kitty-saas repo is not co-located with this
# codebase; the cli-saas-current-api.yaml contract file is not accessible.
#
# Verification basis is historical: the former local SaaS client was removed
# with the retired transport. No runtime client seam is expected in this tree.
#
# Client protocol: send_event(event: dict) is ASYNC and takes a single flat
# dict with an "event_type" discriminator field at the top level.  There is NO
# idempotency_key keyword argument.  The emitter pattern (emitter.py:993-1000)
# calls it via asyncio.ensure_future() when a loop is running, or via
# loop.run_until_complete() otherwise.
#
# Envelope shape (mission do-dispatch-open-op-lifecycle, decision
# 01KTSJEQANMNEV16WMSAJP6FR1 — no wire-compat with the pre-mission envelope;
# SaaS handlers are unimplemented, #1720/#1693):
#   Envelope dicts are rebuilt 1:1 from the v2 Op event models
#   (contracts/op-record-events.md):
#   ProfileInvocationStarted:   event_type + all OpStartedEvent fields
#                               (None fields omitted; request_text policy-gated)
#   ProfileInvocationCompleted: event_type + all OpCompletedEvent fields incl.
#                               closed_by (evidence_ref omitted when None and
#                               policy-gated)

from __future__ import annotations

import atexit
import asyncio
import contextlib
import json
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from kernel.event_log_append import append_event_log_lines
from kernel.clock import now_utc_iso
from specify_cli.invocation.adapters import get_saas_client as _get_saas_client_from_seam
from specify_cli.invocation.projection_policy import EventKind, ModeOfWork, resolve_projection
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent

# v2 Op lifecycle events accepted by the propagator (WP01 schema split).
OpEvent = OpStartedEvent | OpCompletedEvent

logger = logging.getLogger(__name__)

PROPAGATION_ERRORS_PATH = "kitty-ops/propagation-errors.jsonl"
_ATEXIT_TIMEOUT_SECONDS = 5.0
_PENDING_SEND_TASKS: set[asyncio.Task[Any]] = set()


def _track_send_task(task: asyncio.Task[Any]) -> None:
    """Retain scheduled send tasks until completion to avoid premature GC."""
    _PENDING_SEND_TASKS.add(task)
    task.add_done_callback(_PENDING_SEND_TASKS.discard)


def _get_saas_client(repo_root: Path) -> Any | None:
    """Return the connected SaaS client if available; None otherwise.

    Dispatches through the invocation adapter seam so that propagator.py
    has no direct import edge into the sync package (Leak #3 fix).
    Never raises — the seam guarantees safe-degrade on missing registration.

    **In production this returns ``None`` every time, and has always done so**
    (#3030 FR-032). No package registers a SaaS-client factory. ``sync`` used to
    register one, but its whole body read ``token_manager._ws_client`` — an attribute
    ``src/`` has never assigned — so it answered ``None`` on every call; the
    registration was deleted rather than left as an accident that happens to be safe.
    Everything below this lookup in :func:`_propagate_one` is therefore inert until
    someone registers a real factory, and that is a deliberate state, not an oversight.

    Registering a factory here opens an egress path carrying ``request_text`` — the
    verbatim agent prompt. Wiring it to ``SyncRuntime.ws_client`` was considered
    during #3030 and explicitly rejected; whoever registers a real transport owns
    the auth/admission gate that makes that safe. (The former egress-consent gate
    ahead of this lookup retired with the sync transport, issue #5.)
    """
    return _get_saas_client_from_seam(repo_root)


def _propagate_one(record: OpEvent, repo_root: Path) -> None:
    """Propagate a single Op lifecycle event to SaaS.

    Runs in a background thread.  Logs errors to propagation-errors.jsonl on
    failure.  Never raises — swallows all exceptions.

    The real SaaS client uses ``async def send_event(self, event: dict)``.
    It is NOT synchronous and does NOT accept an idempotency_key kwarg.
    This call pattern historically mirrored the deleted sync package's
    ``sync/emitter.py`` (removed along with the sync transport, issue #5).

    Check ordering (invariant — do not reorder):
      1. Auth/client lookup (_get_saas_client returns None → early return)
      2. Policy lookup (resolve_projection → project=False → early return)
      3. Envelope build + send

    (The former step-1 egress-consent gate retired with the sync transport,
    issue #5.)
    """
    client = _get_saas_client(repo_root)
    if client is None:
        return  # No SaaS token / client not connected → no-op, no log

    # 3. Policy lookup (read-only, never raises, never blocks).
    rule = _projection_rule_for(record)
    if rule is None:
        return  # Record could not be classified → no policy row → no projection.
    if not rule.project:
        return  # Policy says no projection for this (mode, event) pair.

    try:
        event_dict = _build_event_dict(record, rule)
        _send_event(client, event_dict)

    except Exception as exc:  # noqa: BLE001
        _log_propagation_error(repo_root, record, str(exc))

    # NOTE: Correlation events (artifact_link / commit_link) are written locally by
    # InvocationWriter.append_correlation_link() in executor.py but are NOT currently
    # submitted to the propagator.  The executor submits both v2 lifecycle events
    # (OpStartedEvent at invoke time, OpCompletedEvent at close time) to
    # propagator.submit(); correlation events remain local-only per the ADR-004
    # Tier-2 stance.  The dict-record branch for correlation events is therefore
    # deferred until the executor wires correlation-event propagation.  When that
    # wiring lands, add a branch here:
    #   if isinstance(record, dict):
    #       event_type_map = {"artifact_link": "ProfileInvocationArtifactLink",
    #                         "commit_link": "ProfileInvocationCommitLink"}
    #       ...and consult rule.project before calling client.send_event.


def _projection_rule_for(record: OpEvent) -> Any | None:
    """Resolve the projection rule for *record*, or ``None`` if it cannot be classified.

    ``None`` means "this record's policy row is unknown", and the caller drops the
    record rather than projecting it. That is a behaviour change from the two
    coercions this replaced, both of which resolved an *unintelligible* value to the
    most permissive rule available — an unknown ``event`` became ``STARTED`` and a
    malformed ``mode_of_work`` became ``None``, and both land on a rule with
    ``project=True, include_request_text=True``. Same shape as FR-025's guard: a
    value meaning "unknown" was spelled the same way as a definite answer, and the
    definite answer it borrowed was the permissive one. Reachable only through a
    schema change (the models validate both fields against Literals today), which
    is exactly when nobody is looking.

    **Absence is not malformation, and the two must not re-collapse.**
    ``OpCompletedEvent`` carries no ``mode_of_work`` at all, and neither do pre-v2
    records; those keep the documented legacy default (``None`` → treated as
    ``TASK_EXECUTION`` by ``resolve_projection``). Refusing on absence instead would
    silently stop propagating every completed event — a fail-closed answer to a
    question nobody asked.
    """
    try:
        event_kind = EventKind(record.event)
    except ValueError:
        logger.warning(
            "Op %s has an unrecognised event kind %r; not projecting it "
            "(no projection-policy row applies)",
            record.invocation_id,
            record.event,
        )
        return None

    raw_mode = getattr(record, "mode_of_work", None)
    if raw_mode is None or raw_mode == "":
        # Absent: legacy records and every OpCompletedEvent. Documented default.
        return resolve_projection(None, event_kind)
    try:
        mode = ModeOfWork(raw_mode)
    except ValueError:
        logger.warning(
            "Op %s declares an unrecognised mode_of_work %r; not projecting it "
            "(the record's disclosure policy cannot be determined)",
            record.invocation_id,
            raw_mode,
        )
        return None
    return resolve_projection(mode, event_kind)


def _build_event_dict(
    record: OpEvent,
    rule: Any,
) -> dict[str, object]:
    if isinstance(record, OpStartedEvent):
        return _build_started_event_dict(record, rule)
    return _build_completed_event_dict(record, rule)


def _build_started_event_dict(
    record: OpStartedEvent,
    rule: Any,
) -> dict[str, object]:
    """Envelope built 1:1 from the v2 OpStartedEvent (op-record-events.md).

    No wire-compat with the pre-mission envelope (decision
    01KTSJEQANMNEV16WMSAJP6FR1). Optional fields (router_confidence,
    mission_id, wp_id, model_id) are omitted when absent, mirroring the on-disk
    JSONL shape. request_text is policy-gated
    (projection_policy.include_request_text).
    """
    event_dict: dict[str, object] = record.model_dump(exclude_none=True)
    del event_dict["event"]
    event_dict["event_type"] = "ProfileInvocationStarted"
    if not rule.include_request_text:
        event_dict.pop("request_text", None)
    return event_dict


def _build_completed_event_dict(record: OpCompletedEvent, rule: Any) -> dict[str, object]:
    """Envelope built 1:1 from the v2 OpCompletedEvent — includes ``closed_by``.

    evidence_ref is omitted when None (on-disk parity) and policy-gated.
    """
    event_dict: dict[str, object] = record.model_dump(exclude_none=True)
    del event_dict["event"]
    event_dict["event_type"] = "ProfileInvocationCompleted"
    if not rule.include_evidence_ref:
        event_dict.pop("evidence_ref", None)
    return event_dict


def _send_event(client: Any, event_dict: dict[str, object]) -> None:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already inside a running loop (rare in CLI threads, but safe)
            _track_send_task(asyncio.create_task(client.send_event(event_dict)))
            return
        loop.run_until_complete(client.send_event(event_dict))
    except RuntimeError:
        # No current event loop (background thread with no loop) → create one
        asyncio.run(client.send_event(event_dict))


def _log_propagation_error(
    repo_root: Path, record: OpEvent, error: str
) -> None:
    """Append propagation failure to the local error log.  Never raises."""
    try:
        error_log = repo_root / PROPAGATION_ERRORS_PATH
        entry = {
            "invocation_id": record.invocation_id,
            "event": record.event,
            "error": error,
            "at": now_utc_iso(),
        }
        # interim-locked-append: retires at the #6193 handover (kernel.event_log_append).
        append_event_log_lines(error_log, [json.dumps(entry)], create_parents=True)
    except Exception:  # noqa: BLE001
        pass  # Error logging must never raise


class InvocationSaaSPropagator:
    """Background-thread SaaS propagator for Op lifecycle events.

    Properties:
    - Non-blocking: submit() returns immediately; propagation happens in background.
    - Additive: if no SaaS token, no-op (no error, no warning to caller).
    - Failure-safe: propagation errors logged to propagation-errors.jsonl, never raised.
    - Process-exit: atexit handler waits for the ThreadPoolExecutor to drain
      (up to the OS process-exit timeout; work not finished is abandoned).
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._executor: ThreadPoolExecutor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="invocation-saas"
        )
        self._pending: list[Future[None]] = []
        atexit.register(self._shutdown)

    def submit(self, record: OpEvent) -> None:
        """Submit a record for background propagation.  Returns immediately."""
        future: Future[None] = self._executor.submit(_propagate_one, record, self._repo_root)
        self._pending.append(future)

    def _shutdown(self) -> None:
        """Wait for pending propagations at process exit.

        ``shutdown(wait=True)`` blocks until all submitted futures complete.
        Python's process-exit machinery imposes its own timeout, so threads
        that have not finished by then are abandoned (acceptable behaviour).
        """
        with contextlib.suppress(Exception):
            self._executor.shutdown(wait=True, cancel_futures=False)
