"""Start, reuse, health-check, recover and stop the write service of a clone (#6590, #6676, WP04).

The binding contract is ``kitty-specs/pinned-service-binaries-01M64N66/contracts/launch-contract.md``
(accepted 2026-10-29):

* **start** -- ``<binary> serve --git-common-dir <abs> [--idle-timeout <s>]``, detached,
  ``stdin`` from the null device, ``stdout``/``stderr`` appended to
  ``<gcd>/spec-kitty-write-service/service.log``;
* **ready** -- ``endpoint.json`` passes ``read_endpoint_file``, then ``GET /handshake``
  reports ``repositoryId == sha256(realpath(gcd))``, a protocol major the CLI speaks
  and the endpoint's ``instanceId``, then ``GET /health`` reads ``ready`` for that
  same instance;
* **stop** -- ``POST /shutdown``, then, when the process is still alive after the stop
  budget (10 s) *and* still answers as the endpoint's instance, SIGTERM on POSIX or
  TerminateProcess on Windows.

:meth:`ServiceLauncher.ensure` returns only an endpoint that passed the ready check,
or raises: a :class:`~specify_cli.services.errors.ServiceRefusal`
(``SERVICE_UNHEALTHY``, ``SERVICE_VERSION_MISMATCH``, or a resolution refusal), or an
:class:`~specify_cli.status.write_service_protocol.EndpointFileError` other than
"missing" (exposed, not loopback, malformed), passed through unchanged: those are
security refusals and are never repaired.

An ``OSError`` while starting is a refusal, never a traceback: a directory or log the
launcher cannot create or open (a read-only or full ``.git``, a symlinked log, which
``O_NOFOLLOW`` refuses) is ``SERVICE_UNHEALTHY`` with a remedy naming the directory, and a
spawn that fails (no exec bit, a ``noexec`` mount) is ``SERVICE_BINARY_MISSING`` naming the
path and the cause. A ``MALFORMED`` endpoint read while the started service comes up is
"not ready yet" until the start budget runs out (a reader on Windows can see the file mid-replace).

The launcher never writes ``endpoint.json`` or ``service.lock``: the service owns both
and its lock decides which of several concurrent starters serves the clone
(``data-model.md``, ServiceInstance). The launcher creates the endpoint directory
owner-only when it is missing (never changing an existing one), appends to
``service.log``, and signals only a process that just proved it is the endpoint's
instance (pid reuse) or its own child, through the child's handle.
"""

from __future__ import annotations

import contextlib
import enum
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import IO, Any, Protocol

import psutil

from kernel.clock import now_utc_iso, parse_iso
from kernel.git_topology import git_common_dir
from kernel.paths import is_windows
from specify_cli.services.client import DEFAULT_TIMEOUT_S, ServiceClient, ServiceUnreachable
from specify_cli.services.errors import ServiceRefusal, ServiceRefusalCode, remedy_for
from specify_cli.services.policies import ServicePolicy, policy_for
from specify_cli.services.resolution import ResolvedBinary, resolve_binary, verify_before_exec
from specify_cli.status import (
    ENDPOINT_DIRECTORY,
    EndpointFileError,
    EndpointRefusalCode,
    Handshake,
    ProtocolShapeError,
    WriteServiceEndpoint,
    endpoint_file_path,
    negotiate_protocol_version,
    read_endpoint_file,
    repository_id,
)

__all__ = ["ServiceLauncher", "StopOutcome"]

SERVICE_LOG = "service.log"
START_TIMEOUT_ENV = "SPEC_KITTY_SERVICE_START_TIMEOUT"
DEFAULT_START_TIMEOUT_S = 15.0
#: Floor of the start window ``stop`` uses when proving a pid is the published instance. The
#: budget configured at stop time may be shorter than the one the service was started with.
MIN_PROOF_START_WINDOW_S = 300.0
POLL_INTERVAL_S = 0.05
STOP_TIMEOUT_S = 10.0
#: How long a discarded child of this launcher gets to exit after terminate, before kill.
_DISCARD_WAIT_S = 5.0
_READY = "ready"
_STOP_COMMAND = "`spec-kitty service stop`"
_OWNER_ONLY_DIRECTORY = 0o700
_OWNER_ONLY_FILE = 0o600
_DIGEST_PREFIX = 12
#: Rounding slack between a process's creation time and the ``started_at`` it published (second precision).
_CREATE_TIME_SLACK_S = 2.0

Resolver = Callable[[str], ResolvedBinary]
Spawner = Callable[[Sequence[str], IO[bytes]], "subprocess.Popen[bytes]"]


class StopOutcome(enum.StrEnum):
    """What :meth:`ServiceLauncher.stop` did."""

    STOPPED = "stopped"
    NOT_RUNNING = "not_running"
    FORCED = "forced"
    #: The published process is alive but could not be proven to be the instance: it was not signalled.
    UNCONFIRMED = "unconfirmed"


def start_timeout_from_env(env: Mapping[str, str]) -> float:
    """The start budget: ``SPEC_KITTY_SERVICE_START_TIMEOUT`` seconds when it is a positive finite number, else 15 s."""
    raw = env.get(START_TIMEOUT_ENV)
    if not raw:
        return DEFAULT_START_TIMEOUT_S
    try:
        value = float(raw)
    except ValueError:
        return DEFAULT_START_TIMEOUT_S
    return value if math.isfinite(value) and value > 0 else DEFAULT_START_TIMEOUT_S


def detach_options(*, windows: bool) -> dict[str, Any]:
    """``Popen`` keyword arguments that let the service outlive the CLI (research R-5)."""
    if windows:
        # getattr with the documented values: the constants exist only in a Windows build of ``subprocess``.
        detached = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        new_group = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        return {"creationflags": detached | new_group | no_window}
    return {"start_new_session": True}


#: JVM option variables the JVM reads on its own: ambient values would change the verified jar's behaviour.
JVM_OPTION_ENV_VARS = ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")
_JAR_FLAG = "-jar"


def spawn_env(argv: Sequence[str]) -> dict[str, str] | None:
    """The child environment: ``None`` (inherit) for a native build, the process env minus the JVM option variables for ``java -jar``."""
    if _JAR_FLAG not in argv[1:3]:
        return None
    return {name: value for name, value in os.environ.items() if name not in JVM_OPTION_ENV_VARS}


def spawn_detached(argv: Sequence[str], log: IO[bytes]) -> subprocess.Popen[bytes]:
    """Start *argv* detached, ``stdin`` from the null device and both output streams into *log*.

    A ``java -jar`` launch drops the ambient JVM option variables (:data:`JVM_OPTION_ENV_VARS`).
    """
    return subprocess.Popen(
        list(argv),
        env=spawn_env(argv),
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=log,
        close_fds=True,
        **detach_options(windows=is_windows()),
    )


def pid_alive(pid: int) -> bool:
    """Whether *pid* names a running process (a zombie awaiting its parent counts as exited)."""
    if pid <= 0:
        return False
    try:
        return psutil.Process(pid).status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True


def terminate_pid(pid: int) -> None:
    """SIGTERM on POSIX, TerminateProcess on Windows; a process that is already gone is not an error."""
    with contextlib.suppress(psutil.NoSuchProcess):
        psutil.Process(pid).terminate()


def process_create_time(pid: int) -> float | None:
    """When *pid* was created (epoch seconds), or ``None`` when there is no such process to read."""
    if pid <= 0:
        return None
    try:
        return psutil.Process(pid).create_time()
    except psutil.Error:
        return None


def _epoch(stamp: str) -> float | None:
    """*stamp* (ISO 8601 with an offset) as epoch seconds; ``None`` for a malformed or naive stamp."""
    try:
        moment = parse_iso(stamp)
    except ValueError:
        return None
    return None if moment.tzinfo is None else moment.timestamp()


class CreationProof(enum.Enum):
    """What the creation time of the published pid proves about it (FR-008, beyond the pid)."""

    #: Created when the published instance started: it is the instance.
    MATCHES = "matches"
    #: Created after the published instance started: the pid was reused by another process.
    REUSED = "reused"
    #: Nothing readable, or created long before the instance's start window: proves neither way.
    UNPROVEN = "unproven"


def proof_window(configured: float) -> float:
    """The start window used to prove an instance: the configured budget, never below :data:`MIN_PROOF_START_WINDOW_S`."""
    return max(configured, MIN_PROOF_START_WINDOW_S)


def creation_proof(endpoint: WriteServiceEndpoint, *, start_window: float) -> CreationProof:
    """Compare the creation time of the process *endpoint* names with the ``started_at`` it published.

    A service publishes ``started_at`` after its process was created and before the start budget ran
    out; a reused pid belongs to a process created later. Anything unreadable proves nothing.
    """
    created = process_create_time(endpoint.pid)
    published = _epoch(endpoint.started_at)
    if created is None or published is None:
        return CreationProof.UNPROVEN
    lead = published - created
    if lead < -_CREATE_TIME_SLACK_S:
        return CreationProof.REUSED
    if lead <= start_window + _CREATE_TIME_SLACK_S:
        return CreationProof.MATCHES
    return CreationProof.UNPROVEN


def _log_path(git_common: Path) -> Path:
    path: Path = git_common / ENDPOINT_DIRECTORY / SERVICE_LOG
    return path


def _unconfirmed_message(service: str, pid: int, git_common: Path) -> str:
    return (
        f"the {service} process {pid} is still alive but could not be proven to be the published instance,"
        f" so it was not signalled; check that process and end it by hand if it is the stuck service"
        f" (its log is {_log_path(git_common)})"
    )


def _warn_stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _default_resolve(service: str) -> ResolvedBinary:
    return resolve_binary(service)


def _ensure_directory(git_common: Path) -> Path:
    """The endpoint directory, created owner-only when missing; an existing one is never changed."""
    directory: Path = git_common / ENDPOINT_DIRECTORY
    with contextlib.suppress(FileExistsError):
        directory.mkdir(mode=_OWNER_ONLY_DIRECTORY)
    return directory


def _open_log(path: Path) -> IO[bytes]:
    """Open the log for appending; ``O_NOFOLLOW`` (where the platform has it) refuses a symlink planted in its place."""
    flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, _OWNER_ONLY_FILE)
    return os.fdopen(descriptor, "ab")


def _state_dir_refusal(service: str, directory: Path, exc: OSError) -> ServiceRefusal:
    """The endpoint directory or its log could not be prepared (read-only or full ``.git``, a planted symlink)."""
    return ServiceRefusal(
        ServiceRefusalCode.UNHEALTHY,
        f"cannot prepare {directory} to start the {service} ({_os_cause(exc)})",
        remedy_for(ServiceRefusalCode.UNHEALTHY, variant="state_dir", directory=directory),
    )


def _spawn_refusal(service: str, argv: Sequence[str], resolved: ResolvedBinary, exc: OSError) -> ServiceRefusal:
    """The verified binary (or the Java runtime for a jar) could not be executed."""
    program = argv[0]
    via = "" if Path(program) == resolved.path else f" through {program}"
    return ServiceRefusal(
        ServiceRefusalCode.BINARY_MISSING,
        f"cannot run {resolved.path}{via} for the {service} ({_os_cause(exc)})",
        remedy_for(ServiceRefusalCode.BINARY_MISSING, variant="spawn", program=program),
    )


def _os_cause(exc: OSError) -> str:
    return f"{type(exc).__name__}: {exc.strerror}" if exc.strerror else type(exc).__name__


def _start_line(service: str, resolved: ResolvedBinary) -> bytes:
    kind = "pinned" if resolved.pinned else "UNPINNED"
    line = f"{now_utc_iso()} spec-kitty: starting {service} from {resolved.path} (sha256 {resolved.sha256[:_DIGEST_PREFIX]}, {kind})\n"
    return line.encode("utf-8")


def _mismatch(message: str) -> ServiceRefusal:
    return ServiceRefusal(ServiceRefusalCode.VERSION_MISMATCH, message, remedy_for(ServiceRefusalCode.VERSION_MISMATCH))


def _check_identity(handshake: Handshake, git_common: Path) -> None:
    """Refuse a service of another clone, or one that speaks no protocol major of this CLI."""
    if handshake.repository_id != repository_id(git_common):
        raise _mismatch(f"a service for another clone answered at the endpoint of {git_common}")
    try:
        negotiate_protocol_version(handshake.protocol_versions)
    except ProtocolShapeError as exc:
        raise _mismatch(str(exc)) from None


def _read_endpoint(git_common: Path) -> WriteServiceEndpoint | None:
    """The published endpoint, ``None`` when there is none; every other endpoint refusal propagates unchanged."""
    try:
        return read_endpoint_file(endpoint_file_path(git_common))
    except EndpointFileError as exc:
        if exc.error_code == EndpointRefusalCode.MISSING.value:
            return None
        raise


class _Child(Protocol):
    """The part of ``subprocess.Popen`` the discard uses."""

    def poll(self) -> int | None: ...

    def terminate(self) -> None: ...

    def kill(self) -> None: ...

    def wait(self, timeout: float | None = None) -> int: ...


def _lock_holder(git_common: Path) -> int | None:
    """The live pid the published endpoint names, or ``None`` (no readable endpoint, or its process is gone)."""
    try:
        endpoint = _read_endpoint(git_common)
    except EndpointFileError:
        return None  # an untrusted file names no holder; the refusal itself stays UNHEALTHY
    if endpoint is None or not pid_alive(endpoint.pid):
        return None
    pid: int = endpoint.pid
    return pid


def _discard(process: _Child) -> None:
    """Stop a child this launcher spawned. Its own handle names it, so no pid can have been reused."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=_DISCARD_WAIT_S)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


class ServiceLauncher:
    """Hands out a verified, healthy endpoint of a pinned service, starting it when needed.

    Every collaborator is injectable for tests: ``resolve`` (default: WP03's
    :func:`resolve_binary`), ``spawn`` (default: :func:`spawn_detached`), ``clock``
    and ``sleep``, and ``warn``, which receives the resolver's warning (the
    unpinned developer opt-in) on every start. ``start_timeout`` defaults to
    ``SPEC_KITTY_SERVICE_START_TIMEOUT`` or 15 s (NFR-002); ``idle_timeout``, when
    given, is passed to the service as ``--idle-timeout``.
    """

    def __init__(
        self,
        *,
        resolve: Resolver | None = None,
        spawn: Spawner | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        start_timeout: float | None = None,
        poll_interval: float = POLL_INTERVAL_S,
        stop_timeout: float = STOP_TIMEOUT_S,
        idle_timeout: int | None = None,
        client_timeout: float = DEFAULT_TIMEOUT_S,
        warn: Callable[[str], None] | None = None,
    ) -> None:
        self._resolve = _default_resolve if resolve is None else resolve
        self._spawn = spawn_detached if spawn is None else spawn
        self._clock = clock
        self._sleep = sleep
        self._start_timeout = start_timeout_from_env(os.environ) if start_timeout is None else start_timeout
        self._poll_interval = poll_interval
        self._stop_timeout = stop_timeout
        self._idle_timeout = idle_timeout
        self._client_timeout = client_timeout
        self._warn = _warn_stderr if warn is None else warn

    # -- public surface ------------------------------------------------------------------------

    def ensure(self, service: str, repo_root: Path) -> WriteServiceEndpoint:
        """A healthy, identity-checked endpoint of *service* for the clone of *repo_root*, or a refusal."""
        policy = self._launchable(service)
        # A launchable policy is scoped to the git common dir (the charter service's worktree
        # scope is not launchable yet), so the scope directory is the clone's common dir.
        git_common = git_common_dir(repo_root)
        endpoint = self._reusable(git_common)
        if endpoint is not None:
            return endpoint
        return self._start(policy, git_common)

    def stop(self, service: str, repo_root: Path) -> StopOutcome:
        """Stop the running instance of *service* for the clone of *repo_root* (FR-009)."""
        policy = self._launchable(service)
        git_common = git_common_dir(repo_root)
        endpoint = _read_endpoint(git_common)
        if endpoint is None:
            return StopOutcome.NOT_RUNNING
        client = self._client(endpoint)
        if self._answers_as(client, endpoint):
            # The answer to /shutdown does not decide the outcome; liveness and identity below do.
            with contextlib.suppress(ServiceUnreachable):
                client.shutdown()
            if self._wait_for_exit(endpoint.pid):
                return StopOutcome.STOPPED
        elif not pid_alive(endpoint.pid):
            return StopOutcome.NOT_RUNNING  # a stale file naming a process that is gone
        return self._force_if_proven(policy.service, client, endpoint, git_common)

    def _force_if_proven(self, service: str, client: ServiceClient, endpoint: WriteServiceEndpoint, git_common: Path) -> StopOutcome:
        """Terminate the live published pid only once it is proven to be the instance; else report it unconfirmed.

        Proof is a handshake answering as the endpoint's instance, or a process creation time that
        matches the endpoint's ``started_at``; a pid alone is never enough (pid reuse). A process
        created after the instance started is proven to be another process reusing the pid: the
        instance is gone, so the outcome is ``NOT_RUNNING`` and nothing invites ending that process.
        """
        if not self._answers_as(client, endpoint):
            proof = creation_proof(endpoint, start_window=proof_window(self._start_timeout))
            if proof is CreationProof.REUSED:
                return StopOutcome.NOT_RUNNING
            if proof is CreationProof.UNPROVEN:
                self._warn(_unconfirmed_message(service, endpoint.pid, git_common))
                return StopOutcome.UNCONFIRMED
        terminate_pid(endpoint.pid)
        if self._wait_for_exit(endpoint.pid):
            return StopOutcome.FORCED
        self._warn(_unconfirmed_message(service, endpoint.pid, git_common))
        return StopOutcome.UNCONFIRMED

    # -- phases ----------------------------------------------------------------------------------

    @staticmethod
    def _launchable(service: str) -> ServicePolicy:
        policy = policy_for(service)
        policy.require_launchable()
        return policy

    def _client(self, endpoint: WriteServiceEndpoint) -> ServiceClient:
        return ServiceClient(endpoint, timeout=self._client_timeout)

    def _reusable(self, git_common: Path) -> WriteServiceEndpoint | None:
        """The published endpoint when it passes the ready check; ``None`` when absent or stale."""
        endpoint = _read_endpoint(git_common)
        if endpoint is None:
            return None
        return self._verified(endpoint, git_common)

    def _verified(self, endpoint: WriteServiceEndpoint, git_common: Path) -> WriteServiceEndpoint | None:
        """*endpoint* when its service is this clone's, speaks our protocol and is ready; ``None`` when stale."""
        client = self._client(endpoint)
        try:
            handshake = client.handshake()
            if handshake.instance_id != endpoint.instance_id:
                return None  # another instance answers at a published port: the file is stale
            _check_identity(handshake, git_common)
            health = client.health()
        except ServiceUnreachable:
            return None
        if health.status != _READY or health.instance_id != endpoint.instance_id:
            return None
        return endpoint

    def _start(self, policy: ServicePolicy, git_common: Path) -> WriteServiceEndpoint:
        resolved = self._resolve(policy.service)
        argv = [*resolved.argv_prefix, *policy.start_args(git_common), *self._idle_args()]
        with self._prepared_log(policy.service, git_common, resolved) as log:
            if resolved.warning:
                self._warn(resolved.warning)
            verify_before_exec(resolved)
            try:
                process = self._spawn(argv, log)
            except OSError as exc:  # no exec bit, a noexec mount, a vanished file, a foreign binary format
                raise _spawn_refusal(policy.service, argv, resolved, exc) from exc
        return self._await_ready(policy.service, process, git_common)

    @staticmethod
    def _prepared_log(service: str, git_common: Path, resolved: ResolvedBinary) -> IO[bytes]:
        """The endpoint directory and the open log, with the start line written; an ``OSError`` is a refusal."""
        directory = git_common / ENDPOINT_DIRECTORY
        try:
            log = _open_log(_ensure_directory(git_common) / SERVICE_LOG)
        except OSError as exc:
            raise _state_dir_refusal(service, directory, exc) from exc
        try:
            log.write(_start_line(service, resolved))
            log.flush()
        except OSError as exc:
            log.close()
            raise _state_dir_refusal(service, directory, exc) from exc
        return log

    def _idle_args(self) -> list[str]:
        return [] if self._idle_timeout is None else ["--idle-timeout", str(self._idle_timeout)]

    def _await_ready(self, service: str, process: subprocess.Popen[bytes], git_common: Path) -> WriteServiceEndpoint:
        """Poll until a verified endpoint is published, or stop *process* and refuse.

        A ``MALFORMED`` endpoint read is "not ready yet" until the deadline (on Windows a reader can
        catch the file while the service replaces it), and is raised if it is still malformed then.
        ``EXPOSED`` and ``NOT_LOOPBACK`` stay fatal at once: those are security refusals.
        """
        deadline = self._clock() + self._start_timeout
        try:
            while True:
                endpoint, malformed = self._poll_endpoint(git_common)
                if endpoint is not None:
                    return endpoint  # ours, or a concurrent starter's whose lock won
                self._refuse_if_failed(service, process, git_common)
                if self._clock() >= deadline:
                    if malformed is not None:
                        raise malformed
                    raise self._unhealthy(service, git_common, self._timeout_reason(process.poll(), git_common))
                self._sleep(self._poll_interval)
        except (ServiceRefusal, EndpointFileError):
            _discard(process)
            raise

    def _poll_endpoint(self, git_common: Path) -> tuple[WriteServiceEndpoint | None, EndpointFileError | None]:
        """One ready check: ``(endpoint, None)``, ``(None, None)`` when not ready, ``(None, error)`` for a malformed read."""
        try:
            return self._reusable(git_common), None
        except EndpointFileError as exc:
            if exc.error_code != EndpointRefusalCode.MALFORMED.value:
                raise
            return None, exc

    def _refuse_if_failed(self, service: str, process: subprocess.Popen[bytes], git_common: Path) -> None:
        """Refuse at once when the child failed; exit code 0 means another instance holds the lock."""
        code = process.poll()
        if code not in (None, 0):
            raise self._unhealthy(service, git_common, f"exited with code {code} before it was ready")

    def _timeout_reason(self, exit_code: int | None, git_common: Path) -> str:
        """Why the start budget ran out, naming a live instance that holds the lock when there is one."""
        reason = f"did not become ready within {self._start_timeout:g} s"
        if exit_code != 0:
            return reason
        holder = _lock_holder(git_common)
        if holder is None:
            return f"{reason}: the started process exited because another instance holds the lock"
        return f"{reason}: another instance (pid {holder}) holds the lock and is draining or not ready; stop it with {_STOP_COMMAND}"

    @staticmethod
    def _unhealthy(service: str, git_common: Path, why: str) -> ServiceRefusal:
        return ServiceRefusal(
            ServiceRefusalCode.UNHEALTHY,
            f"the {service} {why}; its log is {_log_path(git_common)}",
            remedy_for(ServiceRefusalCode.UNHEALTHY, gcd=git_common),
        )

    def _answers_as(self, client: ServiceClient, endpoint: WriteServiceEndpoint) -> bool:
        """Whether the service at *endpoint* still answers as the endpoint's own instance."""
        try:
            answered: str = client.handshake().instance_id
        except ServiceUnreachable:
            return False
        expected: str = endpoint.instance_id
        return answered == expected

    def _wait_for_exit(self, pid: int) -> bool:
        deadline = self._clock() + self._stop_timeout
        while self._clock() < deadline:
            if not pid_alive(pid):
                return True
            self._sleep(self._poll_interval)
        return not pid_alive(pid)
