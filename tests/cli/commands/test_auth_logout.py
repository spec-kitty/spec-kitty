"""Unit + CliRunner tests for ``spec-kitty auth logout`` (WP02).

Covers the acceptance paths from WP02:

- **Not logged in**: prints a friendly notice, exits 0.
- **Happy path (REVOKED)**: RevokeFlow returns REVOKED, local cleanup runs.
- **Server failure**: RevokeFlow returns SERVER_FAILURE, local cleanup still runs.
- **Network error**: RevokeFlow returns NETWORK_ERROR, local cleanup still runs.
- **No refresh token**: RevokeFlow returns NO_REFRESH_TOKEN, local cleanup still runs.
- **Local cleanup failure**: storage.delete raises, exits 1 with error message.
- **``--force``**: skips the revoke call entirely, clears local session.
- **Missing SAAS URL**: config error short-circuits revoke, local cleanup still runs.

Every test drives the real Typer ``app`` from
``specify_cli.cli.commands.auth`` via :class:`typer.testing.CliRunner`
(T063 audit requirement) and mocks ``SecureStorage.from_environment`` so
no real auth store is touched. The revoke call is mocked at the
``RevokeFlow.revoke`` seam via AsyncMock.
"""

from __future__ import annotations

from kernel.clock import timedelta, now_utc
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.flows.revoke import RevokeOutcome
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

pytestmark = pytest.mark.fast


runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures + helpers
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, canonical_home):
    """Reset the process-wide TokenManager between tests.

    ``canonical_home`` pins ``SPEC_KITTY_HOME`` to a per-test tmp dir so no
    test can read or write a real auth store (isolate, never skip).

    Also sets ``SPEC_KITTY_SAAS_URL`` so ``get_saas_base_url`` succeeds
    without touching real config. Tests that verify the missing-config
    path delete the env var explicitly.
    """
    monkeypatch.setenv("SPEC_KITTY_SAAS_URL", "https://saas.test")
    reset_token_manager()
    yield
    reset_token_manager()


def _make_session(
    *,
    access_remaining_seconds: int = 3600,
    refresh_remaining_days: int = 89,
    refresh_token: str = "rt_xyz",
) -> StoredSession:
    """Build a concrete StoredSession for logout tests.

    We use stable dummy token values (``at_xyz``/``rt_xyz``) because the
    test suite asserts they do NOT appear in stdout, i.e. the logout
    command must not leak tokens into its user-facing output.
    """
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
        access_token_expires_at=now + timedelta(seconds=access_remaining_seconds),
        refresh_token_expires_at=now + timedelta(days=refresh_remaining_days),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
    )


def _mock_storage(session: StoredSession | None):
    """Build a Mock SecureStorage that returns ``session`` on ``read()``.

    ``delete`` is a ``MagicMock`` so tests can assert call counts to
    verify FR-004 (local credentials ARE cleared even on server failure).
    """
    storage = Mock()
    storage.read.return_value = session
    storage.write = Mock(return_value=None)
    storage.delete = MagicMock()
    storage.backend_name = "file"
    return storage


# ---------------------------------------------------------------------------
# CliRunner E2E — drive ``auth logout`` through the live Typer app
# ---------------------------------------------------------------------------


class TestAuthLogoutCommand:
    """Exercise the full dispatch path: ``runner.invoke(app, ['logout'])``."""

    def test_not_logged_in(self):
        """No session -> friendly ``Not logged in`` notice, exit 0."""
        storage = _mock_storage(None)
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=storage,
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "Not logged in" in result.stdout
        # No server call or local delete since there was nothing to clear.
        storage.delete.assert_not_called()

    def test_logout_success_revoked(self):
        """Happy path: RevokeFlow returns REVOKED, local cleanup runs."""
        storage = _mock_storage(_make_session())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                new_callable=AsyncMock,
                return_value=RevokeOutcome.REVOKED,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "Server revocation confirmed" in result.stdout
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()
        # Tokens must NOT leak into stdout.
        assert "at_xyz" not in result.stdout
        assert "rt_xyz" not in result.stdout

    def test_logout_server_failure_still_clears_local(self):
        """FR-004: SERVER_FAILURE must NOT block local credential deletion."""
        storage = _mock_storage(_make_session())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                new_callable=AsyncMock,
                return_value=RevokeOutcome.SERVER_FAILURE,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "not confirmed" in result.stdout
        # Rich may wrap long lines; check the key phrase ignoring newlines.
        assert "still" in result.stdout
        assert "deleted" in result.stdout
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()

    def test_logout_network_error_still_clears_local(self):
        """FR-004: NETWORK_ERROR must NOT block local credential deletion."""
        storage = _mock_storage(_make_session())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                new_callable=AsyncMock,
                return_value=RevokeOutcome.NETWORK_ERROR,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "not confirmed" in result.stdout
        # Rich may wrap long lines; check the key phrase ignoring newlines.
        assert "still" in result.stdout
        assert "deleted" in result.stdout
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()

    def test_logout_no_refresh_token_still_clears_local(self):
        """NO_REFRESH_TOKEN: revocation not attempted, local cleanup still runs."""
        storage = _mock_storage(_make_session())

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                new_callable=AsyncMock,
                return_value=RevokeOutcome.NO_REFRESH_TOKEN,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        assert "could not be attempted" in result.stdout
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()

    def test_logout_storage_delete_failure_propagates(self):
        """storage.delete() raising flows through clear_session() to logout_impl.

        TokenManager.clear_session() no longer swallows storage.delete() errors.
        This test exercises the real clear_session() path with a storage backend
        whose delete() raises, confirming the real failure mode is surfaced.
        """
        storage = _mock_storage(_make_session())
        storage.delete.side_effect = OSError("permission denied")

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                new_callable=AsyncMock,
                return_value=RevokeOutcome.REVOKED,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 1, result.stdout
        assert "could not be deleted" in result.stdout
        assert "Logged out" not in result.stdout

    def test_logout_force_skips_server(self):
        """``--force`` must skip the RevokeFlow call and only delete locally."""
        storage = _mock_storage(_make_session())
        revoke_mock = AsyncMock(return_value=RevokeOutcome.REVOKED)

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                revoke_mock,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout", "--force"])

        assert result.exit_code == 0, result.stdout
        # Revoke was NOT called.
        revoke_mock.assert_not_called()
        # Force-skip banner printed.
        assert "Skipping server revocation" in result.stdout
        # Local cleanup still ran.
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()

    def test_logout_missing_saas_url_still_attempts_revoke_and_cleans_up_locally(self, monkeypatch):
        """Local cleanup is unconditional regardless of endpoint config
        (FR-004): a missing ``SPEC_KITTY_SAAS_URL`` never short-circuits
        ``logout`` before it even attempts server-side revocation — the
        decision of whether the target resolves lives entirely inside
        ``RevokeFlow.revoke`` (mocked here to REVOKED), which since endpoint
        opt-in (FR-011) folds an unconfigured endpoint into
        ``RevokeOutcome.ISSUER_MISMATCH`` rather than ever reaching this
        command's own config-error handling."""
        monkeypatch.delenv("SPEC_KITTY_SAAS_URL", raising=False)
        storage = _mock_storage(_make_session())
        revoke_mock = AsyncMock(return_value=RevokeOutcome.REVOKED)

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=storage,
            ),
            patch(
                "specify_cli.cli.commands._auth_logout.RevokeFlow.revoke",
                revoke_mock,
            ),
        ):
            reset_token_manager()
            result = runner.invoke(app, ["logout"])

        assert result.exit_code == 0, result.stdout
        # No config-error warning surfaces here: RevokeFlow.revoke owns the
        # target-resolution outcome, and it is mocked to REVOKED.
        assert "config error" not in result.stdout.lower()
        revoke_mock.assert_called_once()
        # Local cleanup still ran.
        assert "Logged out" in result.stdout
        storage.delete.assert_called_once()
