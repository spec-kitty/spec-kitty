"""Tests for ``specify_cli.auth.token_manager`` (feature 080, WP01 T007).

The headline test is ``test_concurrent_get_access_token_is_single_flight``:
10 concurrent callers with an expired session must result in **exactly one**
refresh call. This is the central guarantee WP08 and every subsequent WP
depends on.

TokenManager's refresh path imports ``auth.flows.refresh.TokenRefreshFlow``
lazily — these tests inject a fake ``flows.refresh`` module into
``sys.modules`` so the lazy import picks up our mock.

WP02 (cli-session-survival-daemon-singleton) extends the suite with
coverage for every :class:`RefreshOutcome` branch, the stale-grant
preservation invariant (FR-006 — the actual incident fix), and the
machine-wide lock-timeout escape hatches (FR-016/FR-017).
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
import types
from kernel.clock import datetime, now_utc, timedelta

import pytest

from specify_cli.auth import refresh_transaction as rtx
from specify_cli.auth.errors import (
    NotAuthenticatedError,
    RefreshTokenExpiredError,
    SessionInvalidError,
    StorageDecryptionError,
)
from specify_cli.auth.refresh_transaction import (
    RefreshLockTimeoutError,
    RefreshOutcome,
)
from specify_cli.auth.secure_storage import SecureStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.session_hot_path import SessionHotPathSummary
from specify_cli.auth import token_manager as tm_module
from specify_cli.auth.token_manager import SessionAssessment, TokenManager
import kernel.locks as file_lock_module
from kernel.locks import LockAcquireTimeout


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]


def _now() -> datetime:
    return now_utc()


def _make_session(
    *,
    access_expires_in: int = 900,
    refresh_token_expires_at: datetime | None = None,
    refresh_token: str = "refresh-v1",
    access_token: str = "access-v1",
) -> StoredSession:
    now = _now()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        # WP02: include a Private Teamspace so the post-refresh hook in
        # ``refresh_if_needed`` short-circuits (no synthetic /api/v1/me HTTP).
        teams=[Team(id="t1", name="T1", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token=access_token,
        refresh_token=refresh_token,
        session_id="sess",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=access_expires_in),
        refresh_token_expires_at=refresh_token_expires_at,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class FakeStorage(SecureStorage):
    """Minimal in-memory :class:`SecureStorage` for TokenManager tests."""

    def __init__(self) -> None:
        self._session: StoredSession | None = None
        self.writes = 0
        self.deletes = 0

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session
        self.writes += 1

    def delete(self) -> None:
        self._session = None
        self.deletes += 1

    @property
    def backend_name(self) -> str:
        return "file"


class FakeRefreshFlow:
    """Counts how many times ``refresh`` is invoked and returns a fresh token."""

    call_count = 0
    delay_seconds: float = 0.05
    raise_session_invalid: bool = False
    raise_refresh_expired: bool = False

    def __init__(self) -> None:
        # Instance counter so each test starts clean.
        pass

    async def refresh(self, session: StoredSession) -> StoredSession:
        FakeRefreshFlow.call_count += 1
        await asyncio.sleep(FakeRefreshFlow.delay_seconds)
        if FakeRefreshFlow.raise_refresh_expired:
            raise RefreshTokenExpiredError("refresh token invalid")
        if FakeRefreshFlow.raise_session_invalid:
            raise SessionInvalidError("server says no")
        # Return a brand-new session with a fresh access token and a non-expired window.
        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            teams=list(session.teams),
            default_team_id=session.default_team_id,
            access_token=f"access-v{FakeRefreshFlow.call_count + 1}",
            refresh_token=session.refresh_token,
            session_id=session.session_id,
            issued_at=_now(),
            access_token_expires_at=_now() + timedelta(seconds=900),
            refresh_token_expires_at=session.refresh_token_expires_at,
            scope=session.scope,
            storage_backend=session.storage_backend,
            last_used_at=_now(),
            auth_method=session.auth_method,
        )


@pytest.fixture(autouse=True)
def _isolated_refresh_lock(monkeypatch, tmp_path):
    """Redirect the machine-wide refresh lock to ``tmp_path``.

    Without this every test in this suite would touch the real
    ``~/.spec-kitty/auth/refresh.lock`` file, which is unsafe for parallel
    workers and pollutes the developer's home directory.
    """
    lock_path = tmp_path / "refresh.lock"
    monkeypatch.setattr(tm_module, "_refresh_lock_path", lambda: lock_path)
    yield lock_path


@pytest.fixture
def install_fake_refresh_flow(monkeypatch):
    """Install ``specify_cli.auth.flows.refresh`` as a fake module in sys.modules."""
    FakeRefreshFlow.call_count = 0
    FakeRefreshFlow.raise_session_invalid = False
    FakeRefreshFlow.raise_refresh_expired = False
    FakeRefreshFlow.delay_seconds = 0.05

    flows_pkg = types.ModuleType("specify_cli.auth.flows")
    flows_pkg.__path__ = []  # mark as a package
    refresh_module = types.ModuleType("specify_cli.auth.flows.refresh")
    refresh_module.TokenRefreshFlow = FakeRefreshFlow

    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows", flows_pkg)
    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows.refresh", refresh_module)
    yield FakeRefreshFlow


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_current_session_none_by_default():
    tm = TokenManager(FakeStorage())
    assert tm.get_current_session() is None
    assert tm.is_authenticated is False


def test_load_from_storage_sync_populates_session():
    storage = FakeStorage()
    session = _make_session()
    storage._session = session
    tm = TokenManager(storage)
    tm.load_from_storage_sync()
    assert tm.get_current_session() == session
    assert tm.is_authenticated is True
    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=True,
        reason="session_usable",
    )


def test_session_assessment_conclusively_reports_absent_session():
    tm = TokenManager(FakeStorage())

    tm.load_from_storage_sync()

    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=False,
        reason="session_absent",
    )
    assert tm.is_authenticated is False


def test_session_assessment_uses_refresh_token_semantics():
    storage = FakeStorage()
    storage._session = _make_session(
        access_expires_in=-60,
        refresh_token_expires_at=_now() + timedelta(minutes=5),
    )
    tm = TokenManager(storage)

    tm.load_from_storage_sync()

    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=True,
        reason="session_usable",
    )
    assert tm.is_authenticated is True


def test_session_assessment_conclusively_reports_expired_refresh_token():
    storage = FakeStorage()
    storage._session = _make_session(
        refresh_token_expires_at=_now() - timedelta(minutes=5),
    )
    tm = TokenManager(storage)

    tm.load_from_storage_sync()

    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=False,
        reason="refresh_token_expired",
    )
    assert tm.is_authenticated is False


def test_load_from_storage_sync_handles_storage_errors():
    class BrokenStorage(FakeStorage):
        def read(self):
            raise RuntimeError("disk on fire")

    tm = TokenManager(BrokenStorage())
    tm.load_from_storage_sync()  # must not raise
    assert tm.get_current_session() is None
    assert tm.session_assessment == SessionAssessment(
        completed=False,
        usable_session=None,
        reason="storage_read_failed",
    )
    assert tm.is_authenticated is False


def test_load_from_storage_sync_preserves_decryption_failure_reason(caplog):
    class UndecryptableStorage(FakeStorage):
        def read(self):
            raise StorageDecryptionError("credential-shaped-secret-must-not-escape")

    tm = TokenManager(UndecryptableStorage())
    tm.load_from_storage_sync()

    assert tm.session_assessment == SessionAssessment(
        completed=False,
        usable_session=None,
        reason="storage_decryption_failed",
    )
    assert "could not be decrypted" in caplog.text
    assert "credential-shaped-secret-must-not-escape" not in caplog.text


def test_hot_summary_materialization_failure_preserves_failed_assessment(
    monkeypatch,
    caplog,
):
    class BrokenStorage(FakeStorage):
        @property
        def store_path(self):
            return "/synthetic/auth"

        def read(self):
            raise RuntimeError("credential-shaped-secret-must-not-escape")

    summary = SessionHotPathSummary(
        refresh_token_expires_at=None,
        not_after_monotonic=time.monotonic() + 30,
    )
    monkeypatch.setattr(tm_module, "load_session_hot_path", lambda _path: summary)
    tm = TokenManager(BrokenStorage())
    tm.load_from_storage_sync()

    assert tm.session_assessment == SessionAssessment(
        completed=False,
        usable_session=None,
        reason="session_materialization_failed",
    )
    assert tm.is_authenticated is False
    assert "credential-shaped-secret-must-not-escape" not in caplog.text


def test_successful_set_and_clear_replace_prior_failed_assessment():
    class InitiallyBrokenStorage(FakeStorage):
        def __init__(self) -> None:
            super().__init__()
            self.fail_reads = True

        def read(self):
            if self.fail_reads:
                raise RuntimeError("synthetic read failure")
            return super().read()

    storage = InitiallyBrokenStorage()
    tm = TokenManager(storage)
    tm.load_from_storage_sync()
    assert tm.session_assessment.completed is False

    storage.fail_reads = False
    tm.set_session(_make_session())
    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=True,
        reason="session_usable",
    )

    tm.clear_session()
    assert tm.session_assessment == SessionAssessment(
        completed=True,
        usable_session=False,
        reason="session_cleared",
    )


def test_set_session_writes_to_storage():
    storage = FakeStorage()
    tm = TokenManager(storage)
    s = _make_session()
    tm.set_session(s)
    assert tm.get_current_session() == s
    assert storage.writes == 1
    assert storage._session == s


def test_clear_session_deletes_from_storage():
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session())
    tm.clear_session()
    assert tm.get_current_session() is None
    assert storage._session is None
    assert storage.deletes == 1


def test_clear_session_propagates_delete_errors():
    """clear_session() must re-raise storage.delete() failures.

    Callers (e.g. _auth_logout.py) are responsible for catching and surfacing
    storage errors to the user; TokenManager must not swallow them.
    """

    class DeleteFailsStorage(FakeStorage):
        def delete(self):
            raise RuntimeError("nope")

    tm = TokenManager(DeleteFailsStorage())
    tm.set_session(_make_session())
    with pytest.raises(RuntimeError, match="nope"):
        tm.clear_session()
    # In-memory session is cleared regardless of storage failure.
    assert tm.get_current_session() is None


def test_is_authenticated_false_when_refresh_expired():
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(refresh_token_expires_at=_now() - timedelta(days=1)))
    assert tm.is_authenticated is False


def test_is_authenticated_true_when_refresh_expiry_is_none():
    """D-9: no hardcoded client-side refresh TTL."""
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(refresh_token_expires_at=None))
    assert tm.is_authenticated is True


@pytest.mark.asyncio
async def test_get_access_token_without_session_raises():
    tm = TokenManager(FakeStorage())
    with pytest.raises(NotAuthenticatedError):
        await tm.get_access_token()


@pytest.mark.asyncio
async def test_get_access_token_raises_typed_error_for_naive_expired_refresh():
    tm = TokenManager(FakeStorage())
    naive_past = now_utc().replace(tzinfo=None) - timedelta(minutes=1)
    tm.set_session(
        _make_session(
            access_expires_in=-60,
            refresh_token_expires_at=naive_past,
        )
    )

    with pytest.raises(RefreshTokenExpiredError):
        await tm.get_access_token()


@pytest.mark.asyncio
async def test_get_access_token_returns_current_when_not_expired():
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(access_expires_in=900, access_token="still-valid"))
    token = await tm.get_access_token()
    assert token == "still-valid"


@pytest.mark.asyncio
async def test_get_access_token_refreshes_when_expired(install_fake_refresh_flow):
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1, access_token="stale"))
    token = await tm.get_access_token()
    assert token != "stale"
    assert install_fake_refresh_flow.call_count == 1
    # The refresh result should also have been persisted.
    assert storage.writes >= 2  # initial set_session + refresh write


@pytest.mark.asyncio
async def test_get_access_token_refreshes_within_buffer_window(install_fake_refresh_flow):
    """The 5-second buffer must trigger refresh for near-expiry tokens."""
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(access_expires_in=2, access_token="near-expiry"))
    token = await tm.get_access_token()
    assert token != "near-expiry"
    assert install_fake_refresh_flow.call_count == 1


@pytest.mark.asyncio
async def test_refresh_if_needed_raises_when_refresh_token_expired(
    install_fake_refresh_flow,
):
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(
        _make_session(
            access_expires_in=-1,
            refresh_token_expires_at=_now() - timedelta(days=1),
        )
    )
    with pytest.raises(RefreshTokenExpiredError):
        await tm.refresh_if_needed()
    # No network call was made.
    assert install_fake_refresh_flow.call_count == 0
    # Locally-known expiry is not stale state; keep the session loaded so
    # status commands can still explain why re-login is required.
    assert tm.get_current_session() is not None
    assert storage.deletes == 0


@pytest.mark.asyncio
async def test_refresh_if_needed_clears_session_on_server_invalid_grant(
    install_fake_refresh_flow,
):
    install_fake_refresh_flow.raise_refresh_expired = True
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1))
    with pytest.raises(RefreshTokenExpiredError):
        await tm.refresh_if_needed()
    assert tm.get_current_session() is None
    assert storage.deletes >= 1


@pytest.mark.asyncio
async def test_refresh_if_needed_clears_session_on_session_invalid(
    install_fake_refresh_flow,
):
    install_fake_refresh_flow.raise_session_invalid = True
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1))
    with pytest.raises(SessionInvalidError):
        await tm.refresh_if_needed()
    assert tm.get_current_session() is None
    assert storage.deletes >= 1


@pytest.mark.asyncio
async def test_refresh_if_needed_returns_false_when_not_needed(
    install_fake_refresh_flow,
):
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(access_expires_in=900))
    refreshed = await tm.refresh_if_needed()
    assert refreshed is False
    assert install_fake_refresh_flow.call_count == 0


@pytest.mark.asyncio
async def test_refresh_if_needed_raises_without_session():
    tm = TokenManager(FakeStorage())
    with pytest.raises(NotAuthenticatedError):
        await tm.refresh_if_needed()


@pytest.mark.asyncio
async def test_concurrent_get_access_token_is_single_flight(install_fake_refresh_flow):
    """10 concurrent callers with an expired session → exactly one refresh."""
    install_fake_refresh_flow.delay_seconds = 0.1  # ensure overlap
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(access_expires_in=-1, access_token="stale"))

    tasks = [asyncio.create_task(tm.get_access_token()) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    assert install_fake_refresh_flow.call_count == 1, f"Expected 1 refresh, got {install_fake_refresh_flow.call_count}"
    assert len(set(results)) == 1  # all callers see the same fresh token
    assert all(r != "stale" for r in results)


@pytest.mark.asyncio
async def test_second_burst_after_refresh_does_not_re_refresh(
    install_fake_refresh_flow,
):
    """Once a fresh token is in place, subsequent calls must not refresh again."""
    install_fake_refresh_flow.delay_seconds = 0.01
    tm = TokenManager(FakeStorage())
    tm.set_session(_make_session(access_expires_in=-1))

    # First burst: triggers one refresh.
    await asyncio.gather(*[tm.get_access_token() for _ in range(5)])
    assert install_fake_refresh_flow.call_count == 1

    # Second burst: token is fresh now, no further refreshes.
    await asyncio.gather(*[tm.get_access_token() for _ in range(5)])
    assert install_fake_refresh_flow.call_count == 1


# ---------------------------------------------------------------------------
# WP02 — refresh transaction with stale-grant preservation
# ---------------------------------------------------------------------------


def _replace(session: StoredSession, **changes: object) -> StoredSession:
    """Return a copy of ``session`` with selected fields replaced."""
    fields: dict[str, object] = {
        "user_id": session.user_id,
        "email": session.email,
        "name": session.name,
        "teams": list(session.teams),
        "default_team_id": session.default_team_id,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "session_id": session.session_id,
        "issued_at": session.issued_at,
        "access_token_expires_at": session.access_token_expires_at,
        "refresh_token_expires_at": session.refresh_token_expires_at,
        "scope": session.scope,
        "storage_backend": session.storage_backend,
        "last_used_at": session.last_used_at,
        "auth_method": session.auth_method,
    }
    fields.update(changes)
    return StoredSession(**fields)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_adopts_newer_persisted_material_skips_network(
    install_fake_refresh_flow,
):
    """FR-004: when persisted material is newer-and-valid, skip the refresh."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    # In-memory session has expired access token and rotation-token "v1".
    in_memory = _make_session(access_expires_in=-1, refresh_token="rot-v1")
    tm._session = in_memory  # bypass set_session so storage stays "newer" only
    # Persisted material: a different refresh token that is still valid.
    persisted = _replace(
        in_memory,
        access_token="fresh",
        refresh_token="rot-v2",
        access_token_expires_at=_now() + timedelta(seconds=900),
    )
    storage._session = persisted

    refreshed = await tm.refresh_if_needed()

    assert install_fake_refresh_flow.call_count == 0
    assert refreshed is False
    current = tm.get_current_session()
    assert current is not None
    assert current.refresh_token == "rot-v2"


@pytest.mark.asyncio
async def test_stale_grant_with_expired_persisted_preserves_session(
    install_fake_refresh_flow,
):
    """Direct stale-rejection path: persisted is expired so we DO call network.

    The flow then rejects with invalid_grant; a third party has already
    rotated the persisted material between our re-read and the rejection
    return. Identity comparison sees the rejected token differs from the
    now-persisted token, so we preserve the session.
    """
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, refresh_token="rot-v1")
    tm._session = in_memory
    # Persisted has the SAME refresh token (not rotated yet) so the FR-004
    # adoption branch does not fire — we go straight to the network refresh.
    storage._session = _replace(in_memory)

    # Capture call count to detect the moment the flow is invoked, then
    # mutate storage and raise.
    rejected_during_refresh: dict[str, StoredSession] = {}

    class StaleRotatingFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            # Simulate another process rotating the refresh token while we
            # were on the wire, then having the SaaS reject our (stale) one.
            # The rotating peer persists a fresh access+refresh pair (this
            # is what production rotation actually writes); our reconciler
            # must preserve it.
            rejected_during_refresh["sent_with_rt"] = session
            storage._session = _replace(
                session,
                refresh_token="rot-v2-rotated-by-other-process",
                access_token="access-v2-fresh",
                access_token_expires_at=_now() + timedelta(seconds=900),
            )
            raise RefreshTokenExpiredError("stale token rejected")

    refresh_module = sys.modules["specify_cli.auth.flows.refresh"]
    refresh_module.TokenRefreshFlow = StaleRotatingFlow  # type: ignore[attr-defined]

    refreshed = await tm.refresh_if_needed()

    assert refreshed is False
    current = tm.get_current_session()
    assert current is not None
    # The freshly persisted session must be adopted; bug-fix invariant:
    # storage.delete must NOT have been called.
    assert current.refresh_token == "rot-v2-rotated-by-other-process"
    assert storage.deletes == 0
    assert rejected_during_refresh["sent_with_rt"].refresh_token == "rot-v1"


@pytest.mark.asyncio
async def test_stale_grant_with_concurrent_storage_delete_clears_cleanly(
    install_fake_refresh_flow,
):
    """Repersisted is None (a parallel logout/clear).

    Without the guard, the reconciler returns STALE_REJECTION_PRESERVED with
    ``session=None``; the caller asserts non-None and the process crashes
    with ``AssertionError``. The fix routes this case through
    CURRENT_REJECTION_CLEARED so the canonical re-login error surfaces
    cleanly.
    """
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, refresh_token="rot-v1")
    tm._session = in_memory
    storage._session = _replace(in_memory)

    class StaleRejectingFlowThatDeletes:
        async def refresh(self, session: StoredSession) -> StoredSession:
            # Another process logs the user out between our send and the
            # SaaS rejection arriving back.
            storage._session = None
            raise RefreshTokenExpiredError("stale token rejected")

    refresh_module = sys.modules["specify_cli.auth.flows.refresh"]
    refresh_module.TokenRefreshFlow = StaleRejectingFlowThatDeletes  # type: ignore[attr-defined]

    with pytest.raises(RefreshTokenExpiredError):
        await tm.refresh_if_needed()

    assert tm.get_current_session() is None


@pytest.mark.asyncio
async def test_stale_grant_with_repersisted_refresh_token_expired_clears(
    install_fake_refresh_flow,
):
    """Repersisted material is itself unusable — clear and require re-login."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, refresh_token="rot-v1")
    tm._session = in_memory
    storage._session = _replace(in_memory)

    class StaleRejectingFlowRotatesToExpiredRefresh:
        async def refresh(self, session: StoredSession) -> StoredSession:
            # Another process rotated, but the new refresh token is past
            # its absolute lifetime. The repersisted session is no good.
            storage._session = _replace(
                session,
                refresh_token="rot-v2-but-expired",
                refresh_token_expires_at=_now() - timedelta(days=1),
            )
            raise RefreshTokenExpiredError("stale token rejected")

    refresh_module = sys.modules["specify_cli.auth.flows.refresh"]
    refresh_module.TokenRefreshFlow = StaleRejectingFlowRotatesToExpiredRefresh  # type: ignore[attr-defined]

    with pytest.raises(RefreshTokenExpiredError):
        await tm.refresh_if_needed()

    assert tm.get_current_session() is None
    assert storage.deletes >= 1


@pytest.mark.asyncio
async def test_stale_grant_with_repersisted_access_token_expired_raises_lock_timeout(
    install_fake_refresh_flow,
):
    """Refresh token still valid; access token already expired.

    Adopting the repersisted session would leak an expired bearer to the
    next ``get_access_token()`` call. The fix surfaces a retryable
    :class:`RefreshLockTimeoutError`; storage is preserved so a follow-up
    call can rotate cleanly via ADOPTED_NEWER on the next attempt.
    """
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, refresh_token="rot-v1")
    tm._session = in_memory
    storage._session = _replace(in_memory)

    class StaleRejectingFlowRotatesToExpiredAccess:
        async def refresh(self, session: StoredSession) -> StoredSession:
            storage._session = _replace(
                session,
                refresh_token="rot-v2",
                access_token="access-v2-already-expired",
                access_token_expires_at=_now() - timedelta(seconds=10),
            )
            raise RefreshTokenExpiredError("stale token rejected")

    refresh_module = sys.modules["specify_cli.auth.flows.refresh"]
    refresh_module.TokenRefreshFlow = StaleRejectingFlowRotatesToExpiredAccess  # type: ignore[attr-defined]

    with pytest.raises(RefreshLockTimeoutError):
        await tm.refresh_if_needed()

    # Storage must be preserved: the refresh token is still good, so a
    # retry will refresh the persisted material under the lock and rotate
    # the access token cleanly.
    assert storage.deletes == 0
    assert storage._session is not None
    assert storage._session.refresh_token == "rot-v2"


@pytest.mark.asyncio
async def test_current_grant_rejection_clears_and_propagates(
    install_fake_refresh_flow,
):
    """FR-005: rejection of current persisted material clears + raises."""
    install_fake_refresh_flow.raise_refresh_expired = True
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1))

    with pytest.raises(RefreshTokenExpiredError):
        await tm.refresh_if_needed()

    assert tm.get_current_session() is None
    assert storage.deletes >= 1


@pytest.mark.asyncio
async def test_current_grant_session_invalid_propagates_session_invalid(
    install_fake_refresh_flow,
):
    """The original SessionInvalidError must propagate (not collapsed into RefreshTokenExpiredError)."""
    install_fake_refresh_flow.raise_session_invalid = True
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1))

    with pytest.raises(SessionInvalidError):
        await tm.refresh_if_needed()

    assert tm.get_current_session() is None
    assert storage.deletes >= 1


@pytest.mark.asyncio
async def test_lock_timeout_adopts_when_persisted_is_fresh(install_fake_refresh_flow, monkeypatch):
    """FR-017: lock contention with usable persisted material is non-fatal."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, access_token="stale")
    tm._session = in_memory
    # Persisted has a fresh access token (e.g. another process already refreshed).
    persisted = _replace(
        in_memory,
        access_token="fresh",
        access_token_expires_at=_now() + timedelta(seconds=900),
    )
    storage._session = persisted

    class _ImmediateTimeoutLock:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._path = kwargs.get("path") or (args[0] if args else "")

        async def __aenter__(self):
            raise LockAcquireTimeout(path=str(self._path))

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(rtx, "MachineFileLock", _ImmediateTimeoutLock)

    refreshed = await tm.refresh_if_needed()

    assert refreshed is False
    assert install_fake_refresh_flow.call_count == 0
    current = tm.get_current_session()
    assert current is not None
    assert current.access_token == "fresh"


@pytest.mark.asyncio
async def test_lock_timeout_error_when_persisted_is_unusable(install_fake_refresh_flow, monkeypatch):
    """FR-016: lock contention with unusable persisted material raises retry hint."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, access_token="stale")
    tm._session = in_memory
    # Persisted is also expired — adoption is unsafe.
    storage._session = _replace(in_memory)

    class _ImmediateTimeoutLock:
        def __init__(self, *args: object, **kwargs: object) -> None:
            self._path = kwargs.get("path") or (args[0] if args else "")

        async def __aenter__(self):
            raise LockAcquireTimeout(path=str(self._path))

        async def __aexit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr(rtx, "MachineFileLock", _ImmediateTimeoutLock)

    with pytest.raises(RefreshLockTimeoutError):
        await tm.refresh_if_needed()
    assert install_fake_refresh_flow.call_count == 0


@pytest.mark.asyncio
async def test_lock_timeout_error_uses_transaction_message(install_fake_refresh_flow, monkeypatch):
    """TokenManager must preserve replay-specific messages from the transaction."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1, access_token="stale")
    tm._session = in_memory
    storage._session = _replace(in_memory)

    async def _fake_transaction(**kwargs):  # type: ignore[no-untyped-def]
        return rtx.RefreshResult(
            outcome=RefreshOutcome.LOCK_TIMEOUT_ERROR,
            session=in_memory,
            network_call_made=True,
            lock_timeout_message=("Refresh token replay detected and no newer local token is available. Run `spec-kitty auth login` if this persists."),
        )

    monkeypatch.setattr(tm_module, "run_refresh_transaction", _fake_transaction)

    with pytest.raises(RefreshLockTimeoutError) as exc_info:
        await tm.refresh_if_needed()

    message = str(exc_info.value)
    assert "replay detected" in message
    assert "auth login" in message
    assert "Another spec-kitty process" not in message
    assert install_fake_refresh_flow.call_count == 0


@pytest.mark.asyncio
async def test_refresh_logs_outcome_at_info(install_fake_refresh_flow, caplog):
    """FR-019: every transaction emits a single INFO log line keyed by outcome."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    tm.set_session(_make_session(access_expires_in=-1))

    with caplog.at_level(logging.INFO, logger="specify_cli.auth.token_manager"):
        await tm.refresh_if_needed()

    matching = [r for r in caplog.records if r.levelno == logging.INFO and "refresh_transaction outcome=" in r.getMessage()]
    assert len(matching) == 1
    assert "outcome=refreshed" in matching[0].getMessage()
    assert "network_call=True" in matching[0].getMessage()


@pytest.mark.asyncio
async def test_storage_emptied_mid_transaction_returns_lock_timeout_error(install_fake_refresh_flow, monkeypatch):
    """T007 edge case: persisted is None mid-transaction → LOCK_TIMEOUT_ERROR."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1)
    tm._session = in_memory
    # storage is empty even though tm holds an in-memory session.
    assert storage._session is None

    with pytest.raises(RefreshLockTimeoutError):
        await tm.refresh_if_needed()
    assert install_fake_refresh_flow.call_count == 0


@pytest.mark.asyncio
async def test_network_timeout_raises_lock_timeout_error(install_fake_refresh_flow, monkeypatch):
    """``asyncio.wait_for`` enforces NFR-002's 10 s ceiling on the network leg."""
    storage = FakeStorage()
    tm = TokenManager(storage)
    in_memory = _make_session(access_expires_in=-1)
    tm.set_session(in_memory)

    class _HangingFlow:
        async def refresh(self, session: StoredSession) -> StoredSession:
            await asyncio.sleep(60)  # never returns within max_hold_s
            raise AssertionError("unreachable")

    refresh_module = sys.modules["specify_cli.auth.flows.refresh"]
    refresh_module.TokenRefreshFlow = _HangingFlow  # type: ignore[attr-defined]

    # Patch max-hold to a tiny value so the test runs quickly.
    monkeypatch.setattr(tm_module, "_REFRESH_MAX_HOLD_S", 0.05)

    with pytest.raises(RefreshLockTimeoutError):
        await tm.refresh_if_needed()


@pytest.mark.asyncio
async def test_refresh_outcome_enum_has_six_canonical_members():
    """Documented contract: the state machine has exactly the six members we ship."""
    members = {m.value for m in RefreshOutcome}
    assert members == {
        "adopted_newer",
        "refreshed",
        "stale_rejection_preserved",
        "current_rejection_cleared",
        "lock_timeout_adopted",
        "lock_timeout_error",
    }


def test_refresh_lock_path_is_under_spec_kitty_home():
    """The default (non-test) lock path resolves through the runtime root.

    The autouse fixture redirects ``_refresh_lock_path`` to a tmp path; here
    we inspect the original source so the documented production contract stays
    under test. WP03 reroutes the helper through
    :func:`specify_cli.paths.get_runtime_root` (honoring ``SPEC_KITTY_HOME``),
    so the lock lands under ``<runtime-root>/auth/refresh.lock`` —
    ``~/.spec-kitty/auth/refresh.lock`` on POSIX with the env var unset.
    """
    import inspect  # noqa: PLC0415

    source = inspect.getsource(tm_module)
    # Locate the production helper definition.
    assert "def _refresh_lock_path" in source
    body = source.split("def _refresh_lock_path", 1)[1].split("\n\nclass", 1)[0]
    assert "refresh.lock" in body
    assert "get_runtime_root" in body
    assert "auth" in body


def test_file_lock_module_exposes_lock_acquire_timeout():
    """Smoke check on the WP01 dependency surface this WP relies on."""
    assert hasattr(file_lock_module, "LockAcquireTimeout")
    assert hasattr(file_lock_module, "MachineFileLock")


# ===========================================================================
# WP02 (private-teamspace-ingress-safeguards): rehydrate_membership_if_needed
# ===========================================================================
#
# T009: 7 contract branches for sync rehydrate.
# T010: concurrent-callers single-flight test.
# Plus: set_session unconditional cache reset (T007).
#
# Tests are sync (no ``pytest.mark.asyncio``). ``respx.mock`` intercepts the
# sync httpx calls inside ``request_with_fallback_sync``.


import concurrent.futures  # noqa: E402

import httpx  # noqa: E402
import respx  # noqa: E402


_SAAS_BASE_URL = "https://saas.example"


def _make_session_with_teams(teams: list[Team]) -> StoredSession:
    """Build a ``StoredSession`` with the supplied team list, otherwise a no-op session."""
    now = _now()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=teams,
        default_team_id=teams[0].id if teams else "",
        access_token="access-v1",
        refresh_token="refresh-v1",
        session_id="sess",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=900),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


@pytest.fixture
def token_manager_with_private_session() -> TokenManager:
    """A ``TokenManager`` whose loaded session already has a Private Teamspace."""
    storage = FakeStorage()
    tm = TokenManager(storage, saas_base_url=_SAAS_BASE_URL)
    tm._session = _make_session_with_teams(
        [
            Team(
                id="t-private",
                name="Private",
                role="owner",
                is_private_teamspace=True,
            ),
        ]
    )
    return tm


@pytest.fixture
def token_manager_with_shared_only_session() -> TokenManager:
    """A ``TokenManager`` whose loaded session has only a shared (non-private) team."""
    storage = FakeStorage()
    tm = TokenManager(storage, saas_base_url=_SAAS_BASE_URL)
    tm._session = _make_session_with_teams(
        [
            Team(
                id="t-shared",
                name="Shared",
                role="member",
                is_private_teamspace=False,
            ),
        ]
    )
    return tm


# --- T009 contract branches -------------------------------------------------


@respx.mock
def test_rehydrate_early_returns_when_session_already_has_private(
    token_manager_with_private_session: TokenManager,
) -> None:
    """Branch (a): existing Private Teamspace short-circuits — no HTTP issued."""
    route = respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(return_value=httpx.Response(200, json={}))

    assert token_manager_with_private_session.rehydrate_membership_if_needed() is True
    assert route.call_count == 0


@respx.mock
def test_rehydrate_fetches_persists_and_recomputes_default_team_id(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """Spec FR-003 + design: ``default_team_id`` is recomputed via
    ``pick_default_team_id``, NOT preserved from the old shared-only session.

    The SaaS does NOT return ``default_team_id`` in ``/api/v1/me`` (see
    auth/flows/authorization_code.py:281).
    """
    respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": "u@example.com",
                "teams": [
                    {
                        "id": "t-shared",
                        "name": "Shared",
                        "role": "member",
                        "is_private_teamspace": False,
                    },
                    {
                        "id": "t-private",
                        "name": "Private",
                        "role": "owner",
                        "is_private_teamspace": True,
                    },
                ],
            },
        )
    )
    tm = token_manager_with_shared_only_session

    assert tm.rehydrate_membership_if_needed() is True

    updated = tm.get_current_session()
    assert updated is not None
    assert any(t.is_private_teamspace for t in updated.teams)
    # pick_default_team_id prefers the Private Teamspace.
    assert updated.default_team_id == "t-private"


@respx.mock
def test_rehydrate_sets_negative_cache_when_no_private_returned(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """Authoritative empty-private response sets the process-scoped cache."""
    respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": "u@example.com",
                "teams": [
                    {
                        "id": "t-shared",
                        "name": "Shared",
                        "role": "member",
                        "is_private_teamspace": False,
                    }
                ],
            },
        )
    )
    tm = token_manager_with_shared_only_session

    assert tm.rehydrate_membership_if_needed() is False
    assert tm._membership_negative_cache is True


@respx.mock
def test_rehydrate_negative_cache_skips_http(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """Negative-cache fast path: no HTTP GET when cache is hot and ``force=False``."""
    tm = token_manager_with_shared_only_session
    tm._membership_negative_cache = True
    route = respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(return_value=httpx.Response(200, json={}))

    assert tm.rehydrate_membership_if_needed() is False
    assert route.call_count == 0


@respx.mock
def test_rehydrate_force_true_bypasses_negative_cache(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """``force=True`` ignores the negative cache; on success ``set_session``
    clears it (T007 contract)."""
    tm = token_manager_with_shared_only_session
    tm._membership_negative_cache = True
    route = respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": "u@example.com",
                "teams": [
                    {
                        "id": "t-private",
                        "name": "Private",
                        "role": "owner",
                        "is_private_teamspace": True,
                    }
                ],
            },
        )
    )

    assert tm.rehydrate_membership_if_needed(force=True) is True
    assert route.call_count == 1
    assert tm._membership_negative_cache is False  # cleared via set_session in T007


@respx.mock
def test_rehydrate_returns_false_on_http_error_without_setting_cache(
    token_manager_with_shared_only_session: TokenManager,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Transient errors (5xx) MUST NOT poison the cache — only authoritative
    empty-private responses do. Failure path logs at WARNING."""
    respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(return_value=httpx.Response(500))
    tm = token_manager_with_shared_only_session

    with caplog.at_level(logging.WARNING, logger="specify_cli.auth.token_manager"):
        assert tm.rehydrate_membership_if_needed() is False

    assert tm._membership_negative_cache is False
    assert any("/api/v1/me fetch failed" in rec.getMessage() for rec in caplog.records)


def test_set_session_unconditionally_clears_negative_cache(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """T007: every set_session resets the cache, even for same-user re-login."""
    tm = token_manager_with_shared_only_session
    tm._membership_negative_cache = True

    current = tm.get_current_session()
    assert current is not None
    # Same-user re-login: build a session with the same email.
    tm.set_session(_make_session_with_teams(list(current.teams)))

    assert tm._membership_negative_cache is False


# --- T010 concurrent-callers single-flight ---------------------------------


@respx.mock
def test_rehydrate_concurrent_callers_serialize(
    token_manager_with_shared_only_session: TokenManager,
) -> None:
    """Four concurrent threads must produce exactly one ``/api/v1/me`` GET.

    The first thread acquires the threading.Lock, performs the GET, persists
    the new session via ``set_session``, releases. The other three then
    acquire the lock in turn and find ``get_private_team_id(session.teams)
    is not None`` — they early-return without HTTP.
    """
    route = respx.get(f"{_SAAS_BASE_URL}/api/v1/me").mock(
        return_value=httpx.Response(
            200,
            json={
                "email": "u@example.com",
                "teams": [
                    {
                        "id": "t-private",
                        "name": "Private",
                        "role": "owner",
                        "is_private_teamspace": True,
                    }
                ],
            },
        )
    )
    tm = token_manager_with_shared_only_session

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(tm.rehydrate_membership_if_needed) for _ in range(4)]
        results = [f.result() for f in futures]

    assert all(results)  # all four observed the now-private session
    assert route.call_count == 1  # but only one GET hit the network
