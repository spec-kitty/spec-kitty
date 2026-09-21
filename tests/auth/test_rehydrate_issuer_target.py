"""Unit tests: rehydrate issuer/target guard (#4755, WP02 T006/T010).

``TokenManager.rehydrate_membership_if_needed`` is a best-effort, fail-closed
path (D-4): on an issuer/target mismatch it must return ``False`` (no
``/api/v1/me`` GET is ever issued) rather than raise — a hard raise here
would break an otherwise-working session — but the warning it logs must be
specific (naming the issuer host, the resolved host, and the remedy) and
token-free (NFR-006), not the generic HTTP-failure text used for a genuine
transport error.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import httpx
import pytest
import respx
from kernel.clock import now_utc, timedelta

from specify_cli.auth.secure_storage import SecureStorage
from specify_cli.auth.session import StoredSession, Team
from specify_cli.auth.token_manager import TokenManager

pytestmark = [pytest.mark.integration]

_LEGIT_ISSUER = "https://team.spec-kitty.ai"
_ATTACKER_HOST = "http://127.0.0.1:48901"


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


def _make_shared_only_session(*, issuer_url: str | None) -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="user-1",
        email="a@b.com",
        name="A B",
        teams=[Team(id="t-shared", name="Shared", role="member", is_private_teamspace=False)],
        default_team_id="t-shared",
        access_token="rehydrate-access-token",
        refresh_token="rehydrate-refresh-token",
        session_id="sess-1",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=900),
        refresh_token_expires_at=None,
        scope="openid",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[Path, None, None]:
    home = tmp_path / "spec-kitty-home"
    home.mkdir()
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home))
    yield home


def test_rehydrate_mismatch_returns_false_with_specific_token_free_warning(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Issuer/target mismatch: fail-closed no-op, no HTTP GET, warning names
    both hosts and the remedy without leaking token material."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _ATTACKER_HOST)
    session = _make_shared_only_session(issuer_url=_LEGIT_ISSUER)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    # assert_all_called=False: the whole point of this test is that the
    # mocked route is NEVER called — the guard must skip the GET entirely.
    with respx.mock(assert_all_called=False) as router:
        route = router.get(url__regex=r".*/api/v1/me$").mock(return_value=httpx.Response(200, json={}))
        with caplog.at_level(logging.WARNING, logger="specify_cli.auth.token_manager"):
            result = tm.rehydrate_membership_if_needed()

        assert route.call_count == 0

    assert result is False
    assert caplog.text, "expected a specific mismatch warning to be logged"
    assert _LEGIT_ISSUER in caplog.text
    assert _ATTACKER_HOST in caplog.text
    assert "auth login" in caplog.text  # names the remedy
    # NFR-006: zero token material anywhere in the warning.
    assert "rehydrate-access-token" not in caplog.text
    assert "rehydrate-refresh-token" not in caplog.text


def test_rehydrate_issuer_matches_target_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: issuer == resolved target — rehydrate proceeds exactly as
    before (NFR-005), fetching and adopting the Private Teamspace."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _LEGIT_ISSUER)
    session = _make_shared_only_session(issuer_url=_LEGIT_ISSUER)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    with respx.mock() as router:
        router.get(f"{_LEGIT_ISSUER}/api/v1/me").mock(
            return_value=httpx.Response(
                200,
                json={
                    "teams": [
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
        result = tm.rehydrate_membership_if_needed()

    assert result is True
    updated = tm.get_current_session()
    assert updated is not None
    assert any(t.is_private_teamspace for t in updated.teams)


def test_rehydrate_legacy_null_issuer_routes_to_resolved_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Legacy session (``issuer_url=None``) never refuses — it routes to
    whatever the resolver currently names, matching the pre-guard behavior
    for sessions minted before issuer recording existed."""
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", _LEGIT_ISSUER)
    session = _make_shared_only_session(issuer_url=None)
    storage = _FakeStorage(session)
    tm = TokenManager(storage)
    tm._session = session

    with respx.mock() as router:
        route = router.get(f"{_LEGIT_ISSUER}/api/v1/me").mock(return_value=httpx.Response(200, json={"teams": []}))
        result = tm.rehydrate_membership_if_needed()

    assert route.call_count == 1
    # No Private Teamspace in the response: authoritative empty result.
    assert result is False
