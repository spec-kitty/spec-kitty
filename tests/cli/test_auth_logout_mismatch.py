"""Red-first repros: ``auth logout`` targets the issuer, refuses on mismatch,
and still tears down the local session (WP03, #4755, T013).

Two consequences from
``kitty-specs/token-target-issuer-guard-01M319HS/tasks/WP03-revoke-logout-teardown.md``:

1. Session issuer is a config-only self-hosted host -> logout's revoke call
   targets the issuer host (not the packaged default).
2. Session issuer is ``team.spec-kitty.ai``, but
   ``SPEC_KITTY_SAAS_URL=attacker`` -> logout refuses (no POST to the
   attacker host) AND local teardown still happens.

Every test drives the real Typer ``app`` via :class:`typer.testing.CliRunner`
and mocks ``SecureStorage.from_environment`` so no real auth store is
touched. The HTTP seam (``httpx.AsyncClient``) is mocked so no real network
traffic occurs; these tests were RED before the WP03 fix (revoke.py called
``get_saas_base_url()`` unconditionally) and are green after.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from kernel.clock import now_utc, timedelta
from specify_cli.auth import reset_token_manager
from specify_cli.auth.server_target import SAAS_URL_ENV_VAR
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

pytestmark = [pytest.mark.fast, pytest.mark.regression]

runner = CliRunner()

CONFIG_ONLY_HOST = "https://selfhosted.example.com"
TEAM_ISSUER = "https://team.spec-kitty.ai"
ATTACKER_HOST = "https://attacker.example.com"


@pytest.fixture(autouse=True)
def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Isolate SPEC_KITTY_HOME (config.toml) and reset the process-wide TokenManager."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    reset_token_manager()
    yield
    reset_token_manager()


def _write_config(root: Path, server_url: str) -> None:
    (root / "config.toml").write_text(f'[sync]\nserver_url = "{server_url}"\n', encoding="utf-8")


def _make_session(*, issuer_url: str | None, refresh_token: str = "rt_xyz") -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="u_alice",
        email="alice@example.com",
        name="Alice",
        teams=[Team(id="tm_acme", name="Acme", role="admin")],
        default_team_id="tm_acme",
        access_token="at_xyz",
        refresh_token=refresh_token,
        session_id="sess_xyz",
        issued_at=now,
        access_token_expires_at=now + timedelta(hours=1),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=issuer_url,
    )


def _mock_storage(session: StoredSession | None):
    storage = Mock()
    storage.read.return_value = session
    storage.write = Mock(return_value=None)
    storage.delete = MagicMock()
    storage.backend_name = "file"
    return storage


def _make_response(status_code: int, json_body: dict | None = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    if json_body is not None:
        response.json = MagicMock(return_value=json_body)
    else:
        response.json = MagicMock(side_effect=ValueError("no JSON"))
    return response


def _make_async_client(post_return=None) -> MagicMock:
    async_client = MagicMock()
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=None)
    async_client.post = AsyncMock(return_value=post_return)
    return async_client


# ---------------------------------------------------------------------------
# Consequence 1: config-only self-hosted issuer -> revoke targets the issuer.
# ---------------------------------------------------------------------------


def test_logout_targets_config_only_issuer_host(tmp_path: Path):
    """Session issuer == the configured self-hosted host -> logout's revoke
    POST goes to that host, not the packaged default."""
    _write_config(tmp_path, CONFIG_ONLY_HOST)
    storage = _mock_storage(_make_session(issuer_url=CONFIG_ONLY_HOST))
    async_client = _make_async_client(post_return=_make_response(200, {"revoked": True}))

    with (
        patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=storage,
        ),
        patch(
            "specify_cli.auth.flows.revoke.httpx.AsyncClient",
            return_value=async_client,
        ),
    ):
        reset_token_manager()
        result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0, result.stdout
    async_client.post.assert_awaited_once()
    called_url = async_client.post.call_args.args[0]
    assert called_url == f"{CONFIG_ONLY_HOST}/oauth/revoke"
    assert "Server revocation confirmed" in result.stdout
    assert "Logged out" in result.stdout
    storage.delete.assert_called_once()


# ---------------------------------------------------------------------------
# Consequence 2: attacker-controlled env override -> refuse, no POST, but
# local teardown still happens.
# ---------------------------------------------------------------------------


def test_logout_refuses_attacker_env_override_but_still_tears_down_locally(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Session issuer is the real team host; SPEC_KITTY_SAAS_URL points at an
    attacker host -> logout must NOT POST to the attacker host, must warn,
    and must still delete local credentials."""
    monkeypatch.setenv(SAAS_URL_ENV_VAR, ATTACKER_HOST)
    storage = _mock_storage(_make_session(issuer_url=TEAM_ISSUER))

    with (
        patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=storage,
        ),
        patch("specify_cli.auth.flows.revoke.httpx.AsyncClient") as client_cls,
    ):
        reset_token_manager()
        result = runner.invoke(app, ["logout"])

    assert result.exit_code == 0, result.stdout
    # No POST was ever attempted against the attacker-controlled target.
    client_cls.assert_not_called()
    # Local teardown still happened (US2 AC5 — never strand the user).
    storage.delete.assert_called_once()
    assert "Logged out" in result.stdout
    # The refusal is reported, naming both hosts, token-free.
    assert TEAM_ISSUER in result.stdout
    assert ATTACKER_HOST in result.stdout
    assert "at_xyz" not in result.stdout
    assert "rt_xyz" not in result.stdout
