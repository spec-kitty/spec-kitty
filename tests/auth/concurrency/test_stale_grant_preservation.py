"""Stale-grant reconciler regression tests.

These tests pin the *actual incident fix* from WP02: when one
:class:`TokenManager` rotates the refresh token and persists the new
material, a second TokenManager that still holds the stale (now-rotated-out)
token in memory must NOT delete the freshly persisted session when the
SaaS rejects its stale grant attempt.

Two scenarios are pinned:

1. **Stale rejection** — TokenManager A rotates first, TokenManager B's
   in-memory session points at the pre-rotation refresh token. When B
   sends the stale token the fake refresh raises ``invalid_grant``;
   ``run_refresh_transaction`` re-reads the on-disk material, observes
   it differs from the in-memory token (rotation already happened), and
   takes the :attr:`RefreshOutcome.STALE_REJECTION_PRESERVED` branch —
   B's ``_session`` is replaced with the freshly persisted session and
   the file is preserved (FR-006).

2. **Current rejection** — only one TokenManager exists; the SaaS revokes
   the current refresh token (e.g. user clicked "Sign out everywhere").
   The reconciler observes the persisted token still matches the
   in-memory token (no rotation happened), takes the
   :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED` branch, deletes the
   on-disk session, and the caller re-raises
   :class:`RefreshTokenExpiredError` with a user-readable hint (FR-005).
"""

from __future__ import annotations

import logging
import sys
import types
from kernel.clock import now_utc, timedelta
from pathlib import Path
import pytest

from specify_cli.auth.errors import RefreshReplayError, RefreshTokenExpiredError
from specify_cli.auth.refresh_transaction import (
    RefreshOutcome,
    run_refresh_transaction,
)
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

class _MembershipRehydrateAttempted(BaseException):
    """Raised when stale-grant tests accidentally enter hosted membership I/O."""


def _private_teamspace() -> Team:
    return Team(
        id="t-private",
        name="Private",
        role="owner",
        is_private_teamspace=True,
    )


def _make_session(
    *,
    refresh_token: str,
    access_token: str,
    session_id: str = "sess_seed",
    expired: bool = True,
) -> StoredSession:
    now = now_utc()
    access_exp = (
        now - timedelta(seconds=1)
        if expired
        else now + timedelta(seconds=900)
    )
    return StoredSession(
        user_id="user_seed",
        email="seed@example.com",
        name="Seed User",
        teams=[Team(id="t-seed", name="T", role="owner")],
        default_team_id="t-seed",
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session_id,
        issued_at=now - timedelta(seconds=900),
        access_token_expires_at=access_exp,
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class _RotateOnceFlow:
    """Token refresh flow that rotates exactly once.

    The first call rotates ``rt_seed_v1`` -> ``rt_rotated_v2`` and
    persists ``at_rotated_v2``. Any subsequent call presenting the seed
    token (now stale on disk) raises :class:`RefreshTokenExpiredError`.
    Calls presenting the rotated token also rotate again idempotently
    (kept for symmetry; no test exercises that branch here).
    """

    rotated: bool = False

    async def refresh(self, session: StoredSession) -> StoredSession:
        if session.refresh_token == "rt_seed_v1" and _RotateOnceFlow.rotated:
            raise RefreshTokenExpiredError(
                "Refresh token is invalid or expired. "
                "Run `spec-kitty auth login` again."
            )
        if session.refresh_token == "rt_seed_v1":
            _RotateOnceFlow.rotated = True
            now = now_utc()
            return StoredSession(
                user_id=session.user_id,
                email=session.email,
                name=session.name,
                # This suite validates refresh reconciliation, not membership
                # rehydrate. Return a Private Teamspace so TokenManager's
                # post-refresh hook remains a no-op.
                teams=[_private_teamspace()],
                default_team_id="t-private",
                access_token="at_rotated_v2",
                refresh_token="rt_rotated_v2",
                session_id=session.session_id,
                issued_at=now,
                access_token_expires_at=now + timedelta(seconds=900),
                refresh_token_expires_at=session.refresh_token_expires_at,
                scope=session.scope,
                storage_backend=session.storage_backend,
                last_used_at=now,
                auth_method=session.auth_method,
            )
        # The rotated token presented again — idempotent rotation.
        now = now_utc()
        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            teams=[_private_teamspace()],
            default_team_id="t-private",
            access_token="at_rotated_v3",
            refresh_token=session.refresh_token,
            session_id=session.session_id,
            issued_at=now,
            access_token_expires_at=now + timedelta(seconds=900),
            refresh_token_expires_at=session.refresh_token_expires_at,
            scope=session.scope,
            storage_backend=session.storage_backend,
            last_used_at=now,
            auth_method=session.auth_method,
        )


class _AlwaysRejectFlow:
    """Token refresh flow that always rejects with ``invalid_grant``.

    Models the case where the SaaS has revoked the session out-of-band
    (e.g. user signed out everywhere); the persisted token on disk is
    still the same token the caller is sending, so the reconciler falls
    through to ``CURRENT_REJECTION_CLEARED`` and deletes the session.
    """

    async def refresh(self, session: StoredSession) -> StoredSession:
        raise RefreshTokenExpiredError(
            "Refresh token is invalid or expired. "
            "Run `spec-kitty auth login` again."
        )


def _install_flow(
    monkeypatch: pytest.MonkeyPatch, flow_cls: type[object]
) -> None:
    """Install ``flow_cls`` as ``TokenRefreshFlow`` in ``sys.modules``."""
    flows_pkg = types.ModuleType("specify_cli.auth.flows")
    flows_pkg.__path__ = []
    refresh_module = types.ModuleType("specify_cli.auth.flows.refresh")
    refresh_module.TokenRefreshFlow = flow_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows", flows_pkg)
    monkeypatch.setitem(
        sys.modules, "specify_cli.auth.flows.refresh", refresh_module
    )


def _build_token_manager(auth_store_root: Path) -> TokenManager:
    storage = FileFallbackStorage(base_dir=auth_store_root)
    tm = TokenManager(storage)
    tm.load_from_storage_sync()
    return tm


@pytest.fixture(autouse=True)
def fail_on_membership_rehydrate(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    """Fail if this hermetic stale-grant suite attempts ``/api/v1/me``."""
    from specify_cli.auth.http import me_fetch

    calls: list[tuple[str, str]] = []

    def _fail(saas_base_url: str, access_token: str) -> dict[str, object]:
        calls.append((saas_base_url, access_token))
        raise _MembershipRehydrateAttempted(
            "stale-grant refresh tests must not call hosted /api/v1/me"
        )

    monkeypatch.setattr(me_fetch, "fetch_me_payload", _fail)
    return calls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_stale_rejection_preserves_session(
    auth_store_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """B's stale-grant rejection MUST NOT clear the freshly rotated session.

    Sequence:

    1. Seed disk with the v1 session.
    2. ``tm_a`` rotates → disk now holds v2 (``rt_rotated_v2``).
    3. ``tm_b`` (loaded BEFORE A's rotation) calls ``refresh_if_needed``
       holding the now-stale ``rt_seed_v1`` in memory.
    4. The fake refresh rejects the stale token; the reconciler sees that
       the on-disk material is no longer ``rt_seed_v1`` and falls into
       :attr:`RefreshOutcome.STALE_REJECTION_PRESERVED`.
    5. ``tm_b._session`` is replaced with the rotated session; the file
       still exists; no exception is raised.
    """
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(
        _make_session(
            refresh_token="rt_seed_v1",
            access_token="at_seed_v1",
            expired=True,
        )
    )

    _RotateOnceFlow.rotated = False
    _install_flow(monkeypatch, _RotateOnceFlow)

    tm_a = _build_token_manager(auth_store_root)
    tm_b = _build_token_manager(auth_store_root)
    # Sanity: both started with the seed token.
    a_initial = tm_a.get_current_session()
    b_initial = tm_b.get_current_session()
    assert a_initial is not None
    assert b_initial is not None
    assert a_initial.refresh_token == "rt_seed_v1"
    assert b_initial.refresh_token == "rt_seed_v1"

    # 1. tm_a rotates first.
    await tm_a.refresh_if_needed()
    a_after = tm_a.get_current_session()
    assert a_after is not None
    assert a_after.refresh_token == "rt_rotated_v2"

    # 2. tm_b still has the stale rt_seed_v1 in memory; force its
    #    in-memory session back to the pre-rotation state to simulate a
    #    long-running process. (After load_from_storage_sync there is a
    #    moment where its in-memory state predates A's rotation.)
    tm_b._session = b_initial  # noqa: SLF001 — controlled regression test

    # 3. tm_b refreshes — fake rejects the stale token.
    await tm_b.refresh_if_needed()

    # 4. tm_b's session is now the rotated material — NOT cleared.
    b_after = tm_b.get_current_session()
    assert b_after is not None, (
        "FR-006 regression: stale-grant rejection cleared the local session"
    )
    assert b_after.refresh_token == "rt_rotated_v2"
    assert b_after.access_token == "at_rotated_v2"

    # 5. The on-disk session matches A's rotated material.
    on_disk = FileFallbackStorage(base_dir=auth_store_root).read()
    assert on_disk is not None
    assert on_disk.refresh_token == "rt_rotated_v2"
    assert on_disk.access_token == "at_rotated_v2"


async def test_current_rejection_clears_with_message(
    auth_store_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A current-token rejection clears the session and surfaces the hint.

    The reconciler must:

    1. Hit the network with the current persisted refresh token.
    2. Observe the rejection (``invalid_grant``).
    3. Re-read disk; the token is unchanged (no rotation in flight).
    4. Take the :attr:`RefreshOutcome.CURRENT_REJECTION_CLEARED` branch:
       delete the session file and ``_session = None``.
    5. ``TokenManager`` re-raises :class:`RefreshTokenExpiredError` with
       the canonical "spec-kitty auth login" hint.
    """
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(
        _make_session(
            refresh_token="rt_current_v1",
            access_token="at_current_v1",
            expired=True,
        )
    )

    _install_flow(monkeypatch, _AlwaysRejectFlow)

    tm = _build_token_manager(auth_store_root)
    assert tm.get_current_session() is not None

    caplog.set_level(logging.INFO, logger="specify_cli.auth.token_manager")

    with pytest.raises(RefreshTokenExpiredError) as exc_info:
        await tm.refresh_if_needed()

    # The error message must point the user at the canonical recovery.
    assert "spec-kitty auth login" in str(exc_info.value)

    # Local session is gone.
    assert tm.get_current_session() is None
    assert FileFallbackStorage(base_dir=auth_store_root).read() is None

    # Exactly one outcome line was logged and it identifies the
    # current-rejection clear branch.
    outcomes = [
        record.message
        for record in caplog.records
        if record.name == "specify_cli.auth.token_manager"
        and record.message.startswith("refresh_transaction outcome=")
    ]
    assert len(outcomes) == 1
    assert "current_rejection_cleared" in outcomes[0]


# ---------------------------------------------------------------------------
# T013 — RefreshReplayError handler tests in _run_locked (WP03)
# ---------------------------------------------------------------------------


def _make_replay_session(
    *,
    refresh_token: str,
    access_token: str = "at_v1",
    session_id: str = "sess_replay",
) -> StoredSession:
    """Build a StoredSession for replay tests."""
    now = now_utc()
    return StoredSession(
        user_id="user_replay",
        email="replay@example.com",
        name="Replay User",
        teams=[Team(id="t-replay", name="T", role="owner")],
        default_team_id="t-replay",
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session_id,
        issued_at=now - timedelta(seconds=900),
        access_token_expires_at=now - timedelta(seconds=1),  # expired
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


def _make_refreshed_session(base: StoredSession, *, refresh_token: str, access_token: str) -> StoredSession:
    """Build a refreshed StoredSession with rotated tokens."""
    now = now_utc()
    return StoredSession(
        user_id=base.user_id,
        email=base.email,
        name=base.name,
        teams=list(base.teams),
        default_team_id=base.default_team_id,
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=base.session_id,
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=900),
        refresh_token_expires_at=base.refresh_token_expires_at,
        scope=base.scope,
        storage_backend=base.storage_backend,
        last_used_at=now,
        auth_method=base.auth_method,
    )


@pytest.mark.asyncio
async def test_replay_newer_persisted_retries_and_refreshes(
    auth_store_root: Path,
) -> None:
    """
    Scenario: flow.refresh(persisted) raises RefreshReplayError.
    Persisted session has a different (newer) refresh_token.
    Expected: _run_locked retries with repersisted; returns REFRESHED.
    Verify: mock_flow.refresh was called with repersisted, NOT with persisted.
    """
    # Initial persisted session (the "spent" token)
    persisted = _make_replay_session(refresh_token="spent_token")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    # The repersisted session (newer token another process already wrote)
    repersisted = _make_replay_session(refresh_token="fresh_token")

    # The result of a successful second refresh
    refreshed = _make_refreshed_session(repersisted, refresh_token="rotated_v2", access_token="at_v2")

    call_count = 0

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: update storage to simulate another process having rotated
                storage.write(repersisted)
                raise RefreshReplayError(retry_after=0)
            # Second call (with repersisted): succeed
            assert session.refresh_token == "fresh_token", (
                f"Second call must use repersisted token, got {session.refresh_token!r}"
            )
            return refreshed

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_test.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.REFRESHED
    assert result.session is not None
    assert result.session.refresh_token == "rotated_v2"
    assert call_count == 2


@pytest.mark.asyncio
async def test_replay_same_token_returns_lock_timeout(
    auth_store_root: Path,
) -> None:
    """
    Scenario: flow.refresh(persisted) raises RefreshReplayError.
    Persisted session has the SAME refresh_token as persisted.
    Expected: returns LOCK_TIMEOUT_ERROR; mock_flow.refresh called exactly once.
    """
    persisted = _make_replay_session(refresh_token="same_token")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    call_count = 0

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            nonlocal call_count
            call_count += 1
            # Storage still has the same token (no rotation happened yet)
            raise RefreshReplayError(retry_after=0)

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_same.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.LOCK_TIMEOUT_ERROR
    assert call_count == 1


@pytest.mark.asyncio
async def test_replay_none_persisted_returns_lock_timeout(
    auth_store_root: Path,
) -> None:
    """
    Scenario: flow.refresh(persisted) raises RefreshReplayError.
    storage.read() returns None (session cleared concurrently).
    Expected: returns LOCK_TIMEOUT_ERROR.
    """
    persisted = _make_replay_session(refresh_token="some_token")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            # Clear storage to simulate concurrent logout
            storage.delete()
            raise RefreshReplayError(retry_after=0)

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_none.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.LOCK_TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_replay_retry_also_fails_returns_lock_timeout(
    auth_store_root: Path,
) -> None:
    """
    Scenario: first call raises RefreshReplayError; second call also raises RefreshReplayError.
    Expected: returns LOCK_TIMEOUT_ERROR; no third call.
    Verify no infinite loop: mock_flow.refresh.call_count == 2.
    """
    persisted = _make_replay_session(refresh_token="spent_token")
    repersisted = _make_replay_session(refresh_token="fresh_token")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    call_count = 0

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: update storage with newer token, then replay
                storage.write(repersisted)
                raise RefreshReplayError(retry_after=0)
            # Second call: also replay — no third attempt allowed
            raise RefreshReplayError(retry_after=0)

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_double.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.LOCK_TIMEOUT_ERROR
    assert call_count == 2, f"Expected exactly 2 calls, got {call_count}"


@pytest.mark.asyncio
async def test_replay_spent_token_never_resubmitted(
    auth_store_root: Path,
) -> None:
    """
    Critical invariant test: after a 409, the retry MUST NOT use persisted.refresh_token.
    Arrange: persisted.refresh_token = "spent"; repersisted.refresh_token = "fresh".
    Assert: the second refresh call received a session with refresh_token="fresh".
    Assert: no call ever received refresh_token="spent" after the 409.
    """
    persisted = _make_replay_session(refresh_token="spent")
    repersisted = _make_replay_session(refresh_token="fresh")
    refreshed = _make_refreshed_session(repersisted, refresh_token="rotated", access_token="at_rotated")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    calls: list[str] = []  # Record the refresh_token used in each call

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            calls.append(session.refresh_token)
            if len(calls) == 1:
                # First call: simulate another process already rotated
                storage.write(repersisted)
                raise RefreshReplayError(retry_after=0)
            return refreshed

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_spent.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.REFRESHED

    # The first call used the persisted (spent) token — that's expected
    assert calls[0] == "spent"
    # The second call MUST use the fresh (repersisted) token — NEVER the spent one
    assert calls[1] == "fresh", (
        f"Second call must use repersisted token 'fresh', got {calls[1]!r}"
    )
    # No call after the 409 used the spent token
    assert "spent" not in calls[1:], (
        "Spent token was re-submitted after the 409 replay"
    )


@pytest.mark.asyncio
async def test_replay_lock_timeout_carries_replay_message(
    auth_store_root: Path,
) -> None:
    """LOCK_TIMEOUT_ERROR from a replay path carries a replay-specific message.

    The message must NOT say "Another spec-kitty process is refreshing" —
    that wording implies lock contention, which is false for a benign replay.
    """
    persisted = _make_replay_session(refresh_token="same_token")
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(persisted)

    class _MockFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            raise RefreshReplayError(retry_after=0)

    result = await run_refresh_transaction(
        storage=storage,
        in_memory_session=persisted,
        refresh_flow=_MockFlow(),  # type: ignore[arg-type]
        lock_path=auth_store_root / "replay_msg.lock",
        max_hold_s=5.0,
    )

    assert result.outcome == RefreshOutcome.LOCK_TIMEOUT_ERROR
    assert result.lock_timeout_message is not None
    assert "replay detected" in result.lock_timeout_message
    assert "auth login" in result.lock_timeout_message
    assert "Another spec-kitty process" not in result.lock_timeout_message
