"""Concurrent single-flight refresh regression test (WP11 T061).

Covers FR-016 and the central single-flight invariant: when 10+ callers
concurrently request an access token from a :class:`TokenManager` whose
session is expired, the underlying refresh network call must run
**exactly once**. All 10 callers must receive the identical fresh token.

This is the spiritual successor to the legacy
``test_auth_concurrent_refresh.py``, but driven against the NEW TokenManager
+ :func:`get_token_manager` factory — never ``TokenManager()`` directly.

Test isolation: this file does not drive the CLI (no CliRunner is needed)
because the contract under test is the async lock inside TokenManager, not
the CLI surface. The test resolves the TokenManager via the public factory
so a future regression that adds a direct constructor call in a caller
path would still be caught by the integration tests in the sibling
``tests/auth/integration/`` directory.
"""

from __future__ import annotations

import asyncio
import sys
import types
from kernel.clock import datetime, now_utc, timedelta
from unittest.mock import patch

import pytest

from specify_cli.auth import get_token_manager, reset_token_manager
from specify_cli.auth.secure_storage.abstract import SecureStorage
from specify_cli.auth.session import StoredSession, Team


pytestmark = [pytest.mark.integration]

class _MembershipRehydrateAttempted(BaseException):
    """Raised when single-flight tests accidentally enter hosted membership I/O."""


def _now() -> datetime:
    return now_utc()


def _private_teamspace() -> Team:
    return Team(
        id="t-private",
        name="Private",
        role="owner",
        is_private_teamspace=True,
    )


def _expired_session() -> StoredSession:
    """Return a StoredSession whose access token is already past expiry."""
    now = _now()
    return StoredSession(
        user_id="u_concurrent",
        email="concurrent@example.com",
        name="Concurrent User",
        teams=[Team(id="t1", name="T1", role="admin")],
        default_team_id="t1",
        access_token="stale_access_token",
        refresh_token="refresh_token_v1",
        session_id="sess_concurrent",
        issued_at=now - timedelta(hours=2),
        access_token_expires_at=now - timedelta(minutes=1),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class _InMemoryStorage(SecureStorage):
    """Minimal in-memory storage that the factory will see on first call."""

    def __init__(self, session: StoredSession | None = None) -> None:
        self._session = session
        self.writes = 0

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session
        self.writes += 1

    def delete(self) -> None:
        self._session = None

    @property
    def backend_name(self) -> str:
        return "file"


class _FakeRefreshFlow:
    """Test double for :class:`TokenRefreshFlow` that counts refresh calls.

    The TokenManager lazy-imports ``specify_cli.auth.flows.refresh``, so we
    inject a fake module into :data:`sys.modules` that exposes this class as
    ``TokenRefreshFlow``. The ``asyncio.sleep`` call forces concurrent callers
    to overlap inside the refresh lock, proving the single-flight guarantee.
    """

    call_count = 0

    async def refresh(self, session: StoredSession) -> StoredSession:
        _FakeRefreshFlow.call_count += 1
        # Sleep long enough that all 10 concurrent callers queue behind the
        # lock before the first refresh completes. If the lock is broken,
        # multiple calls will increment call_count inside this window.
        await asyncio.sleep(0.1)
        now = _now()
        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            # This suite validates refresh single-flight behavior, not
            # membership rehydrate. Return a Private Teamspace so the
            # post-refresh hook remains a no-op and the test stays hermetic.
            teams=[_private_teamspace()],
            default_team_id="t-private",
            access_token="fresh_access_token_v2",
            refresh_token=session.refresh_token,
            session_id=session.session_id,
            issued_at=now,
            access_token_expires_at=now + timedelta(minutes=15),
            refresh_token_expires_at=session.refresh_token_expires_at,
            scope=session.scope,
            storage_backend=session.storage_backend,
            last_used_at=now,
            auth_method=session.auth_method,
        )


@pytest.fixture
def install_fake_refresh_flow(monkeypatch: pytest.MonkeyPatch):
    """Inject a fake ``specify_cli.auth.flows.refresh`` module.

    The TokenManager lazy-imports this module on first refresh, so we
    pre-populate :data:`sys.modules` with a fake package + module that
    exposes :class:`_FakeRefreshFlow` as ``TokenRefreshFlow``.
    """
    _FakeRefreshFlow.call_count = 0

    # The real module may already be loaded from other tests, so replace it.
    flows_pkg = types.ModuleType("specify_cli.auth.flows")
    flows_pkg.__path__ = []  # mark as package
    refresh_module = types.ModuleType("specify_cli.auth.flows.refresh")
    refresh_module.TokenRefreshFlow = _FakeRefreshFlow  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows", flows_pkg)
    monkeypatch.setitem(
        sys.modules, "specify_cli.auth.flows.refresh", refresh_module
    )
    yield _FakeRefreshFlow


@pytest.fixture(autouse=True)
def fail_on_membership_rehydrate(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    """Fail if this hermetic single-flight suite attempts ``/api/v1/me``."""
    from specify_cli.auth.http import me_fetch

    calls: list[tuple[str, str]] = []

    def _fail(saas_base_url: str, access_token: str) -> dict[str, object]:
        calls.append((saas_base_url, access_token))
        raise _MembershipRehydrateAttempted(
            "single-flight refresh tests must not call hosted /api/v1/me"
        )

    monkeypatch.setattr(me_fetch, "fetch_me_payload", _fail)
    return calls


@pytest.fixture(autouse=True)
def _clean_factory():
    """Reset the process-wide TokenManager singleton before and after."""
    reset_token_manager()
    yield
    reset_token_manager()


@pytest.mark.asyncio
async def test_ten_concurrent_callers_single_flight_via_factory(
    install_fake_refresh_flow,
) -> None:
    """FR-016: 10 concurrent ``get_access_token`` calls → exactly 1 refresh.

    This test resolves the :class:`TokenManager` via :func:`get_token_manager`
    (the public factory) so it exercises exactly the same code path the
    production CLI uses. A regression that bypasses the single-flight lock
    (e.g. by instantiating TokenManager in each caller) would show up here
    as ``call_count > 1``.
    """
    storage = _InMemoryStorage(session=_expired_session())

    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=storage,
    ):
        # Resolve via the public factory — never TokenManager() directly.
        tm = get_token_manager()
        assert tm.get_current_session() is not None

        # Fire 10 concurrent requests at the same TokenManager.
        tasks = [asyncio.create_task(tm.get_access_token()) for _ in range(10)]
        results = await asyncio.gather(*tasks)

    # HARD invariant: exactly one refresh call despite 10 concurrent callers.
    assert install_fake_refresh_flow.call_count == 1, (
        f"Expected single-flight refresh but got "
        f"{install_fake_refresh_flow.call_count} refresh calls"
    )

    # All 10 callers must see the same, fresh token.
    assert len(set(results)) == 1
    assert results[0] == "fresh_access_token_v2"
    # And the stale token must never leak back.
    assert all(r != "stale_access_token" for r in results)


@pytest.mark.asyncio
async def test_fifty_concurrent_callers_single_flight(
    install_fake_refresh_flow,
) -> None:
    """Stress variant: 50 concurrent callers → still exactly 1 refresh.

    Exceeds the FR-016 floor of ``>=10`` by 5x. A flaky lock under load
    would surface as ``call_count > 1`` here even if the 10-caller test
    passed by luck.
    """
    storage = _InMemoryStorage(session=_expired_session())

    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=storage,
    ):
        tm = get_token_manager()
        tasks = [asyncio.create_task(tm.get_access_token()) for _ in range(50)]
        results = await asyncio.gather(*tasks)

    assert install_fake_refresh_flow.call_count == 1, (
        f"Expected 1 refresh call for 50 callers, got "
        f"{install_fake_refresh_flow.call_count}"
    )
    assert len(set(results)) == 1
    assert results[0] == "fresh_access_token_v2"


@pytest.mark.asyncio
async def test_second_burst_after_refresh_uses_cached_token(
    install_fake_refresh_flow,
) -> None:
    """Once refreshed, subsequent bursts must NOT trigger another refresh.

    This proves the lock is not the only mechanism: the refreshed token is
    actually persisted on the TokenManager instance so later callers use
    the cached value directly.
    """
    storage = _InMemoryStorage(session=_expired_session())

    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=storage,
    ):
        tm = get_token_manager()

        # First burst triggers refresh #1.
        first = await asyncio.gather(
            *[tm.get_access_token() for _ in range(10)]
        )
        assert install_fake_refresh_flow.call_count == 1
        assert all(t == "fresh_access_token_v2" for t in first)

        # Second burst must reuse the fresh token — no new refresh.
        second = await asyncio.gather(
            *[tm.get_access_token() for _ in range(10)]
        )
        assert install_fake_refresh_flow.call_count == 1
        assert all(t == "fresh_access_token_v2" for t in second)


@pytest.mark.asyncio
async def test_factory_returns_same_instance_across_concurrent_callers(
    install_fake_refresh_flow,
) -> None:
    """FR-016: the factory is a true singleton — all callers see one TM.

    If the factory ever regressed to returning a new instance per call,
    the single-flight guarantee would silently collapse: each caller would
    have its own refresh lock and all 10 refreshes would proceed in parallel.
    """
    storage = _InMemoryStorage(session=_expired_session())

    with patch(
        "specify_cli.auth.secure_storage.SecureStorage.from_environment",
        return_value=storage,
    ):
        # Each caller resolves its own TokenManager via the factory.
        async def _caller() -> tuple[int, str]:
            tm = get_token_manager()
            token = await tm.get_access_token()
            return id(tm), token

        pairs = await asyncio.gather(*[_caller() for _ in range(10)])

    tm_ids = {pair[0] for pair in pairs}
    tokens = {pair[1] for pair in pairs}
    # All 10 callers resolved the SAME TokenManager instance.
    assert len(tm_ids) == 1, (
        f"Factory returned {len(tm_ids)} distinct TokenManagers; "
        f"expected 1 (singleton regression)"
    )
    # And refresh still ran exactly once.
    assert install_fake_refresh_flow.call_count == 1
    assert tokens == {"fresh_access_token_v2"}
