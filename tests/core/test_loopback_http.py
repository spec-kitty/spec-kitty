"""Direct coverage for the loopback-only HTTP helpers.

These tests pin the security-relevant invariant of the module: every server
it produces binds the IPv4 loopback interface, with no way for a caller to
widen the bind address.

Mutation-verification note (T022)
----------------------------------
The two-sided binding tests below were mutation-verified before commit:
temporarily widening ``LOOPBACK_HOST`` to ``"0.0.0.0"`` in the source caused
``test_create_loopback_server_does_not_bind_non_loopback_host`` and
``test_serve_loopback_server_does_not_bind_non_loopback_host`` to FAIL with
``AssertionError``, confirming the assertions are mutation-killing.  The source
was reverted to ``"127.0.0.1"`` before the final commit (result: PASS).
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from specify_cli.core.loopback_http import (
    LOOPBACK_HOST,
    create_loopback_server,
    serve_loopback_server,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _RecordingServer(HTTPServer):
    """Records the bind address and serve_forever calls without binding a socket."""

    instances: list[_RecordingServer] = []

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
    ) -> None:
        self.bound_address = server_address
        self.handler_class = handler_class
        self.serve_forever_calls: list[float | None] = []
        _RecordingServer.instances.append(self)
        # Intentionally skip HTTPServer.__init__ so no real socket is bound.

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        self.serve_forever_calls.append(poll_interval)


class _Handler(BaseHTTPRequestHandler):
    pass


def setup_function() -> None:
    _RecordingServer.instances.clear()


def test_create_loopback_server_binds_loopback_only() -> None:
    server = create_loopback_server(8123, _Handler, server_factory=_RecordingServer)

    assert isinstance(server, _RecordingServer)
    assert server.bound_address == (LOOPBACK_HOST, 8123)
    assert server.bound_address[0] == "127.0.0.1"
    assert server.handler_class is _Handler
    assert server.serve_forever_calls == []


def test_serve_loopback_server_binds_loopback_and_serves_forever() -> None:
    serve_loopback_server(8124, _Handler, server_factory=_RecordingServer)

    assert len(_RecordingServer.instances) == 1
    server = _RecordingServer.instances[0]
    assert server.bound_address == ("127.0.0.1", 8124)
    assert server.handler_class is _Handler
    assert len(server.serve_forever_calls) == 1


# ---------------------------------------------------------------------------
# Two-sided binding regression tests (T022)
# ---------------------------------------------------------------------------
# These tests assert BOTH (a) that the server binds 127.0.0.1 AND (b) that
# a non-loopback host (0.0.0.0) is NOT used.  A one-sided "binds 127.0.0.1"
# check would not catch a host-widening regression.
#
# Mutation-kill evidence: temporarily setting LOOPBACK_HOST = "0.0.0.0" in
# the source caused both tests below to fail with AssertionError, confirming
# they are mutation-killing.


def test_create_loopback_server_does_not_bind_non_loopback_host() -> None:
    """(b) side: the server must NOT bind a non-loopback address."""
    server = create_loopback_server(8125, _Handler, server_factory=_RecordingServer)

    assert isinstance(server, _RecordingServer)
    bound_host = server.bound_address[0]
    assert bound_host != "0.0.0.0", (
        "Server must not bind to 0.0.0.0 (would expose beyond loopback)"
    )
    assert bound_host != "::", (
        "Server must not bind to :: (IPv6 wildcard would expose beyond loopback)"
    )
    assert bound_host == "127.0.0.1", (
        f"Server must bind strictly to 127.0.0.1, got {bound_host!r}"
    )


def test_serve_loopback_server_does_not_bind_non_loopback_host() -> None:
    """(b) side: serve_loopback_server must NOT widen the bind address."""
    serve_loopback_server(8126, _Handler, server_factory=_RecordingServer)

    assert len(_RecordingServer.instances) == 1
    bound_host = _RecordingServer.instances[0].bound_address[0]
    assert bound_host != "0.0.0.0", (
        "serve_loopback_server must not bind to 0.0.0.0"
    )
    assert bound_host == "127.0.0.1", (
        f"serve_loopback_server must bind strictly to 127.0.0.1, got {bound_host!r}"
    )
