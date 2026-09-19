"""Baseline test capture for Spec Kitty review loop stabilization.

Captures baseline test results at implement time (before the agent starts
coding) when the project explicitly configures a baseline-capable test
command. Results are cached as a committed artifact (baseline-tests.json).
At review time, the review prompt includes a "Baseline Context" section
showing which failures are pre-existing vs. newly introduced.

Design decisions:
- Capture timing: implement time, not claim time.
- Baseline capture is opt-in via ``review.test_command`` in ``.kittify/config.yaml``.
- Supported output formats are parser-specific; JUnit XML is supported today.
- Artifact format: structured JSON with test name, status, one-line error for failures only.
"""
from __future__ import annotations

import json
import logging
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from kernel.clock import now_utc_stamp
from kernel.errors import GuardedReadError
from kernel.guarded_read import read_guarded
from pathlib import Path
from typing import Any

from specify_cli.configured_command import ConfiguredCommandUnsupported, run_configured_command_template
from specify_cli.review.scope_source import (
    UNKNOWN_SOURCE_IDENTITY,
    RawRunResult,
    ScopeSource,
    scope_source_identity,
)

logger = logging.getLogger(__name__)

# Wall-clock bound for a single scoped/full test run. Shared with the
# pre-review gate's head-run default
# (``pre_review_gate._DEFAULT_HEAD_RUN_TIMEOUT``) so the two mirror each other
# by construction rather than by a hand-copied literal that could silently
# diverge when one is retuned.
CAPTURE_BASELINE_TIMEOUT_SECONDS = 300  # 5 minutes


class ReviewBaselineReadError(GuardedReadError, ValueError):
    """Raised when ``baseline-tests.json`` exists but cannot be decoded.

    Mission cli-error-surface-seam WP07/#4746: subclasses ``ValueError`` (in
    addition to :class:`kernel.errors.GuardedReadError`) so the pre-existing
    ``pytest.raises(ValueError, match="Malformed baseline JSON")`` contract
    (``tests/review/test_baseline.py``) keeps matching (D3 — subclass, never
    flat-replace). Never raised when the artifact is simply absent (D5);
    :meth:`BaselineTestResult.load` still returns ``None`` for that case.
    """

    def __init__(self, *, path: str | None = None, reason: str | None = None) -> None:
        message = f"Malformed baseline JSON at {path}: {reason}"
        super().__init__(path=path, reason=message)


@dataclass(frozen=True)
class BaselineFailure:
    """A single test failure recorded in the baseline."""

    test: str   # fully qualified test name
    error: str  # one-line error summary (max 200 chars)
    file: str   # file:line

    def to_dict(self) -> dict[str, Any]:
        return {"test": self.test, "error": self.error, "file": self.file}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineFailure:
        return cls(
            test=data["test"],
            error=data["error"],
            file=data["file"],
        )


@dataclass(frozen=True)
class BaselineTestResult:
    """Baseline test results captured at implement time."""

    wp_id: str
    captured_at: str      # ISO 8601 UTC
    base_branch: str
    base_commit: str      # 7-40 hex chars
    test_runner: str      # "pytest", "custom"
    total: int
    passed: int
    failed: int           # -1 means capture failed (sentinel)
    skipped: int
    failures: tuple[BaselineFailure, ...] = field(default_factory=tuple)
    source_identity: str = UNKNOWN_SOURCE_IDENTITY  # FR-009: "<ScopeSource class>/<parse-mode>",
                                       # or UNKNOWN_SOURCE_IDENTITY for a straddling-upgrade
                                       # artifact captured before this field existed.

    def to_dict(self) -> dict[str, Any]:
        return {
            "wp_id": self.wp_id,
            "captured_at": self.captured_at,
            "base_branch": self.base_branch,
            "base_commit": self.base_commit,
            "test_runner": self.test_runner,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "failures": [f.to_dict() for f in self.failures],
            "source_identity": self.source_identity,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaselineTestResult:
        failures = tuple(BaselineFailure.from_dict(f) for f in data.get("failures", []))
        return cls(
            wp_id=data["wp_id"],
            captured_at=data["captured_at"],
            base_branch=data["base_branch"],
            base_commit=data["base_commit"],
            test_runner=data["test_runner"],
            total=data["total"],
            passed=data["passed"],
            failed=data["failed"],
            skipped=data["skipped"],
            failures=failures,
            # Straddling-upgrade artifact captured before this field existed
            # (US1 AS4): degrade to UNKNOWN_SOURCE_IDENTITY, never a KeyError. It
            # makes WP04's head-side compare emit UNVERIFIED_BASELINE at diff
            # time, never a spurious SOURCE_MISMATCH.
            source_identity=data.get("source_identity", UNKNOWN_SOURCE_IDENTITY),
        )

    @classmethod
    def load(cls, path: Path) -> BaselineTestResult | None:
        """Load from JSON file.  Returns None if file doesn't exist.

        Raises:
            ReviewBaselineReadError: When *path* exists but is malformed
                (non-UTF-8 bytes or invalid JSON) -- a
                :class:`kernel.errors.GuardedReadError` subclass that is
                also a ``ValueError`` (D3), so existing
                ``except ValueError`` call sites keep matching. Never raised
                for a missing file (D5).
        """
        if not path.exists():
            return None
        data = read_guarded(
            path,
            json.loads,
            errors=(json.JSONDecodeError,),
            error_cls=ReviewBaselineReadError,
        )
        return cls.from_dict(data)

    def save(self, path: Path) -> None:
        """Write baseline result as JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")


def _get_test_command(repo_root: Path) -> tuple[str | None, str | None]:
    """Return configured ``(command_template, output_format)`` or ``(None, None)``.

    The command template may use ``{output_file}`` as a placeholder that will
    be substituted at runtime with the path to the parser-specific output file.
    Baseline capture is intentionally opt-in; when no command is configured,
    callers should skip baseline capture silently.
    """
    config_path = repo_root / ".kittify" / "config.yaml"
    if config_path.exists():
        try:
            from ruamel.yaml import YAML
            yaml = YAML()
            config = yaml.load(config_path)
            if config:
                review_config = config.get("review", {}) or {}
                if "test_command" in review_config:
                    return (
                        review_config["test_command"],
                        review_config.get("test_output_format", "junit_xml"),
                    )
        except Exception as exc:
            logger.warning("Could not read config.yaml: %s", exc)

    return (None, None)


def _parse_junit_xml(junit_xml_path: Path) -> tuple[int, int, int, int, list[BaselineFailure]]:
    """Parse a JUnit XML file and return (total, passed, failed, skipped, failures).

    Handles nested <testsuite> elements via ``root.iter("testcase")``.
    """
    tree = ET.parse(str(junit_xml_path))  # nosec B314 — XML comes from local test-runner output, not network input
    root = tree.getroot()

    failures: list[BaselineFailure] = []
    total = passed = failed = skipped = 0

    for testcase in root.iter("testcase"):
        total += 1
        failure_el = testcase.find("failure")
        error_el = testcase.find("error")
        skip_el = testcase.find("skipped")

        if failure_el is not None or error_el is not None:
            failed += 1
            active_el = failure_el if failure_el is not None else error_el
            assert active_el is not None
            msg = active_el.get("message", "Unknown error") or ""
            # Truncate to one line, max 200 chars
            msg = msg.split("\n")[0][:200]
            classname = testcase.get("classname", "") or ""
            name = testcase.get("name", "") or ""
            test_name = f"{classname}.{name}" if classname else name
            file_attr = testcase.get("file", "unknown") or "unknown"
            line_attr = testcase.get("line", "?") or "?"
            failures.append(BaselineFailure(
                test=test_name,
                error=msg,
                file=f"{file_attr}:{line_attr}",
            ))
        elif skip_el is not None:
            skipped += 1
        else:
            passed += 1

    return total, passed, failed, skipped, failures


def _resolve_base_commit(repo_root: Path, base_branch: str) -> str | None:
    """``git rev-parse base_branch`` -> commit SHA, or ``None`` on any failure.

    Shared by both baseline-capture paths (config-driven and
    ``ScopeSource``-driven): a failure (rev-parse raised or exited non-zero) is
    logged and reported as ``None`` so the caller emits its sentinel result.
    """
    try:
        rev_result = subprocess.run(
            ["git", "rev-parse", base_branch],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.warning("git rev-parse failed: %s", exc)
        return None
    if rev_result.returncode != 0:
        logger.warning("Could not resolve base branch %s: %s", base_branch, rev_result.stderr)
        return None
    return rev_result.stdout.strip()


@contextmanager
def _baseline_worktree(repo_root: Path, base_branch: str) -> Iterator[Path | None]:
    """Own a detached baseline worktree on ``base_branch`` for the block's lifetime.

    Adds ``.../baseline-worktree`` under a private ``TemporaryDirectory`` on
    ``base_branch`` (detached), yields its path, and ALWAYS removes it on exit
    (``git worktree remove --force``). On an add failure the sentinel value
    ``None`` is yielded instead of raising, so the caller emits its own
    sentinel result — the shared scaffolding both capture paths hand-rolled.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_worktree = Path(tmp_dir) / "baseline-worktree"
        try:
            wt_result = subprocess.run(
                ["git", "worktree", "add", str(tmp_worktree), base_branch, "--detach"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            logger.warning("git worktree add failed: %s", exc)
            yield None
            return
        if wt_result.returncode != 0:
            logger.warning("Could not create baseline worktree for %s: %s", base_branch, wt_result.stderr)
            yield None
            return
        try:
            yield tmp_worktree
        finally:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", str(tmp_worktree), "--force"],
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError as exc:
                logger.warning("Could not remove temporary worktree: %s", exc)


def capture_baseline(
    worktree_path: Path,
    base_branch: str,
    wp_id: str,
    mission_slug: str,
    feature_dir: Path,
    wp_slug: str,
    test_command: str | None = None,
    scope_source: ScopeSource | None = None,
) -> BaselineTestResult | None:
    """Capture baseline test results at implement time.

    Creates a temporary git worktree on the base branch, runs the test
    suite, parses JUnit XML output, and saves the result to
    ``feature_dir/tasks/{wp_slug}/baseline-tests.json``.

    Returns the BaselineTestResult on success, or a sentinel result
    (``failed=-1``) if the test suite cannot be run.  Returns the cached
    result if the artifact already exists.

    Args:
        worktree_path: Path to the execution worktree (used to find repo root).
        base_branch: The git branch to run tests against.
        wp_id: Work package ID (e.g. "WP04").
        mission_slug: Mission slug (e.g. "066-review-loop-stabilization").
        feature_dir: Path to the feature directory in kitty-specs/.
        wp_slug: Slug of the WP task file (e.g. "WP04-baseline-test-capture").
        test_command: Optional override for the test command.  If None, reads
            from config; without config, baseline capture is skipped.
        scope_source: Optional injected ``ScopeSource`` (mission
            ``doctrine-controlled-transition-gates-01KY51Z7`` WP03, FR-011).
            When provided, baseline capture routes through its
            ``test_command()``/``parse_results()`` — the SAME authority the
            pre-review head run uses — instead of independently reading
            ``review.test_command`` from config (see
            :func:`_capture_baseline_via_scope_source`). ``None`` (the
            default) preserves this function's exact prior, config-driven
            behaviour.
    """
    artifact_dir = feature_dir / "tasks" / wp_slug
    artifact_path = artifact_dir / "baseline-tests.json"

    # Return cached result if it already exists (idempotent)
    cached = BaselineTestResult.load(artifact_path)
    if cached is not None:
        logger.info("Baseline already captured for %s — skipping re-capture.", wp_id)
        return cached

    # Locate repo root (parent of .git)
    repo_root = _find_repo_root(worktree_path)
    if repo_root is None:
        logger.warning("Could not find repo root from %s; skipping baseline capture.", worktree_path)
        return _make_sentinel(wp_id, base_branch, "")

    if scope_source is not None:
        return _capture_baseline_via_scope_source(
            scope_source,
            repo_root=repo_root,
            base_branch=base_branch,
            wp_id=wp_id,
            artifact_path=artifact_path,
        )

    return _capture_baseline_via_config(
        repo_root,
        base_branch=base_branch,
        wp_id=wp_id,
        test_command=test_command,
        artifact_path=artifact_path,
    )


def _capture_baseline_via_config(
    repo_root: Path,
    *,
    base_branch: str,
    wp_id: str,
    test_command: str | None,
    artifact_path: Path,
) -> BaselineTestResult | None:
    """The original, config-driven capture body (unchanged behaviour):
    resolves ``review.test_command`` from ``.kittify/config.yaml`` (unless
    an explicit override is given), runs it in a detached worktree on
    ``base_branch``, and parses its JUnit XML output. Extracted out of
    :func:`capture_baseline` so that function stays a thin dispatcher
    between this path and :func:`_capture_baseline_via_scope_source`
    (keeps both at or under the project's complexity ceiling).
    """
    # Determine test command
    if test_command is None:
        test_command, output_format = _get_test_command(repo_root)
    else:
        output_format = "junit_xml"

    if not test_command:
        logger.info("No review.test_command configured; skipping baseline capture for %s.", wp_id)
        return None

    if output_format != "junit_xml":
        logger.info(
            "Baseline capture configured with unsupported output format %r; skipping baseline capture for %s.",
            output_format,
            wp_id,
        )
        return None

    # Resolve base commit hash
    base_commit = _resolve_base_commit(repo_root, base_branch)
    if base_commit is None:
        return _make_sentinel(wp_id, base_branch, "")

    with _baseline_worktree(repo_root, base_branch) as tmp_worktree:
        if tmp_worktree is None:
            return _make_sentinel(wp_id, base_branch, base_commit)
        # JUnit output lives beside the worktree (same private temp dir).
        junit_xml_path = tmp_worktree.parent / "junit.xml"

        try:
            run_result = run_configured_command_template(
                test_command,
                {"output_file": junit_xml_path},
                cwd=str(tmp_worktree),
                capture_output=True,
                text=True,
                check=False,
                timeout=CAPTURE_BASELINE_TIMEOUT_SECONDS,
            )
        except ConfiguredCommandUnsupported as exc:
            logger.warning("Test command is not supported on this platform: %s", exc)
            return _make_sentinel(wp_id, base_branch, base_commit)
        except Exception as exc:
            logger.warning("Test command failed to execute: %s", exc)
            return _make_sentinel(wp_id, base_branch, base_commit)

        # Parse JUnit XML (test runners often exit non-zero when tests fail — that's OK)
        if not junit_xml_path.exists():
            logger.warning(
                "JUnit XML not produced by baseline test run (exit=%d). stderr: %s",
                run_result.returncode,
                run_result.stderr[:500],
            )
            return _make_sentinel(wp_id, base_branch, base_commit)

        try:
            total, passed, failed, skipped, failures = _parse_junit_xml(junit_xml_path)
        except Exception as exc:
            logger.warning("Failed to parse JUnit XML: %s", exc)
            return _make_sentinel(wp_id, base_branch, base_commit)

    # Build result
    result = BaselineTestResult(
        wp_id=wp_id,
        captured_at=now_utc_stamp(),
        base_branch=base_branch,
        base_commit=base_commit,
        test_runner="pytest" if "pytest" in test_command else "custom",
        total=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        failures=tuple(failures),
    )
    result.save(artifact_path)
    return result


# ---------------------------------------------------------------------------
# Port-driven baseline capture (mission doctrine-controlled-transition-gates-01KY51Z7
# WP03, FR-011) — baseline capture via the injected ScopeSource, the SAME
# test_command()/parse_results() authority the pre-review head run uses, so
# baseline<->head symmetry is structural rather than two independently
# resolved commands. This is additive: capture_baseline's existing,
# config-driven body above (test_command is None -> _get_test_command) is
# untouched — this path only engages when a caller explicitly injects a
# scope_source.
# ---------------------------------------------------------------------------


def _extract_junit_output_path(command: Sequence[str]) -> Path | None:
    """Best-effort recovery of a ``--junitxml=<path>`` argument embedded in a
    ``ScopeSource``-provided argv, so a raw run's JUnit artifact (when the
    resolved command happens to write one) can be handed to
    ``parse_results`` without the port needing a dedicated accessor for it.
    ``None`` when absent (e.g. a declared, non-JUnit command).
    """
    for arg in command:
        if arg.startswith("--junitxml="):
            return Path(arg.split("=", 1)[1])
    return None


def _run_command_for_baseline(command: list[str], *, cwd: Path) -> RawRunResult:
    """Run a ``ScopeSource``-resolved command for baseline capture, producing
    a :class:`RawRunResult` — the same UNPARSED shape the pre-review head
    run produces (FR-011 symmetry) — for ``scope_source.parse_results``.

    B1 fix (FR-008): a ``--junitxml=<relative path>`` embedded in a
    ``DeclaredCommandScopeSource``-resolved command resolves against the
    subprocess's ``cwd`` (the baseline worktree), NOT this process's own
    working directory. Anchoring the extracted path to ``cwd`` here — while
    the caller still holds the worktree open — is what makes the artifact
    locatable at all; without it, ``raw.output_artifact_path.exists()``
    would check a path relative to the wrong directory regardless of when
    ``parse_results`` runs. Absolute ``--junitxml`` paths are used as-is.

    Issue #3612 fast-follow (regression review finding, post-#3612):
    ``DeclaredCommandScopeSource.test_command()`` now renders a ``["sh",
    "-c", "export ...; <command>"]`` COMPOUND statement (the #3612 shell +
    ``{output_file}`` fix) — ``sh`` forks the real command as its OWN child,
    so a bare ``subprocess.run(..., timeout=...)`` here would SIGKILL only
    ``sh`` on timeout, orphaning the real command as a grandchild that keeps
    running (with its cwd inside the baseline worktree) after
    ``_baseline_worktree``'s ``finally`` removes that very worktree out from
    under it. Delegates to the head runner's OWN tested scoped-launch +
    reap machinery (:func:`pre_review_gate._run_raw_command`, itself
    ``_launch_scoped_process`` + ``_observe_process``) instead of
    hand-replicating ``start_new_session``/``os.killpg`` here — one
    group-safe launcher for both capture and head, so they cannot re-drift.
    Lazy import: ``pre_review_gate.py`` imports FROM this module at its own
    top level (``CAPTURE_BASELINE_TIMEOUT_SECONDS``, ``_parse_junit_xml``,
    ...), so a module-level import here would be a two-way cycle.
    """
    from specify_cli.review.pre_review_gate import HeadRunState, _default_process_wait, _run_raw_command

    junit_path = _extract_junit_output_path(command)
    if junit_path is not None and not junit_path.is_absolute():
        junit_path = cwd / junit_path

    state, raw, error = _run_raw_command(
        command,
        repo_root=cwd,
        timeout=CAPTURE_BASELINE_TIMEOUT_SECONDS,
        progress_callback=None,
        monotonic=time.monotonic,
        wait=_default_process_wait,
    )
    if state is HeadRunState.TIMED_OUT:
        return RawRunResult(
            returncode=-1,
            stdout="",
            stderr=f"baseline command timed out after {CAPTURE_BASELINE_TIMEOUT_SECONDS}s",
            output_artifact_path=junit_path,
        )
    if state is HeadRunState.CANCELLED:
        return RawRunResult(
            returncode=-1,
            stdout="",
            stderr=f"baseline command cancelled: {error}",
            output_artifact_path=junit_path,
        )
    if state is HeadRunState.LAUNCH_FAILED:
        return RawRunResult(
            returncode=-1,
            stdout="",
            stderr=f"baseline command failed to execute: {error}",
            output_artifact_path=junit_path,
        )
    assert raw is not None  # guaranteed by _run_raw_command for every non-{TIMED_OUT,CANCELLED,LAUNCH_FAILED} state
    return raw


def _capture_baseline_via_scope_source(
    scope_source: ScopeSource,
    *,
    repo_root: Path,
    base_branch: str,
    wp_id: str,
    artifact_path: Path,
) -> BaselineTestResult | None:
    """FR-011: baseline capture via the injected ``ScopeSource`` — the SAME
    ``test_command()``/``parse_results()`` authority the pre-review head run
    uses, so baseline<->head symmetry is structural. Opt-in-and-visible: no
    command resolved via the port -> skip, mirroring the config-driven
    path's "No review.test_command configured" notice (FR-012) — never a
    crash, never a silently fabricated baseline.

    B1 fix (FR-008, data-model.md sec. 5): ``parse_results`` — and the
    ``source_identity`` derived from the SAME raw result via
    ``scope_source_identity`` — run INSIDE the ``with _baseline_worktree``
    block, before teardown. A ``DeclaredCommandScopeSource``'s
    worktree-relative ``--junitxml`` artifact (now anchored to ``cwd`` by
    :func:`_run_command_for_baseline`) only exists while the worktree is
    still alive; parsing after the block exited (the prior, buggy ordering)
    silently lost it, degrading every declared-command baseline failure to
    the generic whole-run synthetic placeholder.
    """
    command = scope_source.test_command()
    if not command:
        logger.info(
            "No test command resolved via the injected ScopeSource; skipping baseline capture for %s.", wp_id,
        )
        return None

    base_commit = _resolve_base_commit(repo_root, base_branch)
    if base_commit is None:
        return _make_sentinel(wp_id, base_branch, "")

    with _baseline_worktree(repo_root, base_branch) as tmp_worktree:
        if tmp_worktree is None:
            return _make_sentinel(wp_id, base_branch, base_commit)
        raw = _run_command_for_baseline(command, cwd=tmp_worktree)
        failures = tuple(scope_source.parse_results(raw))
        source_identity = scope_source_identity(scope_source, raw)

    # Issue #3612 (refuse-not-store): a "text"-mode run with NO parseable
    # per-failure identity and a clean (zero) exit is genuinely ambiguous —
    # unlike GateCoverageScopeSource (always junit_xml, always a REAL parsed
    # count) or a text-mode run that ended non-zero (parse_results always
    # surfaces at least one whole-run failure for that case, never empty),
    # this specific combination cannot distinguish "a suite of zero tests
    # ran cleanly" from "the declared command produced nothing this capture
    # could verify at all". Storing it as total=0/passed=0/failed=0 would be
    # a FABRICATED clean baseline — refuse to store it; the sentinel makes
    # the gate treat it as UNVERIFIED_BASELINE instead of verified-clean.
    if not failures and source_identity.rsplit("/", 1)[-1] == "text":
        logger.warning(
            "Declared test command exited cleanly but produced no verifiable "
            "output (no JUnit artifact, no parseable failure line) for %s; "
            "refusing to store an ambiguous zero-failure baseline.",
            wp_id,
        )
        return _make_sentinel(wp_id, base_branch, base_commit)

    # NOTE (issue #3612, documented rather than redesigned — see PR notes):
    # total/passed below are DERIVED from the failure count, not real suite
    # counts. Unlike the legacy config-driven path (_capture_baseline_via_config,
    # which parses REAL total/passed/skipped out of JUnit XML), the
    # ScopeSource.parse_results() port only returns per-failure identities —
    # it has no channel to report suite size. A junit_xml-mode declared
    # command with a real artifact DOES have real total/passed/skipped
    # available (parse_results computes them internally) but they are
    # discarded before reaching here. Fixing this fully would mean widening
    # the ScopeSource port (an optional richer-capability refinement, the
    # same pattern as ScopeBreakdownSource) — out of scope for this fix;
    # flagged for a follow-up rather than silently left unexplained.
    result = BaselineTestResult(
        wp_id=wp_id,
        captured_at=now_utc_stamp(),
        base_branch=base_branch,
        base_commit=base_commit,
        test_runner="pytest" if any("pytest" in part for part in command) else "custom",
        total=len(failures),
        passed=0,
        failed=len(failures),
        skipped=0,
        failures=failures,
        source_identity=source_identity,
    )
    result.save(artifact_path)
    return result


def load_baseline(path: Path) -> BaselineTestResult | None:
    """Convenience wrapper — delegates to BaselineTestResult.load()."""
    return BaselineTestResult.load(path)


def diff_baseline(
    baseline: BaselineTestResult,
    current_failures: list[BaselineFailure],
) -> tuple[list[BaselineFailure], list[BaselineFailure], list[str]]:
    """Compare baseline failures against current failures.

    Args:
        baseline: The pre-captured baseline result.
        current_failures: List of failures from the current test run.

    Returns:
        A 3-tuple of:
          - pre_existing: failures that existed in the baseline
          - new_failures: failures NOT in baseline (regressions)
          - fixed: test names that failed in baseline but pass now
    """
    # Sentinel baseline: no baseline data — treat everything as new
    if baseline.failed == -1:
        return [], list(current_failures), []

    baseline_test_names = {f.test for f in baseline.failures}
    current_test_names = {f.test for f in current_failures}

    pre_existing: list[BaselineFailure] = []
    new_failures: list[BaselineFailure] = []

    for failure in current_failures:
        if failure.test in baseline_test_names:
            pre_existing.append(failure)
        else:
            new_failures.append(failure)

    fixed: list[str] = [
        f.test for f in baseline.failures if f.test not in current_test_names
    ]

    return pre_existing, new_failures, fixed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_repo_root(start: Path) -> Path | None:
    """Walk up from start until we find a .git directory or file."""
    current = start.resolve()
    for _ in range(20):  # limit depth
        git_path = current / ".git"
        if git_path.is_file() or (git_path.is_dir() and (git_path / "HEAD").is_file()):
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _make_sentinel(wp_id: str, base_branch: str, base_commit: str) -> BaselineTestResult:
    """Return a sentinel BaselineTestResult indicating capture failure."""
    return BaselineTestResult(
        wp_id=wp_id,
        captured_at=now_utc_stamp(),
        base_branch=base_branch,
        base_commit=base_commit,
        test_runner="pytest",
        total=0,
        passed=0,
        failed=-1,
        skipped=0,
        failures=(),
    )
