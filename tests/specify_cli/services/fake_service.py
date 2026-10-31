#!/usr/bin/env python3
"""A stand-in write service written to the launch contract (#6590, WP04 T016).

``kitty-specs/pinned-service-binaries-01M64N66/contracts/launch-contract.md`` is
the contract this script follows, so the real ``command-cli`` binary drops in
where the tests run this file:

* ``serve --git-common-dir <abs> [--idle-timeout <seconds>]``;
* an exclusive OS lock on ``<gcd>/spec-kitty-write-service/service.lock`` for
  the whole life of the process; when the lock is held it exits 0 at once;
* ``endpoint.json`` (ADR 2026-10-27-1 D-2 fields, owner-only) published by
  writing a temporary file and renaming it into place, and deleted at exit only
  while it still names this process's ``instance_id``;
* ``GET /handshake``, ``GET /health`` and ``POST /shutdown``, each behind
  ``Authorization: Bearer <token>`` (401 otherwise).

Standard library only, like a real service binary: it imports nothing from
spec-kitty. Tests run it as ``[sys.executable, fake_service.py, ...]`` so it is
portable to Windows. Behaviour switches for tests come from ``FAKE_SERVICE_MODE``:

``healthy`` (default), ``never_ready`` (health answers 503), ``wrong_repo``,
``wrong_protocol``, ``exit_immediately`` (exit 3 before anything),
``slow_start:<seconds>`` (sleep before publishing), ``ignore_shutdown``
(answer 202 to ``/shutdown`` and keep serving), ``hang`` (accept connections,
never answer).

Not a test module (no ``test_`` prefix), so pytest never collects it.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import http.server
import json
import os
import secrets
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any

ENDPOINT_DIRECTORY = "spec-kitty-write-service"
ENDPOINT_FILE = "endpoint.json"
LOCK_FILE = "service.lock"
MODE_ENV = "FAKE_SERVICE_MODE"
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_EXIT_IMMEDIATELY_CODE = 3


def _mode() -> tuple[str, str]:
    raw = os.environ.get(MODE_ENV, "healthy")
    name, _, argument = raw.partition(":")
    return name, argument


def _instance_id() -> str:
    """A ULID-shaped id: 26 Crockford base-32 characters."""
    return "".join(secrets.choice(_CROCKFORD) for _ in range(26))


def _repository_id(git_common_dir: Path) -> str:
    return hashlib.sha256(git_common_dir.resolve().as_posix().encode("utf-8")).hexdigest()  # noqa: TID251 -- clone identity, not a charter hash


def _take_lock(directory: Path) -> int | None:
    """The locked descriptor of ``service.lock``, or ``None`` when another process holds it."""
    descriptor = os.open(directory / LOCK_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(descriptor)
        return None
    return descriptor


class _State:
    """Everything the request handler reads."""

    def __init__(self, git_common_dir: Path, mode: str) -> None:
        self.git_common_dir = git_common_dir
        self.mode = mode
        self.token = secrets.token_urlsafe(32)
        self.instance_id = _instance_id()
        self.draining = False
        self.last_request = time.monotonic()
        self.stop = threading.Event()

    def handshake(self) -> dict[str, Any]:
        repository = _repository_id(self.git_common_dir)
        if self.mode == "wrong_repo":
            repository = _repository_id(self.git_common_dir / "another-clone")
        versions = [99] if self.mode == "wrong_protocol" else [1]
        return {"protocolVersions": versions, "serviceVersion": "fake", "instanceId": self.instance_id, "repositoryId": repository}

    def health(self) -> tuple[int, dict[str, Any]]:
        if self.mode == "never_ready":
            return 503, {"code": "SERVICE_BUSY", "status": 503, "title": "not ready"}
        return 200, {"status": "draining" if self.draining else "ready", "instanceId": self.instance_id}


def _handler(state: _State) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            """Silent: request lines never reach ``service.log``."""

        def _send(self, status: int, body: dict[str, Any] | None = None) -> None:
            payload = b"" if body is None else json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _authorized(self) -> bool:
            state.last_request = time.monotonic()
            if state.mode == "hang":
                state.stop.wait()  # a hung service: the connection is accepted, no answer ever comes
                return False
            supplied = self.headers.get("Authorization", "")
            if hmac.compare_digest(supplied.encode("utf-8"), f"Bearer {state.token}".encode()):
                return True
            self._send(401, {"code": "WRITE_TOKEN_INVALID", "status": 401, "title": "invalid token"})
            return False

        def do_GET(self) -> None:
            if not self._authorized():
                return
            if self.path == "/handshake":
                self._send(200, state.handshake())
            elif self.path == "/health":
                self._send(*state.health())
            else:
                self._send(404, {"title": "no such route"})

        def do_POST(self) -> None:
            if not self._authorized():
                return
            if self.path != "/shutdown":
                self._send(404, {"title": "no such route"})
                return
            if self.headers.get("Spec-Kitty-Write-Protocol") != "1":
                self._send(400, {"code": "PROTOCOL_VERSION_UNSUPPORTED", "status": 400, "title": "protocol header"})
                return
            self._send(202)
            if state.mode != "ignore_shutdown":
                state.draining = True
                state.stop.set()

    return Handler


def _publish(directory: Path, state: _State, port: int) -> Path:
    endpoint = directory / ENDPOINT_FILE
    temporary = directory / f".endpoint.{os.getpid()}.tmp"
    document = {
        "schema_version": 1,
        "host": "127.0.0.1",
        "port": port,
        "token": state.token,
        "instance_id": state.instance_id,
        "pid": os.getpid(),
        "protocol_versions": [1],
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(document, handle)
    os.replace(temporary, endpoint)
    return endpoint


def _unpublish(endpoint: Path, instance_id: str) -> None:
    """Delete the endpoint file only while it still names this instance."""
    with contextlib.suppress(OSError, ValueError):
        if json.loads(endpoint.read_text(encoding="utf-8")).get("instance_id") == instance_id:
            endpoint.unlink()


def _wait(state: _State, idle_timeout: float | None) -> None:
    while not state.stop.wait(0.05):
        if idle_timeout is not None and time.monotonic() - state.last_request > idle_timeout:
            return


def serve(git_common_dir: Path, idle_timeout: float | None) -> int:
    mode, argument = _mode()
    if mode == "exit_immediately":
        return _EXIT_IMMEDIATELY_CODE
    directory = git_common_dir / ENDPOINT_DIRECTORY
    with contextlib.suppress(FileExistsError):
        directory.mkdir(mode=0o700)
    lock = _take_lock(directory)
    if lock is None:
        print("fake service: the lock is held; another instance serves this clone", flush=True)
        return 0
    state = _State(git_common_dir, mode)
    signal.signal(signal.SIGTERM, lambda *_: state.stop.set())
    if mode == "slow_start":
        time.sleep(float(argument or "1"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _handler(state))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    endpoint = _publish(directory, state, server.server_address[1])
    print(f"fake service {state.instance_id} ready on 127.0.0.1:{server.server_address[1]}", flush=True)
    try:
        _wait(state, idle_timeout)
    finally:
        _unpublish(endpoint, state.instance_id)
        server.shutdown()
        os.close(lock)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fake-write-service")
    commands = parser.add_subparsers(dest="command", required=True)
    serve_parser = commands.add_parser("serve")
    serve_parser.add_argument("--git-common-dir", required=True, type=Path)
    serve_parser.add_argument("--idle-timeout", type=float, default=None)
    args = parser.parse_args(argv)
    if not args.git_common_dir.is_absolute():
        parser.error("--git-common-dir must be absolute")
    return serve(args.git_common_dir, args.idle_timeout)


if __name__ == "__main__":
    sys.exit(main())
