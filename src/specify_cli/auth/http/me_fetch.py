"""Sync GET /api/v1/me — used by TokenManager.rehydrate_membership_if_needed.

Intentionally tiny: no state mutation, no caching, no logging. Sync so it can be
called from sync direct-ingress paths (batch.py, queue.py, emitter.py) without
event-loop bridging. See contracts/api.md §2.

Note: this helper deliberately does NOT use ``OAuthHttpClient`` because that
client routes through ``TokenManager.get_access_token`` and would re-enter the
manager during rehydrate, creating a deadlock on the membership lock.
"""

from __future__ import annotations

from typing import Any

from ..server_target import _normalize_url
from .transport import request_with_fallback_sync


def fetch_me_payload(saas_base_url: str, access_token: str) -> dict[str, Any]:
    """GET ``<saas_base_url>/api/v1/me`` with ``Authorization: Bearer <access_token>``.

    Issues exactly one HTTP GET. No retries inside this function (the underlying
    ``request_with_fallback_sync`` handles transport-layer fallback once).

    Raises ``httpx.HTTPStatusError`` on non-2xx (caller decides how to handle).
    Returns the parsed JSON dict. Caller is responsible for extracting ``teams[]``.

    Uses the canonical :func:`specify_cli.auth.server_target._normalize_url`
    (strip + drop one trailing slash) rather than a strip-less ``rstrip("/")``,
    so the URL actually requested here is byte-identical to the one the
    issuer/target guard compared *saas_base_url* against (NFR-002,
    ``contracts/issuer-target-helper.md``).
    """
    url = _normalize_url(saas_base_url) + "/api/v1/me"
    response = request_with_fallback_sync(
        method="GET",
        url=url,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload
