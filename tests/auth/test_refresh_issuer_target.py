"""Red-first repro: refresh must target the session's issuer, not a stale
default (#4755, WP02 T004/T008).

Consequence 1 (self-hosted): a session minted against a self-hosted server
configured only via ``config.toml [sync].server_url`` must have its refresh
POST go to that configured host — never to the packaged default
``https://team.spec-kitty.ai`` (which the pre-fix ``get_saas_base_url()``
accessor would silently prefer, because it never reads ``config.toml`` at
all). Before the fix (WP02 T004), ``TokenRefreshFlow.refresh`` always called
``get_saas_base_url()`` directly, which ignores ``[sync].server_url``
entirely — this test is RED against that code and GREEN once
``TokenManager.refresh_if_needed`` resolves + guards via
``resolve_token_endpoint(session)`` at the boundary and threads the result
into the flow (D-3, ``contracts/issuer-target-helper.md``).

Also covers US1-AC4 (D-5): a legacy session with ``issuer_url=None`` and a
config-only self-hosted host still routes to the configured host with no
refusal — the null-session/legacy branch never falls back to the packaged
default.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from kernel.clock import now_utc, timedelta

from specify_cli.auth import token_manager as tm_module
from specify_cli.auth.secure_storage import SecureStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager

pytestmark = [pytest.mark.integration]

_CONFIGURED_HOST = "http://127.0.0.1:48765"
_PACKAGED_DEFAULT_HOST = "https://team.spec-kitty.ai"


class _FakeStorage(SecureStorage):
    """Minimal in-memory :class:`SecureStorage` double."""

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


def _make_expired_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t1", name="T1", role="owner", is_private_teamspace=True)],
        default_team_id="t1",
        access_token="access-v1",
        refresh_token="refresh-secret-v1",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now - timedelta(seconds=60),
        refresh_token_expires_at=now + timedelta(days=30),
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


@pytest.fixture(autouse=True)
def _isolated_refresh_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Path, None, None]:
    """Redirect the machine-wide refresh lock into ``tmp_path`` (see
    ``tests/auth/test_token_manager.py``'s identical fixture)."""
    lock_path = tmp_path / "refresh.lock"
    monkeypatch.setattr(tm_module, "_refresh_lock_path", lambda: lock_path)
    yield lock_path


@pytest.fixture(autouse=True)
def _isolated_home_no_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Path, None, None]:
    """Isolate ``SPEC_KITTY_HOME`` and clear any env-supplied SaaS override.

    Every test in this module supplies its own ``config.toml`` under this
    isolated home, so the resolver never sees the real developer machine's
    configuration.
    """
    home = tmp_path / "spec-kitty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
    yield home


def _write_config_toml(home: Path, *, server_url: str) -> None:
    (home / "config.toml").write_text(f'[sync]\nserver_url = "{server_url}"\n', encoding="utf-8")


def _mock_httpx_response(status_code: int, json_body: dict | None = None) -> Mock:
    response = Mock(spec=httpx.Response)
    response.status_code = status_code
    response.json = Mock(return_value=json_body or {})
    response.text = str(json_body or {})
    return response


def _refresh_success_body() -> dict:
    return {
        "access_token": "access-v2",
        "refresh_token": "refresh-secret-v2",
        "expires_in": 3600,
        "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
        "scope": "offline_access",
    }


@pytest.mark.asyncio
async def test_refresh_targets_configured_host_not_packaged_default(
    _isolated_home_no_env_override: Path,
) -> None:
    """Session issuer == the configured self-hosted host (matching, no
    mismatch): the refresh POST must go to that host, never to the packaged
    default. RED before WP02 T004 (``TokenRefreshFlow`` called
    ``get_saas_base_url()``, which ignores ``config.toml`` and would resolve
    to the packaged default here); GREEN after."""
    _write_config_toml(_isolated_home_no_env_override, server_url=_CONFIGURED_HOST)
    session = _make_expired_session(issuer_url=_CONFIGURED_HOST)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    requested_urls: list[str] = []

    with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        async def _record_post(url: str, **_kwargs: object) -> Mock:
            requested_urls.append(url)
            return _mock_httpx_response(200, _refresh_success_body())

        mock_client.post.side_effect = _record_post

        refreshed = await tm.refresh_if_needed()

    assert refreshed is True
    assert len(requested_urls) == 1
    assert requested_urls[0] == f"{_CONFIGURED_HOST}/oauth/token"
    for url in requested_urls:
        assert _PACKAGED_DEFAULT_HOST not in url
    # The refresh token itself must never appear anywhere the attacker host
    # could have seen it — trivially true here since only one host was ever
    # contacted, but asserted for NFR-006 defense-in-depth.
    assert all("refresh-secret-v1" not in url for url in requested_urls)


@pytest.mark.asyncio
async def test_refresh_legacy_null_issuer_routes_to_config_host_no_refusal(
    _isolated_home_no_env_override: Path,
) -> None:
    """US1-AC4 / D-5: a legacy session with ``issuer_url=None`` plus a
    config-only self-hosted host routes to that host with no refusal — the
    null-session branch never falls back to the packaged default."""
    _write_config_toml(_isolated_home_no_env_override, server_url=_CONFIGURED_HOST)
    session = _make_expired_session(issuer_url=None)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    requested_urls: list[str] = []

    with patch("specify_cli.auth.flows.refresh.PublicHttpClient") as mock_cls:
        mock_client = AsyncMock()
        mock_cls.return_value.__aenter__.return_value = mock_client

        async def _record_post(url: str, **_kwargs: object) -> Mock:
            requested_urls.append(url)
            return _mock_httpx_response(200, _refresh_success_body())

        mock_client.post.side_effect = _record_post

        refreshed = await tm.refresh_if_needed()

    assert refreshed is True
    assert requested_urls == [f"{_CONFIGURED_HOST}/oauth/token"]
