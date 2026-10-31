"""The launcher's loopback client of the write service: handshake, health and shutdown (#6590, WP04 T017).

The transport is plain HTTP to ``127.0.0.1``, on purpose: the endpoint file
only ever names the loopback host (``read_endpoint_file`` refuses anything
else) and the bearer token in that owner-only file is the credential, so TLS
would add nothing (ADR 2026-10-27-1; CLAUDE.md, loopback HTTP). The standard
library's ``http.client`` is used instead of httpx so the warm path (NFR-001)
pays no third-party import cost.

The request and response shapes are the protocol module's
(``specify_cli.status.write_service_protocol``); nothing is redefined here.
``/handshake`` and ``/health`` carry the bearer token only; ``/shutdown`` also
carries the negotiated major in ``Spec-Kitty-Write-Protocol`` (ADR 2026-10-27-1
D-4).

Every failure -- a refused connection, a timeout, a non-2xx answer, a body
outside the contract -- is a :class:`ServiceUnreachable` whose message names the
operation and the cause but never the token, and which chains no exception.
"""

from __future__ import annotations

import http.client
import json
from collections.abc import Mapping
from typing import Any

from specify_cli.status import (
    WRITE_PROTOCOL_HEADER,
    Handshake,
    Health,
    ProtocolShapeError,
    WriteServiceEndpoint,
    negotiate_protocol_version,
)

__all__ = ["ServiceClient", "ServiceUnreachable"]

DEFAULT_TIMEOUT_S = 2.0
_MAX_BODY_BYTES = 64 * 1024
_GET = "GET"
_POST = "POST"


class ServiceUnreachable(Exception):
    """The service did not answer as the contract says (internal to the launcher; never carries the token)."""


def _decode(body: bytes, what: str) -> Mapping[str, Any]:
    try:
        document: Any = json.loads(body.decode("utf-8"))
    except (ValueError, RecursionError):
        document = None
    if not isinstance(document, Mapping):
        raise ServiceUnreachable(f"{what} answered with a body outside the contract (not a JSON object)")
    return document


class ServiceClient:
    """One running service, reached through the endpoint its file names."""

    def __init__(self, endpoint: WriteServiceEndpoint, *, timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._protocol_version: int | None = None

    def _request(self, method: str, path: str, headers: Mapping[str, str] | None = None) -> tuple[int, bytes]:
        what = f"{method} {path}"
        connection = http.client.HTTPConnection(self._endpoint.host, self._endpoint.port, timeout=self._timeout)
        sent = {"Authorization": f"Bearer {self._endpoint.token}", **(headers or {})}
        failure: str | None = None
        status, body = 0, b""
        try:
            connection.request(method, path, headers=sent)
            response = connection.getresponse()
            status, body = response.status, response.read(_MAX_BODY_BYTES + 1)
        except (OSError, http.client.HTTPException) as exc:
            failure = type(exc).__name__
        finally:
            connection.close()
        # Raised outside the handler, so no exception (and no request state) is chained.
        if failure is not None:
            raise ServiceUnreachable(f"{what} failed ({failure})")
        if not 200 <= status < 300:
            raise ServiceUnreachable(f"{what} answered {status}")
        if len(body) > _MAX_BODY_BYTES:
            raise ServiceUnreachable(f"{what} answered with a body outside the contract (too large)")
        return status, body

    def _get(self, path: str) -> Mapping[str, Any]:
        _, body = self._request(_GET, path)
        return _decode(body, f"{_GET} {path}")

    def handshake(self) -> Handshake:
        """``GET /handshake``; it also remembers the negotiated major when one exists."""
        wire = self._get("/handshake")
        try:
            handshake = Handshake.from_wire(wire)
        except ProtocolShapeError:
            raise ServiceUnreachable("GET /handshake answered with a body outside the contract") from None
        try:
            self._protocol_version = negotiate_protocol_version(handshake.protocol_versions)
        except ProtocolShapeError:
            self._protocol_version = None
        return handshake

    def health(self) -> Health:
        """``GET /health``."""
        wire = self._get("/health")
        try:
            return Health.from_wire(wire)
        except ProtocolShapeError:
            raise ServiceUnreachable("GET /health answered with a body outside the contract") from None

    def shutdown(self) -> None:
        """``POST /shutdown`` with the negotiated major (a handshake first when none is known yet)."""
        if self._protocol_version is None:
            handshake = self.handshake()
            if self._protocol_version is None:
                raise ServiceUnreachable(f"no common protocol version with the service (it speaks {list(handshake.protocol_versions)})")
        self._request(_POST, "/shutdown", {WRITE_PROTOCOL_HEADER: str(self._protocol_version)})
