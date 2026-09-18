"""Bounded refresh transaction with stale-grant preservation.

This module is the actual incident fix for the
``cli-session-survival-daemon-singleton`` mission. Before this WP,
:meth:`TokenManager.refresh_if_needed` cleared the local session whenever the
SaaS rejected the in-memory refresh token with ``invalid_grant``. With
multiple concurrent CLI processes that pattern was unsafe: process A could
rotate the refresh token, persist the new material, and exit; process B —
still holding the now-rotated-out token in memory — would attempt a refresh,
receive ``invalid_grant`` against the stale token, and silently delete the
*new* session that A had just persisted.

The fix is the **read-decide-refresh-reconcile** sequence executed inside a
machine-wide :class:`MachineFileLock` (WP01):

1. Acquire the lock (bounded wait).
2. **Read** persisted material under the lock.
3. **Decide** — if the persisted refresh token differs from the in-memory
   one and is non-expired, adopt it and skip the network call (FR-004).
4. Otherwise **refresh** with the persisted material.
5. **Reconcile** any rejection: re-read persisted material; if the rejected
   token still matches the persisted token (the rejection was current),
   delete the session (FR-005); otherwise preserve the freshly persisted
   material (FR-006) — that's the bug fix.

The :class:`RefreshOutcome` enum records which branch ran. Callers consume
:class:`RefreshResult` and translate it into legacy exception semantics so
existing call sites in ``auth/transport.py`` are unaffected (FR-020).

Identity comparison uses ``(session_id, refresh_token)`` byte equality per
``data-model.md`` §"AuthSession" (research D4). Both fields must match for
the rejected material to count as "current".

This module is consumed by :class:`specify_cli.auth.token_manager.TokenManager`
and is **never** imported by call sites outside the auth package. It performs
no I/O at import time and adds no third-party dependencies.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from kernel.locks import LockAcquireTimeout, MachineFileLock
from .errors import RefreshReplayError, RefreshTokenExpiredError, SessionInvalidError
from .secure_storage import SecureStorage
from .session import StoredSession

if TYPE_CHECKING:  # pragma: no cover - import only for static type checking
    from .flows.refresh import TokenRefreshFlow

__all__ = [
    "RefreshLockTimeoutError",
    "RefreshOutcome",
    "RefreshRejectionCause",
    "RefreshResult",
    "run_refresh_transaction",
]

log = logging.getLogger(__name__)

# Buffer (seconds) used when deciding whether the persisted material would
# survive long enough to be adopted in lieu of a network call. Mirrors the
# value used in :class:`TokenManager` so the two stay in lock-step.
_ADOPT_BUFFER_SECONDS = 5


class RefreshOutcome(StrEnum):
    """Discriminates the six terminal states of a refresh transaction.

    See research D5 for the state machine that maps inputs to outcomes.
    """

    ADOPTED_NEWER = "adopted_newer"
    """Persisted material was newer-and-valid — adopted without network call (FR-004)."""

    REFRESHED = "refreshed"
    """Performed a network refresh; rotated tokens persisted."""

    STALE_REJECTION_PRESERVED = "stale_rejection_preserved"
    """SaaS rejected stale material; freshly persisted session preserved (FR-006)."""

    CURRENT_REJECTION_CLEARED = "current_rejection_cleared"
    """SaaS rejected current material; local session deleted (FR-005)."""

    LOCK_TIMEOUT_ADOPTED = "lock_timeout_adopted"
    """Lock contention timed out, but persisted material is still usable."""

    LOCK_TIMEOUT_ERROR = "lock_timeout_error"
    """Lock contention timed out and persisted material is unusable — caller must surface error."""


class RefreshRejectionCause(StrEnum):
    """Identifies which canonical rejection exception triggered a clear.

    Set on :class:`RefreshResult` only when the outcome is
    :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED` so the caller can
    re-raise the correct legacy exception (preserving FR-020 byte-equal
    behaviour for ``auth/transport.py``).
    """

    # `refresh_token_expired` is an enum label surfaced to callers, not a secret.
    REFRESH_TOKEN_EXPIRED = "refresh_token_expired"  # noqa: S105
    SESSION_INVALID = "session_invalid"


@dataclass(frozen=True)
class RefreshResult:
    """The terminal state of a single :func:`run_refresh_transaction` call.

    Attributes:
        outcome: which :class:`RefreshOutcome` branch ran.
        session: the session the caller should adopt as in-memory state, or
            ``None`` for :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED`.
        network_call_made: ``True`` iff the SaaS refresh endpoint was hit.
        rejection_cause: which exception caused
            :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED`; ``None`` for
            every other outcome.
    """

    outcome: RefreshOutcome
    session: StoredSession | None
    network_call_made: bool
    rejection_cause: RefreshRejectionCause | None = None
    lock_timeout_message: str | None = None


class RefreshLockTimeoutError(Exception):
    """Raised by :class:`TokenManager` when the refresh lock cannot be acquired.

    Distinct from :class:`LockAcquireTimeout` (raised by the lock helper) so
    callers can pattern-match cleanly. Carries a user-friendly recovery hint
    for surface-level reporting.
    """

    def __init__(
        self,
        message: str = (
            "Another spec-kitty process is refreshing the auth session; "
            "retry in a moment."
        ),
    ) -> None:
        super().__init__(message)


def _identity_matches(a: StoredSession, b: StoredSession) -> bool:
    """Return ``True`` when ``a`` and ``b`` represent the same auth material.

    Uses ``(session_id, refresh_token)`` byte equality per
    ``data-model.md`` §"AuthSession" (research D4). Both fields must match;
    matching only one is **not** sufficient because refresh-token rotation
    inside a single session is the precise scenario that triggered the
    incident.
    """
    same_session = bool(a.session_id == b.session_id)
    same_refresh = bool(a.refresh_token == b.refresh_token)
    return same_session and same_refresh


async def run_refresh_transaction(
    *,
    storage: SecureStorage,
    in_memory_session: StoredSession,
    refresh_flow: TokenRefreshFlow,
    lock_path: Path,
    max_hold_s: float = 10.0,
) -> RefreshResult:
    """Execute one bounded refresh transaction.

    Behavior overview:

    - Attempts to acquire :class:`MachineFileLock` at ``lock_path`` within
      ``max_hold_s`` seconds.
    - On success: reloads persisted material; if newer-and-valid, adopts and
      skips the network call. Otherwise calls
      ``refresh_flow.refresh(persisted)`` wrapped in
      :func:`asyncio.wait_for` so the network leg also honours
      ``max_hold_s``. On rejection (``RefreshTokenExpiredError`` /
      ``SessionInvalidError``) re-reads persisted material and decides
      between :attr:`RefreshOutcome.STALE_REJECTION_PRESERVED` and
      :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED`.
    - On lock-acquire timeout: re-reads persisted material; if non-expired
      adopts (``LOCK_TIMEOUT_ADOPTED``), otherwise reports
      ``LOCK_TIMEOUT_ERROR`` so the caller can surface a retry hint.
    - On network timeout (``asyncio.TimeoutError``): the lock context manager
      releases on the way out; the result is reported as
      ``LOCK_TIMEOUT_ERROR`` (semantically a retryable error per the spec).

    The function never raises ``RefreshTokenExpiredError`` or
    ``SessionInvalidError`` directly — the caller (``TokenManager``) is
    responsible for re-raising those after observing the outcome so existing
    callers in ``auth/transport.py`` keep working unchanged (FR-020).

    Args:
        storage: secure storage backend (authoritative on-disk state).
        in_memory_session: the caller's current in-memory session — used as
            the identity baseline for the reload-vs-adopt decision.
        refresh_flow: the network refresh flow (DI for testability).
        lock_path: filesystem path of the machine-wide lock file.
        max_hold_s: bounded wait for both lock acquisition and network refresh.

    Returns:
        :class:`RefreshResult` describing the terminal outcome.
    """
    try:
        async with MachineFileLock(
            lock_path,
            max_hold_s=max_hold_s,
            acquire_timeout_s=max_hold_s,
        ):
            return await _run_locked(
                storage=storage,
                in_memory_session=in_memory_session,
                refresh_flow=refresh_flow,
                max_hold_s=max_hold_s,
            )
    except LockAcquireTimeout:
        # Another process is mid-transaction. Try to adopt the persisted
        # material if it still looks usable; otherwise surface the timeout
        # so the caller can ask the user to retry.
        persisted = storage.read()
        if persisted is not None and not persisted.is_access_token_expired(
            buffer_seconds=_ADOPT_BUFFER_SECONDS
        ):
            return RefreshResult(
                outcome=RefreshOutcome.LOCK_TIMEOUT_ADOPTED,
                session=persisted,
                network_call_made=False,
            )
        return RefreshResult(
            outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
            session=in_memory_session,
            network_call_made=False,
        )


async def _run_locked(
    *,
    storage: SecureStorage,
    in_memory_session: StoredSession,
    refresh_flow: TokenRefreshFlow,
    max_hold_s: float,
) -> RefreshResult:
    """Body of the transaction — assumes the machine-wide lock is held."""
    persisted = storage.read()

    # Edge case: storage emptied mid-transaction (e.g. another process
    # cleared the session). The caller cannot keep using the in-memory
    # session blindly — surface as a retryable error so re-login is the
    # explicit path forward (per T007 edge case).
    if persisted is None:
        return RefreshResult(
            outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
            session=in_memory_session,
            network_call_made=False,
        )

    # FR-004: adopt persisted-newer material instead of refreshing.
    if not _identity_matches(persisted, in_memory_session) and not (
        persisted.is_access_token_expired(buffer_seconds=_ADOPT_BUFFER_SECONDS)
    ):
        return RefreshResult(
            outcome=RefreshOutcome.ADOPTED_NEWER,
            session=persisted,
            network_call_made=False,
        )

    # Network refresh, bounded by max_hold_s. The lock is released by the
    # outer context manager regardless of which branch we exit through.
    try:
        updated = await asyncio.wait_for(
            refresh_flow.refresh(persisted), timeout=max_hold_s
        )
    except TimeoutError:
        # Network leg exceeded the hold budget — semantically a retryable
        # lock-timeout-style outcome. The caller surfaces a recovery hint.
        return RefreshResult(
            outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
            session=in_memory_session,
            network_call_made=True,
        )
    except (RefreshTokenExpiredError, SessionInvalidError) as exc:
        # Reconciler — the entire incident fix in two lines plus a guard.
        # Re-read persisted material AFTER the rejection and compare to the
        # token we sent. Identity rule: (session_id, refresh_token) byte
        # equality (data-model.md §"AuthSession", research D4).
        cause = (
            RefreshRejectionCause.REFRESH_TOKEN_EXPIRED
            if isinstance(exc, RefreshTokenExpiredError)
            else RefreshRejectionCause.SESSION_INVALID
        )
        repersisted = storage.read()
        rejected_was_current = (
            repersisted is not None and _identity_matches(repersisted, persisted)
        )
        if rejected_was_current:
            # FR-005: the SaaS rejected current material. Clear local
            # session and let the caller re-raise the original exception
            # so transport.py's existing pattern keeps working.
            storage.delete()
            return RefreshResult(
                outcome=RefreshOutcome.CURRENT_REJECTION_CLEARED,
                session=None,
                network_call_made=True,
                rejection_cause=cause,
            )
        if repersisted is None:
            # A concurrent process deleted the storage (logout/clear). The
            # rejection was not against current material, but there is no
            # session left to preserve. Surface as cleared so the caller
            # raises the canonical re-login error instead of asserting on
            # a None session downstream.
            return RefreshResult(
                outcome=RefreshOutcome.CURRENT_REJECTION_CLEARED,
                session=None,
                network_call_made=True,
                rejection_cause=cause,
            )
        if repersisted.is_refresh_token_expired():
            # The repersisted material is itself unusable: even though our
            # rejection was stale, the local session can no longer refresh.
            # Clear and require re-login.
            storage.delete()
            return RefreshResult(
                outcome=RefreshOutcome.CURRENT_REJECTION_CLEARED,
                session=None,
                network_call_made=True,
                rejection_cause=cause,
            )
        if repersisted.is_access_token_expired(buffer_seconds=_ADOPT_BUFFER_SECONDS):
            # Refresh token still valid, but the access token is already
            # expired. Adopting it would leak an expired bearer to the
            # caller of get_access_token(). Preserve storage but fail this
            # call retryably; the next refresh_if_needed will rotate the
            # access token cleanly.
            return RefreshResult(
                outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
                session=repersisted,
                network_call_made=True,
            )
        # FR-006: a different process has already rotated; the rejection
        # was against stale material we held in memory. Preserve the
        # freshly persisted session — DO NOT delete.
        return RefreshResult(
            outcome=RefreshOutcome.STALE_REJECTION_PRESERVED,
            session=repersisted,
            network_call_made=True,
        )

    except RefreshReplayError:
        # Server says the presented token was just spent (benign network race).
        # Re-read persisted session and retry once if a newer token is available.
        repersisted = storage.read()

        _REPLAY_MSG = (
            "Refresh token replay detected and no newer local token is available. "
            "Run `spec-kitty auth login` if this persists."
        )

        if repersisted is None:
            # Session cleared concurrently; surface as retryable.
            log.warning("409 replay: session cleared concurrently; surfacing as LOCK_TIMEOUT_ERROR")
            return RefreshResult(
                outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
                session=in_memory_session,
                network_call_made=True,
                lock_timeout_message=_REPLAY_MSG,
            )

        if repersisted.refresh_token == persisted.refresh_token:
            # Persisted token matches the spent one — no newer token in storage yet.
            # Do NOT retry; surfacing LOCK_TIMEOUT_ERROR signals "please retry later",
            # which is the correct caller behavior. This is NOT machine lock contention;
            # the log below distinguishes it from actual _run_locked timeout cases.
            log.warning(
                "409 replay: no newer token in storage yet; "
                "surfacing LOCK_TIMEOUT_ERROR to trigger caller retry. "
                "This is a benign replay outcome, not lock contention."
            )
            return RefreshResult(
                outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
                session=repersisted,
                network_call_made=True,
                lock_timeout_message=_REPLAY_MSG,
            )

        # Persisted token differs from spent — another process already rotated it.
        # Retry ONCE with the newer token. CRITICAL: never use `persisted` here.
        try:
            updated = await asyncio.wait_for(
                refresh_flow.refresh(repersisted), timeout=max_hold_s
            )
        except Exception:  # noqa: BLE001 - any second refresh failure becomes bounded replay retry guidance
            # Catch all failures on the second attempt: TokenRefreshError and
            # subclasses (expired, session-invalid, another replay), asyncio
            # TimeoutError, httpx network errors, and anything else.
            # Any second failure surfaces as LOCK_TIMEOUT_ERROR — no third attempt.
            log.warning("409 replay: second refresh attempt also failed; surfacing LOCK_TIMEOUT_ERROR")
            return RefreshResult(
                outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
                session=repersisted,
                network_call_made=True,
                lock_timeout_message=_REPLAY_MSG,
            )

        storage.write(updated)
        return RefreshResult(
            outcome=RefreshOutcome.REFRESHED,
            session=updated,
            network_call_made=True,
        )

    # Happy path: persist and report.
    storage.write(updated)
    return RefreshResult(
        outcome=RefreshOutcome.REFRESHED,
        session=updated,
        network_call_made=True,
    )
