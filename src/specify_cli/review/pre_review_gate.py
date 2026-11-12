"""Auto-scoped pre-review regression gate: scope aggregation + head-side runner + verdict.

Mission ``review-regression-gate-01KWX6DF`` WP01 (closes #572 + the per-WP
review-blind-spot facet of #1979; part of #2283). ``move-task --to
for_review`` (``cli/commands/agent/tasks_move_task.py``) scopes review to a
WP's ``owned_files`` — a WP that breaks a *consumer* outside its owned set
would otherwise reach approval unnoticed. This module is the engine half of
the fix (the CLI hook + config/override wiring lives in ``tasks_move_task_gates.py``):

1. **Build a :class:`ScopeResult`** (FR-002/FR-005/FR-006) from a WP's
   changed files via an injected
   :class:`~specify_cli.review.scope_source.ScopeSource` (see
   :func:`_scope_result_from_source`). The per-file derivation SHAPE — which
   dorny filter groups match, catch-all exclusion, composite-dir cone
   routing — is owned entirely by the port's implementations
   (``scope_source.py``); this module never re-derives it (mission
   ``scopesource-gate-followup-01KY6S9P`` WP04 retired the census tier this
   module used to own directly, FR-001). An EMPTY affected scope from a
   census-*narrowing* source is NEVER "verified clean" — always a
   ``no_coverage`` warn (SC-007), distinct from a green ``no_new_failures``
   verdict.

2. **Run the derived scope at head** (subprocess) — either the legacy
   hardcoded pytest/JUnit path (:func:`run_scoped_tests_at_head`, kept live
   via the FR-004 override tier) or the injected port's own
   ``test_command()``/``parse_results()`` (:func:`_evaluate_via_scope_source`)
   — and parse its output into per-failure identities.

3. **Compute the verdict** as ``head_failures - base_failures`` via
   ``review/baseline.py``'s existing ``diff_baseline`` (reused unchanged).
   An uncomputable baseline degrades to a warn, never a hard block (FR-003);
   a KNOWN baseline/head ``ScopeSource`` identity mismatch degrades to
   ``SOURCE_MISMATCH``, also a warn, never a hard block (FR-009/FR-011,
   mission ``scopesource-gate-followup-01KY6S9P`` WP04).
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from kernel.locks import LockAcquireTimeout, LockNotAcquired, machine_file_lock
from kernel.paths import is_windows, to_posix
from specify_cli.lanes.lane_invocation import INTERPRETER_REDIRECT_KEYS
from specify_cli.paths import get_runtime_root
from specify_cli.review._interpreter import resolve_pytest_command
from specify_cli.review.test_timeout import resolve_review_test_timeout
from specify_cli.review.baseline import (
    CAPTURE_BASELINE_TIMEOUT_SECONDS,
    BaselineFailure,
    BaselineTestResult,
    _extract_junit_output_path,
    _parse_junit_xml,
    diff_baseline,
)
from specify_cli.review.gate_budget import (
    BudgetClassification,
    ScopeBudgetAssessment,
    assess_scope_budget,
)
from specify_cli.review.scope_source import (
    UNKNOWN_SOURCE_IDENTITY,
    RawRunResult,
    ScopeBreakdownSource,
    ScopeSource,
    empty_scope_is_coverage_gap,
    exposes_scope_breakdown,
    scope_source_identity,
)

# ---------------------------------------------------------------------------
# Composite-route shape kept for the resolver's compatibility arguments and
# narrowing-source test doubles. The production GitHub Actions census source
# was retired by issue #380.
# ---------------------------------------------------------------------------

# Mirrors _gate_coverage._CompositeRoute: (target_group, target_shard, cone_roots).
_CompositeRoute = tuple[str | None, str | None, tuple[str, ...]]

_DEFAULT_HEAD_RUN_TIMEOUT = CAPTURE_BASELINE_TIMEOUT_SECONDS  # shared with baseline.py's capture_baseline.
_HEAD_RUN_HEARTBEAT_INTERVAL = 30.0
_HEAD_RUN_TERMINATE_GRACE = 5.0
_JUNIT_ARTIFACT_FILENAME = "pre-review-junit.xml"

# How many trailing stderr chars a run-error message carries (bounded tail).
_STDERR_TAIL_CHARS = 500


def _gate_run_env(run_env: Mapping[str, str] | None = None) -> dict[str, str]:
    """Environment for an automated gate subprocess: *run_env* (or inherit) + force headless.

    Shared by the pytest/JUnit runner (:func:`run_scoped_tests_at_head`) and
    the raw-command runner (:func:`_run_raw_command`) so the ``PWHEADLESS``
    guard — never pop a browser window during an automated gate run — is set
    in ONE place rather than copied per call site. ``run_env=None`` inherits
    this process's environment (today's behaviour); a given *run_env* (the
    lane test invocation's environment, #7547) replaces it.
    """
    env = dict(os.environ) if run_env is None else dict(run_env)
    env["PWHEADLESS"] = "1"
    return env


def _strip_interpreter_path_env(env: dict[str, str]) -> dict[str, str]:
    """Return ``env`` without the variables that redirect ``uv`` off the lane (#2803).

    The list is :data:`~specify_cli.lanes.lane_invocation.INTERPRETER_REDIRECT_KEYS`,
    the one home of the interpreter-redirect variables (#7547).
    """
    return {key: value for key, value in env.items() if key not in INTERPRETER_REDIRECT_KEYS}


def _launch_failed_error(exc: OSError) -> str:
    """Shared ``OSError`` launch-failure message for the head-run subprocess."""
    return f"scoped test run failed to launch: {exc}"


def _timed_out_error(timeout: int, stderr: str) -> str:
    """Shared timeout message carrying a bounded stderr tail."""
    return f"scoped test run timed out after {timeout}s; stderr tail: {stderr[-_STDERR_TAIL_CHARS:]}"


def _cancelled_error(stderr: str) -> str:
    """Shared cancellation message carrying a bounded stderr tail."""
    return f"scoped test run cancelled; stderr tail: {stderr[-_STDERR_TAIL_CHARS:]}"


class GateAuthoritiesUnavailable(RuntimeError):
    """Compatibility signal for callers that still handle authority failures.

    The production resolver no longer imports the retired GitHub Actions
    coverage authority. The exception remains importable so older injection
    tests and callers can keep treating authority loss as a visible
    ``no_coverage`` warning instead of a hard crash.
    """

    def __init__(self, message: str, *, is_consumer_repo: bool) -> None:
        super().__init__(message)
        self.is_consumer_repo = is_consumer_repo


# ---------------------------------------------------------------------------
# Scope derivation (FR-002/FR-005/FR-006)
#
# The census-narrowing DERIVATION that used to live here (``derive_test_scope``
# + its glob/path helpers) is retired (FR-001, mission
# scopesource-gate-followup-01KY6S9P WP04). This module only builds/consumes
# :class:`ScopeResult` from an injected
# :class:`~specify_cli.review.scope_source.ScopeSource` now.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScopeResult:
    """The affected-test-set derivation outcome for a WP's changed files.

    ``test_targets`` unions every focused (non-catch-all) matched group's
    contribution: a per-shard group's own ``tests/**`` globs, or a composite
    group's dir-specific ``_COMPOSITE_ROUTING`` cone_roots.
    """

    test_targets: tuple[str, ...]
    matched_shard_groups: tuple[str, ...]
    matched_composite_dirs: tuple[str, ...]
    empty_cone_composite_dirs: tuple[str, ...]
    excluded_scope_files: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        """True iff no test target was derived — ALWAYS a no_coverage warn, never clean."""
        return not self.test_targets

    def describe_empty_reason(self) -> str:
        """Human-readable reason for an empty scope, distinguishing SC-007's two causes."""
        if self.empty_cone_composite_dirs:
            dirs = ", ".join(self.empty_cone_composite_dirs)
            return f"unmapped composite dir(s) with no test cone_roots — unverified (SC-007): {dirs}"
        return "excluded scope — unverified: every changed file landed only in a catch-all group (core_misc/e2e/any_src) or matched no dorny group at all"

    @classmethod
    def from_override(cls, targets: tuple[str, ...]) -> ScopeResult:
        """Build a ``ScopeResult`` for an explicit override scope (FR-004).

        An override IS the test scope, by definition — no shard-group or
        composite-dir matching runs for it, and no scope files are excluded.
        """
        return cls(
            test_targets=targets,
            matched_shard_groups=(),
            matched_composite_dirs=(),
            empty_cone_composite_dirs=(),
            excluded_scope_files=(),
        )


# ---------------------------------------------------------------------------
# Head-side scoped runner (FR-001/FR-003, net-new — C-001)
# ---------------------------------------------------------------------------


class HeadRunState(StrEnum):
    """Typed completion state for the runner-owned subprocess lifecycle."""

    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    LAUNCH_FAILED = "launch_failed"
    INCOMPLETE_OUTPUT = "incomplete_output"
    NOT_STARTED = "not_started"


@dataclass(frozen=True)
class HeadRunResult:
    """Outcome of invoking the derived test scope at head."""

    ran: bool
    current_failures: tuple[BaselineFailure, ...] = ()
    returncode: int | None = None
    error: str | None = None
    state: HeadRunState = HeadRunState.COMPLETED
    stdout: str = ""
    stderr: str = ""
    observed_elapsed_seconds: float | None = None


GATE_LOCK_DIRECTORY = "gate-locks"
_SCOPED_RUN_LOCK_FILENAME = "pre-review-gate-run.lock"

# K-9: the lock-acquire wait is bounded on ITS OWN short timeout, deliberately
# DECOUPLED from ``_DEFAULT_HEAD_RUN_TIMEOUT`` (300s) below. Charging a
# lock-wait against the subprocess run timeout would re-create the exact
# #2493 contention bug FR-004 removes: under N concurrent lanes a shard that
# is fast on its own could still see ``TimeoutExpired`` purely from queueing
# behind a sibling lane's run. A module-level (not a bound default-argument)
# constant so tests can monkeypatch it without needing to re-import the call
# site — a default argument value is frozen at function-definition time and
# a monkeypatch of the constant afterwards would not be observed.
_LOCK_ACQUIRE_TIMEOUT_DEFAULT: float = 5.0


@contextlib.contextmanager
def _scoped_run_lock(*, acquire_timeout: float | None = None) -> Iterator[None]:
    """Advisory lock serializing concurrent scoped subprocess runs (#2493).

    WP04: migrated onto the canonical sync facade,
    :func:`kernel.locks.machine_file_lock` -- the "materially more machinery"
    concern the pre-migration docstring raised was about bridging through the
    ASYNC facade / an event loop for one bounded synchronous critical
    section; the sync facade added by the cross-os-primitive-unification
    mission's WP03 is exactly the sync-native fit this call site always
    wanted, with no event loop involved.

    Acquisition is a short, independently-timed retry loop bounded by
    ``acquire_timeout`` (default :data:`_LOCK_ACQUIRE_TIMEOUT_DEFAULT`) --
    never the caller's (much larger) subprocess run timeout. If the lock
    cannot be acquired within that bound, the caller proceeds WITHOUT it
    (fallback-to-run): losing the advisory serialization guarantee is
    preferable to a gate that blocks indefinitely or trips a false timeout.
    On Windows this remains a no-op — advisory contention protection is a
    POSIX-only nicety here, not a correctness requirement (unchanged; now
    routed through the canonical ``is_windows()`` seam rather than an inline
    ``sys.platform`` literal, per FR-012).
    """
    if is_windows():  # pragma: no cover - platform-specific, advisory-only nicety
        yield
        return

    timeout = _LOCK_ACQUIRE_TIMEOUT_DEFAULT if acquire_timeout is None else acquire_timeout
    # Lock lives under the canonical runtime root (FR-010: no hand-rolled
    # ``.spec-kitty`` home literal). One machine-wide lock is the right scope
    # for CPU contention: concurrent gate runs across lanes/worktrees on the
    # same machine serialize on it (a per-repo_root lock would not, since each
    # worktree has a distinct root).
    lock_path = get_runtime_root().base / GATE_LOCK_DIRECTORY / _SCOPED_RUN_LOCK_FILENAME
    try:
        with machine_file_lock(lock_path, blocking=True, timeout_s=timeout):
            yield
    except (LockAcquireTimeout, LockNotAcquired):
        # fallback-to-run: see docstring -- losing the advisory guarantee is
        # preferable to blocking indefinitely or tripping a false timeout.
        yield


_ProgressCallback = Callable[[float], None]
_ProcessWait = Callable[[subprocess.Popen[str], float], tuple[str, str]]
_ElapsedObserver = Callable[[float], None]


def _default_process_wait(process: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
    """Drain both pipes while waiting for at most ``timeout`` seconds."""
    return process.communicate(timeout=timeout)


def _run_windows_taskkill(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Invoke Windows' tree-aware process terminator without a shell."""
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )


def _signal_owned_process_tree(
    process: subprocess.Popen[str],
    *,
    force: bool,
    platform: str | None = None,
    windows_tree_kill: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] = (_run_windows_taskkill),
) -> None:
    """Signal only the process group created for this runner-owned child."""
    platform = platform or os.name
    if platform == "nt":
        command = ["taskkill", "/PID", str(process.pid), "/T"]
        if force:
            command.append("/F")
        result = windows_tree_kill(command)
        if result.returncode != 0 and process.poll() is None:
            # The tree-aware authority can race a naturally exiting child. If
            # it genuinely fails while the parent is still alive, ensure at
            # least that direct child receives the requested signal; the
            # non-zero taskkill diagnostic remains captured by the caller's
            # process output rather than widening to unrelated host PIDs.
            (process.kill if force else process.terminate)()
        return
    try:
        os.killpg(process.pid, signal.SIGKILL if force else signal.SIGTERM)
    except (OSError, ProcessLookupError):
        (process.kill if force else process.terminate)()


def _terminate_and_reap(
    process: subprocess.Popen[str],
    *,
    wait: _ProcessWait,
) -> tuple[str, str]:
    """Request termination, escalate after a bound, and reap the owned child."""
    _signal_owned_process_tree(process, force=False)
    try:
        return wait(process, _HEAD_RUN_TERMINATE_GRACE)
    except subprocess.TimeoutExpired:
        _signal_owned_process_tree(process, force=True)
        try:
            return process.communicate(timeout=_HEAD_RUN_TERMINATE_GRACE)
        except subprocess.TimeoutExpired:
            # The owned child is dead post-SIGKILL, but a grandchild that
            # escaped the process group (it called ``setsid`` itself) can
            # inherit and hold the stdout pipe, so the drain never sees EOF.
            # Reap the dead child by PID and return rather than wedging the
            # gate forever on a pipe the group-kill cannot reach. The escaped
            # orphan subtree is a separate, tracked reaping concern
            # (killpg/taskkill cannot cover a re-parented subtree) — it must
            # never turn the runner's own reap into an unbounded hang.
            with contextlib.suppress(Exception):
                process.wait(timeout=_HEAD_RUN_TERMINATE_GRACE)
            return "", ""


def _observe_process(
    process: subprocess.Popen[str],
    *,
    timeout: float,
    progress_callback: _ProgressCallback | None,
    monotonic: Callable[[], float],
    wait: _ProcessWait,
    elapsed_observer: _ElapsedObserver | None = None,
) -> tuple[HeadRunState, str, str]:
    """Drain, observe, and clean up one runner-owned process."""
    started_at = monotonic()
    deadline = started_at + timeout
    while True:
        now = monotonic()
        remaining = deadline - now
        if remaining <= 0:
            stdout, stderr = _terminate_and_reap(process, wait=wait)
            if elapsed_observer is not None:
                elapsed_observer(now - started_at)
            return HeadRunState.TIMED_OUT, stdout, stderr
        try:
            stdout, stderr = wait(process, min(_HEAD_RUN_HEARTBEAT_INTERVAL, remaining))
            return HeadRunState.COMPLETED, stdout, stderr
        except subprocess.TimeoutExpired:
            now = monotonic()
            if now >= deadline:
                stdout, stderr = _terminate_and_reap(process, wait=wait)
                if elapsed_observer is not None:
                    elapsed_observer(now - started_at)
                return HeadRunState.TIMED_OUT, stdout, stderr
            if progress_callback is not None:
                progress_callback(now - started_at)
        except KeyboardInterrupt:
            stdout, stderr = _terminate_and_reap(process, wait=wait)
            return HeadRunState.CANCELLED, stdout, stderr
        except BaseException:
            _terminate_and_reap(process, wait=wait)
            raise


def _launch_scoped_process(
    command: Sequence[str],
    *,
    repo_root: Path,
    env: Mapping[str, str],
    platform: str | None = None,
) -> subprocess.Popen[str]:
    """Launch one isolated process group using platform-native flags."""
    platform = platform or os.name
    if platform == "nt":
        return subprocess.Popen(
            command,
            cwd=str(repo_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    return subprocess.Popen(
        command,
        cwd=str(repo_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def run_scoped_tests_at_head(
    test_targets: Sequence[str],
    *,
    repo_root: Path,
    timeout: int = _DEFAULT_HEAD_RUN_TIMEOUT,
    progress_callback: _ProgressCallback | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    wait: _ProcessWait = _default_process_wait,
    run_env: Mapping[str, str] | None = None,
) -> HeadRunResult:
    """Run ``test_targets`` at head and parse JUnit into ``current_failures``.

    The shard-scoped invocation itself is net-new (``baseline.py``'s
    ``capture_baseline`` runs one whole, un-scoped ``review.test_command``
    and has no head-side runner of its own) — but the JUnit parsing is
    ``baseline.py``'s existing ``_parse_junit_xml``, reused unchanged (C-001).

    The subprocess command is built via :func:`resolve_pytest_command`
    (#2570.3) so it runs under whichever interpreter actually has ``pytest``
    installed, and the subprocess itself is serialized against concurrent
    scoped runs via :func:`_scoped_run_lock` (#2493).

    ``run_env`` (#7547): the environment to run in (``PWHEADLESS`` still
    forced); ``None`` inherits this process's environment. Either way the uv
    path drops the interpreter-redirect variables, and the ``sys.executable``
    fallback runs in exactly that environment (#5985 item 2).
    """
    if not test_targets:
        return HeadRunResult(
            ran=False,
            error="empty test scope — nothing to run",
            state=HeadRunState.INCOMPLETE_OUTPUT,
        )

    env = _gate_run_env(run_env)
    observed_elapsed: list[float] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        junit_path = Path(tmp_dir) / _JUNIT_ARTIFACT_FILENAME
        command = resolve_pytest_command(
            [*test_targets, f"--junitxml={junit_path}", "-q"],
            repo_root=repo_root,
        )
        if command[0] == "uv":
            # Scoped to the uv path: the sys.executable fallback may rely on
            # the PYTHONPATH of its run environment to find the code under test.
            env = _strip_interpreter_path_env(env)
        try:
            with _scoped_run_lock():
                process = _launch_scoped_process(
                    command,
                    repo_root=repo_root,
                    env=env,
                )
                state, stdout, stderr = _observe_process(
                    process,
                    timeout=timeout,
                    progress_callback=progress_callback,
                    monotonic=monotonic,
                    wait=wait,
                    elapsed_observer=observed_elapsed.append,
                )
        except OSError as exc:
            return HeadRunResult(
                ran=False,
                error=_launch_failed_error(exc),
                state=HeadRunState.LAUNCH_FAILED,
            )

        if state is HeadRunState.TIMED_OUT:
            return HeadRunResult(
                ran=False,
                returncode=process.returncode,
                error=_timed_out_error(timeout, stderr),
                state=state,
                stdout=stdout,
                stderr=stderr,
                observed_elapsed_seconds=(observed_elapsed[-1] if observed_elapsed else float(timeout)),
            )
        if state is HeadRunState.CANCELLED:
            return HeadRunResult(
                ran=False,
                returncode=process.returncode,
                error=_cancelled_error(stderr),
                state=state,
                stdout=stdout,
                stderr=stderr,
            )

        if not junit_path.exists():
            return HeadRunResult(
                ran=False,
                returncode=process.returncode,
                error=(f"no JUnit XML produced by the scoped run (exit={process.returncode}); stderr tail: {stderr[-_STDERR_TAIL_CHARS:]}"),
                state=HeadRunState.INCOMPLETE_OUTPUT,
                stdout=stdout,
                stderr=stderr,
            )

        try:
            # Broad catch mirrors baseline.py's own handling around this exact parse
            # call: a malformed-XML runner bug degrades to a warn (error=...), never a crash.
            _total, _passed, _failed, _skipped, failures = _parse_junit_xml(junit_path)
        except Exception as exc:
            return HeadRunResult(
                ran=False,
                returncode=process.returncode,
                error=f"failed to parse scoped-run JUnit XML: {exc}",
                state=HeadRunState.INCOMPLETE_OUTPUT,
                stdout=stdout,
                stderr=stderr,
            )

    return HeadRunResult(
        ran=True,
        current_failures=tuple(failures),
        returncode=process.returncode,
        state=HeadRunState.COMPLETED,
        stdout=stdout,
        stderr=stderr,
    )


# ---------------------------------------------------------------------------
# Verdict (FR-001/FR-003)
# ---------------------------------------------------------------------------


class GateOutcome(StrEnum):
    """The verdict shapes a pre-review gate evaluation can produce."""

    NO_COVERAGE = "no_coverage"  # FR-001/SC-007: empty scope OR run didn't complete — warn, NEVER "clean"
    NO_NEW_FAILURES = "no_new_failures"  # non-empty run, no new failures vs. baseline
    NEW_FAILURES = "new_failures"  # non-empty run, >=1 new failure vs. baseline
    UNVERIFIED_BASELINE = "unverified_baseline"  # FR-003: baseline uncomputable -> warn
    SOURCE_MISMATCH = "source_mismatch"  # FR-009/FR-011: baseline/head ScopeSource identity differs -> warn
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    # #3821: the gate did not run because the repo has not declared a gate to
    # run (no ``review.test_command`` configured, no override scope pinned).
    # Deliberately NOT a ``NO_COVERAGE`` warn: there is no coverage gap to
    # surface on a gate this repo never declared — #2598's acceptance
    # criterion ("does not fire/leak in a consumer repo that has not declared
    # it") makes this a quiet skip, recorded in transition metadata, never a
    # console warn.
    SKIPPED = "skipped"
    SCOPE_OVERSIZED = "scope_oversized"
    # #7554: the hook's probe proved the run would load another tree's code;
    # refused unless --force (``verdict_aggregation``'s refusal tier).
    FOREIGN_TREE = "foreign_tree"


@dataclass(frozen=True)
class ScopeAssessed:
    """Renderer-neutral notification that deterministic preflight completed."""

    assessment: ScopeBudgetAssessment


@dataclass(frozen=True)
class Heartbeat:
    """Renderer-neutral liveness notification from the candidate-head run."""

    phase: str
    observed_elapsed_seconds: float


GateStatusEvent = ScopeAssessed | Heartbeat


class GateStatusObserver(Protocol):
    """Presentation-neutral consumer of typed gate status events."""

    def __call__(self, event: GateStatusEvent) -> None:
        """Observe one ordered event without affecting the gate verdict."""
        ...


@dataclass(frozen=True)
class GateVerdict:
    """The end-to-end pre-review gate result: scope + head run + new-failure diff."""

    outcome: GateOutcome
    scope: ScopeResult
    reason: str | None = None
    new_failures: tuple[BaselineFailure, ...] = ()
    pre_existing_failures: tuple[BaselineFailure, ...] = ()
    run_state: HeadRunState = HeadRunState.COMPLETED
    budget_assessment: ScopeBudgetAssessment | None = None
    classification_candidate: bool = False
    observed_elapsed_seconds: float | None = None
    #: The candidate declared command's OBSERVED exit status, when the classifier
    #: had one. Recorded on every verdict the injected-``ScopeSource`` path
    #: classifies — including ``UNVERIFIED_BASELINE`` — so a baseline-relative
    #: ``NO_NEW_FAILURES`` can never be read as "the candidate exited 0" (issue
    #: #6751). ``None`` only for verdicts reached before a completed run (no
    #: coverage, skipped, oversized, source mismatch, timeout/cancel) and for the
    #: legacy JUnit branch, which never sees a raw ``returncode``.
    candidate_exit_code: int | None = None


def _progress_observer(
    progress_callback: _ProgressCallback | None,
    status_observer: GateStatusObserver | None,
) -> _ProgressCallback | None:
    """Compose the incumbent float callback with typed renderer-neutral events."""
    if progress_callback is None and status_observer is None:
        return None

    def _observe(elapsed: float) -> None:
        if progress_callback is not None:
            progress_callback(elapsed)
        if status_observer is not None:
            status_observer(Heartbeat(phase="candidate_head", observed_elapsed_seconds=elapsed))

    return _observe


_POLICY_METADATA_OWNER = "src/specify_cli/review/gate_budget.py (_RULES)"
_WHOLE_COMMAND_SHAPE = "whole declared command"
_BOUNDED_SHAPE = "bounded target list"
#: How much of the executed command / runner stderr tail a refusal carries.
_COMMAND_REASON_CHARS = 140
_STDERR_TAIL_REASON_CHARS = 180
#: NFR-002: a refusal reason is one bounded line, JSON-safe by construction.
_REASON_MAX_CHARS = 800


def describe_scope_shape(scope: ScopeResult, scope_source: ScopeSource | None) -> str:
    """Name the scope the gate actually chose (#6865, FR-006/FR-007).

    No resolved target narrows the run, so the declared command executes whole.
    With targets, a ``None`` source is the FR-004 override tier (an explicit
    target list, bounded by definition) and a ``ScopeBreakdownSource`` derives
    one per changed file. A source with no such refinement runs its declared
    command in full whatever targets it reports: appending a target list after a
    ``["sh", "-c", ...]`` argv could not narrow it anyway.
    """
    if not scope.test_targets:
        return _WHOLE_COMMAND_SHAPE
    if scope_source is None or exposes_scope_breakdown(scope_source):
        return _BOUNDED_SHAPE
    return _WHOLE_COMMAND_SHAPE


def _bounded_text(text: str, limit: int) -> str:
    """Collapse to one line and cap the length (JSON-safe diagnostic text)."""
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: limit - 3]}..."


def _declared_command_text(scope_source: ScopeSource | None) -> str | None:
    """The command the gate would execute, as one line (or ``None``).

    A ``None`` source is the FR-004 override tier: the pinned target list
    replaced the declared command entirely, so there is no command to name.
    """
    if scope_source is None:
        return None
    command = scope_source.test_command()
    if not command:
        return None
    return " ".join(command)


def _scope_shape_recovery(scope_shape: str) -> str:
    """The action an operator can take for THIS shape (never a generic hint)."""
    if scope_shape == _WHOLE_COMMAND_SHAPE:
        return "declare review.test_timeout_seconds for a longer whole-command run, or pin a bounded pre_review_test_scope in the WP frontmatter"
    return "raise review.test_timeout_seconds, narrow the pinned pre_review_test_scope, or use --skip-pre-review-gate explicitly"


def _timeout_shape_head(
    assessment: ScopeBudgetAssessment,
    *,
    scope_shape: str | None,
    declared_command: str | None,
) -> str:
    """The actionable head of every timeout refusal (#6865, FR-006).

    Names the shape the gate chose, the recovery for THAT shape and the command
    it executed — the three things an operator needs and the pre-#6865 message
    never said.
    """
    shape = scope_shape or "unknown"
    if declared_command:
        command_text = _bounded_text(declared_command, _COMMAND_REASON_CHARS)
    else:
        command_text = "(none — the pinned override scope replaced the declared command)"
    return f"timed out after {assessment.effective_budget_seconds:g}s on the {shape}. Recovery: {_scope_shape_recovery(shape)}. declared command: {command_text};"


def _timeout_shape_reason(
    reason: str | None,
    assessment: ScopeBudgetAssessment,
    *,
    scope_shape: str | None = None,
    declared_command: str | None = None,
) -> str:
    """A timeout refusal for an ALREADY-classified scope: shape, recovery, command."""
    tail = _bounded_text(reason, _STDERR_TAIL_REASON_CHARS) if reason else None
    head = _timeout_shape_head(assessment, scope_shape=scope_shape, declared_command=declared_command)
    return _bounded_text(f"{head} runner detail: {tail}" if tail else head, _REASON_MAX_CHARS)


def _unknown_timeout_reason(
    reason: str | None,
    assessment: ScopeBudgetAssessment,
    observed_elapsed_seconds: float | None,
    *,
    scope_shape: str | None = None,
    declared_command: str | None = None,
) -> str:
    """Build immutable-policy diagnostic evidence for an unknown timeout.

    #6865: keeps the classification-candidate evidence AND leads with the scope
    shape, the recovery and the executed command, so an operator can act without
    reading the source. Actionable text leads; the runner's own stderr tail
    trails it, so the final length cap can only trim the tail.
    """
    elapsed = observed_elapsed_seconds
    elapsed_text = "unavailable" if elapsed is None else f"{elapsed:.3f}s"
    targets = ", ".join(assessment.scope_identity.normalized_targets) or "(empty)"
    tail = _bounded_text(reason, _STDERR_TAIL_REASON_CHARS) if reason else None
    head = _timeout_shape_head(assessment, scope_shape=scope_shape, declared_command=declared_command)
    return _bounded_text(
        " ".join(
            part
            for part in (
                head,
                f"normalized targets: {targets};",
                f"policy metadata: {_POLICY_METADATA_OWNER} (a timeout with no matching rule is a",
                "classification candidate for a reviewed update of it; runtime policy was not modified);",
                f"scope identity: {assessment.scope_identity.value};",
                f"observed elapsed: {elapsed_text};",
                "lane remains unchanged.",
                f"runner detail: {tail}" if tail else "",
            )
            if part
        ),
        _REASON_MAX_CHARS,
    )


def _finalize_budget_evidence(
    verdict: GateVerdict,
    assessment: ScopeBudgetAssessment,
    observed_elapsed_seconds: float | None = None,
    *,
    scope_shape: str | None = None,
    declared_command: str | None = None,
) -> GateVerdict:
    """Attach one assessment and, only for unknown timeout, candidate evidence."""
    is_timeout = verdict.outcome is GateOutcome.TIMED_OUT
    is_candidate = is_timeout and assessment.classification is BudgetClassification.UNKNOWN
    reason = verdict.reason
    if is_candidate:
        reason = _unknown_timeout_reason(
            reason,
            assessment,
            observed_elapsed_seconds,
            scope_shape=scope_shape,
            declared_command=declared_command,
        )
    elif is_timeout:
        # #6865: an ALREADY-classified timeout still has to name the scope it ran.
        reason = _timeout_shape_reason(
            reason,
            assessment,
            scope_shape=scope_shape,
            declared_command=declared_command,
        )
    return replace(
        verdict,
        reason=reason,
        budget_assessment=assessment,
        classification_candidate=is_candidate,
        observed_elapsed_seconds=observed_elapsed_seconds,
    )


def _baseline_relative_reason(pre_existing: list[BaselineFailure], candidate_exit_code: int) -> str:
    """Say what a ``NO_NEW_FAILURES`` verdict does and does not assert (issue #6751).

    The verdict is a BASELINE-RELATIVE statement. Without the observed exit
    status an operator cannot tell "the suite ran clean" from "the suite failed,
    but only in ways the baseline already had", and the real incident behind
    #6751 had a candidate that exited 0 only because that was proved separately.
    So the reason names the exit status, the counts, and the boundary explicitly.
    """
    reason = f"baseline-relative: candidate declared command exited {candidate_exit_code}; {len(pre_existing)} pre-existing failure(s), 0 new"
    if candidate_exit_code != 0:
        # Only a NONZERO candidate run needs the boundary spelled out; saying it
        # next to "exited 0" would read as a contradiction.
        reason += " — this verdict does not assert a clean candidate exit"
    opaque = [failure for failure in pre_existing if failure.opaque]
    if opaque:
        bound = ", ".join(f"exit {f.exit_code}/digest {f.output_digest}" for f in opaque)
        reason += f"; the opaque whole-run failure matches the baseline exactly ({bound})"
    return reason


def _classify_current_failures(
    current_failures: tuple[BaselineFailure, ...],
    *,
    scope: ScopeResult,
    baseline: BaselineTestResult | None,
    candidate_exit_code: int | None = None,
) -> GateVerdict:
    """The shared baseline-diff tail: classify a completed run's failures.

    Extracted (WP03, mission ``doctrine-controlled-transition-gates-01KY51Z7``)
    so BOTH the legacy ``run_scoped_tests_at_head`` path and the NEW
    injected-``ScopeSource`` path (:func:`_evaluate_via_scope_source`) share
    ONE tested verdict-classification body instead of duplicating the
    ``diff_baseline`` call and its outcome mapping.

    ``candidate_exit_code`` (issue #6751) is the run's observed exit status when
    the caller has one. It is recorded on every verdict this body returns, and it
    makes ``NO_NEW_FAILURES`` state its baseline-relative scope instead of
    reading as a clean exit.
    """
    if baseline is None or baseline.failed == -1:
        return GateVerdict(
            outcome=GateOutcome.UNVERIFIED_BASELINE,
            scope=scope,
            reason="baseline uncomputable — surfacing all current failures as unverified",
            new_failures=current_failures,
            candidate_exit_code=candidate_exit_code,
        )

    pre_existing, new_failures, _fixed = diff_baseline(baseline, list(current_failures))
    if new_failures:
        return GateVerdict(
            outcome=GateOutcome.NEW_FAILURES,
            scope=scope,
            new_failures=tuple(new_failures),
            pre_existing_failures=tuple(pre_existing),
            candidate_exit_code=candidate_exit_code,
        )
    return GateVerdict(
        outcome=GateOutcome.NO_NEW_FAILURES,
        scope=scope,
        reason=(_baseline_relative_reason(pre_existing, candidate_exit_code) if candidate_exit_code is not None else None),
        pre_existing_failures=tuple(pre_existing),
        candidate_exit_code=candidate_exit_code,
    )


def _run_raw_command(
    command: Sequence[str],
    *,
    repo_root: Path,
    timeout: int,
    progress_callback: _ProgressCallback | None,
    monotonic: Callable[[], float],
    wait: _ProcessWait,
    elapsed_observer: _ElapsedObserver | None = None,
    serialize: bool = True,
    env: Mapping[str, str] | None = None,
) -> tuple[HeadRunState, RawRunResult | None, str | None]:
    """Run ``command`` under the SAME process-lifecycle machinery
    :func:`run_scoped_tests_at_head` uses (launch/observe/reap), but
    without baking in a pytest/JUnit-specific command shape — the
    injected-``ScopeSource`` counterpart (T011/FR-010). Returns the run
    state, an unparsed :class:`RawRunResult` (``None`` on a non-completion),
    and an error string (``None`` on success).

    ``serialize`` (#6062) selects whether the launch is wrapped in
    :func:`_scoped_run_lock` — the machine-wide ``pre-review-gate-run.lock``
    that serializes concurrent ``for_review`` head runs (#2493). The
    ``for_review`` head path (:func:`_evaluate_via_scope_source`) keeps the
    default ``True`` so its #2493 serialization is unchanged. Implement-time /
    for_review-time BASELINE capture (``baseline._run_command_for_baseline``)
    passes ``False``: a baseline run is NOT a pre-review gate head run, it
    already executes in its own isolated detached base-branch worktree, and
    taking that gate lock made a *claim* (``agent action implement``)
    acquire/await a lock scoped to the ``move-task --to for_review``
    transition — the #6062 hang (and a cross-lane block of a concurrent
    for_review gate). Baseline capture still reuses this function for its
    group-safe launch/reap machinery (the #3612 ``sh -c`` orphan fix); only
    the gate-lock coupling is dropped.

    A ``--junitxml=<relative path>`` embedded in a ``DeclaredCommandScopeSource``
    -resolved command resolves against the subprocess's ``cwd`` (``repo_root``,
    per :func:`_launch_scoped_process`) — mirroring the SAME B1 anchor
    ``baseline._run_command_for_baseline`` applies (data-model.md sec. 5),
    on the head side (mission scopesource-gate-followup-01KY6S9P WP04). Without
    this, a relative artifact path is checked against THIS process's own cwd
    (the gate's, not the subprocess's), silently missing a genuinely-produced
    artifact and mislabeling the run's ``scope_source_identity`` parse-mode —
    the exact false-``SOURCE_MISMATCH`` shape T024's parity suite exists to
    catch.

    ``env`` (#7547): the environment to run in (``PWHEADLESS`` still forced);
    ``None`` inherits this process's environment.
    """
    run_env = _gate_run_env(env)
    lock_cm: contextlib.AbstractContextManager[object] = _scoped_run_lock() if serialize else contextlib.nullcontext()
    try:
        with lock_cm:
            process = _launch_scoped_process(list(command), repo_root=repo_root, env=run_env)
            state, stdout, stderr = _observe_process(
                process,
                timeout=timeout,
                progress_callback=progress_callback,
                monotonic=monotonic,
                wait=wait,
                elapsed_observer=elapsed_observer,
            )
    except OSError as exc:
        return HeadRunState.LAUNCH_FAILED, None, _launch_failed_error(exc)

    if state is HeadRunState.TIMED_OUT:
        return state, None, _timed_out_error(timeout, stderr)
    if state is HeadRunState.CANCELLED:
        return state, None, _cancelled_error(stderr)

    artifact_path = _extract_junit_output_path(command)
    if artifact_path is not None and not artifact_path.is_absolute():
        artifact_path = repo_root / artifact_path
    raw = RawRunResult(returncode=process.returncode, stdout=stdout, stderr=stderr, output_artifact_path=artifact_path)
    return state, raw, None


_NO_TEST_COMMAND_REASON = "no test command configured for the injected ScopeSource — review proceeds without it"


def _evaluate_via_scope_source(
    scope: ScopeResult,
    *,
    repo_root: Path,
    baseline: BaselineTestResult | None,
    timeout: int,
    progress_callback: _ProgressCallback | None,
    monotonic: Callable[[], float],
    wait: _ProcessWait,
    scope_source: ScopeSource,
    elapsed_observer: _ElapsedObserver | None = None,
    run_env: Mapping[str, str] | None = None,
) -> GateVerdict:
    """T011/FR-010/FR-011/FR-012: drive the head run + parse through the
    injected port instead of the hardcoded pytest/JUnit path
    (:func:`run_scoped_tests_at_head` / :func:`_parse_junit_xml`).

    Empty-scope handling is impl-shape-dependent (NFR-001):

    - A narrowing source (satisfying
      :class:`~specify_cli.review.scope_source.ScopeBreakdownSource`) treats an
      empty derived scope as a coverage gap — a ``no_coverage`` warn carrying the
      incumbent :meth:`ScopeResult.describe_empty_reason` wording — exactly as
      the now-retired census tier + the legacy branch of :func:`evaluate_with_scope`
      did. Restoring this keeps the empty-cone / all-excluded cases from silently
      running the whole suite through the inverted hook.
    - A non-narrowing implementation (``DeclaredCommandScopeSource``)
      legitimately reports an empty per-file scope while still running its whole
      declared suite (FR-003/FR-010) — that is not a no-coverage signal. For it,
      the ONLY no-coverage trigger here is ``test_command() -> None`` (FR-012),
      the port's own explicit no-config signal.

    **``SOURCE_MISMATCH`` (FR-009/FR-011, mission
    scopesource-gate-followup-01KY6S9P WP04).** After a completed run, the
    head-side identity (:func:`~specify_cli.review.scope_source.scope_source_identity`)
    is compared against the already-loaded ``baseline.source_identity`` (the
    baseline itself is loaded upstream, by ``tasks_move_task_gates._mt_resolve_gate_baseline``
    — this function only COMPARES). A KNOWN (non-``"unknown"``) baseline
    identity that differs from the head's own -> ``SOURCE_MISMATCH`` (warn,
    fail-open by construction — see ``verdict_aggregation``'s member
    allowlists). ``baseline is None`` or its identity is ``"unknown"`` (legacy
    artifact / never captured) -> degrades to the existing
    ``UNVERIFIED_BASELINE`` path via :func:`_classify_current_failures`, never a
    mismatch.

    ``run_env`` (#7547) is the environment the declared command runs in;
    ``None`` inherits this process's environment.
    """
    if empty_scope_is_coverage_gap(scope_source) and scope.is_empty:
        return GateVerdict(outcome=GateOutcome.NO_COVERAGE, scope=scope, reason=scope.describe_empty_reason())

    command = scope_source.test_command()
    if command is None:
        return GateVerdict(outcome=GateOutcome.NO_COVERAGE, scope=scope, reason=_NO_TEST_COMMAND_REASON)

    state, raw, error = _run_raw_command(
        [*command, *scope.test_targets],
        repo_root=repo_root,
        timeout=timeout,
        progress_callback=progress_callback,
        monotonic=monotonic,
        wait=wait,
        elapsed_observer=elapsed_observer,
        env=run_env,
    )
    if state is HeadRunState.TIMED_OUT:
        return GateVerdict(outcome=GateOutcome.TIMED_OUT, scope=scope, reason=error, run_state=state)
    if state is HeadRunState.CANCELLED:
        return GateVerdict(outcome=GateOutcome.CANCELLED, scope=scope, reason=error, run_state=state)
    if raw is None:
        return GateVerdict(
            outcome=GateOutcome.NO_COVERAGE,
            scope=scope,
            reason=f"scoped test run did not complete: {error}",
            run_state=state,
        )

    failures = scope_source.parse_results(raw)
    head_identity = scope_source_identity(scope_source, raw)
    if baseline is not None and baseline.source_identity != UNKNOWN_SOURCE_IDENTITY and baseline.source_identity != head_identity:
        return GateVerdict(
            outcome=GateOutcome.SOURCE_MISMATCH,
            scope=scope,
            reason=(f"baseline captured under {baseline.source_identity}; head ran under {head_identity} — failure identities are not comparable"),
        )
    return _classify_current_failures(
        failures,
        scope=scope,
        baseline=baseline,
        candidate_exit_code=raw.returncode,
    )


def evaluate_with_scope(
    scope: ScopeResult,
    *,
    repo_root: Path,
    baseline: BaselineTestResult | None,
    timeout: int | None = None,
    progress_callback: _ProgressCallback | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    wait: _ProcessWait = _default_process_wait,
    scope_source: ScopeSource | None = None,
    status_observer: GateStatusObserver | None = None,
    run_env: Mapping[str, str] | None = None,
) -> GateVerdict:
    """The shared verdict tail: run ``scope`` at head, diff vs. ``baseline``.

    Extracted (pre-merge finding, #572/#1979/#2283) so BOTH the
    injected-``ScopeSource`` tier (:func:`evaluate_pre_review_gate`, below —
    the census-derived auto-scope tier it used to also serve was retired by
    mission ``scopesource-gate-followup-01KY6S9P`` WP04, FR-001) AND the
    FR-004 explicit-override tier
    (``tasks_move_task_gates._mt_pre_review_gate_with_override_scope``) drive the
    EXACT same warn/new-failure/unverified-baseline policy from ONE tested
    body — instead of the override tier hand-mirroring this tail as a
    divergence-prone copy (the pre-fix shape, which left its
    ``NEW_FAILURES``/block/force + ``UNVERIFIED_BASELINE`` branches with zero
    coverage).

    An empty ``scope`` still degrades to a ``no_coverage`` warn here, via
    :meth:`ScopeResult.describe_empty_reason` — the wording that fits
    :func:`evaluate_pre_review_gate`'s own auto-derived empty scope. A
    caller building a scope whose empty case needs DIFFERENT wording (e.g.
    the override tier's literal "override test scope is empty" — an
    explicit override list isn't a census exclusion, so
    ``describe_empty_reason()``'s catch-all/composite-dir phrasing would be
    misleading there) should check ``scope.is_empty`` itself and skip this
    function entirely for that branch, exactly as the override tier does.

    ``scope_source`` (T011, mission ``doctrine-controlled-transition-gates-01KY51Z7``
    WP03): when injected, the head run + parse route through the port
    (:func:`_evaluate_via_scope_source`) instead of the legacy hardcoded
    pytest/JUnit path — see that function's docstring for why its
    empty-scope handling differs. ``None`` (the default, C-002 KEPT LIVE) is
    the FR-004 explicit-override tier's own shape
    (``tasks_move_task_gates._mt_pre_review_gate_with_override_scope``) — it never
    injects a ``scope_source``, by design, since an override IS the test
    scope.

    ``run_env`` (#7547): the environment both runners use (the hook passes the
    lane test invocation's environment); ``None`` inherits this process's.
    """
    timeout = resolve_review_test_timeout(repo_root, timeout)
    assessment = assess_scope_budget(scope.test_targets, timeout)
    if status_observer is not None:
        status_observer(ScopeAssessed(assessment=assessment))

    # #6865: a refusal must name the scope the gate chose. Resolve the shape and
    # the executed command once, from the same source/scope pair the run uses.
    scope_shape = describe_scope_shape(scope, scope_source)
    declared_command = _declared_command_text(scope_source)

    if assessment.classification is BudgetClassification.OVERSIZED:
        return GateVerdict(
            outcome=GateOutcome.SCOPE_OVERSIZED,
            scope=scope,
            reason=(
                f"validation did not start because the selected scope ({scope_shape}: {', '.join(scope.test_targets) or '(empty)'}"[:_COMMAND_REASON_CHARS]
                + "}) is explicitly "
                f"oversized for the {assessment.effective_budget_seconds:g}s budget; "
                f"{assessment.guidance}"
            ),
            run_state=HeadRunState.NOT_STARTED,
            budget_assessment=assessment,
        )

    combined_progress = _progress_observer(progress_callback, status_observer)
    if scope_source is None:
        if scope.is_empty:
            return _finalize_budget_evidence(
                GateVerdict(outcome=GateOutcome.NO_COVERAGE, scope=scope, reason=scope.describe_empty_reason()),
                assessment,
            )

        run_result = run_scoped_tests_at_head(
            scope.test_targets,
            repo_root=repo_root,
            timeout=timeout,
            progress_callback=combined_progress,
            monotonic=monotonic,
            wait=wait,
            run_env=run_env,
        )
        if run_result.state is HeadRunState.TIMED_OUT:
            return _finalize_budget_evidence(
                GateVerdict(
                    outcome=GateOutcome.TIMED_OUT,
                    scope=scope,
                    reason=run_result.error,
                    run_state=run_result.state,
                ),
                assessment,
                run_result.observed_elapsed_seconds,
                scope_shape=scope_shape,
            )
        if run_result.state is HeadRunState.CANCELLED:
            return _finalize_budget_evidence(
                GateVerdict(
                    outcome=GateOutcome.CANCELLED,
                    scope=scope,
                    reason=run_result.error,
                    run_state=run_result.state,
                ),
                assessment,
                run_result.observed_elapsed_seconds,
            )
        if not run_result.ran:
            return _finalize_budget_evidence(
                GateVerdict(
                    outcome=GateOutcome.NO_COVERAGE,
                    scope=scope,
                    reason=f"scoped test run did not complete: {run_result.error}",
                    run_state=run_result.state,
                ),
                assessment,
                run_result.observed_elapsed_seconds,
            )
        return _finalize_budget_evidence(
            _classify_current_failures(run_result.current_failures, scope=scope, baseline=baseline),
            assessment,
            run_result.observed_elapsed_seconds,
        )

    observed_elapsed: list[float] = []
    verdict = _evaluate_via_scope_source(
        scope,
        repo_root=repo_root,
        baseline=baseline,
        timeout=timeout,
        progress_callback=combined_progress,
        monotonic=monotonic,
        wait=wait,
        scope_source=scope_source,
        elapsed_observer=observed_elapsed.append,
        run_env=run_env,
    )
    return _finalize_budget_evidence(
        verdict,
        assessment,
        observed_elapsed[-1] if observed_elapsed else None,
        scope_shape=scope_shape,
        declared_command=declared_command,
    )


def _scope_result_from_source(scope_source: ScopeSource, changed_files: Sequence[str]) -> ScopeResult:
    """Build a :class:`ScopeResult` from the injected port's per-file scoping.

    A narrowing source (satisfying the
    :class:`~specify_cli.review.scope_source.ScopeBreakdownSource` refinement)
    reconstructs the FULL breakdown — ``matched_shard_groups`` /
    ``matched_composite_dirs`` / ``empty_cone_composite_dirs`` /
    ``excluded_scope_files`` — so the inverted hook's transition metadata is
    byte-identical to the incumbent (now-retired) census tier (NFR-001).

    A non-narrowing source (``DeclaredCommandScopeSource`` or an arbitrary
    injected stub) has no shard groups by construction — the injected-port path
    only needs the flat union of ``file_to_scope`` targets, exactly as before.
    """
    if exposes_scope_breakdown(scope_source):
        return _scope_result_from_breakdown(scope_source, changed_files)
    targets: set[str] = set()
    for changed_file in changed_files:
        targets.update(scope_source.file_to_scope(changed_file))
    return ScopeResult(
        test_targets=tuple(sorted(targets)),
        matched_shard_groups=(),
        matched_composite_dirs=(),
        empty_cone_composite_dirs=(),
        excluded_scope_files=(),
    )


def _scope_result_from_breakdown(scope_source: ScopeBreakdownSource, changed_files: Sequence[str]) -> ScopeResult:
    """Aggregate a narrowing source's per-file
    :class:`~specify_cli.review.scope_source.FileScopeBreakdown` contributions
    into a full :class:`ScopeResult`.

    Mirrors the retired census tier's own union/aggregation (recall >
    precision across focused groups; a file contributing no focused group
    lands in ``excluded_scope_files``) so the port-driven path reproduces the
    incumbent ``ScopeResult`` shape for the same changed set (NFR-001).
    """
    targets: set[str] = set()
    shard_groups: set[str] = set()
    composite_dirs: set[str] = set()
    empty_cone_dirs: set[str] = set()
    excluded_scope_files: list[str] = []
    for raw_file in changed_files:
        changed_file = to_posix(raw_file)
        breakdown = scope_source.scope_breakdown(changed_file)
        targets.update(breakdown.test_targets)
        shard_groups.update(breakdown.matched_shard_groups)
        composite_dirs.update(breakdown.matched_composite_dirs)
        empty_cone_dirs.update(breakdown.empty_cone_composite_dirs)
        if not breakdown.contributes_scope:
            excluded_scope_files.append(changed_file)
    return ScopeResult(
        test_targets=tuple(sorted(targets)),
        matched_shard_groups=tuple(sorted(shard_groups)),
        matched_composite_dirs=tuple(sorted(composite_dirs)),
        empty_cone_composite_dirs=tuple(sorted(empty_cone_dirs)),
        excluded_scope_files=tuple(sorted(set(excluded_scope_files))),
    )


def evaluate_pre_review_gate(
    changed_files: Sequence[str],
    *,
    repo_root: Path,
    baseline: BaselineTestResult | None,
    timeout: int | None = None,
    progress_callback: _ProgressCallback | None = None,
    monotonic: Callable[[], float] = time.monotonic,
    wait: _ProcessWait = _default_process_wait,
    scope_source: ScopeSource,
    status_observer: GateStatusObserver | None = None,
    run_env: Mapping[str, str] | None = None,
) -> GateVerdict:
    """Compose scope derivation + the shared head-run/verdict tail.

    Warn-shaped outcomes (``NO_COVERAGE`` / ``UNVERIFIED_BASELINE`` /
    ``SOURCE_MISMATCH``) are never escalated to a hard failure here — the
    warn-default/opt-in-block/``--force`` policy is layered on top of this
    verdict by the ``for_review`` hook, not this function's concern.

    ``scope_source`` (mission ``doctrine-controlled-transition-gates-01KY51Z7``
    WP03; required as of mission ``scopesource-gate-followup-01KY6S9P`` WP04,
    which retired the census-derived auto-scope tier this function used to
    fall back to when ``scope_source`` was omitted): scope/command/parse are
    sourced ENTIRELY from the injected port. The sole production caller
    (``gate_registry._spec_kitty_pre_review_handler``) always supplies a
    concrete, non-``None`` source resolved by activation.

    ``run_env`` (#7547) is forwarded to :func:`evaluate_with_scope`.
    """
    scope = _scope_result_from_source(scope_source, changed_files)
    return evaluate_with_scope(
        scope,
        repo_root=repo_root,
        baseline=baseline,
        timeout=timeout,
        progress_callback=progress_callback,
        monotonic=monotonic,
        wait=wait,
        scope_source=scope_source,
        status_observer=status_observer,
        run_env=run_env,
    )
