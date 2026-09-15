"""E2E tests for ``spec-kitty auth login --machine`` via CliRunner (#3277).

Covers the machine/CI ``client_credentials`` path end-to-end:

1. CliRunner invokes the real Typer ``app`` with ``["login", "--machine"]``.
2. ``_auth_login.login_impl`` loads the credential pair from the
   environment (fail closed, never prompted) and dispatches to
   :class:`specify_cli.auth.flows.client_credentials.ClientCredentialsFlow`.
3. ``httpx.AsyncClient`` is patched to serve ``/oauth/token`` and
   ``/api/v1/me`` — the same two endpoints the SaaS machine-credential
   contract defines.
4. :class:`SecureStorage.from_environment` is patched to an in-memory
   storage so the resulting :class:`StoredSession` is captured.

Acceptance-criteria coverage (issue #3277):

- A clean runner authenticates with **only** the machine credential — no
  browser, no TTY, no prompt, no device flow.
- The auth mode is visible in ``auth status`` and ``auth doctor --json``
  without exposing any token or secret material.
- A misconfigured machine login fails closed with a precise remediation —
  never a device-flow prompt.
- ``--machine`` and ``--headless`` are mutually exclusive.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.auth import app

from .conftest import FakeSecureStorage


pytestmark = [pytest.mark.integration]

runner = CliRunner()


def _token_response() -> dict[str, Any]:
    return {
        "access_token": "at_machine_xyz",
        "refresh_token": "rt_machine_xyz",
        "expires_in": 3600,
        "refresh_token_expires_at": "2099-01-01T00:00:00+00:00",
        "scope": "sync:ingest sync:read",
        "session_id": "sess_machine_xyz",
        "token_type": "Bearer",
    }


def _me_response() -> dict[str, Any]:
    return {
        "user_id": "u_svc_ci",
        "email": "ci-runner@machine.local",
        "name": "CI Runner Principal",
        "teams": [
            {
                "id": "tm_acme",
                "name": "Acme Corp",
                "role": "member",
                "is_private_teamspace": True,
            }
        ],
        "session_id": "sess_machine_xyz",
    }


def _mock_httpx_response(status_code: int, json_body: dict[str, Any]) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = str(json_body)
    response.json = MagicMock(return_value=json_body)
    return response


def _happy_client() -> AsyncMock:
    async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
        assert url.endswith("/oauth/token")
        assert data is not None
        assert data["grant_type"] == "client_credentials"
        return _mock_httpx_response(200, _token_response())

    async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
        assert url.endswith("/api/v1/me")
        return _mock_httpx_response(200, _me_response())

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=_post)
    fake_client.get = AsyncMock(side_effect=_get)
    return fake_client


class TestMachineLoginE2E:
    def test_machine_login_happy_path(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", "super-secret")

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = _happy_client()
            result = runner.invoke(app, ["login", "--machine"])

        assert result.exit_code == 0, f"machine login failed: stdout={result.stdout!r} exception={result.exception!r}"

        # Machine identity and non-secret scope echoed; human banner absent.
        assert "ci-runner@machine.local" in result.stdout
        assert "(machine)" in result.stdout
        assert "sync:ingest sync:read" in result.stdout

        # Fail-closed hygiene: neither token nor secret ever hits stdout.
        assert "at_machine_xyz" not in result.stdout
        assert "rt_machine_xyz" not in result.stdout
        assert "super-secret" not in result.stdout

        # The session was written through the token-manager seam, tagged machine.
        assert len(fake_storage.writes) == 1
        stored = fake_storage.writes[0]
        assert stored.auth_method == "client_credentials"
        assert stored.email == "ci-runner@machine.local"
        assert stored.scope == "sync:ingest sync:read"

    def test_machine_login_via_secret_file(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Any,
    ) -> None:
        secret_file = tmp_path / "machine.secret"
        secret_file.write_text("file-secret\n", encoding="utf-8")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE", str(secret_file))

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = _happy_client()
            result = runner.invoke(app, ["login", "--machine"])

        assert result.exit_code == 0, result.stdout
        assert "file-secret" not in result.stdout
        assert len(fake_storage.writes) == 1

    def test_missing_credentials_fail_closed_no_device_prompt(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_MACHINE_CLIENT_ID", raising=False)
        monkeypatch.delenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", raising=False)
        monkeypatch.delenv("SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE", raising=False)

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            # No transport is patched to a fake on purpose: a missing
            # credential must fail before any network attempt, so a real
            # AsyncClient left in place would surface as a test error only
            # if the fail-closed contract regressed.
            patch("httpx.AsyncClient"),
        ):
            result = runner.invoke(app, ["login", "--machine"])

        assert result.exit_code == 1
        # Precise remediation naming the variables...
        assert "SPEC_KITTY_MACHINE_CLIENT_ID" in result.stdout
        assert "SPEC_KITTY_MACHINE_CLIENT_SECRET" in result.stdout
        # ...never a device-flow or browser prompt.
        assert "--headless" not in result.stdout
        assert "browser" not in result.stdout.lower()
        # No session was written.
        assert fake_storage.writes == []

    def test_rejected_credential_fails_closed_with_operator_remediation(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", "wrong-secret")

        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_httpx_response(400, {"error": "invalid_client"})

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("me must not be fetched after a refused grant")

        fake_client = AsyncMock()
        fake_client.post = AsyncMock(side_effect=_post)
        fake_client.get = AsyncMock(side_effect=_get)

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = fake_client
            result = runner.invoke(app, ["login", "--machine"])

        assert result.exit_code == 1
        assert "revoked" in result.stdout
        assert "provision_service_principal" in result.stdout
        assert "--headless" not in result.stdout
        assert "wrong-secret" not in result.stdout
        assert fake_storage.writes == []

    def test_network_failure_uses_network_specific_remediation(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", "super-secret")

        request = httpx.Request("POST", "https://saas.invalid/oauth/token")
        fake_client = AsyncMock()
        fake_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused", request=request))

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = fake_client
            result = runner.invoke(app, ["login", "--machine"])

        assert result.exit_code == 1
        assert "Could not reach the SaaS" in result.stdout
        assert "Check SPEC_KITTY_SAAS_URL and network access from this runner." in result.stdout
        assert "super-secret" not in result.stdout
        assert fake_storage.writes == []

    def test_machine_and_headless_are_mutually_exclusive(
        self,
        fake_storage: FakeSecureStorage,
    ) -> None:
        with patch(
            "specify_cli.auth.secure_storage.SecureStorage.from_environment",
            return_value=fake_storage,
        ):
            result = runner.invoke(app, ["login", "--machine", "--headless"])
        assert result.exit_code == 2
        assert "mutually exclusive" in result.stdout

    def test_auth_status_shows_machine_mode(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The auth mode is visible in diagnostics, without secret material."""
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", "super-secret")

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = _happy_client()
            login_result = runner.invoke(app, ["login", "--machine"])
            assert login_result.exit_code == 0, login_result.stdout

            status_result = runner.invoke(app, ["status"])

        assert status_result.exit_code == 0
        assert "Machine / CI (Client Credentials Grant)" in status_result.stdout
        assert "at_machine_xyz" not in status_result.stdout
        assert "super-secret" not in status_result.stdout

    def test_auth_doctor_json_reports_auth_mode(
        self,
        fake_storage: FakeSecureStorage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``auth doctor --json`` deterministically carries ``auth_method``."""
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_ID", "cid_ci")
        monkeypatch.setenv("SPEC_KITTY_MACHINE_CLIENT_SECRET", "super-secret")

        with (
            patch(
                "specify_cli.auth.secure_storage.SecureStorage.from_environment",
                return_value=fake_storage,
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
            mock_client_cls.return_value.__aenter__.return_value = _happy_client()
            login_result = runner.invoke(app, ["login", "--machine"])
            assert login_result.exit_code == 0, login_result.stdout

            doctor_result = runner.invoke(app, ["doctor", "--json"])

        assert doctor_result.exit_code in (0, 1), doctor_result.stdout
        payload = json.loads(doctor_result.stdout)
        assert payload["session"]["auth_method"] == "client_credentials"
        # No token or secret material anywhere in the JSON.
        assert "at_machine_xyz" not in doctor_result.stdout
        assert "rt_machine_xyz" not in doctor_result.stdout
        assert "super-secret" not in doctor_result.stdout
