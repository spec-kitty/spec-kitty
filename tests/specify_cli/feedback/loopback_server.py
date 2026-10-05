"""Loopback HTTP fixture for Feedback Submission delivery tests.

Starts an ``http.server`` on ``127.0.0.1:<ephemeral>`` in a daemon thread.
Modes:

* ``ok`` — record JSON body + headers, respond 204
* ``hang`` — sleep longer than the client's 5 s timeout before responding
* ``error`` — respond 500 with an empty body
* ``closed`` — bind nothing; expose a free port that refuses connections

Never talks to a non-loopback address.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Literal

__all__ = [
    "LoopbackServer",
    "closed_port",
    "loopback_server",
]

ServerMode = Literal["ok", "hang", "error"]

_HANG_SECONDS = 30.0
_DEFAULT_WAIT_TIMEOUT = 5.0


class LoopbackServer:
    """Thread-backed loopback HTTP server that records POSTs."""

    def __init__(self, mode: ServerMode = "ok") -> None:
        self.mode: ServerMode = mode
        self.received: list[tuple[dict[str, Any], dict[str, str]]] = []
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def url(self) -> str:
        if self._httpd is None:
            raise RuntimeError("server has not started")
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}/feedback"

    def start(self) -> None:
        owner = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 — http.server API
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b""
                headers = dict(self.headers.items())
                try:
                    body: dict[str, Any] = json.loads(raw.decode("utf-8")) if raw else {}
                except (UnicodeDecodeError, json.JSONDecodeError):
                    body = {"_unparseable": True}

                with owner._lock:
                    owner.received.append((body, headers))

                if owner.mode == "hang":
                    # Sleep until stopped or the hang budget elapses so teardown
                    # can unblock children stuck in their 5 s client timeout.
                    deadline = time.monotonic() + _HANG_SECONDS
                    while not owner._stop.is_set() and time.monotonic() < deadline:
                        time.sleep(0.05)
                    if owner._stop.is_set():
                        return
                if owner.mode == "error":
                    self.send_response(500)
                    self.end_headers()
                    return
                self.send_response(204)
                self.end_headers()

            def log_message(self, format: str, *args: object) -> None:  # noqa: A003
                return

        # Bind an ephemeral port on loopback only.
        httpd = HTTPServer(("127.0.0.1", 0), _Handler)
        httpd.timeout = 0.5
        self._httpd = httpd

        def _serve() -> None:
            self._ready.set()
            while not self._stop.is_set():
                httpd.handle_request()

        thread = threading.Thread(target=_serve, name="feedback-loopback", daemon=True)
        self._thread = thread
        thread.start()
        if not self._ready.wait(timeout=2.0):
            raise RuntimeError("loopback server failed to start")

    def wait_for(self, n: int, timeout: float = _DEFAULT_WAIT_TIMEOUT) -> bool:
        """Block until at least *n* requests arrive, or *timeout* elapses."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if len(self.received) >= n:
                    return True
            time.sleep(0.05)
        with self._lock:
            return len(self.received) >= n

    def stop(self) -> None:
        self._stop.set()
        httpd = self._httpd
        if httpd is not None:
            # One self-connect wakes handle_request so the thread can exit.
            try:
                host, port = httpd.server_address[:2]
                with socket.create_connection((host, port), timeout=0.2):
                    pass
            except OSError:
                pass
            httpd.server_close()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._httpd = None
        self._thread = None


@contextmanager
def loopback_server(mode: ServerMode = "ok") -> Iterator[LoopbackServer]:
    """Context manager that starts and tears down a :class:`LoopbackServer`."""
    server = LoopbackServer(mode=mode)
    server.start()
    try:
        yield server
    finally:
        server.stop()


@contextmanager
def closed_port() -> Iterator[str]:
    """Yield an ``http://127.0.0.1:<port>/feedback`` URL that refuses connections."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()
    yield f"http://{host}:{port}/feedback"
