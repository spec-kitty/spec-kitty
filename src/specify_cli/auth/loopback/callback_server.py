"""Localhost HTTP server for receiving OAuth Authorization Code callbacks.

The SaaS redirects the browser back to ``http://127.0.0.1:<PORT>/callback``
after the user consents. This module implements a tiny HTTP server that:

- binds to ``127.0.0.1`` only (never externally reachable)
- searches ports 28888..28898 first so firewall allowlists are small
- falls back to an OS-assigned port if all the preferred ports are taken
- serves the ``/callback`` endpoint in a daemon thread
- exposes an ``async wait_for_callback()`` that the main login loop awaits
- times out after 5 minutes with :class:`CallbackTimeoutError`

The server deliberately uses HTTP on loopback because OAuth native-app
callbacks cannot terminate TLS on a local ephemeral port. Binding is
restricted to ``127.0.0.1`` only, matching RFC 8252 loopback guidance.
The stdlib ``http.server.BaseHTTPRequestHandler`` is plenty for a single
callback.
"""

from __future__ import annotations

import asyncio
import socket
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Event, Thread
from urllib.parse import parse_qs, urlparse

from ..errors import CallbackTimeoutError

_PORT_RANGE = range(28888, 28899)  # 28888..28898 inclusive
_HOST = "127.0.0.1"
_DEFAULT_TIMEOUT = 300.0  # 5 minutes
_LATE_CALLBACK_SECONDS = 300.0  # keep the listener available for late redirects
_POLL_INTERVAL = 0.1  # seconds between async polls


_SUCCESS_HTML = (
    b"<!DOCTYPE html>"
    b"<html lang='en'><head><meta charset='utf-8'>"
    b"<title>Authentication complete</title>"
    b"<style>body{font-family:system-ui,sans-serif;margin:4rem auto;"
    b"max-width:32rem;text-align:center;color:#222}h1{color:#2e7d32}</style>"
    b"</head><body>"
    b"<h1>Authentication complete</h1>"
    b"<p>You can close this tab and return to your terminal.</p>"
    b"</body></html>"
)

_NOT_FOUND_HTML = b"<html><body><h1>404 Not Found</h1></body></html>"
_TIMEOUT_HTML = (
    b"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
    b"<title>Authentication timed out</title></head><body>"
    b"<h1>Authentication timed out</h1>"
    b"<p>The 5-minute approval window has closed. This approval was not accepted.</p>"
    b"<p>Run <code>spec-kitty auth login</code> again in your terminal. "
    b"If you need more time, use <code>spec-kitty auth login --headless</code>.</p>"
    b"</body></html>"
)


class _CallbackHTTPHandler(BaseHTTPRequestHandler):
    """Handler that records ``/callback`` query parameters on the server instance."""

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        parsed = urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_NOT_FOUND_HTML)))
            self.end_headers()
            self.wfile.write(_NOT_FOUND_HTML)
            return

        deadline = getattr(self.server, "callback_deadline", None)
        if deadline is not None and time.monotonic() >= deadline:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_TIMEOUT_HTML)))
            self.end_headers()
            self.wfile.write(_TIMEOUT_HTML)
            self.server.late_callback_received.set()  # type: ignore[attr-defined]
            return

        # parse_qs returns list values; we only care about the first occurrence.
        params = {k: v[0] for k, v in parse_qs(parsed.query).items() if v}

        # Record on the server instance; first-writer-wins so a browser refresh
        # after success cannot clobber the accepted params.
        if getattr(self.server, "callback_params", None) is None:
            self.server.callback_params = params  # type: ignore[attr-defined]

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_SUCCESS_HTML)))
        self.end_headers()
        self.wfile.write(_SUCCESS_HTML)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        # Silence BaseHTTPRequestHandler's default stderr access logging.
        # We don't want auth callback URLs (which contain `code` and `state`)
        # landing in the user's terminal or any log file.
        # (The `format`/`args` parameter names are fixed by the stdlib
        # BaseHTTPRequestHandler base class signature; we must accept them.)
        return


class CallbackServer:
    """Localhost HTTP server that captures a single OAuth callback.

    Typical usage::

        server = CallbackServer()
        callback_url = server.start()
        # ... redirect the browser to the authorize endpoint with this URL ...
        params = await server.wait_for_callback()
        server.stop()

    The server runs in a daemon thread so the main async loop remains free
    to poll via :meth:`wait_for_callback`. ``stop()`` is idempotent.
    """

    def __init__(
        self,
        timeout_seconds: float = _DEFAULT_TIMEOUT,
        late_callback_seconds: float = _LATE_CALLBACK_SECONDS,
    ) -> None:
        self._timeout = timeout_seconds
        self._late_callback_seconds = late_callback_seconds
        self._server: HTTPServer | None = None
        self._thread: Thread | None = None
        self._port: int | None = None

    @property
    def port(self) -> int:
        """The port the server is bound to. Raises if not started."""
        if self._port is None:
            raise RuntimeError("CallbackServer is not started")
        return self._port

    @property
    def callback_url(self) -> str:
        """The full ``http://127.0.0.1:<port>/callback`` URL."""
        return f"http://{_HOST}:{self.port}/callback"  # NOSONAR -- OAuth loopback redirect URI is localhost-only by design

    def start(self) -> str:
        """Start the HTTP server on an available port.

        Returns:
            The full callback URL (``http://127.0.0.1:<port>/callback``).
        """
        self._port = self._find_port()
        self._server = HTTPServer((_HOST, self._port), _CallbackHTTPHandler)  # NOSONAR -- binds to 127.0.0.1 only for OAuth loopback callback
        self._server.callback_params = None  # type: ignore[attr-defined]
        self._server.callback_deadline = None  # type: ignore[attr-defined]
        self._server.late_callback_received = Event()  # type: ignore[attr-defined]
        self._thread = Thread(
            target=self._server.serve_forever,
            name="spec-kitty-callback-server",
            daemon=True,
        )
        self._thread.start()
        return self.callback_url

    def stop(self) -> None:
        """Shut down the HTTP server and join its thread. Idempotent."""
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    async def wait_for_callback(self) -> dict[str, str]:
        """Async-wait for the callback parameters to arrive.

        Polls the server's recorded ``callback_params`` every
        ``_POLL_INTERVAL`` seconds until either parameters are set or the
        timeout elapses.

        Returns:
            The callback query parameters as a flat ``dict[str, str]``.

        Raises:
            CallbackTimeoutError: if no callback arrives within the timeout.
            RuntimeError: if :meth:`start` was not called first.
        """
        if self._server is None:
            raise RuntimeError("CallbackServer is not started")

        deadline = time.monotonic() + self._timeout
        self._server.callback_deadline = deadline  # type: ignore[attr-defined]
        while time.monotonic() < deadline:
            params = getattr(self._server, "callback_params", None)
            if params is not None:
                return dict(params)
            await asyncio.sleep(_POLL_INTERVAL)

        # A callback accepted just before the deadline may land between polls.
        params = getattr(self._server, "callback_params", None)
        if params is not None:
            return dict(params)

        # A late redirect still needs an HTTP response. Keep the listener bound
        # for a bounded grace period, but never pass its code to the caller.
        await asyncio.to_thread(self._server.late_callback_received.wait, self._late_callback_seconds)  # type: ignore[attr-defined]

        raise CallbackTimeoutError(
            f"Callback timed out after {self._timeout} seconds. "
            "Run `spec-kitty auth login` again."
        )

    def _find_port(self) -> int:
        """Find an available port; try the preferred range first, then OS."""
        for port in _PORT_RANGE:
            if self._is_port_free(port):
                return port
        # Fallback: ask the kernel for any free ephemeral port.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((_HOST, 0))
            return int(s.getsockname()[1])

    @staticmethod
    def _is_port_free(port: int) -> bool:
        """Return True iff we can bind ``127.0.0.1:port`` right now."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            try:
                s.bind((_HOST, port))
                return True
            except OSError:
                return False
