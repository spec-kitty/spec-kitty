"""Shared helpers for dashboard HTTP handlers."""

from __future__ import annotations

import json
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler
from typing import Any

from ..csp import send_csp_header

__all__ = ["DashboardHandler"]


class DashboardHandler(BaseHTTPRequestHandler):
    """Base class that provides shared helpers for router/endpoint handlers."""

    project_dir: str | None = None
    project_token: str | None = None

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - signature from BaseHTTPRequestHandler
        """Suppress default HTTP handler logging noise."""
        del format, args

    def _send_json(self, status_code: int, payload: dict[str, Any]) -> None:
        """Write a JSON response with common headers."""
        self.send_response(status_code)
        send_csp_header(self)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def _handle_shutdown(self) -> None:
        """Validate shutdown tokens and stop the server."""
        expected_token = getattr(self, 'project_token', None)

        token = None
        if self.command == 'POST':
            content_length = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(content_length) if content_length else b''
            if body:
                try:
                    payload = json.loads(body.decode('utf-8'))
                    token = payload.get('token')
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send_json(400, {'error': 'invalid_payload'})
                    return
        else:
            parsed_path = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_path.query)
            token_values = params.get('token')
            if token_values:
                token = token_values[0]

        if expected_token and token != expected_token:
            self._send_json(403, {'error': 'invalid_token'})
            return

        self._send_json(200, {'status': 'stopping'})

        def shutdown_server(server):
            time.sleep(0.05)  # allow response to flush
            server.shutdown()

        threading.Thread(target=shutdown_server, args=(self.server,), daemon=True).start()
