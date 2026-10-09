"""Tests for specify_cli.review.pre_review_gate — WP01: scope derivation +
head-side runner + verdict engine (mission review-regression-gate-01KWX6DF).

Scope-derivation cases below use INJECTED ``filter_groups``/``composite_routing``
fixtures (offline, no repo I/O) so they stay hermetic and fast — the proof that
the derivation reads the LIVE authorities lives in
``tests/architectural/test_pre_review_scope_singlesource.py`` (FR-006), not
here. The fixtures below deliberately mirror the real ci-quality.yml shapes
(status/core_misc/execution_context overlap; auth_audit_git/governance
composites) so the shape + exclusion assertions still pin the real-world
scenarios named in the spec (SC-003/SC-004/SC-007), just against a stable,
hand-built substrate instead of the live workflow file.
"""

from __future__ import annotations

import contextlib
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.review import baseline as baseline_module
from specify_cli.review import pre_review_gate
from specify_cli.review.baseline import BaselineFailure, BaselineTestResult
from specify_cli.review.gate_budget import BudgetClassification, ScopeBudgetAssessment, ScopeIdentity
from specify_cli.review.pre_review_gate import (
    GateOutcome,
    HeadRunResult,
    HeadRunState,
    ScopeResult,
)
from specify_cli.review.baseline import _parse_junit_xml
from specify_cli.review.scope_source import DeclaredCommandScopeSource, FileScopeBreakdown, RawRunResult

# Module-level marker required by tests/architectural/test_pytest_marker_convention.py
# (WP01 landed this file without one — a pre-existing arch-gate red this WP02 sweep
# surfaced and Boy-Scout-fixes here). ``integration`` (not ``fast``) is the correct
# choice: the file's per-function markers stay authoritative and additive under it
# (the 18 ``@pytest.mark.fast`` cases remain selected by the fast-tests-review shard's
# ``-m "fast and not windows_ci"``), while ``integration`` keeps the 3 real-subprocess
# tests (``run_scoped_tests_at_head`` spawns real pytest) OUT of the fast lane — a
# module-level ``fast`` would have wrongly dragged them in.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Synthetic filter-group / composite-routing fixtures (mirror the real
# ci-quality.yml shapes closely enough to pin SC-003/SC-004/SC-007 offline).
# ---------------------------------------------------------------------------

FAKE_GROUPS: dict[str, tuple[str, ...]] = {
    "status": (
        "src/specify_cli/status/**",
        "tests/status/**",
        "tests/specify_cli/status/**",
    ),
    "core_misc": (
        "src/specify_cli/status/**",
        "src/kernel/**",
        "tests/architectural/**",
        "tests/integration/**",
        "tests/contract/**",
    ),
    "execution_context": (
        "src/specify_cli/status/**",
        "tests/architectural/test_execution_context_parity.py",
    ),
    "any_src": ("src/**",),
    "e2e": ("tests/e2e/**",),
    "auth_audit_git": (
        "src/specify_cli/auth/**",
        "src/specify_cli/audit/**",
        "src/specify_cli/git/**",
    ),
    "governance": (
        "src/specify_cli/validators/**",
        "src/specify_cli/charter_packs/**",
    ),
}

FAKE_ROUTING: dict[str, pre_review_gate._CompositeRoute] = {
    "git": (None, None, ("tests/git", "tests/git_ops")),
    "validators": (None, None, ()),
}

_DUMMY_ROOT = Path(".")


@dataclass
class _NarrowingScopeSource:
    repo_root: Path

    treats_empty_scope_as_coverage_gap: bool = True

    def test_command(self) -> list[str] | None:
        junit_path = Path(tempfile.mkdtemp(prefix="spec-kitty-test-narrowing-")) / "pre-review-junit.xml"
        return [sys.executable, "-m", "pytest", f"--junitxml={junit_path}", "-q"]

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        return self.scope_breakdown(path).test_targets

    def scope_breakdown(self, path: str) -> FileScopeBreakdown:
        if path == "src/specify_cli/status/emit.py":
            return FileScopeBreakdown(
                test_targets=(
                    "tests/architectural/test_execution_context_parity.py",
                    "tests/specify_cli/status",
                    "tests/status",
                ),
                matched_shard_groups=("execution_context", "status"),
            )
        if path == "src/specify_cli/git/foo.py":
            return FileScopeBreakdown(
                test_targets=("test_sample.py",),
                matched_composite_dirs=("git",),
            )
        if path == "src/specify_cli/validators/schema.py":
            return FileScopeBreakdown(
                matched_composite_dirs=("validators",),
                empty_cone_composite_dirs=("validators",),
            )
        return FileScopeBreakdown(contributes_scope=False)

    def parse_mode(self, _raw: RawRunResult) -> str:
        return "junit_xml"

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:
        artifact = raw.output_artifact_path
        if artifact is None or not artifact.exists():
            return (
                BaselineFailure(
                    test="<test-narrowing-junit>",
                    error="no JUnit XML artifact produced by the scoped run",
                    file="unknown",
                ),
            )
        _total, _passed, _failed, _skipped, failures = _parse_junit_xml(artifact)
        return tuple(failures)


# ---------------------------------------------------------------------------
# Mission pre-review-gate-operator-flow WP02: budget-authoritative engine seam
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_oversized_override_refuses_before_process_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The explicit-override route refuses an exact oversized atom pre-launch."""

    def _launch_boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("oversized scope must not create a process")

    monkeypatch.setattr(pre_review_gate, "_launch_scoped_process", _launch_boom)
    events: list[object] = []

    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override(("tests/architectural",)),
        repo_root=_DUMMY_ROOT,
        baseline=None,
        status_observer=events.append,
    )

    assert verdict.outcome.value == "scope_oversized"
    assert verdict.run_state.value == "not_started"
    assert verdict.budget_assessment is not None
    assert verdict.budget_assessment.classification is BudgetClassification.OVERSIZED
    assert verdict.classification_candidate is False
    assert len(events) == 1
    assert isinstance(events[0], pre_review_gate.ScopeAssessed)


@pytest.mark.fast
def test_unknown_scope_runs_and_emits_typed_scope_then_heartbeat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown metadata is advisory: the incumbent runner still executes."""
    callbacks: list[object] = []

    def _run(*args: object, **kwargs: object) -> HeadRunResult:
        progress = kwargs["progress_callback"]
        assert callable(progress)
        progress(31.25)
        return HeadRunResult(ran=True)

    monkeypatch.setattr(pre_review_gate, "run_scoped_tests_at_head", _run)
    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override(("tests/review/test_small.py",)),
        repo_root=_DUMMY_ROOT,
        baseline=_make_baseline(),
        status_observer=callbacks.append,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.budget_assessment is not None
    assert verdict.budget_assessment.classification is BudgetClassification.UNKNOWN
    assert isinstance(callbacks[0], pre_review_gate.ScopeAssessed)
    assert callbacks[1] == pre_review_gate.Heartbeat(phase="candidate_head", observed_elapsed_seconds=31.25)


@pytest.mark.fast
def test_unknown_timeout_is_classification_candidate_with_separate_elapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only an unknown timeout carries immutable-policy follow-up evidence."""
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *args, **kwargs: HeadRunResult(
            ran=False,
            error="timed out",
            state=HeadRunState.TIMED_OUT,
            observed_elapsed_seconds=12.75,
        ),
    )

    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override(("tests/review/test_small.py",)),
        repo_root=_DUMMY_ROOT,
        baseline=None,
        timeout=10,
    )

    assert verdict.outcome is GateOutcome.TIMED_OUT
    assert verdict.classification_candidate is True
    assert verdict.observed_elapsed_seconds == 12.75
    assert verdict.budget_assessment is not None
    assert verdict.budget_assessment.effective_budget_seconds == 10.0
    assert verdict.budget_assessment.scope_identity.value in (verdict.reason or "")
    assert "lane remains unchanged" in (verdict.reason or "")
    assert "reviewed metadata update" in (verdict.reason or "")


@pytest.mark.fast
def test_bounded_timeout_is_not_a_classification_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A timeout cannot auto-promote already-bounded deterministic metadata."""
    bounded = ScopeBudgetAssessment(
        classification=BudgetClassification.BOUNDED,
        scope_identity=ScopeIdentity(
            normalized_targets=("tests/review/test_small.py",),
            policy_namespace="spec-kitty.pre-review-budget/v1",
            value="budget-v1:sha256:bounded-fixture",
        ),
        effective_budget_seconds=10,
        matched_rule_id="bounded-fixture",
        evidence="synthetic bounded acceptance fixture",
        guidance="run",
    )
    monkeypatch.setattr(pre_review_gate, "assess_scope_budget", lambda *args: bounded)
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *args, **kwargs: HeadRunResult(
            ran=False,
            error="timed out",
            state=HeadRunState.TIMED_OUT,
            observed_elapsed_seconds=12.75,
        ),
    )

    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override(("tests/review/test_small.py",)),
        repo_root=_DUMMY_ROOT,
        baseline=None,
        timeout=10,
    )

    assert verdict.outcome is GateOutcome.TIMED_OUT
    assert verdict.classification_candidate is False
    assert verdict.observed_elapsed_seconds == 12.75


def test_bounded_fixture_completes_under_incumbent_runner() -> None:
    """Source-controlled bounded metadata permits a real candidate run."""
    target = "tests/review/test_gate_budget.py::test_identity_matches_pinned_vector"

    verdict = pre_review_gate.evaluate_with_scope(
        ScopeResult.from_override((target,)),
        repo_root=_DUMMY_ROOT,
        baseline=_make_baseline(),
        timeout=30,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.run_state is HeadRunState.COMPLETED
    assert verdict.budget_assessment is not None
    assert verdict.budget_assessment.classification is BudgetClassification.BOUNDED
    assert verdict.budget_assessment.scope_identity.normalized_targets == (target,)
    assert verdict.budget_assessment.effective_budget_seconds == 30
    assert verdict.budget_assessment.matched_rule_id == "spec-kitty-gate-budget-pinned-vector"
    assert verdict.classification_candidate is False


# ---------------------------------------------------------------------------
# WP03 (mission doctrine-controlled-transition-gates-01KY51Z7) — T014 migration
# of the probe tests above: ``_is_spec_kitty_source_repo`` and
# ``_load_gate_coverage_module`` are gone from the engine. ``GateAuthoritiesUnavailable``
# itself stays here for compatibility with callers that still catch it.
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_probe_and_loader_are_private_internals_of_the_port_not_the_engine() -> None:
    """T014: the source-repo probe and its live-authority loader are no
    longer public (or even present) on ``pre_review_gate`` — they are
    no longer public (or present) on ``pre_review_gate``."""
    assert not hasattr(pre_review_gate, "_is_spec_kitty_source_repo")
    assert not hasattr(pre_review_gate, "_load_gate_coverage_module")
    assert not hasattr(pre_review_gate, "_default_filter_groups")
    assert not hasattr(pre_review_gate, "_default_composite_routing")


@pytest.mark.fast
def test_gate_authorities_unavailable_is_consumer_repo_field_still_works() -> None:
    """B3 (post-task squad): ``GateAuthoritiesUnavailable`` and its
    ``is_consumer_repo`` field stay on this module — WP09's
    ``tasks_move_task.py`` reader depends on it until that WP's
    hook-inversion lands; only the probe/loader that PRODUCED it moved."""
    exc = pre_review_gate.GateAuthoritiesUnavailable("boom", is_consumer_repo=True)
    assert exc.is_consumer_repo is True
    assert str(exc) == "boom"


@pytest.mark.fast
def test_scope_source_seam_is_injected_not_selected_by_repo_shape(tmp_path: Path) -> None:
    """T013: the engine accepts an ARBITRARY injected ``ScopeSource`` — a
    completely custom stub, not ``GateCoverageScopeSource`` or
    ``DeclaredCommandScopeSource`` — and drives evaluation through it. It
    performs no repo-shape probing of its own to pick an implementation;
    that decision is deferred entirely to the caller (WP09's future
    activation-driven hook)."""

    class _StubScopeSource:
        def test_command(self) -> list[str] | None:
            return None

        def file_to_scope(self, path: str) -> tuple[str, ...]:
            del path
            return ()

        def parse_results(self, raw: object) -> tuple[BaselineFailure, ...]:
            del raw
            return ()

    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["src/anything.py"],
        repo_root=tmp_path,
        baseline=None,
        scope_source=_StubScopeSource(),
    )

    assert verdict.outcome is GateOutcome.NO_COVERAGE
    assert "no test command configured" in (verdict.reason or "")


def _derive(changed_files: list[str]) -> ScopeResult:
    """Drive the SURVIVING ``pre_review_gate`` composition
    (``_scope_result_from_source`` / ``_scope_result_from_breakdown``) over a
    narrowing source with hermetic fixtures — migrated
    (mission scopesource-gate-followup-01KY6S9P WP04) off the retired
    ``derive_test_scope`` census tier, which this module no longer owns.
    """
    source = _NarrowingScopeSource(repo_root=_DUMMY_ROOT)
    return pre_review_gate._scope_result_from_source(source, changed_files)


# ---------------------------------------------------------------------------
# Scope derivation: per-shard shape (FR-002/SC-003)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_per_shard_group_contributes_its_own_test_globs_and_excludes_core_misc() -> None:
    """status/emit.py-shaped file: member of status (focused, per-shard),
    core_misc (catch-all, excluded), and execution_context (focused,
    per-shard) — mirrors the spec's own grounding example."""
    scope = _derive(["src/specify_cli/status/emit.py"])
    assert set(scope.test_targets) == {
        "tests/status",
        "tests/specify_cli/status",
        "tests/architectural/test_execution_context_parity.py",
    }
    assert set(scope.matched_shard_groups) == {"status", "execution_context"}
    assert "core_misc" not in scope.matched_shard_groups
    assert not scope.is_empty


@pytest.mark.fast
def test_recall_over_precision_ambiguous_file_gets_every_focused_group() -> None:
    """An ambiguous file matching >=2 focused groups gets BOTH — no attempt
    to pick a single "best" group (recall > precision, spec edge case)."""
    scope = _derive(["src/specify_cli/status/emit.py"])
    assert {"status", "execution_context"} <= set(scope.matched_shard_groups)


# ---------------------------------------------------------------------------
# Scope derivation: composite shape (FR-002/SC-003/SC-007)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_composite_group_with_nonempty_cone_contributes_cone_roots() -> None:
    """A git/**-shaped change resolves via the composite dir's cone_roots,
    not any dorny test glob (auth_audit_git carries none)."""
    scope = _derive(["src/specify_cli/git/foo.py"])
    assert set(scope.test_targets) == {"test_sample.py"}
    assert scope.matched_composite_dirs == ("git",)
    assert not scope.matched_shard_groups
    assert not scope.is_empty


@pytest.mark.fast
def test_composite_group_with_empty_cone_is_a_no_coverage_warn_not_clean() -> None:
    """SC-007: validators is a real composite dir with an EMPTY committed
    cone — the derivation must surface it as unverified, never silently
    "clean"."""
    scope = _derive(["src/specify_cli/validators/schema.py"])
    assert scope.is_empty
    assert scope.empty_cone_composite_dirs == ("validators",)
    assert "unmapped composite dir" in scope.describe_empty_reason()


# ---------------------------------------------------------------------------
# Scope derivation: catch-all / unmatched exclusion (FR-005)
# ---------------------------------------------------------------------------


@pytest.mark.fast
def test_catch_all_only_file_is_excluded_and_scope_warns() -> None:
    """A file landing ONLY in a catch-all group (here: core_misc via
    src/kernel/**) contributes nothing — excluded, not a whole-tree run."""
    scope = _derive(["src/kernel/foo.py"])
    assert scope.is_empty
    assert scope.excluded_scope_files == ("src/kernel/foo.py",)
    assert "excluded scope" in scope.describe_empty_reason()


@pytest.mark.fast
def test_unmatched_file_is_excluded_and_scope_warns() -> None:
    """A file matching NO dorny group at all is excluded the same way."""
    scope = _derive(["README.md"])
    assert scope.is_empty
    assert scope.excluded_scope_files == ("README.md",)


@pytest.mark.fast
def test_describe_empty_reason_distinguishes_the_two_sc007_causes() -> None:
    empty_cone_scope = ScopeResult(
        test_targets=(),
        matched_shard_groups=(),
        matched_composite_dirs=("validators",),
        empty_cone_composite_dirs=("validators",),
        excluded_scope_files=(),
    )
    excluded_scope = ScopeResult(
        test_targets=(),
        matched_shard_groups=(),
        matched_composite_dirs=(),
        empty_cone_composite_dirs=(),
        excluded_scope_files=("README.md",),
    )
    assert "unmapped composite dir" in empty_cone_scope.describe_empty_reason()
    assert "excluded scope" in excluded_scope.describe_empty_reason()


# ---------------------------------------------------------------------------
# Injected-ScopeSource ScopeResult reconstruction (metadata fidelity, NFR-001)
# — mission ``doctrine-controlled-transition-gates-01KY51Z7`` WP09 remediation:
# the inverted hook builds the ScopeResult from the port; a census-narrowing
# source must reconstruct the FULL shard/composite breakdown, byte-identical to
# ``derive_test_scope``, or the transition metadata silently loses its shard
# groups.
# ---------------------------------------------------------------------------


def _narrowing_source() -> _NarrowingScopeSource:
    return _NarrowingScopeSource(repo_root=_DUMMY_ROOT)


@pytest.mark.fast
def test_scope_result_from_source_reconstructs_full_breakdown_for_narrowing_source() -> None:
    """A narrowing source rebuilds the FULL ``ScopeResult``
    breakdown — shard groups, empty-cone composite dirs, and excluded files, not
    just a flat target union (NFR-001). Pinned via literal expectations (mission
    scopesource-gate-followup-01KY6S9P WP04 retired the ``derive_test_scope``
    oracle this test used to diff against — the pre-fix flat reconstruction
    dropped ``matched_shard_groups``, which is exactly what these literals pin)."""
    changed = ["src/specify_cli/status/emit.py", "src/specify_cli/validators/schema.py", "README.md"]
    scope = pre_review_gate._scope_result_from_source(_narrowing_source(), changed)

    assert set(scope.matched_shard_groups) == {"status", "execution_context"}
    assert "core_misc" not in scope.matched_shard_groups
    assert scope.empty_cone_composite_dirs == ("validators",)
    assert scope.excluded_scope_files == ("README.md",)
    assert set(scope.test_targets) == {
        "tests/status",
        "tests/specify_cli/status",
        "tests/architectural/test_execution_context_parity.py",
    }


@pytest.mark.fast
def test_scope_result_from_source_stays_flat_for_non_narrowing_source(tmp_path: Path) -> None:
    """A non-narrowing source (``DeclaredCommandScopeSource``) carries no shard
    groups by construction — its ``ScopeResult`` is the flat ``file_to_scope``
    union only, unchanged from before."""
    scope = pre_review_gate._scope_result_from_source(
        DeclaredCommandScopeSource(repo_root=tmp_path),
        ["anything/at/all.rb"],
    )

    assert scope.test_targets == ()
    assert scope.matched_shard_groups == ()
    assert scope.matched_composite_dirs == ()
    assert scope.excluded_scope_files == ()


@pytest.mark.fast
def test_narrowing_source_empty_scope_is_no_coverage_not_a_whole_suite_run() -> None:
    """An empty derived scope from a narrowing source is a ``no_coverage`` warn
    (the incumbent ``describe_empty_reason`` wording), never a silent whole-suite
    run through the inverted hook. Returns BEFORE any subprocess/test_command."""
    impl = _narrowing_source()
    empty_scope = pre_review_gate._scope_result_from_source(impl, ["src/specify_cli/validators/schema.py"])
    assert empty_scope.is_empty

    verdict = pre_review_gate.evaluate_with_scope(
        empty_scope,
        repo_root=_DUMMY_ROOT,
        baseline=None,
        scope_source=impl,
    )

    assert verdict.outcome is GateOutcome.NO_COVERAGE
    assert "unmapped composite dir" in (verdict.reason or "")


# ---------------------------------------------------------------------------
# Head-side scoped runner (FR-001/FR-003, net-new)
# ---------------------------------------------------------------------------


_PASSING_TEST_BODY = "def test_pass():\n    assert True\n"
_FAILING_TEST_BODY = f"{_PASSING_TEST_BODY}\n\ndef test_break():\n    assert False, 'boom'\n"


def _write_tiny_pytest_project(base: Path, *, failing: bool) -> None:
    body = _FAILING_TEST_BODY if failing else _PASSING_TEST_BODY
    (base / "test_sample.py").write_text(body, encoding="utf-8")


class _FakeProcess:
    """Small ``Popen`` double for runner lifecycle tests."""

    def __init__(self, *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.pid = 424242
        self.returncode = returncode
        self.stdout_text = stdout
        self.stderr_text = stderr
        self.terminated = False
        self.killed = False

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        del timeout
        return self.stdout_text, self.stderr_text

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        self.killed = True

    def poll(self) -> int | None:
        return self.returncode


@pytest.mark.fast
def test_empty_test_targets_never_invokes_subprocess() -> None:
    result = pre_review_gate.run_scoped_tests_at_head([], repo_root=_DUMMY_ROOT)
    assert result.ran is False
    assert result.current_failures == ()
    assert "empty test scope" in (result.error or "")


@pytest.mark.fast
@pytest.mark.parametrize(
    ("platform", "expected_key"),
    [("posix", "start_new_session"), ("nt", "creationflags")],
)
def test_launch_uses_platform_process_group_isolation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform: str,
    expected_key: str,
) -> None:
    calls: list[dict[str, object]] = []
    process = _FakeProcess()

    def _popen(command: list[str], **kwargs: object) -> _FakeProcess:
        del command
        calls.append(kwargs)
        return process

    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", _popen)
    monkeypatch.setattr(
        pre_review_gate.subprocess,
        "CREATE_NEW_PROCESS_GROUP",
        512,
        raising=False,
    )

    launched = pre_review_gate._launch_scoped_process(
        ["pytest"],
        repo_root=tmp_path,
        env={},
        platform=platform,
    )

    assert launched is process
    assert len(calls) == 1
    assert calls[0][expected_key] == (True if platform == "posix" else 512)
    unexpected_key = "creationflags" if platform == "posix" else "start_new_session"
    assert unexpected_key not in calls[0]


@pytest.mark.fast
@pytest.mark.parametrize("force", [False, True])
def test_windows_signal_targets_owned_descendant_tree(
    force: bool,
) -> None:
    process = _FakeProcess()
    commands: list[tuple[str, ...]] = []

    def _taskkill(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    pre_review_gate._signal_owned_process_tree(
        process,
        force=force,
        platform="nt",
        windows_tree_kill=_taskkill,
    )

    expected = ("taskkill", "/PID", str(process.pid), "/T")
    if force:
        expected += ("/F",)
    assert commands == [expected]
    assert process.terminated is False
    assert process.killed is False


@pytest.mark.fast
@pytest.mark.parametrize(
    ("force", "expected_signal"),
    [(False, signal.SIGTERM), (True, signal.SIGKILL)],
)
def test_posix_signal_targets_owned_process_group(
    monkeypatch: pytest.MonkeyPatch,
    force: bool,
    expected_signal: signal.Signals,
) -> None:
    process = _FakeProcess()
    calls: list[tuple[int, signal.Signals]] = []
    monkeypatch.setattr(pre_review_gate.os, "killpg", lambda pid, sig: calls.append((pid, sig)))

    pre_review_gate._signal_owned_process_tree(
        process,
        force=force,
        platform="posix",
    )

    assert calls == [(process.pid, expected_signal)]


def _spy_on_resolve_pytest_command(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[tuple[str, ...], Path]]:
    """Wrap (not replace) ``resolve_pytest_command`` so the real command is
    still built and run, while recording every call.

    #2570.3 unmask: prior to WP03, these two real-subprocess tests only
    proved that *some* interpreter with pytest installed could run the
    scoped suite — the ambient ``sys.executable`` running this very test
    process necessarily has pytest, so a regression back to the hardcoded
    ``sys.executable`` literal (bypassing the interpreter-resolution seam
    entirely) would still pass every assertion below. Spying on the seam
    itself closes that gap: it fails loudly (``AttributeError`` on
    bug-present code, where the attribute does not exist; a call-count
    mismatch on a reintroduced hardcoded literal) instead of passing
    silently.
    """
    calls: list[tuple[tuple[str, ...], Path]] = []
    real_resolve = pre_review_gate.resolve_pytest_command

    def _spy(pytest_args: list[str], *, repo_root: Path) -> list[str]:
        calls.append((tuple(pytest_args), repo_root))
        return real_resolve(pytest_args, repo_root=repo_root)

    monkeypatch.setattr(pre_review_gate, "resolve_pytest_command", _spy)
    return calls


@pytest.mark.integration
def test_real_subprocess_run_parses_junit_and_captures_current_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_tiny_pytest_project(tmp_path, failing=True)
    calls = _spy_on_resolve_pytest_command(monkeypatch)

    result = pre_review_gate.run_scoped_tests_at_head(["test_sample.py"], repo_root=tmp_path)

    assert result.ran is True
    failing_names = {f.test for f in result.current_failures}
    assert any("test_break" in name for name in failing_names)
    assert not any("test_pass" in name for name in failing_names)
    assert len(calls) == 1
    assert calls[0][1] == tmp_path


@pytest.mark.integration
def test_real_subprocess_run_with_no_failures_yields_empty_current_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _write_tiny_pytest_project(tmp_path, failing=False)
    calls = _spy_on_resolve_pytest_command(monkeypatch)

    result = pre_review_gate.run_scoped_tests_at_head(["test_sample.py"], repo_root=tmp_path)

    assert result.ran is True
    assert result.current_failures == ()
    assert len(calls) == 1
    assert calls[0][1] == tmp_path


@pytest.mark.fast
def test_missing_junit_output_degrades_to_a_warn_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        pre_review_gate.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakeProcess(returncode=1, stderr="boom"),
    )
    result = pre_review_gate.run_scoped_tests_at_head(["tests/status"], repo_root=tmp_path)
    assert result.ran is False
    assert result.returncode == 1
    assert result.state is HeadRunState.INCOMPLETE_OUTPUT
    assert "no JUnit XML produced" in (result.error or "")


@pytest.mark.fast
def test_timeout_degrades_to_a_warn_not_a_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    process = _FakeProcess()
    waits = 0

    def _wait(candidate: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        nonlocal waits
        del candidate
        waits += 1
        if waits == 1:
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=timeout)
        return "", "timed out"

    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(pre_review_gate, "_signal_owned_process_tree", lambda *args, **kwargs: None)
    clock = iter((0.0, 1.0, 1.0))
    result = pre_review_gate.run_scoped_tests_at_head(
        ["tests/status"],
        repo_root=tmp_path,
        timeout=1,
        monotonic=lambda: next(clock),
        wait=_wait,
    )
    assert result.ran is False
    assert result.state is HeadRunState.TIMED_OUT
    assert "timed out" in (result.error or "")


@pytest.mark.fast
def test_launch_failure_degrades_to_a_warn_not_a_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _raise_oserror(command: list[str], **kwargs: object) -> _FakeProcess:
        raise OSError("no such file or directory")

    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", _raise_oserror)
    result = pre_review_gate.run_scoped_tests_at_head(["tests/status"], repo_root=tmp_path)
    assert result.ran is False
    assert result.state is HeadRunState.LAUNCH_FAILED
    assert "failed to launch" in (result.error or "")


@pytest.mark.fast
def test_malformed_junit_degrades_to_a_warn_not_a_crash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def _fake_popen(command: list[str], **kwargs: object) -> _FakeProcess:
        junit_arg = next(arg for arg in command if arg.startswith("--junitxml="))
        junit_path = Path(junit_arg.split("=", 1)[1])
        junit_path.write_text("not valid xml <<<", encoding="utf-8")
        return _FakeProcess(returncode=1)

    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", _fake_popen)
    result = pre_review_gate.run_scoped_tests_at_head(["tests/status"], repo_root=tmp_path)
    assert result.ran is False
    assert result.state is HeadRunState.INCOMPLETE_OUTPUT
    assert "failed to parse" in (result.error or "")


@pytest.mark.fast
def test_observer_emits_bounded_heartbeats_without_delaying_completion() -> None:
    process = _FakeProcess()
    now = 0.0
    wait_calls = 0
    heartbeats: list[float] = []

    def _wait(candidate: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        nonlocal now, wait_calls
        del candidate
        wait_calls += 1
        if wait_calls <= 2:
            now += timeout
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=timeout)
        return "done", ""

    state, stdout, stderr = pre_review_gate._observe_process(
        process,
        timeout=300,
        progress_callback=heartbeats.append,
        monotonic=lambda: now,
        wait=_wait,
    )

    assert state is HeadRunState.COMPLETED
    assert (stdout, stderr) == ("done", "")
    assert heartbeats == [30.0, 60.0]


@pytest.mark.fast
def test_observer_cancellation_terminates_and_reaps_owned_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stderr="cancelled")
    waits = 0
    signals: list[bool] = []

    def _wait(candidate: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        nonlocal waits
        del candidate, timeout
        waits += 1
        if waits == 1:
            raise KeyboardInterrupt
        return "", process.stderr_text

    monkeypatch.setattr(
        pre_review_gate,
        "_signal_owned_process_tree",
        lambda candidate, *, force: signals.append(force),
    )
    state, _stdout, stderr = pre_review_gate._observe_process(
        process,
        timeout=300,
        progress_callback=None,
        monotonic=lambda: 0.0,
        wait=_wait,
    )

    assert state is HeadRunState.CANCELLED
    assert stderr == "cancelled"
    assert signals == [False]
    assert waits == 2


@pytest.mark.fast
def test_termination_escalates_to_kill_and_reaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeProcess(stdout="diagnostic")
    signals: list[bool] = []

    def _wait(candidate: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        del candidate
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=timeout)

    monkeypatch.setattr(
        pre_review_gate,
        "_signal_owned_process_tree",
        lambda candidate, *, force: signals.append(force),
    )
    output = pre_review_gate._terminate_and_reap(process, wait=_wait)

    assert signals == [False, True]
    assert output == ("diagnostic", "")


@pytest.mark.fast
def test_reap_is_bounded_when_escaped_grandchild_holds_pipe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The post-SIGKILL reap must return within a bound, never hang forever.

    A grandchild that escaped the process group (self-``setsid``) can inherit
    and hold the stdout pipe, so ``communicate`` never sees EOF even though the
    owned child is dead. The reap must fall back to reaping the child by PID and
    return, rather than wedging the gate on the leaked pipe.
    """

    class _PipeHeldProcess:
        pid = 909090

        def __init__(self) -> None:
            self.waited = False

        def communicate(self, timeout: float | None = None) -> tuple[str, str]:
            # EOF never arrives — the escaped grandchild still holds the pipe.
            raise subprocess.TimeoutExpired(cmd="pytest", timeout=timeout or 0.0)

        def wait(self, timeout: float | None = None) -> int:
            self.waited = True
            return -9

    process = _PipeHeldProcess()

    def _wait(candidate: object, timeout: float) -> tuple[str, str]:
        del candidate
        raise subprocess.TimeoutExpired(cmd="pytest", timeout=timeout)

    monkeypatch.setattr(pre_review_gate, "_signal_owned_process_tree", lambda *a, **k: None)

    output = pre_review_gate._terminate_and_reap(process, wait=_wait)  # type: ignore[arg-type]

    assert output == ("", "")
    assert process.waited is True  # the dead child was reaped by PID, not left


@pytest.mark.fast
def test_cancellation_releases_scoped_run_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = _FakeProcess()
    lock_events: list[str] = []
    waits = 0

    @contextlib.contextmanager
    def _recording_lock() -> Iterator[None]:
        lock_events.append("enter")
        try:
            yield
        finally:
            lock_events.append("exit")

    def _wait(candidate: subprocess.Popen[str], timeout: float) -> tuple[str, str]:
        nonlocal waits
        del candidate, timeout
        waits += 1
        if waits == 1:
            raise KeyboardInterrupt
        return "", ""

    monkeypatch.setattr(pre_review_gate, "_scoped_run_lock", _recording_lock)
    monkeypatch.setattr(pre_review_gate.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(pre_review_gate, "_signal_owned_process_tree", lambda *args, **kwargs: None)

    result = pre_review_gate.run_scoped_tests_at_head(
        ["tests/status"],
        repo_root=tmp_path,
        wait=_wait,
    )

    assert result.state is HeadRunState.CANCELLED
    assert lock_events == ["enter", "exit"]


# ---------------------------------------------------------------------------
# Verdict composition + diff_baseline reuse (FR-001/FR-003/SC-001/SC-002)
# ---------------------------------------------------------------------------


def _make_baseline(
    failures: tuple[BaselineFailure, ...] = (),
    *,
    failed: int = 0,
) -> BaselineTestResult:
    return BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-07-07T00:00:00Z",
        base_branch="main",
        base_commit="abc1234",
        test_runner="pytest",
        total=10,
        passed=10 - failed,
        failed=failed,
        skipped=0,
        failures=failures,
    )


def _sentinel_baseline() -> BaselineTestResult:
    return BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-07-07T00:00:00Z",
        base_branch="main",
        base_commit="",
        test_runner="pytest",
        total=0,
        passed=0,
        failed=-1,
        skipped=0,
        failures=(),
    )


# The 8 tests below drive ``evaluate_with_scope``'s legacy ``scope_source=None``
# tail directly (mission scopesource-gate-followup-01KY6S9P WP04): they used to
# reach it via ``evaluate_pre_review_gate``'s now-retired census-derived
# auto-scope tier (``derive_test_scope(filter_groups=..., composite_routing=...)``
# then delegate with ``scope_source=None``); that composition is gone, but the
# ``scope_source=None`` tail itself is C-002 KEPT LIVE (the FR-004 override tier
# still drives it via ``_mt_pre_review_gate_with_override_scope``) — so these
# tests migrate to build the equivalent ``ScopeResult`` directly (the exact
# shape ``derive_test_scope`` used to hand it) and call ``evaluate_with_scope``
# in its place, preserving every monkeypatch/assertion unchanged.
_VALIDATORS_EMPTY_CONE_SCOPE = ScopeResult(
    test_targets=(),
    matched_shard_groups=(),
    matched_composite_dirs=("validators",),
    empty_cone_composite_dirs=("validators",),
    excluded_scope_files=(),
)
_GIT_NONEMPTY_SCOPE = ScopeResult(
    test_targets=("tests/git", "tests/git_ops"),
    matched_shard_groups=(),
    matched_composite_dirs=("git",),
    empty_cone_composite_dirs=(),
    excluded_scope_files=(),
)


@pytest.mark.fast
def test_empty_scope_short_circuits_before_running_or_diffing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*args: object, **kwargs: object) -> HeadRunResult:
        raise AssertionError("run_scoped_tests_at_head must not be called for an empty scope")

    monkeypatch.setattr(pre_review_gate, "run_scoped_tests_at_head", _boom)
    verdict = pre_review_gate.evaluate_with_scope(
        _VALIDATORS_EMPTY_CONE_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=None,
    )
    assert verdict.outcome is GateOutcome.NO_COVERAGE


@pytest.mark.fast
def test_run_that_does_not_complete_degrades_to_no_coverage_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *a, **k: HeadRunResult(ran=False, error="boom"),
    )
    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=None,
    )
    assert verdict.outcome is GateOutcome.NO_COVERAGE
    assert "scoped test run did not complete" in (verdict.reason or "")


@pytest.mark.fast
@pytest.mark.parametrize(
    ("state", "outcome"),
    [
        (HeadRunState.TIMED_OUT, GateOutcome.TIMED_OUT),
        (HeadRunState.CANCELLED, GateOutcome.CANCELLED),
    ],
)
def test_terminal_interruption_remains_typed_in_gate_verdict(
    monkeypatch: pytest.MonkeyPatch,
    state: HeadRunState,
    outcome: GateOutcome,
) -> None:
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *args, **kwargs: HeadRunResult(
            ran=False,
            error=state.value,
            state=state,
        ),
    )

    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=None,
    )

    assert verdict.outcome is outcome
    assert verdict.run_state is state
    assert verdict.outcome is not GateOutcome.NO_COVERAGE


@pytest.mark.fast
def test_uncomputable_baseline_none_degrades_to_warn_and_surfaces_all_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_failure = BaselineFailure(test="tests.git.test_x", error="boom", file="tests/git/test_x.py:1")
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *a, **k: HeadRunResult(ran=True, current_failures=(fake_failure,)),
    )
    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=None,
    )
    assert verdict.outcome is GateOutcome.UNVERIFIED_BASELINE
    assert verdict.new_failures == (fake_failure,)


@pytest.mark.fast
def test_sentinel_baseline_degrades_to_warn(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_failure = BaselineFailure(test="tests.git.test_x", error="boom", file="tests/git/test_x.py:1")
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *a, **k: HeadRunResult(ran=True, current_failures=(fake_failure,)),
    )
    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=_sentinel_baseline(),
    )
    assert verdict.outcome is GateOutcome.UNVERIFIED_BASELINE


@pytest.mark.fast
def test_pre_existing_failure_does_not_block_no_new_failures_outcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SC-002: a base failure in the affected shard does NOT block the WP."""
    shared_failure = BaselineFailure(
        test="tests.git.test_known_red",
        error="pre-existing",
        file="tests/git/test_x.py:1",
    )
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *a, **k: HeadRunResult(ran=True, current_failures=(shared_failure,)),
    )
    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=_make_baseline((shared_failure,), failed=1),
    )
    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.pre_existing_failures == (shared_failure,)
    assert verdict.new_failures == ()


@pytest.mark.fast
def test_new_failure_is_surfaced_via_the_real_diff_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: proves genuine ``diff_baseline`` reuse — the real function is
    spied on (still delegated to), not reimplemented."""
    calls: list[tuple[BaselineTestResult, list[BaselineFailure]]] = []
    real_diff_baseline = pre_review_gate.diff_baseline

    def _spy(
        baseline: BaselineTestResult,
        current_failures: list[BaselineFailure],
    ) -> tuple[list[BaselineFailure], list[BaselineFailure], list[str]]:
        calls.append((baseline, list(current_failures)))
        return real_diff_baseline(baseline, current_failures)

    monkeypatch.setattr(pre_review_gate, "diff_baseline", _spy)

    new_failure = BaselineFailure(
        test="tests.git.test_newly_broken",
        error="AssertionError",
        file="tests/git/test_x.py:5",
    )
    monkeypatch.setattr(
        pre_review_gate,
        "run_scoped_tests_at_head",
        lambda *a, **k: HeadRunResult(ran=True, current_failures=(new_failure,)),
    )
    verdict = pre_review_gate.evaluate_with_scope(
        _GIT_NONEMPTY_SCOPE,
        repo_root=_DUMMY_ROOT,
        baseline=_make_baseline(),
    )
    assert verdict.outcome is GateOutcome.NEW_FAILURES
    assert verdict.new_failures == (new_failure,)
    assert len(calls) == 1


@pytest.mark.integration
def test_end_to_end_new_failure_detected_via_real_subprocess_and_real_diff(tmp_path: Path) -> None:
    """Full composition with a REAL subprocess pytest run + the REAL
    diff_baseline — only the scope-derivation inputs are synthetic.

    Migrated (mission scopesource-gate-followup-01KY6S9P WP04) onto an
    injected narrowing-source path now that the census-derived
    ``filter_groups=``/``composite_routing=`` auto-scope tier is retired."""
    _write_tiny_pytest_project(tmp_path, failing=True)
    scope_source = _NarrowingScopeSource(repo_root=tmp_path)
    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["src/specify_cli/git/foo.py"],
        repo_root=tmp_path,
        baseline=_make_baseline(),  # base had no failures
        scope_source=scope_source,
    )
    assert verdict.outcome is GateOutcome.NEW_FAILURES
    assert any("test_break" in f.test for f in verdict.new_failures)


# ---------------------------------------------------------------------------
# T015 — #2330 pre-review-facet closure (non-pytest layout, DeclaredCommandScopeSource)
# ---------------------------------------------------------------------------
#
# A simulated non-pytest / non-``src/specify_cli/`` checkout: no
# ``tests/architectural/_gate_coverage.py``, a bare ``.kittify/config.yaml``
# declaring ``review.test_command``. The declared command is a tiny Python
# script (not pytest) that prints ``FAIL <test>: <message>`` lines — the
# genuinely non-pytest-shaped convention ``DeclaredCommandScopeSource.parse_results``
# understands.

_NON_PYTEST_FAILING_SCRIPT = "print('FAIL test_widget: widget broke')\n"


def _write_declared_command_config(repo_root: Path, script_path: Path) -> None:
    kittify_dir = repo_root / ".kittify"
    kittify_dir.mkdir(parents=True, exist_ok=True)
    (kittify_dir / "config.yaml").write_text(
        f'review:\n  test_command: "{sys.executable} {script_path}"\n',
        encoding="utf-8",
    )


@pytest.mark.integration
def test_declared_command_source_runs_and_parses_a_real_non_pytest_failure_never_importing_gate_coverage(
    tmp_path: Path,
) -> None:
    """T015 (#2330 closure): a non-pytest, non-``src/specify_cli/`` layout
    gates via ITS OWN declared command through the engine — the command
    genuinely RUNS, its output is genuinely PARSED into a real, blocking-
    capable verdict (never a decorative ``NO_COVERAGE``), and
    ``tests.architectural._gate_coverage`` is NEVER imported.

    Asserted structurally (not via a ``sys.modules`` snapshot, which an
    EARLIER test in this same session may have already poisoned by
    genuinely loading the real module for its own bare-repo
    ``GateAuthoritiesUnavailable`` fixture): ``importlib.import_module`` is
    patched, scoped to ``scope_source``'s own module, to fail loudly if the
    internal authority name is ever requested during THIS evaluation.
    """
    script = tmp_path / "run_tests.py"
    script.write_text(_NON_PYTEST_FAILING_SCRIPT, encoding="utf-8")
    _write_declared_command_config(tmp_path, script)
    scope_source = DeclaredCommandScopeSource(repo_root=tmp_path)

    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["anything/at/all.rb"],
        repo_root=tmp_path,
        baseline=_make_baseline(),  # clean baseline — no pre-existing failures
        scope_source=scope_source,
    )

    assert verdict.outcome is GateOutcome.NEW_FAILURES
    assert any("test_widget" in f.test for f in verdict.new_failures)


@pytest.mark.integration
def test_declared_command_source_pre_existing_baseline_failure_is_not_blocked(tmp_path: Path) -> None:
    """T015 pre_existing_not_blocked arm (R-F5 / renata-F3): a
    ``DeclaredCommandScopeSource`` consumer whose declared suite is RED AT
    BASELINE must NOT be blocked by that pre-existing failure — the
    engine's head<->baseline diff classifies it as ``NO_NEW_FAILURES``,
    proving the baseline-relative semantics (never a naive
    ``returncode != 0`` / ANY_FAILURES collapse) hold end-to-end through
    the ENGINE, not just at the port's own unit-test level
    (``test_scope_source.py``'s T009 fixtures). Without this arm a
    pre-existing-red consumer suite blocking every transition ships
    untested."""
    script = tmp_path / "run_tests.py"
    script.write_text(_NON_PYTEST_FAILING_SCRIPT, encoding="utf-8")
    _write_declared_command_config(tmp_path, script)
    scope_source = DeclaredCommandScopeSource(repo_root=tmp_path)

    baseline_failure = BaselineFailure(test="test_widget", error="widget broke", file="unknown")
    baseline = _make_baseline((baseline_failure,), failed=1)

    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["anything/at/all.rb"],
        repo_root=tmp_path,
        baseline=baseline,
        scope_source=scope_source,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.new_failures == ()
    assert any(f.test == "test_widget" for f in verdict.pre_existing_failures)


@pytest.mark.fast
def test_declared_command_source_no_config_yields_no_coverage(tmp_path: Path) -> None:
    """FR-012: no ``review.test_command`` configured -> a visible
    ``NO_COVERAGE`` warn through the injected-port path, never a crash and
    never a silent green."""
    scope_source = DeclaredCommandScopeSource(repo_root=tmp_path)

    verdict = pre_review_gate.evaluate_pre_review_gate(
        ["anything/at/all.rb"],
        repo_root=tmp_path,
        baseline=None,
        scope_source=scope_source,
    )

    assert verdict.outcome is GateOutcome.NO_COVERAGE


# ---------------------------------------------------------------------------
# T012 — baseline capture via the injected ScopeSource (mission
# doctrine-controlled-transition-gates-01KY51Z7, FR-011)
# ---------------------------------------------------------------------------


def _init_baseline_capture_repo(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)


@pytest.mark.integration
@pytest.mark.git_repo
def test_capture_baseline_via_scope_source_runs_and_persists_parsed_failures(tmp_path: Path) -> None:
    """T012 (FR-011): baseline capture routes through the injected
    ``ScopeSource``'s ``test_command()``/``parse_results()`` — the SAME
    authority the pre-review head run uses — instead of an independently
    re-resolved command."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_baseline_capture_repo(repo)
    script = repo / "run_tests.py"
    script.write_text(_NON_PYTEST_FAILING_SCRIPT, encoding="utf-8")
    _write_declared_command_config(repo, script)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    scope_source = DeclaredCommandScopeSource(repo_root=repo)
    feature_dir = tmp_path / "kitty-specs" / "m"

    result = baseline_module.capture_baseline(
        worktree_path=repo,
        base_branch="main",
        wp_id="WP01",
        mission_slug="m",
        feature_dir=feature_dir,
        wp_slug="WP01-test",
        scope_source=scope_source,
    )

    assert result is not None
    assert result.failed == 1
    assert result.failures[0].test == "test_widget"
    assert (feature_dir / "tasks" / "WP01-test" / "baseline-tests.json").exists()


@pytest.mark.git_repo
def test_capture_baseline_via_scope_source_skips_when_no_command_resolved(tmp_path: Path) -> None:
    """FR-012: no command resolved via the injected port -> skip, mirroring
    the config-driven path's opt-in-and-visible behaviour (never a crash,
    never a silently fabricated baseline)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_baseline_capture_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=repo, check=True)

    scope_source = DeclaredCommandScopeSource(repo_root=repo)  # no .kittify/config.yaml
    feature_dir = tmp_path / "kitty-specs" / "m"

    result = baseline_module.capture_baseline(
        worktree_path=repo,
        base_branch="main",
        wp_id="WP01",
        mission_slug="m",
        feature_dir=feature_dir,
        wp_slug="WP01-test",
        scope_source=scope_source,
    )

    assert result is None


@pytest.mark.fast
def test_extract_junit_output_path_finds_and_misses_correctly(tmp_path: Path) -> None:
    """Focused unit coverage for the small pure helper both the baseline
    capture path and the engine's port-driven head run share."""
    junit = tmp_path / "x.xml"
    assert baseline_module._extract_junit_output_path([f"--junitxml={junit}", "-q"]) == junit
    assert baseline_module._extract_junit_output_path(["-q"]) is None
