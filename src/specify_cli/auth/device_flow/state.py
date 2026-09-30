"""In-flight state for the RFC 8628 device authorization flow (WP03).

A :class:`DeviceFlowState` is created by the headless login flow (WP05) from
the SaaS ``/oauth/device`` response. It is then handed to a
:class:`~specify_cli.auth.device_flow.poller.DeviceFlowPoller`, which mutates
``last_polled_at`` and ``poll_count`` on every poll iteration.

No tokens or secrets are stored here; the SaaS response tokens are returned
directly from :meth:`DeviceFlowPoller.poll` on success.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kernel.clock import datetime, now_utc, timedelta


@dataclass
class DeviceFlowState:
    """In-flight device authorization flow state per RFC 8628.

    Attributes:
        device_code: Opaque SaaS device code used on every token poll.
        user_code: Short human-readable code the user types in the browser.
        verification_uri: Base URL the user should visit to approve.
        verification_uri_complete: Optional convenience URL that embeds
            ``user_code`` as a query parameter (RFC 8628 §3.3.1).
        expires_in: Device code lifetime in seconds (typically 900 = 15 min).
        interval: SaaS-suggested polling interval in seconds. The poller caps
            this at 10 seconds regardless of what SaaS sends (FR-018).
        created_at: UTC timestamp when the flow was initiated.
        expires_at: UTC timestamp after which the device code is invalid.
        last_polled_at: UTC timestamp of the most recent token poll, or
            ``None`` if no poll has happened yet.
        poll_count: Number of token poll attempts made so far.
    """

    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str | None
    expires_in: int
    interval: int
    created_at: datetime
    expires_at: datetime
    last_polled_at: datetime | None = None
    poll_count: int = 0

    @classmethod
    def from_oauth_response(cls, response: dict[str, Any]) -> DeviceFlowState:
        """Build a :class:`DeviceFlowState` from a ``/oauth/device`` response.

        The response is the JSON body returned by the SaaS device
        authorization endpoint. Fields follow RFC 8628 §3.2.

        Args:
            response: Parsed JSON response with ``device_code``,
                ``user_code``, ``verification_uri``, and optional
                ``verification_uri_complete``, ``expires_in``, ``interval``.

        Returns:
            A populated :class:`DeviceFlowState`.
        """
        now = now_utc()
        expires_in = int(response.get("expires_in", 900))
        return cls(
            device_code=response["device_code"],
            user_code=response["user_code"],
            verification_uri=response["verification_uri"],
            verification_uri_complete=response.get("verification_uri_complete"),
            expires_in=expires_in,
            interval=int(response.get("interval", 5)),
            created_at=now,
            expires_at=now + timedelta(seconds=expires_in),
        )

    def is_expired(self) -> bool:
        """Return True when the device code has passed its expiry deadline."""
        return now_utc() >= self.expires_at

    def record_poll(self) -> None:
        """Mark that a poll attempt just happened.

        Updates :attr:`last_polled_at` to now (UTC) and increments
        :attr:`poll_count`. Called by the poller immediately before each
        token request so the count reflects attempts, not successes.
        """
        self.last_polled_at = now_utc()
        self.poll_count += 1
