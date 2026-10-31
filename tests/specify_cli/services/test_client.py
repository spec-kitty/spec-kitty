"""``specify_cli.services.client``: the loopback client of the write service (#6590, WP04 T017).

Runs against ``fake_service.py``, the stand-in written to the launch contract,
started directly as a subprocess (no launcher), and against a refusing socket.
Every spawned process is killed at teardown.
"""

from __future__ import annotations

import http.server
import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from specify_cli.services.client import ServiceClient, ServiceUnreachable
from specify_cli.status.write_service_protocol import (
    WriteServiceEndpoint,
    endpoint_file_path,
    read_endpoint_file,
    repository_id,
)

pytestmark = [pytest.mark.integration]

FAKE_SERVICE = Path(__file__).with_name("fake_service.py")
_START_BUDGET_S = 10.0


def _start_fake(git_common_dir: Path, mode: str = "healthy") -> tuple[subprocess.Popen[bytes], WriteServiceEndpoint]:
    env = {**os.environ, "FAKE_SERVICE_MODE": mode}
    argv = [sys.executable, str(FAKE_SERVICE), "serve", "--git-common-dir", str(git_common_dir), "--idle-timeout", "60"]
    process = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + _START_BUDGET_S
    path = endpoint_file_path(git_common_dir)
    while time.monotonic() < deadline:
        if path.exists():
            return process, read_endpoint_file(path)
        time.sleep(0.02)
    process.kill()
    process.wait()
    raise AssertionError("the fake service did not publish its endpoint")


@pytest.fixture
def git_common_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "clone.git"
    directory.mkdir()
    return directory.resolve()


@pytest.fixture
def running(git_common_dir: Path) -> Iterator[tuple[subprocess.Popen[bytes], WriteServiceEndpoint]]:
    process, endpoint = _start_fake(git_common_dir)
    try:
        yield process, endpoint
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


def test_handshake_reports_the_instance_and_the_clone(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint], git_common_dir: Path) -> None:
    _, endpoint = running
    handshake = ServiceClient(endpoint).handshake()
    assert handshake.instance_id == endpoint.instance_id
    assert handshake.repository_id == repository_id(git_common_dir)
    assert handshake.protocol_versions == (1,)


def test_health_is_ready(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint]) -> None:
    _, endpoint = running
    health = ServiceClient(endpoint).health()
    assert (health.status, health.instance_id) == ("ready", endpoint.instance_id)


def test_shutdown_drains_and_the_process_exits(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint], git_common_dir: Path) -> None:
    process, endpoint = running
    ServiceClient(endpoint).shutdown()
    assert process.wait(timeout=10) == 0
    assert not endpoint_file_path(git_common_dir).exists()


def test_a_wrong_token_is_unreachable_and_the_message_carries_no_token(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint]) -> None:
    _, endpoint = running
    wrong = replace(endpoint, token="x" * 43)
    with pytest.raises(ServiceUnreachable) as excinfo:
        ServiceClient(wrong).health()
    assert "401" in str(excinfo.value)
    assert wrong.token not in str(excinfo.value)
    assert endpoint.token not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_a_non_2xx_answer_is_unreachable(git_common_dir: Path) -> None:
    process, endpoint = _start_fake(git_common_dir, mode="never_ready")
    try:
        with pytest.raises(ServiceUnreachable, match="503"):
            ServiceClient(endpoint).health()
    finally:
        process.kill()
        process.wait(timeout=10)


class _GarbageHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        """Silent."""

    def do_GET(self) -> None:
        body = b"not json" if self.path == "/handshake" else b'{"status": "sleeping", "instanceId": "x"}'
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.mark.parametrize("call", ["handshake", "health"])
def test_a_body_outside_the_contract_is_unreachable(call: str) -> None:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _GarbageHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = WriteServiceEndpoint("127.0.0.1", server.server_address[1], "t" * 43, "01INSTANCE", 1, (1,), "2026-10-30T00:00:00Z")
        with pytest.raises(ServiceUnreachable, match="contract"):
            getattr(ServiceClient(endpoint), call)()
    finally:
        server.shutdown()
        server.server_close()


def _closed_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def test_a_refused_connection_is_unreachable() -> None:
    endpoint = WriteServiceEndpoint("127.0.0.1", _closed_port(), "t" * 43, "01INSTANCE", 1, (1,), "2026-10-30T00:00:00Z")
    with pytest.raises(ServiceUnreachable) as excinfo:
        ServiceClient(endpoint, timeout=1.0).handshake()
    assert endpoint.token not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


def test_shutdown_negotiates_once_and_sends_the_protocol_header(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint]) -> None:
    """The fake answers 400 without ``Spec-Kitty-Write-Protocol: 1``; a negotiated client passes."""
    process, endpoint = running
    client = ServiceClient(endpoint)
    client.handshake()
    client.shutdown()
    assert process.wait(timeout=10) == 0


@pytest.mark.windows_ci
def test_windows_client_smoke(running: tuple[subprocess.Popen[bytes], WriteServiceEndpoint], git_common_dir: Path) -> None:
    """The one ``windows_ci`` test of this file (the marker is auto-skipped elsewhere): the three calls, natively."""
    process, endpoint = running
    client = ServiceClient(endpoint)
    assert client.handshake().repository_id == repository_id(git_common_dir)
    assert client.health().status == "ready"
    client.shutdown()
    assert process.wait(timeout=10) == 0
