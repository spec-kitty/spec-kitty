"""AuthorizationCodeFlow — browser OAuth Authorization Code + PKCE orchestration.

This is the orchestration class that ties together every loopback primitive
(``StateManager``, ``CallbackServer``, ``BrowserLauncher``, ``CallbackHandler``)
with the SaaS HTTP calls (``POST /oauth/token``, ``GET /api/v1/me``) to
produce a :class:`StoredSession` ready for ``TokenManager.set_session()``.

Contract with the SaaS (feature 080, contracts/ directory):

- ``POST /oauth/authorize`` — browser-visible endpoint. The CLI builds the
  authorization URL with PKCE + CSRF state and hands it to
  ``BrowserLauncher.launch``.
- ``POST /oauth/token`` with ``grant_type=authorization_code`` — exchanges
  the callback ``code`` for ``access_token`` + ``refresh_token``. The
  response also includes ``expires_in``, ``refresh_token_expires_in``, and
  ``refresh_token_expires_at`` (SaaS amendment landed 2026-04-09).
- ``GET /api/v1/me`` — returns ``user_id``, ``email``, ``name``, ``teams[]``
  plus the same refresh-token expiry fields.

Per C-012 and the 2026-04-09 SaaS refresh-TTL amendment, this flow reads the
refresh-token expiry directly from the server response — it never hardcodes
a TTL and never computes the expiry locally. See ``_build_session`` for the
prefer-absolute-then-relative fallback logic.

The SaaS base URL is resolved, never hardcoded here: callers pass it in
via the constructor, typically from
:func:`specify_cli.auth.config.get_saas_base_url` (env override; raises
``HostedEndpointUnconfigured`` when unset, endpoint opt-in FR-011). Direct
construction with no ``saas_base_url`` and no env override is a dead path
in practice — ``_auth_login.py`` always pre-resolves and passes the URL.
"""

from __future__ import annotations

import logging
from typing import Any, cast

from kernel.clock import datetime, now_utc, parse_iso, timedelta
from urllib.parse import urlencode

from ..config import get_saas_base_url
from ..errors import (
    AuthenticationError,
    BrowserLaunchError,
    NetworkError,
)
from ..http import PublicHttpClient
from ..loopback.browser_launcher import BrowserLauncher
from ..loopback.callback_handler import CallbackHandler
from ..loopback.callback_server import CallbackServer
from ..loopback.state import PKCEState
from ..loopback.state_manager import StateManager
from ..session import StorageBackend, StoredSession, pick_default_team_id
from ._session_payload import parse_me_payload, parse_me_teams, require_me_field

log = logging.getLogger(__name__)

_DEFAULT_CLIENT_ID = "cli_native"
_DEFAULT_SCOPE = "offline_access"
_HTTP_TIMEOUT_SECONDS = 10.0


class AuthorizationCodeFlow:
    """Orchestrates the OAuth Authorization Code + PKCE flow.

    Usage::

        flow = AuthorizationCodeFlow(saas_base_url="https://saas.example.com")
        session = await flow.login()
        token_manager.set_session(session)

    The flow is stateless across calls — each ``login()`` call builds a
    fresh ``PKCEState``, starts its own loopback server, and shuts it down
    before returning.
    """

    def __init__(
        self,
        saas_base_url: str | None = None,
        client_id: str = _DEFAULT_CLIENT_ID,
        *,
        storage_backend: StorageBackend = "file",
    ) -> None:
        """Build a new flow.

        Args:
            saas_base_url: Base URL of the spec-kitty SaaS (no trailing slash).
                When ``None``, the flow calls
                :func:`specify_cli.auth.config.get_saas_base_url` itself
                (env override; raises ``HostedEndpointUnconfigured`` when
                unset, endpoint opt-in FR-011).
                Callers that already have the URL in hand (such as
                ``_auth_login.py``) pass it in directly to avoid two env-var
                reads per login.
            client_id: OAuth client identifier. Defaults to ``"cli_native"``.
            storage_backend: Backend identifier to persist on the resulting
                :class:`StoredSession`. Should match the actual backend that
                ``TokenManager`` will use (passed by ``_auth_login.py``).
        """
        resolved = saas_base_url if saas_base_url is not None else get_saas_base_url()
        self._saas_base_url = resolved.rstrip("/")
        self._client_id = client_id
        self._storage_backend: StorageBackend = storage_backend
        self._state_manager = StateManager()

    async def login(self) -> StoredSession:
        """Execute the full browser-based login flow end-to-end.

        Returns:
            A :class:`StoredSession` ready for ``TokenManager.set_session()``.

        Raises:
            BrowserLaunchError: No browser is available on the host.
            CallbackTimeoutError: The loopback server timed out (5 min).
            CallbackValidationError: CSRF state mismatch or malformed callback.
            StateExpiredError: The PKCE state expired before the callback arrived.
            NetworkError: A network failure during token exchange or user-info fetch.
            AuthenticationError: Any other authentication failure.
        """
        pkce_state = self._state_manager.generate()
        callback_server = CallbackServer()

        try:
            callback_url = callback_server.start()

            auth_url = self._build_auth_url(pkce_state, callback_url)
            if not BrowserLauncher.launch(auth_url):
                raise BrowserLaunchError(f"No browser available. Please visit:\n  {auth_url}")

            callback_params = await callback_server.wait_for_callback()
        finally:
            callback_server.stop()
            self._state_manager.cleanup(pkce_state)

        # State may expire between browser open and callback arrival.
        self._state_manager.validate_not_expired(pkce_state)

        handler = CallbackHandler(pkce_state.state)
        code, _ = handler.validate(callback_params)

        tokens = await self._exchange_code(
            code=code,
            code_verifier=pkce_state.code_verifier,
            redirect_uri=callback_url,
        )
        session = await self._build_session(tokens)
        return session

    # ---- URL construction -------------------------------------------------

    def _build_auth_url(self, pkce_state: PKCEState, callback_url: str) -> str:
        """Build the ``/oauth/authorize`` URL with PKCE + CSRF state params."""
        params = {
            "client_id": self._client_id,
            "redirect_uri": callback_url,
            "response_type": "code",
            "scope": _DEFAULT_SCOPE,
            "code_challenge": pkce_state.code_challenge,
            "code_challenge_method": pkce_state.code_challenge_method,
            "state": pkce_state.state,
        }
        return f"{self._saas_base_url}/oauth/authorize?{urlencode(params)}"

    # ---- Token exchange (T024) -------------------------------------------

    async def _exchange_code(self, *, code: str, code_verifier: str, redirect_uri: str) -> dict[str, Any]:
        """Exchange an authorization code for access + refresh tokens.

        POSTs to ``{saas}/oauth/token`` with grant_type=authorization_code
        and the PKCE verifier. Returns the parsed JSON body on success.

        Raises:
            NetworkError: On httpx transport errors (connect, DNS, timeout).
            AuthenticationError: If the server rejects the exchange or
                returns a malformed response.
        """
        url = f"{self._saas_base_url}/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self._client_id,
            "code_verifier": code_verifier,
        }
        async with PublicHttpClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(url, data=data)
            except NetworkError as exc:
                raise NetworkError(f"Network error during code exchange: {exc}") from exc

        if response.status_code != 200:
            # Include only the status and a trimmed body for diagnostics;
            # the body can contain server-side error descriptions.
            body = response.text[:500]
            raise AuthenticationError(f"Token exchange failed: HTTP {response.status_code} - {body}")

        try:
            tokens = response.json()
        except ValueError as exc:
            raise AuthenticationError(f"Token exchange returned invalid JSON: {exc}") from exc

        required = ("access_token", "refresh_token", "expires_in", "session_id")
        missing = [k for k in required if k not in tokens]
        if missing:
            raise AuthenticationError(f"Token response missing required fields: {missing}")
        return cast(dict[str, Any], tokens)

    # ---- User info + StoredSession (T025) --------------------------------

    async def _build_session(self, tokens: dict[str, Any]) -> StoredSession:
        """Fetch user info from ``/api/v1/me`` and assemble a StoredSession.

        Contract (feature 080, contracts/protected-endpoints.md, SaaS amendment
        landed 2026-04-09):

        - ``/api/v1/me`` returns ``user_id``, ``email``, ``name``, ``teams[]``,
          ``session_id``, ``authenticated_at``, ``access_token_expires_at``,
          ``refresh_token_expires_at``, ``auth_flow``.
        - ``POST /oauth/token`` response now includes both
          ``refresh_token_expires_in`` (int seconds) and
          ``refresh_token_expires_at`` (ISO-8601 UTC string).

        Per C-012, the CLI reads the refresh-token expiry directly from the
        SaaS response — it NEVER hardcodes a TTL and NEVER computes the
        timestamp locally. The ``_build_session`` method:

        1. Prefers ``refresh_token_expires_at`` (absolute, no clock drift)
           from the token response.
        2. Falls back to ``refresh_token_expires_at`` from ``/api/v1/me``
           if the token response omits it.
        3. Falls back to ``now + refresh_token_expires_in`` if neither
           absolute form is present.

        The SaaS does not return ``default_team_id`` (that is a
        client-picked field — see C-011). The CLI prefers the team's
        ``is_private_teamspace`` membership when present and otherwise falls
        back to ``teams[0].id`` on first login; a future mission can add
        ``spec-kitty auth set-default-team`` for explicit override.
        """
        url = f"{self._saas_base_url}/api/v1/me"
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        async with PublicHttpClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.get(url, headers=headers)
            except NetworkError as exc:
                raise NetworkError(f"Network error fetching user info: {exc}") from exc

        if response.status_code != 200:
            raise AuthenticationError(f"User info fetch failed: HTTP {response.status_code}")

        try:
            me = parse_me_payload(response.json())
        except ValueError as exc:
            raise AuthenticationError(f"User info response was not JSON: {exc}") from exc

        user_id = require_me_field(me, "user_id")
        email = require_me_field(me, "email")
        teams = parse_me_teams(me)
        if not teams:
            raise AuthenticationError("User has no team memberships. Contact your administrator.")
        # Client-picked default (see C-011): the SaaS does not return
        # ``default_team_id``; we prefer Private Teamspace when available.
        default_team_id = pick_default_team_id(teams)

        now = now_utc()
        try:
            expires_in = int(tokens["expires_in"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Token response missing or invalid 'expires_in' field.") from exc

        refresh_token_expires_at = self._resolve_refresh_expiry(tokens, me, now)

        return StoredSession(
            user_id=user_id,
            email=email,  # sourced from /api/v1/me .email per C-011
            name=me.get("name", email),
            teams=teams,
            default_team_id=default_team_id,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            session_id=tokens["session_id"],
            issued_at=now,
            access_token_expires_at=now + timedelta(seconds=expires_in),
            refresh_token_expires_at=refresh_token_expires_at,
            scope=tokens.get("scope", _DEFAULT_SCOPE),
            storage_backend=self._storage_backend,
            last_used_at=now,
            auth_method="authorization_code",
            issuer_url=self._saas_base_url,
        )

    @staticmethod
    def _resolve_refresh_expiry(
        tokens: dict[str, Any],
        me: dict[str, Any],
        now: datetime,
    ) -> datetime | None:
        """Resolve ``refresh_token_expires_at`` from the SaaS responses.

        Per C-012 and the 2026-04-09 SaaS amendment, the CLI never hardcodes
        a refresh-token TTL. Preference order:

        1. ``refresh_token_expires_at`` from the token response (absolute).
        2. ``refresh_token_expires_at`` from ``/api/v1/me`` (absolute).
        3. ``refresh_token_expires_in`` from the token response (relative).
        4. ``None`` — server-managed, client learns expiry on refresh.
        """
        absolute = tokens.get("refresh_token_expires_at") or me.get("refresh_token_expires_at")
        if absolute is not None:
            try:
                return _parse_iso_utc(absolute)
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


def _parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp, accepting the ``Z`` suffix.

    SaaS responses may use either ``2026-04-09T12:00:00+00:00`` or
    ``2026-04-09T12:00:00Z``; ``datetime.fromisoformat`` accepts the former
    but historically rejected the latter on Python 3.10. Normalize before
    parsing so both forms round-trip identically.
    """
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return parse_iso(normalized)
