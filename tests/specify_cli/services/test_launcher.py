"""``specify_cli.services.launcher``: start, reuse, health, stale recovery and stop (#6590, WP04 T021).

Acceptance coverage for spec User Story 1 (FR-006..FR-009, NFR-001, NFR-002,
NFR-005) against ``fake_service.py``, the stand-in written to the launch
contract. ``resolve`` is injected: it returns a pinned :class:`ResolvedBinary`
whose ``argv_prefix`` is ``(sys.executable, fake_service.py)`` and whose digest
is that script's, so the launcher's own ``verify_before_exec`` still runs before
every spawn. The spawn seam wraps the real detached spawn and records every
process; a fixture kills each one at teardown, so no test leaks a service.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import select
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import IO

import psutil
from unittest import mock

import pytest

from kernel.git_topology import git_common_dir
from kernel.service_artifacts import sha256_file
from specify_cli.services import launcher as launcher_module
from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode
from specify_cli.services.launcher import (
    SERVICE_LOG,
    START_TIMEOUT_ENV,
    ServiceLauncher,
    StopOutcome,
    start_timeout_from_env,
)
from specify_cli.services.policies import CHARTER_SERVICE, READ_SERVICE, WRITE_SERVICE, policy_for
from specify_cli.services.resolution import ResolvedBinary
from specify_cli.status.write_service_protocol import (
    ENDPOINT_DIRECTORY,
    EndpointFileError,
    EndpointRefusalCode,
    WriteServiceEndpoint,
    endpoint_file_path,
    read_endpoint_file,
)

pytestmark = [pytest.mark.integration]

FAKE_SERVICE = Path(__file__).with_name("fake_service.py")
_MODE_ENV = "FAKE_SERVICE_MODE"
_TEST_START_TIMEOUT_S = 10.0
_TEST_IDLE_TIMEOUT_S = 120
_POSIX_ONLY = pytest.mark.skipif(sys.platform == "win32", reason="POSIX mode bits; Windows relies on the service's owner-only ACL")


def _alive(process: subprocess.Popen[bytes]) -> bool:
    return process.poll() is None


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    return root


@pytest.fixture
def gcd(repo: Path) -> Path:
    return git_common_dir(repo)


@pytest.fixture
def resolved() -> ResolvedBinary:
    return ResolvedBinary(
        argv_prefix=(sys.executable, str(FAKE_SERVICE)),
        path=FAKE_SERVICE,
        source="cache",
        sha256=sha256_file(FAKE_SERVICE),
        pinned=True,
    )


@pytest.fixture
def spawned() -> Iterator[list[subprocess.Popen[bytes]]]:
    """Every process the launcher spawned; each is killed and reaped at teardown."""
    processes: list[subprocess.Popen[bytes]] = []
    yield processes
    for process in processes:
        if _alive(process):
            process.kill()
        process.wait(timeout=10)


@pytest.fixture
def warnings_seen() -> list[str]:
    return []


@pytest.fixture
def make_launcher(resolved: ResolvedBinary, spawned: list[subprocess.Popen[bytes]], warnings_seen: list[str]) -> Callable[..., ServiceLauncher]:
    def recording_spawn(argv: Sequence[str], log: IO[bytes]) -> subprocess.Popen[bytes]:
        process: subprocess.Popen[bytes] = launcher_module.spawn_detached(argv, log)
        spawned.append(process)
        return process

    def factory(
        binary: ResolvedBinary | None = None,
        *,
        start_timeout: float = _TEST_START_TIMEOUT_S,
        stop_timeout: float = 10.0,
        idle_timeout: int | None = _TEST_IDLE_TIMEOUT_S,
        client_timeout: float = 2.0,
    ) -> ServiceLauncher:
        chosen = resolved if binary is None else binary
        return ServiceLauncher(
            resolve=lambda service: chosen,
            spawn=recording_spawn,
            start_timeout=start_timeout,
            stop_timeout=stop_timeout,
            idle_timeout=idle_timeout,
            client_timeout=client_timeout,
            warn=warnings_seen.append,
        )

    return factory


def _start_direct(git_common: Path, spawned: list[subprocess.Popen[bytes]], mode: str) -> tuple[subprocess.Popen[bytes], WriteServiceEndpoint]:
    """Start the fake for *git_common* without the launcher (tracked in *spawned*) and read what it published."""
    argv = [sys.executable, str(FAKE_SERVICE), *WRITE_SERVICE.start_args(git_common), "--idle-timeout", "60"]
    with mock.patch.dict(os.environ, {_MODE_ENV: mode}), open(os.devnull, "wb") as sink:
        process: subprocess.Popen[bytes] = launcher_module.spawn_detached(argv, sink)
    spawned.append(process)
    path = endpoint_file_path(git_common)
    assert _wait_until(path.exists)
    return process, read_endpoint_file(path)


def _wait_until(predicate: Callable[[], bool], budget: float = 10.0) -> bool:
    deadline = time.monotonic() + budget
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


# -- US1-1 / US1-2: start, then reuse ------------------------------------------------------------


def test_an_empty_state_starts_a_healthy_service_and_writes_the_log(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    endpoint = make_launcher().ensure("write-service", repo)

    assert endpoint.host == "127.0.0.1"
    assert len(spawned) == 1 and _alive(spawned[0])
    assert endpoint.pid == spawned[0].pid
    log = (gcd / ENDPOINT_DIRECTORY / SERVICE_LOG).read_text(encoding="utf-8")
    assert "starting write-service" in log
    assert resolved_digest_prefix() in log
    assert "pinned" in log


def resolved_digest_prefix() -> str:
    return sha256_file(FAKE_SERVICE)[:12]


@_POSIX_ONLY
def test_the_directory_the_launcher_creates_is_owner_only(make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path) -> None:
    make_launcher().ensure("write-service", repo)
    directory = gcd / ENDPOINT_DIRECTORY
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((directory / SERVICE_LOG).stat().st_mode) == 0o600


@_POSIX_ONLY
def test_an_existing_directory_is_never_chmodded(make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path) -> None:
    directory = gcd / ENDPOINT_DIRECTORY
    directory.mkdir(mode=0o700)
    directory.chmod(0o750)
    with pytest.raises(EndpointFileError):  # the service publishes into a group-readable directory: refused, never repaired
        make_launcher(start_timeout=2.0).ensure("write-service", repo)
    assert stat.S_IMODE(directory.stat().st_mode) == 0o750


def test_a_second_ensure_reuses_the_running_instance(make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]]) -> None:
    launcher = make_launcher()
    first = launcher.ensure("write-service", repo)
    second = make_launcher().ensure("write-service", repo)

    assert second.instance_id == first.instance_id
    assert len(spawned) == 1


def test_two_concurrent_starters_share_one_instance(make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]]) -> None:
    results: list[WriteServiceEndpoint] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def run() -> None:
        barrier.wait()
        try:
            results.append(make_launcher().ensure("write-service", repo))
        except BaseException as exc:  # collected and asserted below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert len({endpoint.instance_id for endpoint in results}) == 1
    assert _wait_until(lambda: sum(_alive(process) for process in spawned) == 1)


# -- FR-008: stale recovery ----------------------------------------------------------------------


def test_a_killed_service_is_replaced_by_a_fresh_instance(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    first = make_launcher().ensure("write-service", repo)
    spawned[0].kill()
    spawned[0].wait(timeout=10)

    second = make_launcher().ensure("write-service", repo)

    assert second.instance_id != first.instance_id
    assert len(spawned) == 2 and _alive(spawned[1])


# -- NFR-002: unhealthy, and refusals during start -----------------------------------------------


def test_a_service_that_never_gets_ready_is_stopped_and_refused(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_MODE_ENV, "never_ready")
    started = time.monotonic()
    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher(start_timeout=1.0).ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.UNHEALTHY
    assert SERVICE_LOG in excinfo.value.remedy
    assert time.monotonic() - started < 8.0
    assert len(spawned) == 1 and not _alive(spawned[0])


def test_a_service_that_exits_with_an_error_is_refused_without_waiting_out_the_budget(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_MODE_ENV, "exit_immediately")
    started = time.monotonic()
    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher(start_timeout=30.0).ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.UNHEALTHY
    assert "exit" in excinfo.value.message
    assert time.monotonic() - started < 10.0


@pytest.mark.parametrize("mode", ["wrong_repo", "wrong_protocol"])
def test_a_mismatched_service_is_refused_and_stopped(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv(_MODE_ENV, mode)
    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher().ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.VERSION_MISMATCH
    assert _wait_until(lambda: not _alive(spawned[0]))


def test_a_running_service_for_another_clone_is_refused_on_reuse(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_MODE_ENV, "wrong_repo")
    argv = [sys.executable, str(FAKE_SERVICE), *WRITE_SERVICE.start_args(gcd), "--idle-timeout", "60"]
    with open(os.devnull, "wb") as sink:
        spawned.append(launcher_module.spawn_detached(argv, sink))
    assert _wait_until(endpoint_file_path(gcd).exists)

    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher().ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.VERSION_MISMATCH
    assert "another clone" in excinfo.value.message
    assert len(spawned) == 1  # the reuse path refused; nothing new was started


@_POSIX_ONLY
def test_a_world_readable_endpoint_is_refused_and_never_connected_to(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        directory = gcd / ENDPOINT_DIRECTORY
        directory.mkdir(mode=0o700)
        planted = {
            "schema_version": 1,
            "host": "127.0.0.1",
            "port": listener.getsockname()[1],
            "token": "p" * 43,
            "instance_id": "01PLANTED",
            "pid": os.getpid(),
            "protocol_versions": [1],
            "started_at": "2026-10-30T00:00:00Z",
        }
        path = endpoint_file_path(gcd)
        path.write_text(json.dumps(planted), encoding="utf-8")
        path.chmod(0o644)

        with pytest.raises(EndpointFileError) as excinfo:
            make_launcher().ensure("write-service", repo)

        assert excinfo.value.error_code == "WRITE_SERVICE_ENDPOINT_EXPOSED"
        assert spawned == []
        readable, _, _ = select.select([listener], [], [], 0.2)
        assert readable == []  # no connection attempt reached the planted port
    finally:
        listener.close()


def test_bytes_changed_after_resolve_are_never_spawned(
    make_launcher: Callable[..., ServiceLauncher], resolved: ResolvedBinary, repo: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    tampered = dataclasses.replace(resolved, sha256="0" * 64)
    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher(binary=tampered).ensure("write-service", repo)
    assert excinfo.value.code is ServiceRefusalCode.DIGEST_MISMATCH
    assert spawned == []


def test_an_unpinned_binary_warns_on_every_start(
    make_launcher: Callable[..., ServiceLauncher], resolved: ResolvedBinary, repo: Path, warnings_seen: list[str]
) -> None:
    unpinned = dataclasses.replace(resolved, pinned=False, source="unpinned", warning="Running an UNPINNED write-service binary")
    make_launcher(binary=unpinned).ensure("write-service", repo)
    assert warnings_seen == ["Running an UNPINNED write-service binary"]


# -- FR-009: stop --------------------------------------------------------------------------------


def test_stop_drains_the_service_and_a_later_ensure_starts_anew(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    first = make_launcher().ensure("write-service", repo)

    assert make_launcher().stop("write-service", repo) is StopOutcome.STOPPED
    assert not endpoint_file_path(gcd).exists()
    assert _wait_until(lambda: not _alive(spawned[0]))

    second = make_launcher().ensure("write-service", repo)
    assert second.instance_id != first.instance_id


def test_stop_with_nothing_running_is_not_running(make_launcher: Callable[..., ServiceLauncher], repo: Path) -> None:
    assert make_launcher().stop("write-service", repo) is StopOutcome.NOT_RUNNING


def test_stop_never_signals_the_pid_of_a_stale_endpoint(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    make_launcher().ensure("write-service", repo)
    spawned[0].kill()
    spawned[0].wait(timeout=10)
    signalled: list[int] = []
    monkeypatch.setattr(launcher_module, "terminate_pid", signalled.append)

    assert make_launcher().stop("write-service", repo) is StopOutcome.NOT_RUNNING
    assert signalled == []


def test_stop_forces_a_service_that_ignores_shutdown(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(_MODE_ENV, "ignore_shutdown")
    make_launcher().ensure("write-service", repo)

    assert make_launcher(stop_timeout=1.0).stop("write-service", repo) is StopOutcome.FORCED
    assert _wait_until(lambda: not _alive(spawned[0]))


# -- the token never leaks -----------------------------------------------------------------------


def test_no_token_reaches_logs_or_output(
    make_launcher: Callable[..., ServiceLauncher],
    repo: Path,
    gcd: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    warnings_seen: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    caplog.set_level(logging.DEBUG)
    launcher = make_launcher()
    endpoint = launcher.ensure("write-service", repo)
    launcher.ensure("write-service", repo)
    launcher.stop("write-service", repo)
    monkeypatch.setenv(_MODE_ENV, "never_ready")
    never_ready_tokens: list[str] = []
    real_discard = launcher_module._discard

    def discard_recording_the_token(process: subprocess.Popen[bytes]) -> None:
        # The never_ready instance publishes its endpoint, then is discarded (and unpublishes): read it first.
        never_ready_tokens.append(read_endpoint_file(endpoint_file_path(gcd)).token)
        real_discard(process)

    monkeypatch.setattr(launcher_module, "_discard", discard_recording_the_token)
    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher(start_timeout=0.5).ensure("write-service", repo)

    captured = capsys.readouterr()
    service_log = (gcd / ENDPOINT_DIRECTORY / SERVICE_LOG).read_text(encoding="utf-8")
    assert never_ready_tokens and never_ready_tokens[0] != endpoint.token
    for token in (endpoint.token, *never_ready_tokens):
        for text in (caplog.text, captured.out, captured.err, service_log, str(excinfo.value), repr(endpoint), *warnings_seen):
            assert token not in text


# -- policies and configuration ------------------------------------------------------------------


def test_the_write_service_policy_follows_the_launch_contract(gcd: Path) -> None:
    assert policy_for("write-service") is WRITE_SERVICE
    assert WRITE_SERVICE.scope == "git_common_dir" and WRITE_SERVICE.launchable
    assert WRITE_SERVICE.start_args(gcd) == ["serve", "--git-common-dir", str(gcd)]
    assert CHARTER_SERVICE.start_args(gcd) == ["serve", "--worktree", str(gcd)]
    assert CHARTER_SERVICE.scope == "worktree" and not CHARTER_SERVICE.launchable
    assert not READ_SERVICE.launchable
    with pytest.raises(ValueError, match="D-6"):
        READ_SERVICE.start_args(gcd)


@pytest.mark.parametrize("service", ["read-service", "charter-service"])
def test_launching_a_non_launchable_service_is_a_programming_error(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, service: str, spawned: list[subprocess.Popen[bytes]]
) -> None:
    with pytest.raises(ValueError, match="D-6"):
        make_launcher().ensure(service, repo)
    with pytest.raises(ValueError, match="D-6"):
        make_launcher().stop(service, repo)
    assert spawned == []


def test_an_unknown_service_has_no_policy() -> None:
    with pytest.raises(ValueError, match="no-such-service"):
        policy_for("no-such-service")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 15.0), ("2.5", 2.5), ("30", 30.0), ("0", 15.0), ("-1", 15.0), ("soon", 15.0), ("nan", 15.0), ("inf", 15.0)],
)
def test_the_start_budget_comes_from_the_environment(raw: str | None, expected: float) -> None:
    env = {} if raw is None else {START_TIMEOUT_ENV: raw}
    assert start_timeout_from_env(env) == expected


def test_the_idle_timeout_is_passed_to_the_service(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    make_launcher(idle_timeout=1).ensure("write-service", repo)
    assert _wait_until(lambda: not _alive(spawned[0]), budget=15.0)  # the fake exits after one idle second
    assert not endpoint_file_path(gcd).exists()


# -- NFR-006: the Windows lane -------------------------------------------------------------------
# The ``windows_ci`` marker is auto-skipped off Windows (tests/conftest.py), so the portable tests
# above stay unmarked and run on Linux and macOS; this one lifecycle smoke test carries the marker
# so ``ci-windows.yml`` (which selects files by ``@pytest.mark.windows_ci``) runs it natively.


@pytest.mark.windows_ci
def test_windows_lifecycle_smoke(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = make_launcher().ensure("write-service", repo)
    assert make_launcher().ensure("write-service", repo).instance_id == first.instance_id
    assert len(spawned) == 1

    spawned[0].kill()
    spawned[0].wait(timeout=10)
    second = make_launcher().ensure("write-service", repo)
    assert second.instance_id != first.instance_id

    assert make_launcher().stop("write-service", repo) is StopOutcome.STOPPED
    assert _wait_until(lambda: not _alive(spawned[1]))
    assert make_launcher().stop("write-service", repo) is StopOutcome.NOT_RUNNING

    monkeypatch.setenv(_MODE_ENV, "ignore_shutdown")
    make_launcher().ensure("write-service", repo)
    assert make_launcher(stop_timeout=1.0).stop("write-service", repo) is StopOutcome.FORCED
    assert _wait_until(lambda: not _alive(spawned[2]))


# -- NFR-001: the warm path ----------------------------------------------------------------------


@pytest.mark.timing
def test_the_warm_path_costs_at_most_150_ms_p95(make_launcher: Callable[..., ServiceLauncher], repo: Path) -> None:
    make_launcher().ensure("write-service", repo)
    durations: list[float] = []
    for _ in range(20):
        launcher = make_launcher()
        started = time.perf_counter()
        launcher.ensure("write-service", repo)
        durations.append(time.perf_counter() - started)
    durations.sort()
    p95 = durations[int(0.95 * len(durations)) - 1]
    assert p95 < 0.150, f"warm-path p95 was {p95 * 1000:.1f} ms"


# -- seams and helpers ---------------------------------------------------------------------------


def test_stop_does_not_signal_a_lingering_process_that_no_longer_answers(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, warnings_seen: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """After /shutdown the pid still reads alive, but nothing proves it is the instance: unconfirmed, never stopped."""
    endpoint = make_launcher().ensure("write-service", repo)
    signalled: list[int] = []
    monkeypatch.setattr(launcher_module, "pid_alive", lambda pid: True)
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: None)
    monkeypatch.setattr(launcher_module, "terminate_pid", signalled.append)

    assert make_launcher(stop_timeout=0.3).stop("write-service", repo) is StopOutcome.UNCONFIRMED
    assert signalled == []
    assert any(str(endpoint.pid) in message and SERVICE_LOG in message for message in warnings_seen)


def test_stop_reports_a_hung_service_it_cannot_prove_as_unconfirmed(
    make_launcher: Callable[..., ServiceLauncher],
    repo: Path,
    gcd: Path,
    spawned: list[subprocess.Popen[bytes]],
    warnings_seen: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hung before /shutdown (the handshake times out) and its creation time does not match: no signal, no 'not running'."""
    process, endpoint = _start_direct(gcd, spawned, "hang")
    signalled: list[int] = []
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: 0.0)
    monkeypatch.setattr(launcher_module, "terminate_pid", signalled.append)

    assert make_launcher(client_timeout=0.3).stop("write-service", repo) is StopOutcome.UNCONFIRMED
    assert signalled == []
    assert _alive(process)
    assert any(str(endpoint.pid) in message and SERVICE_LOG in message for message in warnings_seen)


def test_stop_forces_a_hung_service_proven_by_its_creation_time(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    """The process was created when the endpoint says the instance started: it is the instance, so it is terminated."""
    process, _ = _start_direct(gcd, spawned, "hang")

    assert make_launcher(client_timeout=0.3, stop_timeout=5.0).stop("write-service", repo) is StopOutcome.FORCED
    assert _wait_until(lambda: not _alive(process))


def test_stop_reports_unconfirmed_when_a_proven_process_survives_terminate(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    _start_direct(gcd, spawned, "hang")
    signalled: list[int] = []
    monkeypatch.setattr(launcher_module, "terminate_pid", signalled.append)

    assert make_launcher(client_timeout=0.3, stop_timeout=0.3).stop("write-service", repo) is StopOutcome.UNCONFIRMED
    assert signalled == [spawned[0].pid]


def test_stop_reports_a_reused_pid_as_not_running_and_never_signals_it(
    make_launcher: Callable[..., ServiceLauncher],
    repo: Path,
    gcd: Path,
    spawned: list[subprocess.Popen[bytes]],
    warnings_seen: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live pid was created after the instance published its start: another process reuses it, so the instance is gone."""
    process, endpoint = _start_direct(gcd, spawned, "hang")
    published = launcher_module._epoch(endpoint.started_at)
    assert published is not None
    signalled: list[int] = []
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: published + 600.0)
    monkeypatch.setattr(launcher_module, "terminate_pid", signalled.append)

    assert make_launcher(client_timeout=0.3).stop("write-service", repo) is StopOutcome.NOT_RUNNING
    assert signalled == []
    assert warnings_seen == []  # nothing invites the user to end an unrelated process
    assert _alive(process)


def _endpoint(pid: int, started_at: str) -> WriteServiceEndpoint:
    return WriteServiceEndpoint("127.0.0.1", 1, "t" * 43, "01INSTANCE", pid, (1,), started_at)


@pytest.mark.parametrize(
    ("created", "started_at", "expected"),
    [
        (1_000.0, "1970-01-01T00:16:40Z", True),  # created at the published start
        (999.5, "1970-01-01T00:16:41+00:00", True),  # published a moment after creation
        (1_000.0, "1970-01-01T00:16:39Z", True),  # second-precision stamp truncated below creation
        (1_100.0, "1970-01-01T00:16:40Z", False),  # created after the instance started: a reused pid
        (100.0, "1970-01-01T00:16:40Z", False),  # created long before the start window
        (None, "1970-01-01T00:16:40Z", False),  # no such process
        (1_000.0, "1970-01-01T00:16:40", False),  # a naive stamp proves nothing
        (1_000.0, "yesterday", False),  # a malformed stamp proves nothing
    ],
)
def test_creation_proof_matches_only_a_process_created_at_the_published_start(
    monkeypatch: pytest.MonkeyPatch, created: float | None, started_at: str, expected: bool
) -> None:
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: created)
    proof = launcher_module.creation_proof(_endpoint(4242, started_at), start_window=15.0)
    assert (proof is launcher_module.CreationProof.MATCHES) is expected


@pytest.mark.parametrize(
    ("created", "expected"),
    [
        (1_000.0, launcher_module.CreationProof.MATCHES),
        (1_100.0, launcher_module.CreationProof.REUSED),  # created after the published start
        (100.0, launcher_module.CreationProof.UNPROVEN),  # created long before the start window
        (None, launcher_module.CreationProof.UNPROVEN),  # no such process
    ],
)
def test_creation_proof_tells_a_reused_pid_from_an_unproven_one(
    monkeypatch: pytest.MonkeyPatch, created: float | None, expected: launcher_module.CreationProof
) -> None:
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: created)
    assert launcher_module.creation_proof(_endpoint(4242, "1970-01-01T00:16:40Z"), start_window=15.0) is expected


@pytest.mark.parametrize("configured", [1.0, 15.0, 600.0])
def test_the_stop_proof_window_covers_a_service_started_with_a_longer_budget(monkeypatch: pytest.MonkeyPatch, configured: float) -> None:
    """Created 60 s before it published: provable whatever budget is configured now (the window is never below the bound)."""
    monkeypatch.setattr(launcher_module, "process_create_time", lambda pid: 1_000.0 - 60.0)
    window = launcher_module.proof_window(configured)
    assert window >= max(configured, launcher_module.MIN_PROOF_START_WINDOW_S)
    assert launcher_module.creation_proof(_endpoint(4242, "1970-01-01T00:16:40Z"), start_window=window) is launcher_module.CreationProof.MATCHES


@pytest.mark.parametrize(
    ("argv", "jvm_vars_kept"),
    [
        (["/opt/jdk-25/bin/java", "-jar", "/cache/write-service.jar", "--port", "0"], False),
        (["/cache/write-service-linux-x64", "--port", "0"], True),  # a native build inherits the environment untouched
    ],
)
def test_a_jar_launch_drops_the_ambient_jvm_option_variables(monkeypatch: pytest.MonkeyPatch, argv: list[str], jvm_vars_kept: bool) -> None:
    for name in launcher_module.JVM_OPTION_ENV_VARS:
        monkeypatch.setenv(name, "-javaagent:/tmp/evil.jar")
    monkeypatch.setenv("PATH", "/usr/bin")
    popen = mock.Mock()
    monkeypatch.setattr(launcher_module.subprocess, "Popen", popen)
    launcher_module.spawn_detached(argv, mock.Mock())
    env = popen.call_args.kwargs["env"]
    if jvm_vars_kept:
        assert env is None
    else:
        assert env["PATH"] == "/usr/bin"
        assert not set(launcher_module.JVM_OPTION_ENV_VARS) & set(env)


def test_process_create_time_reads_the_process_table(monkeypatch: pytest.MonkeyPatch) -> None:
    assert launcher_module.process_create_time(0) is None
    assert launcher_module.process_create_time(os.getpid()) == psutil.Process(os.getpid()).create_time()
    gone = _Process(error=psutil.NoSuchProcess)
    monkeypatch.setattr(psutil, "Process", lambda pid: gone)
    assert launcher_module.process_create_time(4242) is None


def test_a_stale_endpoint_whose_port_serves_another_clone_is_recovered(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, tmp_path: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    """The instance check runs before the clone check, so a foreign answer at a stale port means stale, not mismatch."""
    other = tmp_path / "other.git"
    other.mkdir()
    _, foreign = _start_direct(other.resolve(), spawned, "healthy")
    directory = gcd / ENDPOINT_DIRECTORY
    directory.mkdir(mode=0o700)
    stale = json.loads(endpoint_file_path(other.resolve()).read_text(encoding="utf-8"))
    stale["instance_id"] = "01STALEINSTANCE"
    descriptor = os.open(endpoint_file_path(gcd), os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(stale, handle)

    recovered = make_launcher().ensure("write-service", repo)

    assert recovered.instance_id not in {"01STALEINSTANCE", foreign.instance_id}
    assert len(spawned) == 2


def test_a_live_instance_holding_the_lock_is_named_when_the_start_times_out(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, gcd: Path, spawned: list[subprocess.Popen[bytes]]
) -> None:
    holder, _ = _start_direct(gcd, spawned, "never_ready")

    with pytest.raises(ServiceRefusal) as excinfo:
        make_launcher(start_timeout=1.0).ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.UNHEALTHY
    assert f"another instance (pid {holder.pid}) holds the lock" in excinfo.value.message
    assert "spec-kitty service stop" in excinfo.value.message
    assert _alive(holder)


def test_a_lock_loser_with_no_live_holder_says_so(make_launcher: Callable[..., ServiceLauncher], gcd: Path) -> None:
    """The child exited 0 (lock held) but no live process is published: the reason still says why it exited."""
    launcher = make_launcher(start_timeout=0.1)
    assert "another instance holds the lock" in launcher._timeout_reason(0, gcd)
    assert launcher._timeout_reason(None, gcd) == "did not become ready within 0.1 s"


def test_lock_holder_reads_the_endpoint(gcd: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert launcher_module._lock_holder(gcd) is None  # no endpoint
    directory = gcd / ENDPOINT_DIRECTORY
    directory.mkdir(mode=0o700)
    path = endpoint_file_path(gcd)
    path.write_text("not json", encoding="utf-8")
    path.chmod(0o600)
    assert launcher_module._lock_holder(gcd) is None  # an untrusted file names no holder


@pytest.mark.parametrize(("windows", "key"), [(True, "creationflags"), (False, "start_new_session")])
def test_detach_options_follow_research_r5(windows: bool, key: str) -> None:
    options = launcher_module.detach_options(windows=windows)
    assert list(options) == [key]
    if windows:
        assert options[key] == 0x00000008 | 0x00000200 | 0x08000000
    else:
        assert options[key] is True


class _Process:
    def __init__(self, status: str | None = None, error: type[Exception] | None = None) -> None:
        self._status, self._error = status, error
        self.terminated = False

    def status(self) -> str:
        if self._error is not None:
            raise self._error(1)
        assert self._status is not None
        return self._status

    def terminate(self) -> None:
        if self._error is not None:
            raise self._error(1)
        self.terminated = True

    def create_time(self) -> float:
        if self._error is not None:
            raise self._error(1)
        return 1_000.0


@pytest.mark.parametrize(
    ("process", "expected"),
    [
        (_Process(status=psutil.STATUS_RUNNING), True),
        (_Process(status=psutil.STATUS_ZOMBIE), False),
        (_Process(error=psutil.NoSuchProcess), False),
        (_Process(error=psutil.AccessDenied), True),
    ],
)
def test_pid_alive_reads_the_process_table(monkeypatch: pytest.MonkeyPatch, process: _Process, expected: bool) -> None:
    monkeypatch.setattr(psutil, "Process", lambda pid: process)
    assert launcher_module.pid_alive(4242) is expected


def test_pid_alive_refuses_non_positive_pids() -> None:
    assert launcher_module.pid_alive(0) is False
    assert launcher_module.pid_alive(-1) is False


def test_terminate_pid_tolerates_a_vanished_process(monkeypatch: pytest.MonkeyPatch) -> None:
    gone = _Process(error=psutil.NoSuchProcess)
    monkeypatch.setattr(psutil, "Process", lambda pid: gone)
    launcher_module.terminate_pid(4242)
    alive = _Process(status=psutil.STATUS_RUNNING)
    monkeypatch.setattr(psutil, "Process", lambda pid: alive)
    launcher_module.terminate_pid(4242)
    assert alive.terminated


class _StubbornChild:
    """A child that ignores terminate: the discard falls back to kill."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def poll(self) -> int | None:
        return None

    def terminate(self) -> None:
        self.calls.append("terminate")

    def kill(self) -> None:
        self.calls.append("kill")

    def wait(self, timeout: float | None = None) -> int:
        self.calls.append(f"wait:{timeout}")
        if timeout is not None:
            raise subprocess.TimeoutExpired("fake", timeout)
        return -9


def test_discard_kills_a_child_that_ignores_terminate() -> None:
    child = _StubbornChild()
    launcher_module._discard(child)
    assert child.calls == ["terminate", "wait:5.0", "kill", "wait:None"]


def test_the_default_seams(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], resolved: ResolvedBinary, repo: Path) -> None:
    calls: list[str] = []

    def fake_resolve(service: str) -> ResolvedBinary:
        calls.append(service)
        return resolved

    monkeypatch.setattr(launcher_module, "resolve_binary", fake_resolve)
    assert launcher_module._default_resolve("write-service") is resolved
    assert calls == ["write-service"]
    launcher_module._warn_stderr("unpinned!")
    assert capsys.readouterr().err == "unpinned!\n"
    monkeypatch.setenv(START_TIMEOUT_ENV, "3")
    assert ServiceLauncher()._start_timeout == 3.0


# -- F3: an OSError while preparing or spawning is a refusal, never a traceback -------------------


def _launcher_with(resolved: ResolvedBinary, spawn: launcher_module.Spawner | None = None, *, start_timeout: float = _TEST_START_TIMEOUT_S) -> ServiceLauncher:
    return ServiceLauncher(resolve=lambda service: resolved, spawn=spawn, start_timeout=start_timeout, client_timeout=2.0, warn=lambda message: None)


@pytest.mark.parametrize(
    ("error", "cause"),
    [
        (PermissionError(13, "Permission denied"), "Permission denied"),
        (OSError(8, "Exec format error"), "Exec format error"),
        (FileNotFoundError(2, "No such file or directory"), "No such file or directory"),
    ],
)
def test_a_spawn_failure_is_a_binary_missing_refusal(resolved: ResolvedBinary, repo: Path, error: OSError, cause: str) -> None:
    def failing_spawn(argv: Sequence[str], log: IO[bytes]) -> subprocess.Popen[bytes]:
        raise error

    with pytest.raises(ServiceRefusal) as excinfo:
        _launcher_with(resolved, failing_spawn).ensure("write-service", repo)

    refusal = excinfo.value
    assert refusal.code is ServiceRefusalCode.BINARY_MISSING
    assert str(resolved.path) in refusal.message
    assert cause in refusal.message
    assert "exec" in refusal.remedy and "noexec" in refusal.remedy


@_POSIX_ONLY
def test_a_verified_binary_without_the_exec_bit_is_refused_not_raised(repo: Path, tmp_path: Path) -> None:
    """Real spawn of a pinned file that lost its exec permission: a named refusal, not a PermissionError."""
    binary = tmp_path / "command-cli-0.1.0-linux-x64"
    binary.write_bytes(b"#!/bin/sh\nexit 0\n")
    binary.chmod(0o644)
    pinned = ResolvedBinary(argv_prefix=(str(binary),), path=binary, source="cache", sha256=sha256_file(binary), pinned=True)

    with pytest.raises(ServiceRefusal) as excinfo:
        _launcher_with(pinned).ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.BINARY_MISSING
    assert str(binary) in excinfo.value.message


@pytest.mark.parametrize("seam", ["_ensure_directory", "_open_log"])
def test_an_unwritable_git_dir_is_an_unhealthy_refusal_with_a_remedy(
    resolved: ResolvedBinary, repo: Path, gcd: Path, monkeypatch: pytest.MonkeyPatch, seam: str
) -> None:
    def read_only(*args: object) -> None:
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(launcher_module, seam, read_only)
    spawned: list[Sequence[str]] = []

    def recording_spawn(argv: Sequence[str], log: IO[bytes]) -> subprocess.Popen[bytes]:
        spawned.append(argv)
        raise AssertionError("nothing may be spawned when the state directory cannot be prepared")

    with pytest.raises(ServiceRefusal) as excinfo:
        _launcher_with(resolved, recording_spawn).ensure("write-service", repo)

    refusal = excinfo.value
    assert refusal.code is ServiceRefusalCode.UNHEALTHY
    assert "Read-only file system" in refusal.message
    assert str(gcd / ENDPOINT_DIRECTORY) in refusal.remedy
    assert "writable" in refusal.remedy
    assert spawned == []


@_POSIX_ONLY
def test_the_log_is_never_opened_through_a_symlink(resolved: ResolvedBinary, repo: Path, gcd: Path, tmp_path: Path) -> None:
    directory = gcd / ENDPOINT_DIRECTORY
    directory.mkdir(mode=0o700)
    elsewhere = tmp_path / "elsewhere.log"
    elsewhere.write_text("untouched\n", encoding="utf-8")
    (directory / SERVICE_LOG).symlink_to(elsewhere)

    with pytest.raises(ServiceRefusal) as excinfo:
        _launcher_with(resolved, lambda argv, log: (_ for _ in ()).throw(AssertionError("spawned"))).ensure("write-service", repo)

    assert excinfo.value.code is ServiceRefusalCode.UNHEALTHY
    assert elsewhere.read_text(encoding="utf-8") == "untouched\n"


# -- F4: a half-written endpoint file is "not ready yet" while the service starts ----------------


def _malformed() -> EndpointFileError:
    return EndpointFileError(EndpointRefusalCode.MALFORMED, "the endpoint file is not valid JSON")


def test_a_malformed_endpoint_read_during_start_is_retried(make_launcher: Callable[..., ServiceLauncher], repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Windows: a reader can catch the file mid-replace. Once MALFORMED, then the valid endpoint."""
    real_read = launcher_module.read_endpoint_file
    failures: list[Path] = []

    def flaky_read(path: Path) -> WriteServiceEndpoint:
        endpoint = real_read(path)  # MISSING before the service publishes: passes through unchanged
        if not failures:
            failures.append(path)
            raise _malformed()
        return endpoint

    monkeypatch.setattr(launcher_module, "read_endpoint_file", flaky_read)

    endpoint = make_launcher().ensure("write-service", repo)

    assert failures, "the seam never returned MALFORMED: the test is vacuous"
    assert endpoint.instance_id


def test_a_persistently_malformed_endpoint_refuses_at_the_deadline(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch
) -> None:
    real_read = launcher_module.read_endpoint_file

    def always_malformed(path: Path) -> WriteServiceEndpoint:
        real_read(path)
        raise _malformed()

    monkeypatch.setattr(launcher_module, "read_endpoint_file", always_malformed)

    with pytest.raises(EndpointFileError) as excinfo:
        make_launcher(start_timeout=1.0).ensure("write-service", repo)

    assert excinfo.value.error_code == EndpointRefusalCode.MALFORMED.value
    assert len(spawned) == 1 and not _alive(spawned[0])


@pytest.mark.parametrize("code", [EndpointRefusalCode.EXPOSED, EndpointRefusalCode.NOT_LOOPBACK])
def test_an_untrusted_endpoint_during_start_stays_fatal(
    make_launcher: Callable[..., ServiceLauncher], repo: Path, spawned: list[subprocess.Popen[bytes]], monkeypatch: pytest.MonkeyPatch, code: EndpointRefusalCode
) -> None:
    real_read = launcher_module.read_endpoint_file
    calls: list[int] = []

    def untrusted(path: Path) -> WriteServiceEndpoint:
        real_read(path)
        calls.append(1)
        raise EndpointFileError(code, "untrusted")

    monkeypatch.setattr(launcher_module, "read_endpoint_file", untrusted)

    with pytest.raises(EndpointFileError) as excinfo:
        make_launcher().ensure("write-service", repo)

    assert excinfo.value.error_code == code.value
    assert len(calls) == 1, "a security refusal is never retried"
    assert len(spawned) == 1 and not _alive(spawned[0])
