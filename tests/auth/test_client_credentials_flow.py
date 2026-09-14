"""Tests for :class:`ClientCredentialsFlow` and the credential loader (#3277).

These tests exercise the machine/CI ``client_credentials`` flow with mocked
``httpx.AsyncClient`` — no real sockets, no real network. The headline
assertions per the issue's acceptance criteria:

- Happy path: full login returns a :class:`StoredSession` tagged
  ``auth_method="client_credentials"` carrying the principal's scope.
- A rejected credential (``400 invalid_client``) raises
  :class:`AuthenticationError` with the operator remediation — never the
  secret, never a device-flow suggestion, and byte-identical across the
  unknown-id / revoked / wrong-secret causes the server itself does not
  distinguish.
- A missing or blank credential fails closed via
  :class:`ConfigurationError` naming the variables.
- The secret file form reads once and strips; a missing file fails closed
  naming the path; a file path wins over a stale inline value.
- ``repr`` of :class:`MachineCredentials` never renders the secret.
- ``/api/v1/me`` with empty ``teams`` is tolerated (machine sessions are
  scope-authoritative server-side, not team-picked client-side).
- ``refresh_token_expires_at`` resolution follows the same C-012 preference
  order as the human flows.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from specify_cli.auth.errors import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
)
from specify_cli.auth.flows.client_credentials import (
    CLIENT_ID_ENV_VAR,
    CLIENT_SECRET_ENV_VAR,
    CLIENT_SECRET_FILE_ENV_VAR,
    ClientCredentialsFlow,
    MachineCredentials,
    load_machine_credentials,
)

pytestmark = [pytest.mark.integration]

_SAAS = "https://saas.test"
_FUTURE_ISO = "2099-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _token_response(*, scope: str = "sync:ingest sync:read") -> dict[str, Any]:
    return {
        "access_token": "at_machine_xyz",
        "refresh_token": "rt_machine_xyz",
        "expires_in": 3600,
        "refresh_token_expires_at": _FUTURE_ISO,
        "scope": scope,
        "session_id": "sess_machine_xyz",
        "token_type": "Bearer",
    }


def _me_response(*, teams: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    if teams is None:
        teams = [{"id": "tm_acme", "name": "Acme Corp", "role": "member", "is_private_teamspace": True}]
    return {
        "user_id": "u_svc_ci",
        "email": "ci-runner@machine.local",
        "name": "CI Runner Principal",
        "teams": teams,
        "session_id": "sess_machine_xyz",
    }


def _mock_response(status_code: int, json_body: Any) -> MagicMock:
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.text = str(json_body)
    response.json = MagicMock(return_value=json_body)
    return response


def _install_mock_client(monkeypatch: pytest.MonkeyPatch, post: Any, get: Any) -> None:
    """Patch ``httpx.AsyncClient`` so ``post``/``get`` awaitables are used."""
    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=post)
    fake_client.get = AsyncMock(side_effect=get)
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(httpx, "AsyncClient", MagicMock(return_value=ctx))


# ---------------------------------------------------------------------------
# Credential loader
# ---------------------------------------------------------------------------


class TestLoadMachineCredentials:
    def test_env_pair_resolves(self) -> None:
        creds = load_machine_credentials({CLIENT_ID_ENV_VAR: "cid_1", CLIENT_SECRET_ENV_VAR: "shh"})
        assert creds.client_id == "cid_1"
        assert creds.client_secret == "shh"

    def test_missing_client_id_fails_closed_naming_vars(self) -> None:
        with pytest.raises(ConfigurationError) as excinfo:
            load_machine_credentials({CLIENT_SECRET_ENV_VAR: "shh"})
        assert CLIENT_ID_ENV_VAR in str(excinfo.value)
        assert "shh" not in str(excinfo.value)

    def test_missing_secret_fails_closed_naming_vars(self) -> None:
        with pytest.raises(ConfigurationError) as excinfo:
            load_machine_credentials({CLIENT_ID_ENV_VAR: "cid_1"})
        assert CLIENT_SECRET_ENV_VAR in str(excinfo.value)
        assert CLIENT_SECRET_FILE_ENV_VAR in str(excinfo.value)
        assert "cid_1" not in str(excinfo.value)

    def test_blank_values_fail_closed(self) -> None:
        with pytest.raises(ConfigurationError):
            load_machine_credentials({CLIENT_ID_ENV_VAR: "   ", CLIENT_SECRET_ENV_VAR: "shh"})
        with pytest.raises(ConfigurationError):
            load_machine_credentials({CLIENT_ID_ENV_VAR: "cid_1", CLIENT_SECRET_ENV_VAR: "  "})

    def test_secret_file_read_once_and_stripped(self, tmp_path: Any) -> None:
        secret_file = tmp_path / "machine.secret"
        secret_file.write_text("shh-file\n", encoding="utf-8")
        creds = load_machine_credentials(
            {
                CLIENT_ID_ENV_VAR: "cid_1",
                CLIENT_SECRET_FILE_ENV_VAR: str(secret_file),
                CLIENT_SECRET_ENV_VAR: "stale-inline-value",
            }
        )
        # The file wins over a stale inline value.
        assert creds.client_secret == "shh-file"

    def test_missing_secret_file_fails_closed_naming_path(self, tmp_path: Any) -> None:
        missing = tmp_path / "nope.secret"
        with pytest.raises(ConfigurationError) as excinfo:
            load_machine_credentials(
                {
                    CLIENT_ID_ENV_VAR: "cid_1",
                    CLIENT_SECRET_FILE_ENV_VAR: str(missing),
                    # A present inline value must NOT silently rescue a
                    # pinned-but-missing file.
                    CLIENT_SECRET_ENV_VAR: "shh",
                }
            )
        assert str(missing) in str(excinfo.value)
        assert "shh" not in str(excinfo.value)

    def test_blank_secret_file_fails_closed(self, tmp_path: Any) -> None:
        blank = tmp_path / "blank.secret"
        blank.write_text("\n  \n", encoding="utf-8")
        with pytest.raises(ConfigurationError):
            load_machine_credentials({CLIENT_ID_ENV_VAR: "cid_1", CLIENT_SECRET_FILE_ENV_VAR: str(blank)})

    def test_repr_never_renders_secret(self) -> None:
        creds = MachineCredentials(client_id="cid_1", client_secret="super-secret")
        assert "super-secret" not in repr(creds)
        assert "<redacted>" in repr(creds)


# ---------------------------------------------------------------------------
# Flow — happy path and session shape
# ---------------------------------------------------------------------------


class TestClientCredentialsFlow:
    async def test_happy_path_builds_machine_session(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            assert url == f"{_SAAS}/oauth/token"
            assert data is not None
            assert data["grant_type"] == "client_credentials"
            assert data["client_id"] == "cid_1"
            assert data["client_secret"] == "shh"
            return _mock_response(200, _token_response())

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            assert url == f"{_SAAS}/api/v1/me"
            assert headers == {"Authorization": "Bearer at_machine_xyz"}
            return _mock_response(200, _me_response())

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        session = await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))

        assert session.auth_method == "client_credentials"
        assert session.user_id == "u_svc_ci"
        assert session.email == "ci-runner@machine.local"
        assert session.access_token == "at_machine_xyz"
        assert session.refresh_token == "rt_machine_xyz"
        assert session.session_id == "sess_machine_xyz"
        assert session.scope == "sync:ingest sync:read"
        assert session.issuer_url == _SAAS
        assert session.default_team_id == "tm_acme"

    async def test_empty_teams_tolerated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A machine session's authority is its scope, not a client-picked team."""

        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _token_response())

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _me_response(teams=[]))

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        session = await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))
        assert session.teams == []
        assert session.default_team_id == ""

    async def test_refresh_expiry_prefers_absolute_stamp(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _token_response())

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _me_response())

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        session = await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))
        assert session.refresh_token_expires_at is not None
        assert session.refresh_token_expires_at.year == 2099

    async def test_z_suffix_timestamp_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            body = _token_response()
            body["refresh_token_expires_at"] = "2099-01-01T00:00:00Z"
            return _mock_response(200, body)

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _me_response())

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        session = await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))
        assert session.refresh_token_expires_at is not None
        assert session.refresh_token_expires_at.year == 2099


# ---------------------------------------------------------------------------
# Flow — fail-closed error surface
# ---------------------------------------------------------------------------


class TestClientCredentialsFlowErrors:
    async def test_invalid_client_remediation_without_secret(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``invalid_client`` gets the operator remediation — and the secret,
        the submitted form echo, and any device-flow suggestion all stay out."""

        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(400, {"error": "invalid_client"})

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("me must not be fetched after a refused grant")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError) as excinfo:
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="super-secret"))

        message = str(excinfo.value)
        assert "revoked" in message
        assert "provision_service_principal" in message
        assert "super-secret" not in message
        assert "--headless" not in message
        assert "device" not in message.lower()

    async def test_invalid_client_indistinguishable_across_causes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown id, revoked principal, wrong secret: byte-identical errors,
        mirroring the server's own refusal to distinguish them."""

        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(400, {"error": "invalid_client", "error_description": data["client_id"]})

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)
        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")

        messages = set()
        for client_id in ("unknown-id", "revoked-id", "real-id"):
            with pytest.raises(AuthenticationError) as excinfo:
                await flow.login(MachineCredentials(client_id=client_id, client_secret="wrong"))
            messages.add(str(excinfo.value))
        assert len(messages) == 1

    async def test_non_json_error_body_degrades_to_status_code(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            response = MagicMock(spec=httpx.Response)
            response.status_code = 503
            response.text = "Service Unavailable"
            response.json = MagicMock(side_effect=ValueError("not JSON"))
            return response

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError) as excinfo:
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))
        assert "503" in str(excinfo.value)
        assert "shh" not in str(excinfo.value)

    async def test_rate_limit_surfaces_retryable_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(429, {})

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError, match="rate-limited"):
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))

    async def test_success_payload_missing_field_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            body = _token_response()
            del body["session_id"]
            return _mock_response(200, body)

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError, match="session_id"):
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))

    async def test_non_json_success_body_fails_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            response = MagicMock(spec=httpx.Response)
            response.status_code = 200
            response.text = "<html>"
            response.json = MagicMock(side_effect=ValueError("not JSON"))
            return response

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError, match="not JSON"):
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))

    async def test_network_error_wrapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            raise httpx.ConnectError("refused")

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            raise AssertionError("unreachable")

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(NetworkError):
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))

    async def test_me_failure_surfaces_auth_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def _post(url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(200, _token_response())

        async def _get(url: str, headers: dict[str, str] | None = None, **kwargs: Any) -> MagicMock:
            return _mock_response(500, {"error": "boom"})

        _install_mock_client(monkeypatch, _post, _get)

        flow = ClientCredentialsFlow(saas_base_url=_SAAS, storage_backend="file")
        with pytest.raises(AuthenticationError, match="User info fetch failed"):
            await flow.login(MachineCredentials(client_id="cid_1", client_secret="shh"))
