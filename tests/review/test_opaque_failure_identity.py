"""Red-first reproductions for spec-kitty#6751.

An *opaque* declared-command failure — a nonzero exit with no parseable
per-failure identity — is represented by one synthetic placeholder,
``<declared-command>``. Before this mission that placeholder was the *only*
identity, so any opaque baseline failure matched any opaque candidate failure
and ``_classify_current_failures`` returned ``no_new_failures`` for a candidate
that failed for an unrelated reason. The issue's own counterexample
(missing ``build.zig`` baseline vs. a Zig compilation error) is
:func:`test_differing_opaque_candidate_failure_is_a_new_failure`.

Every case is built from ONE fixture table so the new-failure probe and its
pre-existing positive control cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.review.baseline import (
    OPAQUE_FAILURE_TEST_ID,
    BaselineFailure,
    BaselineTestResult,
    diff_baseline,
)
from specify_cli.review.pre_review_gate import (
    GateOutcome,
    ScopeResult,
    _classify_current_failures,
)
from specify_cli.review.scope_source import DeclaredCommandScopeSource, RawRunResult

pytestmark = pytest.mark.fast

MISSING_BUILD = "error: no build.zig file found, in the current directory or any parent directories\n"
COMPILE_ERROR = "src/example.zig:1:1: error: expected type 'u64', found '[]const u8'\n"


def _parse(tmp_path: Path, *, returncode: int, stdout: str = "", stderr: str = "") -> tuple[BaselineFailure, ...]:
    source = DeclaredCommandScopeSource(repo_root=tmp_path)
    return source.parse_results(RawRunResult(returncode, stdout, stderr))


def _baseline(failures: tuple[BaselineFailure, ...]) -> BaselineTestResult:
    return BaselineTestResult(
        wp_id="WP01",
        captured_at="2026-10-30T00:00:00Z",
        base_branch="fixture",
        base_commit="fixture",
        test_runner="custom",
        total=len(failures),
        passed=0,
        failed=len(failures),
        skipped=0,
        failures=failures,
        source_identity="DeclaredCommandScopeSource/text",
    )


def _scope() -> ScopeResult:
    return ScopeResult((), (), (), (), ())


def _classify(
    current: tuple[BaselineFailure, ...], baseline: BaselineTestResult | None
) -> tuple[GateOutcome, tuple[BaselineFailure, ...], tuple[BaselineFailure, ...]]:
    verdict = _classify_current_failures(current, scope=_scope(), baseline=baseline)
    return verdict.outcome, tuple(verdict.new_failures), tuple(verdict.pre_existing_failures)


# ---------------------------------------------------------------------------
# The synthetic identity itself
# ---------------------------------------------------------------------------


def test_opaque_failure_carries_its_exit_status_and_marker(tmp_path: Path) -> None:
    (failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)

    assert failure.test == OPAQUE_FAILURE_TEST_ID
    assert failure.opaque is True
    assert failure.exit_code == 2
    assert failure.error == MISSING_BUILD.strip()
    # The one-line summary is not the identity: the digest of the full tail is.
    assert failure.output_digest is not None
    assert len(failure.output_digest) == 16


def test_named_failure_is_not_opaque_and_carries_no_exit_status(tmp_path: Path) -> None:
    (failure,) = _parse(tmp_path, returncode=1, stdout="FAIL test_beta: boom\n")

    assert failure.test == "test_beta"
    assert failure.opaque is False
    assert failure.exit_code is None
    assert failure.output_digest is None


# ---------------------------------------------------------------------------
# The comparator: same fixture, opposite verdicts
# ---------------------------------------------------------------------------


def test_differing_opaque_candidate_failure_is_a_new_failure(tmp_path: Path) -> None:
    """The issue's counterexample: unrelated opaque failures must not collide."""
    (baseline_failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)
    (candidate_failure,) = _parse(tmp_path, returncode=1, stderr=COMPILE_ERROR)

    outcome, new_failures, pre_existing = _classify((candidate_failure,), _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert [f.error for f in new_failures] == [COMPILE_ERROR.strip()]
    assert pre_existing == ()


def test_identical_opaque_failure_stays_pre_existing(tmp_path: Path) -> None:
    """Positive control on the SAME fixture: the same opaque failure is not new."""
    (baseline_failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)
    (candidate_failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)

    outcome, new_failures, pre_existing = _classify((candidate_failure,), _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NO_NEW_FAILURES
    assert new_failures == ()
    assert [f.error for f in pre_existing] == [MISSING_BUILD.strip()]


def test_opaque_identity_includes_the_exit_status(tmp_path: Path) -> None:
    """Same summary, different exit status: the identity is not established."""
    (baseline_failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)
    (candidate_failure,) = _parse(tmp_path, returncode=1, stderr=MISSING_BUILD)

    outcome, new_failures, _pre_existing = _classify((candidate_failure,), _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert len(new_failures) == 1


def test_shared_generic_last_line_is_not_an_identity(tmp_path: Path) -> None:
    """Review fold (#6751): two unrelated failures can end in the same line.

    ``make`` ends any recipe failure with the same ``*** [Makefile:1: all]
    Error 1`` tail, so binding the identity to the display summary alone would
    still let a real regression through. The full-output digest distinguishes
    them.
    """
    (baseline_failure,) = _parse(tmp_path, returncode=2, stderr="src/real_bug_a.zig:1:1: error: bug A\nmake: *** [Makefile:1: all] Error 1\n")
    (candidate_failure,) = _parse(tmp_path, returncode=2, stderr="src/real_bug_b.zig:9:1: error: bug B\nmake: *** [Makefile:1: all] Error 1\n")

    assert baseline_failure.error == candidate_failure.error  # same display summary

    outcome, new_failures, _pre_existing = _classify((candidate_failure,), _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert new_failures == (candidate_failure,)


def test_same_stderr_with_different_stdout_is_a_new_failure(tmp_path: Path) -> None:
    """Aggregate review fold (#6751): both streams feed the identity.

    A runner can put the failure detail on stdout and a stable banner on stderr.
    Digesting ``stderr or stdout`` would then hash the banner alone and collapse
    two unrelated failures — the same defect class this issue is about.
    """
    (baseline_failure,) = _parse(tmp_path, returncode=1, stdout="error A: real bug\n", stderr="warning: deprecation\n")
    (candidate_failure,) = _parse(tmp_path, returncode=1, stdout="error B: real bug\n", stderr="warning: deprecation\n")

    assert baseline_failure.error == candidate_failure.error  # same display summary (the banner)

    outcome, new_failures, _pre_existing = _classify((candidate_failure,), _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert new_failures == (candidate_failure,)


def test_named_and_opaque_failures_never_match() -> None:
    """A named entry that happens to sit in the opaque name is still a different identity."""
    named_in_placeholder = BaselineFailure(test=OPAQUE_FAILURE_TEST_ID, error="boom", file="unknown")
    opaque = BaselineFailure(test=OPAQUE_FAILURE_TEST_ID, error="boom", file="unknown", opaque=True, exit_code=2)

    assert diff_baseline(_baseline((named_in_placeholder,)), [opaque])[1] == [opaque]
    assert diff_baseline(_baseline((opaque,)), [named_in_placeholder])[1] == [named_in_placeholder]


# ---------------------------------------------------------------------------
# Ratchets: named failures, clean runs and legacy artifacts are unchanged
# ---------------------------------------------------------------------------


def test_named_failures_keep_name_based_matching(tmp_path: Path) -> None:
    (baseline_failure,) = _parse(tmp_path, returncode=1, stdout="FAIL test_alpha: boom\n")
    candidate_failures = _parse(
        tmp_path,
        returncode=1,
        stdout="FAIL test_alpha: a different message\nFAIL test_beta: new\n",
    )

    outcome, new_failures, pre_existing = _classify(candidate_failures, _baseline((baseline_failure,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert [f.test for f in new_failures] == ["test_beta"]
    assert [f.test for f in pre_existing] == ["test_alpha"]


def test_clean_candidate_with_pre_existing_named_failure_is_no_new_failures(tmp_path: Path) -> None:
    (baseline_failure,) = _parse(tmp_path, returncode=1, stdout="FAIL test_alpha: boom\n")
    clean = _parse(tmp_path, returncode=0, stdout="ok test_alpha\n")

    outcome, new_failures, pre_existing = _classify(clean, _baseline((baseline_failure,)))

    assert clean == ()
    assert outcome is GateOutcome.NO_NEW_FAILURES
    assert (new_failures, pre_existing) == ((), ())


def test_legacy_baseline_artifact_loads_and_cannot_match_a_known_exit_status(tmp_path: Path) -> None:
    """A pre-change record has no opaque marker and no exit status; it must not collide."""
    legacy = BaselineFailure.from_dict({"test": OPAQUE_FAILURE_TEST_ID, "error": MISSING_BUILD.strip(), "file": "unknown"})
    (candidate_failure,) = _parse(tmp_path, returncode=2, stderr=MISSING_BUILD)

    assert legacy.opaque is True
    assert legacy.exit_code is None

    outcome, new_failures, _pre_existing = _classify((candidate_failure,), _baseline((legacy,)))

    assert outcome is GateOutcome.NEW_FAILURES
    assert new_failures == (candidate_failure,)


def test_failure_round_trips_through_the_artifact_payload() -> None:
    opaque = BaselineFailure(
        test=OPAQUE_FAILURE_TEST_ID,
        error="boom",
        file="unknown",
        opaque=True,
        exit_code=2,
        output_digest="0123456789abcdef",
    )
    named = BaselineFailure(test="test_alpha", error="boom", file="tests/test_a.py:1")

    assert BaselineFailure.from_dict(opaque.to_dict()) == opaque
    assert opaque.to_dict() == {
        "test": OPAQUE_FAILURE_TEST_ID,
        "error": "boom",
        "file": "unknown",
        "opaque": True,
        "exit_code": 2,
        "output_digest": "0123456789abcdef",
    }
    # A named failure keeps the incumbent payload shape exactly (no new keys).
    assert named.to_dict() == {"test": "test_alpha", "error": "boom", "file": "tests/test_a.py:1"}
