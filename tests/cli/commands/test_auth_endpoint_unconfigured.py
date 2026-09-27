"""CLI-level contract for the endpoint opt-in reversal (US4).

``auth login`` with no endpoint configured must exit non-zero, print the
guidance line, and make **no** HTTP call. ``auth status``/``whoami`` must
print the "No hosted endpoint configured..." guidance with **no traceback**
-- ``_auth_saas_target.py``'s ``print_saas_endpoint`` must catch every
resolution failure, not only ``ServerTargetSplitBrainError`` (research.md R4).
"""

from __future__ import annotations

from kernel.clock import now_utc, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from specify_cli.auth import reset_token_manager
from specify_cli.auth.server_target import SAAS_URL_ENV_VAR
from specify_cli.auth.session import StoredSession, Team
from specify_cli.cli.commands.auth import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _unconfigured_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No env override, no ``config.toml``, no stored session, no
    ``.kittify/saas-auth.json`` under a throwaway ``SPEC_KITTY_HOME``."""
    monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
    monkeypatch.delenv(SAAS_URL_ENV_VAR, raising=False)
    reset_token_manager()
    return tmp_path


def _make_session() -> StoredSession:
    now = now_utc()
    return StoredSession(
        user_id="u_alice",
        email="alice@example.com",
        name="Alice Developer",
        teams=[Team(id="tm_acme", name="Acme Corp", role="admin", is_private_teamspace=True)],
        default_team_id="tm_acme",
        access_token="at_xyz_ignore",
        refresh_token="rt_xyz_ignore",
        session_id="sess_01HR6CABCDEF",
        issued_at=now,
        access_token_expires_at=now + timedelta(seconds=3600),
        refresh_token_expires_at=now + timedelta(days=89),
        scope="offline_access",
        storage_backend="file",
        last_used_at=now,
        auth_method="authorization_code",
        issuer_url=None,
    )


def _mock_storage_returning(session, *, backend: str = "file"):
    mock_storage = Mock()
    mock_storage.backend_name = backend
    mock_storage.read.return_value = session
    mock_storage.write = Mock(return_value=None)
    mock_storage.delete = Mock(return_value=None)
    return mock_storage


class TestLoginUnconfigured:
    def test_login_exits_nonzero_with_guidance_and_no_http_call(self) -> None:
        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=_mock_storage_returning(None, backend="file"),
            ),
            patch(
                "specify_cli.cli.commands._auth_login._run_browser_flow",
            ) as mock_browser_flow,
        ):
            result = runner.invoke(app, ["login"])

        assert result.exit_code != 0, result.stdout
        assert "No hosted endpoint configured" in result.stdout
        assert SAAS_URL_ENV_VAR in result.stdout
        # No flow was ever constructed -- the resolver refused before any
        # browser/device/machine flow could start, so no HTTP call is made.
        mock_browser_flow.assert_not_called()


class TestStatusUnconfigured:
    def test_status_prints_guidance_with_no_traceback_when_authenticated(self) -> None:
        """Regression pin for research.md R4: ``print_saas_endpoint`` must
        catch ``HostedEndpointUnconfigured`` too, not only
        ``ServerTargetSplitBrainError`` -- otherwise an unconfigured
        resolver tracebacks straight through ``auth status``."""
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=_mock_storage_returning(_make_session(), backend="file"),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0, result.stdout
        assert "Traceback" not in result.stdout
        assert "No hosted endpoint configured" in result.stdout

    def test_whoami_prints_guidance_with_no_traceback_when_authenticated(self) -> None:
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=_mock_storage_returning(_make_session(), backend="file"),
        ):
            result = runner.invoke(app, ["whoami"])

        assert result.exit_code == 0, result.stdout
        assert "Traceback" not in result.stdout
        assert "No hosted endpoint configured" in result.stdout
