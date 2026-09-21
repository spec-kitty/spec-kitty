"""Red-first repro: consequence 2 (hostile env) — refresh + held-token
non-demotion (#4755, WP02 T005/T009).

A session minted against the hosted default (``https://team.spec-kitty.ai``)
must never have its bearer sent to an attacker-controlled host named only by
``SPEC_KITTY_SAAS_URL`` in the process environment:

(a) ``TokenManager.refresh_if_needed`` must refuse (raise
    ``IssuerTargetMismatchError``) instead of POSTing the refresh token to
    the attacker host.
(b) ``saas_client.auth._usable_access_token`` must refuse a *still-valid*
    held access token on the same mismatch — the held-token re-leak trap
    (FR-008): before WP02 T005, ``_dead_session_errors()`` did not include
    the mismatch type and the early "not expired -> return held" fast path
    ran with no issuer check at all, so a valid token would have gone out
    to the attacker host unchanged. RED before the fix, GREEN after.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from kernel.clock import now_utc, timedelta

from specify_cli.auth import token_manager as tm_module
from specify_cli.auth.errors import IssuerTargetMismatchError
from specify_cli.auth.secure_storage import SecureStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager
from specify_cli.saas_client import auth as saas_auth_module
from specify_cli.saas_client.errors import SaasAuthError

pytestmark = [pytest.mark.integration]

_LEGIT_ISSUER = "https://team.spec-kitty.ai"
_ATTACKER_HOST = "http://127.0.0.1:48899"


class _FakeStorage(SecureStorage):
    def __init__(self, session: StoredSession | None = None) -> None:
        self._session = session

    def read(self) -> StoredSession | None:
        return self._session

    def write(self, session: StoredSession) -> None:
        self._session = session

    def delete(self) -> None:
        self._session = None

    @property
    def backend_name(self) -> str:
        return "file"


def _make_session(
    *,
    issuer_url: str | None,
    access_expires_in: int,
) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token="held-access-token",
        refresh_token="held-refresh-token",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=access_expires_in),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


@pytest.fixture(autouse=True)
def _isolated_refresh_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Path, None, None]:
    lock_path = tmp_path / "refresh.lock"
    monkeypatch.setattr(tm_module, "_refresh_lock_path", lambda: lock_path)
    yield lock_path


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Path, None, None]:
    """Isolate ``SPEC_KITTY_HOME`` so no real ``config.toml`` participates."""
    home = tmp_path / "spec-kitty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    yield home


@pytest.fixture
def _attacker_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _ATTACKER_HOST)


# ---------------------------------------------------------------------------
# (a) refresh refuses; the refresh token never reaches the attacker host.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_refuses_attacker_env_override_no_token_sent(
    _attacker_env_override: None,
) -> None:
    session = _make_session(issuer_url=_LEGIT_ISSUER, access_expires_in=-60)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    requested_urls: list[str] = []

    with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        async def _record_post(url: str, **_kwargs: object) -> Mock:
            requested_urls.append(url)
            response = Mock(spec=httpx.Response)
            response.status_code = 200
            response.json = Mock(return_value={})
            return response

        mock_client.post.side_effect = _record_post

        with pytest.raises(IssuerTargetMismatchError) as excinfo:
            await tm.refresh_if_needed()

    # No network call was ever attempted against the attacker host.
    assert requested_urls == []
    message = str(excinfo.value)
    assert _LEGIT_ISSUER in message
    assert _ATTACKER_HOST in message
    # NFR-006: zero token material in the refusal.
    assert "held-refresh-token" not in message
    assert "held-access-token" not in message


# ---------------------------------------------------------------------------
# (b) _usable_access_token refuses a still-valid held token on mismatch.
# ---------------------------------------------------------------------------


class _NeverCalledManager:
    """A TokenManager double whose ``refresh_if_needed`` must never run.

    The access token is still valid, so a correct implementation refuses
    before ever attempting a refresh.
    """

    async def refresh_if_needed(self) -> bool:  # pragma: no cover - must not be reached
        raise AssertionError("refresh_if_needed must not run for a still-valid held token")


def test_usable_access_token_refuses_still_valid_token_on_mismatch(
    _attacker_env_override: None,
) -> None:
    session = _make_session(issuer_url=_LEGIT_ISSUER, access_expires_in=900)
    manager: Any = _NeverCalledManager()

    with pytest.raises(SaasAuthError) as excinfo:
        saas_auth_module._usable_access_token(manager, session)

    message = str(excinfo.value)
    assert _LEGIT_ISSUER in message
    assert _ATTACKER_HOST in message
    assert "held-access-token" not in message


def test_usable_access_token_returns_held_token_when_issuer_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: a matching issuer/target still returns the held token
    unchanged (no false-positive refusal)."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _LEGIT_ISSUER)
    session = _make_session(issuer_url=_LEGIT_ISSUER, access_expires_in=900)
    manager: Any = _NeverCalledManager()

    token = saas_auth_module._usable_access_token(manager, session)

    assert token == "held-access-token"
