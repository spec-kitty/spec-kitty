"""Same-process concurrency tests for the WP01 machine-wide refresh lock.

These tests exercise the contract that a burst of concurrent refresh
attempts against one auth root produces exactly **one** network refresh,
even when the callers are independent :class:`TokenManager` instances
(simulating two CLI invocations in one process — pytest-suite style).

The production path under test is:

* :func:`specify_cli.auth.refresh_transaction.run_refresh_transaction` —
  the read-decide-refresh-reconcile body wrapped in a
  :class:`specify_cli.core.file_lock.MachineFileLock`.
* :class:`specify_cli.auth.token_manager.TokenManager.refresh_if_needed` —
  the in-process ``asyncio.Lock`` plus delegation to the transaction.

The :class:`TokenRefreshFlow` is replaced with a counting fake (lazy
import via :mod:`sys.modules`, mirroring ``tests/auth/test_token_manager``)
so we observe the refresh count without hitting the network. The lock
file (``MachineFileLock``) is exercised for real; the conftest
``auth_store_root`` fixture redirects it under ``tmp_path``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import types
from kernel.clock import now_utc, timedelta
from pathlib import Path

import pytest

from specify_cli.auth.refresh_transaction import RefreshOutcome
from specify_cli.auth.secure_storage.file_fallback import FileFallbackStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

class _MembershipRehydrateAttempted(BaseException):
    """Raised when refresh-lock tests accidentally enter hosted membership I/O."""


def _private_teamspace() -> Team:
    return Team(
        id="t-private",
        name="Private",
        role="owner",
        is_private_teamspace=True,
    )


def _make_expired_session(
    *,
    refresh_token: str = "rt_seed_v1",
    access_token: str = "at_seed_v1",
    session_id: str = "sess_seed",
) -> StoredSession:
    now = now_utc()
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
        # Already expired so refresh_if_needed will fire.
        access_token_expires_at=now - timedelta(seconds=1),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


class _CountingRefreshFlow:
    """Counting test double for :class:`TokenRefreshFlow`.

    Sleeps a configurable interval inside ``refresh`` so that two
    same-process callers visibly contend for the in-process asyncio lock
    when only the lock layer is tested. The class-level counter resets
    per test via the fixture below.
    """

    call_count = 0
    delay_seconds: float = 0.1

    async def refresh(self, session: StoredSession) -> StoredSession:
        _CountingRefreshFlow.call_count += 1
        await asyncio.sleep(_CountingRefreshFlow.delay_seconds)
        now = now_utc()
        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            # The refresh-lock contract is about single-flight refresh, not
            # post-refresh membership rehydrate. Return a Private Teamspace so
            # TokenManager's membership hook is a no-op in this suite.
            teams=[_private_teamspace()],
            default_team_id="t-private",
            access_token=f"at_rotated_v{_CountingRefreshFlow.call_count + 1}",
            refresh_token="rt_rotated_v2",  # rotated material
            session_id=session.session_id,
            issued_at=now,
            access_token_expires_at=now + timedelta(seconds=900),
            refresh_token_expires_at=session.refresh_token_expires_at,
            scope=session.scope,
            storage_backend=session.storage_backend,
            last_used_at=now,
            auth_method=session.auth_method,
        )


@pytest.fixture
def install_counting_refresh_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> type[_CountingRefreshFlow]:
    """Inject a fake ``specify_cli.auth.flows.refresh`` module.

    :class:`TokenManager` lazy-imports this on first refresh, so
    :data:`sys.modules` is the right place to stash the fake.
    """
    _CountingRefreshFlow.call_count = 0
    _CountingRefreshFlow.delay_seconds = 0.1

    flows_pkg = types.ModuleType("specify_cli.auth.flows")
    flows_pkg.__path__ = []  # mark as package
    refresh_module = types.ModuleType("specify_cli.auth.flows.refresh")
    refresh_module.TokenRefreshFlow = _CountingRefreshFlow  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "specify_cli.auth.flows", flows_pkg)
    monkeypatch.setitem(
        sys.modules, "specify_cli.auth.flows.refresh", refresh_module
    )
    return _CountingRefreshFlow


@pytest.fixture
def fail_on_membership_rehydrate(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    """Fail if this hermetic refresh-lock suite attempts ``/api/v1/me``.

    Targeted membership-hook coverage lives in ``tests/auth/test_token_manager.py``
    and ``tests/auth/test_refresh_flow.py``. These tests only validate the
    refresh transaction's single-flight behavior.
    """
    from specify_cli.auth.http import me_fetch

    calls: list[tuple[str, str]] = []

    def _fail(saas_base_url: str, access_token: str) -> dict[str, object]:
        calls.append((saas_base_url, access_token))
        raise _MembershipRehydrateAttempted(
            "refresh-lock tests must not call hosted /api/v1/me"
        )

    monkeypatch.setattr(me_fetch, "fetch_me_payload", _fail)
    return calls


def _build_token_manager(auth_store_root: Path) -> TokenManager:
    """Construct a :class:`TokenManager` rooted at ``auth_store_root``."""
    storage = FileFallbackStorage(base_dir=auth_store_root)
    tm = TokenManager(storage)
    tm.load_from_storage_sync()
    return tm


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_concurrent_refresh_one_network_call(
    auth_store_root: Path,
    install_counting_refresh_flow: type[_CountingRefreshFlow],
    fail_on_membership_rehydrate: list[tuple[str, str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two :class:`TokenManager` instances → exactly one network refresh.

    This pins the ADOPTED_NEWER fast path (FR-004): the second caller
    enters the machine-wide lock after the first persisted rotated
    material, observes the persisted refresh token differs from its
    in-memory copy and is non-expired, and adopts it without a
    network call.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://team.spec-kitty.ai")

    # Seed the encrypted store with an expired session.
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(_make_expired_session())

    tm_a = _build_token_manager(auth_store_root)
    tm_b = _build_token_manager(auth_store_root)
    assert tm_a.get_current_session() is not None
    assert tm_b.get_current_session() is not None

    results = await asyncio.gather(
        tm_a.refresh_if_needed(),
        tm_b.refresh_if_needed(),
    )

    # Exactly one network call: only one TokenManager hit
    # the refresh flow; the other adopted the persisted material.
    assert install_counting_refresh_flow.call_count == 1, (
        f"Expected single network refresh; got "
        f"{install_counting_refresh_flow.call_count}"
    )

    # Each ``refresh_if_needed`` returns True iff IT performed the
    # network refresh. Exactly one of the two callers should report True.
    assert sorted(results) == [False, True]

    # Both managers now hold the rotated refresh token.
    session_a = tm_a.get_current_session()
    session_b = tm_b.get_current_session()
    assert session_a is not None
    assert session_b is not None
    assert session_a.refresh_token == "rt_rotated_v2"
    assert session_b.refresh_token == "rt_rotated_v2"
    assert fail_on_membership_rehydrate == []


async def test_concurrent_refresh_serializes_through_machine_lock(
    auth_store_root: Path,
    install_counting_refresh_flow: type[_CountingRefreshFlow],
    fail_on_membership_rehydrate: list[tuple[str, str]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The machine-wide lock serialises overlapping transactions.

    Both :class:`TokenManager` instances log a
    ``refresh_transaction outcome=...`` line at INFO from
    ``specify_cli.auth.token_manager``. Their order in the log records
    the order of completion, and there are exactly two records — one per
    caller. The first record must be ``refreshed`` (the network leg)
    and the second must be ``adopted_newer`` (the second caller adopting
    the rotated material persisted by the first).
    """
    storage = FileFallbackStorage(base_dir=auth_store_root)
    storage.write(_make_expired_session())

    tm_a = _build_token_manager(auth_store_root)
    tm_b = _build_token_manager(auth_store_root)

    caplog.set_level(logging.INFO, logger="specify_cli.auth.token_manager")

    await asyncio.gather(
        tm_a.refresh_if_needed(),
        tm_b.refresh_if_needed(),
    )

    outcomes = [
        record.message
        for record in caplog.records
        if record.name == "specify_cli.auth.token_manager"
        and record.message.startswith("refresh_transaction outcome=")
    ]
    assert len(outcomes) == 2, (
        f"Expected 2 outcome records, got {outcomes!r}"
    )

    # The first to complete must have done the network refresh; the
    # second must have adopted the persisted rotation.
    assert RefreshOutcome.REFRESHED.value in outcomes[0]
    assert "network_call=True" in outcomes[0]
    assert RefreshOutcome.ADOPTED_NEWER.value in outcomes[1]
    assert "network_call=False" in outcomes[1]

    # And the network counter is exactly one.
    assert install_counting_refresh_flow.call_count == 1
    assert fail_on_membership_rehydrate == []
