"""WebSocket pre-connect token provisioner (feature 080, WP09).

Fetches an ephemeral WebSocket token from the SaaS ``POST /api/v1/ws-token``
endpoint immediately before ``sync/client.py`` opens a WS upgrade. The flow is:

1. Pre-connect refresh: if the access token expires within
   ``_PRE_CONNECT_REFRESH_BUFFER_SECONDS`` (NFR-005: 5 minutes), refresh the
   access token first so we do not waste the short-lived ``ws_token`` on a
   doomed WS handshake.
2. POST ``/api/v1/ws-token`` with a Bearer access token and the target
   ``team_id`` in the body.
3. Return the parsed ``{ws_token, ws_url, expires_in, session_id}`` dict to
   the caller, which sends ``ws_token`` as a Bearer token on the WS upgrade.

All 4xx/5xx responses are translated into :class:`WebSocketProvisioningError`
with user-facing recovery guidance; network-level failures propagate as
:class:`NetworkError` from the shared auth error hierarchy.

This module owns ONLY the provisioner. Integration into the actual WS client
lives in WP08 (``sync/client.py``); this separation keeps the HTTP side
unit-testable without a real WebSocket loop.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .. import get_token_manager
from ..errors import AuthenticationError, IssuerTargetMismatchError, NetworkError, NotAuthenticatedError
from ..http import PublicHttpClient
from ..server_target import resolve_token_endpoint

log = logging.getLogger(__name__)

# NFR-005: refresh the access token if it expires within this window before
# calling /api/v1/ws-token. 5 minutes matches the planning spec.
_PRE_CONNECT_REFRESH_BUFFER_SECONDS = 300

# Required fields the SaaS must return on a 200 response (contract).
_REQUIRED_RESPONSE_FIELDS = ("ws_token", "ws_url", "expires_in", "session_id")

# HTTP timeout for the provisioning POST. Kept tight because the caller is
# about to open a WS — there is no value in waiting on a stalled REST call.
_HTTP_TIMEOUT_SECONDS = 10.0


class WebSocketProvisioningError(AuthenticationError):
    """Raised when WebSocket token provisioning fails.

    Used for all non-200 responses from ``/api/v1/ws-token`` (401, 403, 404,
    5xx, and catch-all). Network-level failures raise :class:`NetworkError`
    instead so the caller can distinguish "server said no" from "couldn't
    reach server".
    """


class WebSocketTokenProvisioner:
    """Fetches ephemeral WebSocket tokens from ``/api/v1/ws-token``.

    The buffer is injectable so tests (and future NFR tuning) can override it
    without monkey-patching the module constant.
    """

    def __init__(
        self,
        *,
        refresh_buffer_seconds: int = _PRE_CONNECT_REFRESH_BUFFER_SECONDS,
    ) -> None:
        self._refresh_buffer = refresh_buffer_seconds

    async def provision(self, team_id: str) -> dict[str, Any]:
        """Provision a WebSocket token for ``team_id``.

        Returns:
            Dict with keys ``ws_token``, ``ws_url``, ``expires_in``, and
            ``session_id``. The caller sends ``ws_token`` as a Bearer token
            on the WS upgrade.

        Raises:
            NotAuthenticatedError: No active session. The user must run
                ``spec-kitty auth login``.
            WebSocketProvisioningError: The SaaS returned a 4xx/5xx response
                (the message includes user-facing recovery guidance), or the
                session's issuer disagrees with the resolved server target
                (#4755, NFR-004/NFR-005/NFR-006) — refused before the ws-token
                POST is ever built, with a token-free remedy message.
            NetworkError: Transport-level failure (DNS, connection refused,
                timeout, TLS handshake error).
            ServerTargetSplitBrainError: An ambiguous env/config target
                disagreement, propagated unchanged from
                :func:`specify_cli.auth.server_target.resolve_token_endpoint`.
        """
        tm = get_token_manager()
        if not tm.is_authenticated:
            raise NotAuthenticatedError("WebSocket provisioning requires authentication. Run `spec-kitty auth login`.")

        # Pre-connect refresh: if the access token expires within the buffer,
        # refresh it before calling /api/v1/ws-token. This avoids burning an
        # ephemeral ws_token on a WS handshake that would get 401'd anyway.
        session = tm.get_current_session()
        if session is not None and session.is_access_token_expired(buffer_seconds=self._refresh_buffer):
            log.debug(
                "Pre-connect refresh: access token within %ds buffer",
                self._refresh_buffer,
            )
            await tm.refresh_if_needed()

        try:
            endpoint = resolve_token_endpoint(session)
        except IssuerTargetMismatchError as exc:
            raise WebSocketProvisioningError(str(exc)) from exc

        url = f"{endpoint}/api/v1/ws-token"
        access_token = await tm.get_access_token()
        headers = {"Authorization": f"Bearer {access_token}"}
        payload = {"team_id": team_id}

        async with PublicHttpClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
            except NetworkError as exc:
                raise NetworkError(f"WebSocket provisioning network error: {exc}") from exc

        return self._handle_response(response, team_id)

    # ---- response handling ----------------------------------------------

    def _handle_response(self, response: httpx.Response, team_id: str) -> dict[str, Any]:
        """Translate an HTTP response into a parsed dict or a typed error."""
        status = response.status_code
        if status == 200:
            try:
                body = response.json()
            except ValueError as exc:
                raise WebSocketProvisioningError(f"WS token response was not valid JSON: {exc}") from exc
            if not isinstance(body, dict):
                raise WebSocketProvisioningError("WS token response was not a JSON object.")
            missing = [k for k in _REQUIRED_RESPONSE_FIELDS if k not in body]
            if missing:
                raise WebSocketProvisioningError(f"WS token response missing required fields: {missing}")
            return body

        self._raise_for_error(response, team_id)
        # ``_raise_for_error`` never returns — this is unreachable but keeps
        # mypy happy about the method returning ``dict``.
        raise WebSocketProvisioningError(  # pragma: no cover
            f"Unexpected fallthrough for HTTP {status}"
        )

    def _raise_for_error(self, response: httpx.Response, team_id: str) -> None:
        """Raise a :class:`WebSocketProvisioningError` for a non-200 response."""
        status = response.status_code
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}

        error = body.get("error", "") if isinstance(body, dict) else ""
        desc = body.get("error_description", "") if isinstance(body, dict) else ""

        if status == 401:
            raise WebSocketProvisioningError("Authentication required. Run `spec-kitty auth login`.")
        if status == 403:
            if error == "not_a_team_member":
                raise WebSocketProvisioningError(f"You are not a member of team '{team_id}'. Check the team ID or contact your team admin.")
            raise WebSocketProvisioningError(f"Forbidden: {desc or 'access denied'}")
        if status == 404:
            raise WebSocketProvisioningError(f"Team '{team_id}' not found. Check the team ID.")
        if 500 <= status < 600:
            raise WebSocketProvisioningError(f"SaaS server error (HTTP {status}). Try again in a few minutes.")

        raise WebSocketProvisioningError(f"Unexpected response from /api/v1/ws-token: HTTP {status}")


async def provision_ws_token(team_id: str) -> dict[str, Any]:
    """Convenience wrapper around :class:`WebSocketTokenProvisioner`.

    ``sync/client.py`` (WP08) calls this immediately before opening the WS
    upgrade. Returns the same dict as ``WebSocketTokenProvisioner.provision``.
    """
    return await WebSocketTokenProvisioner().provision(team_id)
