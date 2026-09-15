"""ClientCredentialsFlow — OAuth ``client_credentials`` machine login (#3277).

This is the non-interactive machine/CI authentication mode. A team admin
provisions a :class:`ServicePrincipal` on the SaaS (management command
``provision_service_principal``) and hands the CI runner its
``client_id`` + ``client_secret``. The CLI exchanges that pair at
``POST /oauth/token`` (``grant_type=client_credentials``) — no browser, no
device flow, no human approval step — and the SaaS mints a real
:class:`StoredSession` for the principal's dedicated service user, with
every audit write attributing to the machine identity.

Contract with the SaaS (machine-credential contract, saas #783 WP01–WP04):

- ``POST /oauth/token`` form-encoded with ``grant_type=client_credentials``,
  ``client_id``, ``client_secret``. Success returns the standard OAuth token
  payload (``access_token``, ``refresh_token``, ``expires_in``,
  ``refresh_token_expires_at``, ``scope``, ``session_id``).
- Failure modes — unknown ``client_id``, a revoked principal, a wrong
  secret — all return the identical ``400 invalid_client`` body. This flow
  mirrors that indistinguishability on its own error surface: no remediation
  text distinguishes them either, and the ``client_secret`` value is never
  echoed in any error, log line, or exception (the server response body is
  discarded on failure for exactly this reason).
- ``GET /api/v1/me`` with the minted bearer — same shape every other flow
  uses; the SaaS guarantees the service user a canonical Private Teamspace
  on this call.

Refresh compatibility: the server's ``refresh_token`` grant requires
``client_id=cli_native`` — the principal's own ``client_id`` is rejected
there — and :mod:`specify_cli.auth.flows.refresh` already sends
``cli_native``, so a machine session refreshes through the exact same
TokenManager path a human session does. No refresh-specific code here.

Credential loading (:func:`load_machine_credentials`) is fail-closed and
never interactive: the secret comes from
``SPEC_KITTY_MACHINE_CLIENT_SECRET`` or the file named by
``SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE`` (a CI secret file), the client
id from ``SPEC_KITTY_MACHINE_CLIENT_ID``. A missing or blank credential
raises :class:`ConfigurationError` naming the variables — never a prompt,
and never the credential values themselves.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kernel.clock import datetime, now_utc, parse_iso, timedelta

import httpx

from ..errors import (
    AuthenticationError,
    ConfigurationError,
    NetworkError,
)
from ..session import StorageBackend, StoredSession, pick_default_team_id
from ._session_payload import parse_me_payload, parse_me_teams, require_me_field

log = logging.getLogger(__name__)

_CLIENT_CREDENTIALS_GRANT_TYPE = "client_credentials"
_HTTP_TIMEOUT_SECONDS = 10.0

#: Environment variable carrying the ServicePrincipal's public client id.
#: Not a secret — the SaaS echoes it in responses and audit metadata.
CLIENT_ID_ENV_VAR = "SPEC_KITTY_MACHINE_CLIENT_ID"

#: Environment variable carrying the client secret directly (CI secret).
# noqa S105 (both lines): these are env-var NAMES, not credential values —
# the same literal appears in the env-var reference and provisioning template.
CLIENT_SECRET_ENV_VAR = "SPEC_KITTY_MACHINE_CLIENT_SECRET"  # noqa: S105

#: Environment variable naming a file that holds the secret (CI secret file
#: / mounted credential). Takes precedence over ``CLIENT_SECRET_ENV_VAR``
#: when both are set, so a runner can pin the secret to a file even when a
#: stale env value lingers.
CLIENT_SECRET_FILE_ENV_VAR = "SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE"  # noqa: S105

_CREDENTIAL_VARS_REMEDY = f"set {CLIENT_ID_ENV_VAR} plus either {CLIENT_SECRET_ENV_VAR} or {CLIENT_SECRET_FILE_ENV_VAR} (never committed, never printed)"

_INVALID_CLIENT_REMEDIATION = (
    "machine credential rejected by the server (unknown client id, revoked "
    "principal, or wrong secret — the server does not distinguish these); "
    "ask a team admin to check the principal (provision_service_principal "
    "/ revoke_service_principal) and re-run spec-kitty auth login --machine"
)


@dataclass(frozen=True)
class MachineCredentials:
    """A resolved ServicePrincipal credential pair.

    ``client_id`` is a public identifier; ``client_secret`` is the secret.
    Nothing in this module ever renders ``client_secret`` — :meth:`__repr__`
    overrides the dataclass default so even a debug log of a caught error
    carries only ``<redacted>``.
    """

    client_id: str
    client_secret: str

    def __repr__(self) -> str:  # pragma: no cover - defensive, asserted in tests
        """Never render the secret, even in debug logs of caught errors."""
        return f"MachineCredentials(client_id={self.client_id!r}, client_secret=<redacted>)"


def load_machine_credentials(environ: dict[str, str] | None = None) -> MachineCredentials:
    """Load the machine credential pair from the environment, fail-closed.

    Args:
        environ: Mapping to read from (defaults to ``os.environ``). Injected
            by tests; never a prompt or interactive source.

    Returns:
        The resolved credential pair.

    Raises:
        ConfigurationError: When the client id is missing/blank, or no
            secret can be resolved (neither env var set, or the named file
            is missing/unreadable/blank). The message names the variables
            and the remediation — never any credential value.
    """
    env = os.environ if environ is None else environ

    client_id = (env.get(CLIENT_ID_ENV_VAR) or "").strip()
    if not client_id:
        raise ConfigurationError(
            f"Machine authentication is missing its client id: {CLIENT_ID_ENV_VAR} is not set. To use machine credentials, {_CREDENTIAL_VARS_REMEDY}."
        )

    secret = _load_client_secret(env)
    if not secret:
        raise ConfigurationError(
            f"Machine authentication is missing its client secret: neither "
            f"{CLIENT_SECRET_ENV_VAR} nor a readable {CLIENT_SECRET_FILE_ENV_VAR} "
            f"resolved to a non-blank value. {_CREDENTIAL_VARS_REMEDY}."
        )

    return MachineCredentials(client_id=client_id, client_secret=secret)


def _load_client_secret(env: Mapping[str, str]) -> str:
    """Resolve the client secret: secret file first, then the env value.

    A file path is stripped and read once; surrounding whitespace (the
    trailing newline a CI secret file almost always carries) is stripped
    from its contents. Read errors raise :class:`ConfigurationError`
    naming the path — the file being *absent* is a misconfiguration to
    fail closed on, not a silent fall-through to the env var, because a
    runner that pinned the secret to a file must not silently authenticate
    with some other value.
    """
    path_raw = (env.get(CLIENT_SECRET_FILE_ENV_VAR) or "").strip()
    if path_raw:
        path = Path(path_raw)
        try:
            contents = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Machine authentication could not read the secret file named by {CLIENT_SECRET_FILE_ENV_VAR} ({path}): {exc}. {_CREDENTIAL_VARS_REMEDY}."
            ) from exc
        return contents.strip()

    return (env.get(CLIENT_SECRET_ENV_VAR) or "").strip()


class ClientCredentialsFlow:
    """Orchestration for the ``client_credentials`` machine login path.

    Mirrors :class:`specify_cli.auth.flows.device_code.DeviceCodeFlow`'s
    shape: constructor takes the resolved SaaS base URL (never hardcoded,
    per D-5 — the caller passes what
    :func:`specify_cli.auth.server_target.resolve_server_target` resolved so
    login and every hosted surface name the same endpoint) and the storage
    backend tag; :meth:`login` returns a :class:`StoredSession` ready for
    ``TokenManager.set_session()``.
    """

    def __init__(
        self,
        saas_base_url: str,
        storage_backend: StorageBackend,
    ) -> None:
        self._saas_base_url = saas_base_url.rstrip("/")
        self._storage_backend = storage_backend

    async def login(self, credentials: MachineCredentials) -> StoredSession:
        """Exchange the credential pair and build the stored session.

        Raises:
            NetworkError: On httpx transport errors.
            AuthenticationError: On a refused grant (with the fail-closed
                remediation — never the secret, never a device-flow prompt),
                a malformed response, or a user-info fetch failure.
        """
        tokens = await self._exchange(credentials)
        me = await self._fetch_me(tokens["access_token"])
        return self._build_session(tokens, me)

    async def _exchange(self, credentials: MachineCredentials) -> dict[str, Any]:
        """POST ``/oauth/token`` with the ``client_credentials`` grant.

        On any non-200 the response body is parsed only for the OAuth
        ``error`` code — never rendered, since a misconfigured server could
        echo submitted form fields back.
        """
        url = f"{self._saas_base_url}/oauth/token"
        data = {
            "grant_type": _CLIENT_CREDENTIALS_GRANT_TYPE,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(url, data=data)
            except httpx.RequestError as exc:
                raise NetworkError(f"Network error exchanging machine credentials: {exc}") from exc

        if response.status_code == 429:
            raise AuthenticationError("Machine credential exchange was rate-limited by the server (HTTP 429); retry shortly.")

        if response.status_code != 200:
            error_code = _safe_error_code(response)
            if error_code == "invalid_client":
                # Byte-identical remediation for unknown id / revoked
                # principal / wrong secret — mirroring the server's own
                # refusal to distinguish them.
                raise AuthenticationError(f"Machine authentication failed: {_INVALID_CLIENT_REMEDIATION}")
            raise AuthenticationError(
                f"Machine credential exchange failed: HTTP {response.status_code}"
                f"{f' ({error_code})' if error_code else ''} — check the SaaS URL and credential provisioning."
            )

        try:
            payload: dict[str, Any] = response.json()
        except ValueError as exc:
            raise AuthenticationError("Machine credential exchange response was not JSON.") from exc

        for field in ("access_token", "refresh_token", "expires_in", "session_id"):
            if field not in payload:
                raise AuthenticationError(f"Machine credential exchange response missing required field '{field}'.")
        return payload

    async def _fetch_me(self, access_token: str) -> dict[str, Any]:
        """GET ``/api/v1/me`` with the minted bearer — same shape as the human flows."""
        url = f"{self._saas_base_url}/api/v1/me"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.get(url, headers=headers)
            except httpx.RequestError as exc:
                raise NetworkError(f"Network error fetching user info: {exc}") from exc

        if response.status_code != 200:
            raise AuthenticationError(f"User info fetch failed: HTTP {response.status_code}")

        try:
            # cast(): ``response.json()`` is Any; ``parse_me_payload`` validates
            # the object shape and re-raises as the auth error contract.
            return cast("dict[str, Any]", parse_me_payload(response.json()))
        except ValueError as exc:
            raise AuthenticationError("User info response was not JSON.") from exc

    def _build_session(self, tokens: dict[str, Any], me: dict[str, Any]) -> StoredSession:
        """Assemble the :class:`StoredSession`, tagged ``client_credentials``.

        Unlike the human flows, an empty ``teams`` list is tolerated: the
        SaaS guarantees the service user a Private Teamspace on ``/me``, but
        a machine credential's authority is its server-side scope (the
        token response's ``scope``), not a client-side team pick — failing
        closed here would block CI on a display-only default the machine
        path never reads.
        """
        user_id = require_me_field(me, "user_id")
        email = require_me_field(me, "email")
        teams = parse_me_teams(me)

        now = now_utc()
        try:
            expires_in = int(tokens["expires_in"])
        except (TypeError, ValueError) as exc:
            raise AuthenticationError("Token response missing or invalid 'expires_in' field.") from exc

        return StoredSession(
            user_id=str(user_id),
            email=str(email),
            name=str(me.get("name", email)),
            teams=teams,
            default_team_id=pick_default_team_id(teams) if teams else "",
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            session_id=tokens["session_id"],
            issued_at=now,
            access_token_expires_at=now + timedelta(seconds=expires_in),
            refresh_token_expires_at=_resolve_refresh_expiry(tokens, me, now),
            # The principal's server-enforced scope (e.g. "sync:ingest
            # sync:read") — the authority the machine credential actually
            # carries, recorded verbatim from the token response.
            scope=str(tokens.get("scope", "")),
            storage_backend=self._storage_backend,
            last_used_at=now,
            auth_method="client_credentials",
            issuer_url=self._saas_base_url,
        )


def _safe_error_code(response: httpx.Response) -> str:
    """Best-effort OAuth ``error`` code from an error response, else ``""``.

    Never raises and never renders the body: a malformed or non-JSON error
    body degrades to the status-code-only message.
    """
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        code = payload.get("error")
        if isinstance(code, str) and code.strip():
            return code.strip()[:64]
    return ""


def _parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp, accepting the ``Z`` suffix.

    Same normalization the human flows' local helpers apply — kept local
    for the same ownership reason they cite.
    """
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return parse_iso(normalized)


def _resolve_refresh_expiry(
    tokens: dict[str, Any],
    me: dict[str, Any],
    now: datetime,
) -> datetime | None:
    """Resolve ``refresh_token_expires_at`` per C-012 — never a hardcoded TTL.

    Same preference order as the human flows: absolute stamp from the token
    response, then from ``/me``, then the relative ``expires_in``-shaped
    field, then ``None`` (server-managed; the client learns expiry on
    refresh).
    """
    absolute = tokens.get("refresh_token_expires_at") or me.get("refresh_token_expires_at")
    if absolute is not None:
        try:
            return _parse_iso_utc(str(absolute))
        except (AttributeError, TypeError, ValueError) as exc:
            raise AuthenticationError("Refresh token expiry field 'refresh_token_expires_at' must be an ISO-8601 timestamp.") from exc

    relative = tokens.get("refresh_token_expires_in")
    if relative is not None:
        try:
            return now + timedelta(seconds=int(relative))
        except (TypeError, ValueError):
            log.warning("refresh_token_expires_in was not an int: %r", relative)
            return None
    return None


__all__ = [
    # Only the two symbols a src/ caller actually imports
    # (``cli.commands._auth_login._run_machine_flow``). The env-var name
    # constants and ``MachineCredentials`` stay deliberately OUT of
    # ``__all__``: they have no cross-module src/ caller (tests import them
    # by name, which ``__all__`` does not gate), and declaring them exports
    # would trip the symbol-level dead-code gate's ``__all__`` rule.
    "ClientCredentialsFlow",
    "load_machine_credentials",
]
