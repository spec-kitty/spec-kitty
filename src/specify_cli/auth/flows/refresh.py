"""TokenRefreshFlow — refresh-grant orchestration for the spec-kitty auth subsystem.

This flow is invoked from :class:`TokenManager.refresh_if_needed` when the
access token is at or near expiry. It POSTs to ``/oauth/token`` with
``grant_type=refresh_token`` and returns an updated :class:`StoredSession`
with rotated tokens.

Per C-012 and the 2026-04-09 SaaS refresh-TTL amendment, this flow reads
``refresh_token_expires_at`` directly from the token response. It prefers
the absolute form (``refresh_token_expires_at``) to avoid clock drift, and
falls back to ``refresh_token_expires_in`` (seconds) if the absolute form
is absent. The CLI NEVER hardcodes a TTL.

Error semantics (feature 080, spec §7.2):

- SaaS returns ``400`` or ``401`` with ``invalid_grant`` →
  :class:`RefreshTokenExpiredError`. The refresh token is invalid or expired;
  the user must re-run ``spec-kitty auth login``.
- SaaS returns ``400`` or ``401`` with ``session_invalid`` →
  :class:`SessionInvalidError`. The server has administratively invalidated
  this session; ``TokenManager`` clears local state and the user must
  re-login.
- Missing local refresh credentials or ``invalid_request`` / ``invalid_client``
  responses → :class:`TokenRefreshError` with specific recovery guidance.
- Any other HTTP error → :class:`TokenRefreshError` without the response body.
- Transport-level failures → :class:`NetworkError`.
"""

from __future__ import annotations

import logging
from typing import Any

from kernel.clock import datetime, now_utc, parse_iso, timedelta

from ..config import get_saas_base_url
from ..errors import (
    NetworkError,
    RefreshReplayError,
    RefreshTokenExpiredError,
    SessionInvalidError,
    TokenRefreshError,
)
from ..http import PublicHttpClient
from ..session import StoredSession

log = logging.getLogger(__name__)

_DEFAULT_CLIENT_ID = "cli_native"
_HTTP_TIMEOUT_SECONDS = 10.0


class TokenRefreshFlow:
    """Refreshes an expired access token using the ``refresh_token`` grant."""

    def __init__(self, client_id: str = _DEFAULT_CLIENT_ID) -> None:
        self._client_id = client_id

    async def refresh(self, session: StoredSession) -> StoredSession:
        """POST ``/oauth/token`` with ``grant_type=refresh_token``.

        Args:
            session: The current :class:`StoredSession` whose access token
                needs refreshing.

        Returns:
            A new :class:`StoredSession` with rotated access + refresh
            tokens and updated expiry timestamps.

        Raises:
            RefreshTokenExpiredError: The SaaS rejected the refresh token
                (``400/401 invalid_grant``). The user must re-run
                ``auth login``.
            SessionInvalidError: The SaaS reports the session has been
                invalidated server-side (``400/401 session_invalid``).
            TokenRefreshError: Any other HTTP failure during refresh.
            NetworkError: Transport-level failure (DNS, connect, timeout).
        """
        if not isinstance(session.refresh_token, str) or not session.refresh_token.strip():
            raise TokenRefreshError(
                "No usable refresh credential is stored. "
                "Run `spec-kitty auth login` again."
            )

        saas_url = get_saas_base_url()
        url = f"{saas_url}/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": session.refresh_token,
            "client_id": self._client_id,
        }

        async with PublicHttpClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(url, data=data)
            except NetworkError as exc:
                raise NetworkError(f"Network error during refresh: {exc}") from exc

        if response.status_code == 200:
            try:
                tokens = response.json()
            except ValueError as exc:
                raise TokenRefreshError(
                    f"Refresh response was not JSON: {exc}"
                ) from exc
            return self._update_session(session, tokens)

        if response.status_code == 409:
            try:
                body = response.json()
            except ValueError:
                body = {}
            if isinstance(body, dict) and body.get("error") == "refresh_replay_benign_retry":
                raise RefreshReplayError(retry_after=int(body.get("retry_after", 0)))
            # Non-replay 409 (unexpected) — fall through to generic TokenRefreshError below

        self._raise_known_auth_error(response)

        raise TokenRefreshError(
            f"Token refresh failed: HTTP {response.status_code}. "
            "Retry later; if this persists, contact your Team Kitty administrator."
        )

    def _update_session(
        self, session: StoredSession, tokens: dict[str, Any]
    ) -> StoredSession:
        """Build an updated session from a refresh response.

        Per C-012 (LANDED 2026-04-09), ``refresh_token_expires_at`` is read
        directly from the SaaS token response on every refresh. The CLI
        never hardcodes a TTL and never computes the timestamp locally.
        Preference order:

        1. ``refresh_token_expires_at`` (absolute, ISO-8601 UTC).
        2. ``refresh_token_expires_in`` (int seconds from now).
        3. Fall back to the previous session's expiry (last resort — only
           reachable if the server is non-compliant with the landed amendment).
        """
        now = now_utc()

        try:
            new_access = tokens["access_token"]
        except KeyError as exc:
            raise TokenRefreshError(
                "Refresh response missing 'access_token'"
            ) from exc

        # Refresh token may rotate; keep the old one if the server doesn't rotate.
        new_refresh = tokens.get("refresh_token", session.refresh_token)

        try:
            expires_in = int(tokens.get("expires_in", 3600))
        except (TypeError, ValueError) as exc:
            raise TokenRefreshError(
                f"Refresh response has invalid 'expires_in': {exc}"
            ) from exc

        refresh_token_expires_at = self._resolve_refresh_expiry(tokens, now, session)

        return StoredSession(
            user_id=session.user_id,
            email=session.email,
            name=session.name,
            teams=session.teams,
            default_team_id=session.default_team_id,
            access_token=new_access,
            refresh_token=new_refresh,
            session_id=session.session_id,
            issued_at=now,
            access_token_expires_at=now + timedelta(seconds=expires_in),
            refresh_token_expires_at=refresh_token_expires_at,
            scope=tokens.get("scope", session.scope),
            storage_backend=session.storage_backend,
            last_used_at=now,
            auth_method=session.auth_method,
            generation=tokens.get("generation"),  # None if server doesn't send it
            # A refresh renews tokens with the same issuer; the session stays
            # "minted against" wherever login happened until a re-login.
            issuer_url=session.issuer_url,
        )

    @staticmethod
    def _resolve_refresh_expiry(
        tokens: dict[str, Any],
        now: datetime,
        session: StoredSession,
    ) -> datetime | None:
        """Resolve ``refresh_token_expires_at`` from the refresh response.

        Preference: absolute form > relative form > previous session's
        value. Never hardcodes a TTL. Returns ``None`` only if all three
        sources are unavailable (non-compliant server + no prior expiry).
        """
        absolute = tokens.get("refresh_token_expires_at")
        if absolute is not None:
            return _parse_iso_utc(absolute)

        relative = tokens.get("refresh_token_expires_in")
        if relative is not None:
            try:
                return now + timedelta(seconds=int(relative))
            except (TypeError, ValueError):
                log.warning(
                    "refresh_token_expires_in was not an int: %r", relative
                )

        # Last-resort fallback: preserve the previous session's expiry so
        # we never produce a session with an indeterminate refresh expiry
        # when we previously had one.
        return session.refresh_token_expires_at

    @staticmethod
    def _raise_known_auth_error(response: Any) -> None:
        if response.status_code not in {400, 401}:
            return
        try:
            body = response.json()
        except ValueError:
            body = {}
        error = body.get("error", "") if isinstance(body, dict) else ""
        if error == "invalid_request":
            raise TokenRefreshError(
                "The server rejected the refresh request (invalid_request): "
                "a required parameter is missing or malformed. "
                "Run `spec-kitty auth login` again; if this persists, "
                "contact your Team Kitty administrator."
            )
        if error == "invalid_client":
            raise TokenRefreshError(
                "The server rejected the CLI client identification (invalid_client). "
                "Check that this CLI is supported by your Team Kitty server; "
                "contact your administrator to verify the CLI client configuration."
            )
        if error == "invalid_grant":
            raise RefreshTokenExpiredError(
                "Refresh token is invalid or expired. "
                "Run `spec-kitty auth login` again."
            )
        if error == "session_invalid":
            raise SessionInvalidError(
                "Session has been invalidated server-side. "
                "Run `spec-kitty auth login` again."
            )


def _parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp, accepting the ``Z`` suffix."""
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    return parse_iso(normalized)
