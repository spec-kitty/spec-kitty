"""RevokeFlow — RFC 7009 token revocation for spec-kitty auth logout."""

from __future__ import annotations

import logging
from enum import StrEnum

import httpx

from ..errors import IssuerTargetMismatchError
from ..server_target import ServerTargetSplitBrainError, resolve_token_endpoint
from ..session import StoredSession

log = logging.getLogger(__name__)

_HTTP_TIMEOUT_SECONDS = 10.0


class RevokeOutcome(StrEnum):
    REVOKED = "revoked"
    """Server confirmed revocation: 200 + {"revoked": true}."""

    SERVER_FAILURE = "server_failure"
    """Server returned 4xx/5xx or unexpected body. NOT revoked."""

    NETWORK_ERROR = "network_error"
    """Transport-level failure (DNS, connect, timeout)."""

    NO_REFRESH_TOKEN = "no_refresh_token"
    """Session has no refresh token; revocation not attempted."""

    ISSUER_MISMATCH = "issuer_mismatch"
    """Refused — the resolved token target does not match the session's
    issuer (or the target is ambiguous, a split-brain). No POST is issued;
    the caller must not fold this into SERVER_FAILURE."""


class RevokeFlow:
    """RFC 7009-compliant token revocation."""

    async def revoke(self, session: StoredSession) -> RevokeOutcome:
        """POST /oauth/revoke with the session's refresh token.

        Never raises. Returns RevokeOutcome so the caller can produce
        accurate output without re-implementing status logic.
        """
        if not session.refresh_token:
            return RevokeOutcome.NO_REFRESH_TOKEN

        # Resolved BEFORE the try/except below so a mismatch or split-brain
        # refusal is never folded into SERVER_FAILURE by the bare
        # `except Exception` guarding the HTTP call.
        try:
            endpoint = resolve_token_endpoint(session)
        except (IssuerTargetMismatchError, ServerTargetSplitBrainError) as exc:
            log.warning("Revoke refused: %s", type(exc).__name__)
            return RevokeOutcome.ISSUER_MISMATCH

        url = f"{endpoint}/oauth/revoke"
        data = {
            "token": session.refresh_token,
            "token_type_hint": "refresh_token",
        }

        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(url, data=data)
        except httpx.RequestError as exc:
            log.warning("Revoke network error: %s", type(exc).__name__)
            return RevokeOutcome.NETWORK_ERROR
        except Exception as exc:  # noqa: BLE001 - revoke must never block local logout cleanup
            log.warning("Revoke unexpected error: %s", type(exc).__name__)
            return RevokeOutcome.SERVER_FAILURE

        if response.status_code == 200:
            try:
                body = response.json()
                if body.get("revoked") is True:
                    return RevokeOutcome.REVOKED
            except ValueError:
                pass
            # 200 but unexpected body
            log.warning("Revoke 200 but unexpected body shape")
            return RevokeOutcome.SERVER_FAILURE

        log.warning("Revoke HTTP %d", response.status_code)
        return RevokeOutcome.SERVER_FAILURE


__all__ = ["RevokeFlow", "RevokeOutcome"]
