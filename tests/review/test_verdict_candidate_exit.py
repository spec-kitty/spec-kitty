"""The verdict states what the candidate command actually did (spec-kitty#6751, WP02).

A baseline-relative ``no_new_failures`` used to be indistinguishable from "the
candidate command exited 0": the verdict carried no exit status and no reason.
These tests drive the REAL gate seam (``evaluate_with_scope`` →
``_evaluate_via_scope_source`` → a real subprocess → ``_classify_current_failures``)
so the observed ``returncode`` is the one a declared-command run really produced,
then assert the verdict surface:

- a nonzero candidate with only pre-existing failures records its exit status and
  says the verdict is baseline-relative;
- a clean candidate records exit 0;
- an opaque candidate failure that differs from the baseline's is ``new_failures``;
- an opaque candidate failure identical to the baseline's stays pre-existing;
- the transition metadata payload and the ``reason is None`` console line are
  byte-identical to the base-captured parity oracle (no new metadata key);
- the opt-in block predicate is untouched.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

from specify_cli.cli.commands.agent import tasks_move_task as tmt
from specify_cli.review import pre_review_gate
from specify_cli.review.baseline import OPAQUE_FAILURE_TEST_ID, BaselineFailure, BaselineTestResult
from specify_cli.review.pre_review_gate import GateOutcome, GateVerdict, ScopeResult
from specify_cli.review.scope_source import RawRunResult
from specify_cli.review.verdict_aggregation import AggregateDecision, aggregate_verdicts

pytestmark = [pytest.mark.fast]

_SCOPE = ScopeResult(
    test_targets=("tests/whatever",),
    matched_shard_groups=(),
    matched_composite_dirs=(),
    empty_cone_composite_dirs=(),
    excluded_scope_files=(),
)


@dataclass
class _HeadRunSource:
    """A real (non-narrowing) ``ScopeSource`` whose declared command really exits ``exit_code``.

    ``parse_results`` returns the scripted failures: the parser itself is covered
    by ``test_opaque_failure_identity.py`` / ``test_scope_source.py``; this stub
    isolates the VERDICT surface while still exercising the real subprocess
    launch, so ``raw.returncode`` is genuinely observed.
    """

    head_failures: tuple[BaselineFailure, ...] = ()
    exit_code: int = 0

    def test_command(self) -> list[str] | None:
        return [sys.executable, "-c", f"import sys; sys.exit({self.exit_code})"]

    def file_to_scope(self, path: str) -> tuple[str, ...]:
        del path
        return ("tests/whatever",)

    def parse_mode(self, raw: RawRunResult) -> str:
        del raw
        return "text"

    def parse_results(self, raw: RawRunResult) -> tuple[BaselineFailure, ...]:
        del raw
        return self.head_failures


#: ``scope_source_identity`` is "<class>/<parse-mode>"; the baseline must agree.
_IDENTITY = "_HeadRunSource/text"


def _baseline(failures: tuple[BaselineFailure, ...]) -> BaselineTestResult:
    return BaselineTestResult(
        wp_id="WP02",
        captured_at="2026-10-30T00:00:00Z",
        base_branch="fixture",
        base_commit="fixture",
        test_runner="custom",
        total=len(failures),
        passed=0,
        failed=len(failures),
        skipped=0,
        failures=failures,
        source_identity=_IDENTITY,
    )


def _named(test: str, error: str = "boom") -> BaselineFailure:
    return BaselineFailure(test=test, error=error, file="unknown")


def _opaque(*, exit_code: int, digest: str, error: str = "error: no build.zig file found") -> BaselineFailure:
    return BaselineFailure(
        test=OPAQUE_FAILURE_TEST_ID,
        error=error,
        file="unknown",
        opaque=True,
        exit_code=exit_code,
        output_digest=digest,
    )


def _evaluate(source: _HeadRunSource, baseline: BaselineTestResult, tmp_path: Path) -> GateVerdict:
    return pre_review_gate.evaluate_with_scope(
        _SCOPE,
        repo_root=tmp_path,
        baseline=baseline,
        timeout=120,
        scope_source=source,
    )


# ---------------------------------------------------------------------------
# The exit status reaches the verdict
# ---------------------------------------------------------------------------


def test_nonzero_candidate_with_only_pre_existing_failures_records_its_exit(tmp_path: Path) -> None:
    verdict = _evaluate(
        _HeadRunSource(head_failures=(_named("test_alpha"),), exit_code=2),
        _baseline((_named("test_alpha"),)),
        tmp_path,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.candidate_exit_code == 2
    assert len(verdict.pre_existing_failures) == 1
    reason = verdict.reason or ""
    assert "exited 2" in reason
    assert "baseline-relative" in reason
    assert "does not assert a clean candidate exit" in reason


def test_clean_candidate_records_exit_zero(tmp_path: Path) -> None:
    verdict = _evaluate(
        _HeadRunSource(head_failures=(), exit_code=0),
        _baseline((_named("test_alpha"),)),
        tmp_path,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.candidate_exit_code == 0
    assert verdict.new_failures == ()
    assert verdict.pre_existing_failures == ()
    reason = verdict.reason or ""
    assert "exited 0" in reason
    assert "baseline-relative" in reason
    # The "does not assert a clean exit" boundary belongs to a NONZERO run; next
    # to "exited 0" it would read as a contradiction (review fold, WP02).
    assert "does not assert a clean candidate exit" not in reason


def test_opaque_mismatch_through_the_gate_is_new_failures(tmp_path: Path) -> None:
    """The #6751 regression proved through the gate, not only the comparator."""
    candidate = _opaque(exit_code=1, digest="bbbbbbbbbbbbbbbb", error="expected type 'u64', found '[]const u8'")
    verdict = _evaluate(
        _HeadRunSource(head_failures=(candidate,), exit_code=1),
        _baseline((_opaque(exit_code=2, digest="aaaaaaaaaaaaaaaa"),)),
        tmp_path,
    )

    assert verdict.outcome is GateOutcome.NEW_FAILURES, verdict.reason
    assert verdict.new_failures == (candidate,)
    assert verdict.pre_existing_failures == ()
    assert verdict.candidate_exit_code == 1


def test_opaque_match_through_the_gate_stays_pre_existing_and_names_it(tmp_path: Path) -> None:
    candidate = _opaque(exit_code=2, digest="aaaaaaaaaaaaaaaa")
    verdict = _evaluate(
        _HeadRunSource(head_failures=(candidate,), exit_code=2),
        _baseline((_opaque(exit_code=2, digest="aaaaaaaaaaaaaaaa"),)),
        tmp_path,
    )

    assert verdict.outcome is GateOutcome.NO_NEW_FAILURES
    assert verdict.pre_existing_failures == (candidate,)
    assert verdict.candidate_exit_code == 2
    reason = verdict.reason or ""
    assert "opaque" in reason
    assert "aaaaaaaaaaaaaaaa" in reason


# ---------------------------------------------------------------------------
# Parity: no new metadata key, unchanged console line, unchanged block predicate
# ---------------------------------------------------------------------------

#: The budget-evidence keys ``_mt_pre_review_gate_metadata`` adds when a run
#: carried a :class:`ScopeBudgetAssessment` (the gate path always does).
_BUDGET_METADATA_KEYS = frozenset(
    {
        "budget_classification",
        "scope_identity",
        "effective_budget_seconds",
        "matched_budget_rule",
        "classification_candidate",
        "observed_elapsed_seconds",
        "classification_guidance",
    }
)

#: The incumbent FR-004 metadata payload key set (base-captured parity fixtures).
_INCUMBENT_METADATA_KEYS = frozenset(
    {
        "outcome",
        "reason",
        "new_failure_count",
        "new_failure_nodeids",
        "pre_existing_failure_count",
        "affected_shard_count",
        "matched_shard_groups",
        "matched_composite_dirs",
        "test_targets",
        "block_enabled",
        "blocked",
        "force_bypassed",
        "run_state",
    }
)


def test_metadata_payload_gains_no_key_and_carries_the_reason(tmp_path: Path) -> None:
    verdict = _evaluate(
        _HeadRunSource(head_failures=(_named("test_alpha"),), exit_code=2),
        _baseline((_named("test_alpha"),)),
        tmp_path,
    )
    metadata = tmt._mt_pre_review_gate_metadata(verdict, block_enabled=False, blocked=False, force_bypassed=False)

    expected = _INCUMBENT_METADATA_KEYS
    if verdict.budget_assessment is not None:
        expected = expected | _BUDGET_METADATA_KEYS
    assert frozenset(metadata) == expected
    assert "candidate_exit_code" not in metadata
    assert metadata["reason"] == verdict.reason
    assert metadata["pre_existing_failure_count"] == 1


def test_console_line_without_a_reason_is_byte_identical() -> None:
    verdict = GateVerdict(outcome=GateOutcome.NO_NEW_FAILURES, scope=_SCOPE)

    assert tmt._mt_pre_review_gate_console_warning(verdict, block_enabled=False) == ("[dim]Pre-review regression gate: no new failures[/dim]")


def test_console_line_carries_the_reason_when_the_verdict_has_one(tmp_path: Path) -> None:
    verdict = _evaluate(
        _HeadRunSource(head_failures=(_named("test_alpha"),), exit_code=2),
        _baseline((_named("test_alpha"),)),
        tmp_path,
    )
    line = tmt._mt_pre_review_gate_console_warning(verdict, block_enabled=False) or ""

    assert line.startswith("[dim]Pre-review regression gate: no new failures")
    assert "exited 2" in line


def test_block_predicate_is_untouched(tmp_path: Path) -> None:
    new_failures_verdict = _evaluate(
        _HeadRunSource(head_failures=(_named("test_new"),), exit_code=1),
        _baseline(()),
        tmp_path,
    )
    pre_existing_verdict = _evaluate(
        _HeadRunSource(head_failures=(_named("test_alpha"),), exit_code=2),
        _baseline((_named("test_alpha"),)),
        tmp_path,
    )

    assert new_failures_verdict.outcome is GateOutcome.NEW_FAILURES
    blocked = aggregate_verdicts([new_failures_verdict], block_enabled=True, force=False)
    assert blocked.decision is AggregateDecision.BLOCK
    forced = aggregate_verdicts([new_failures_verdict], block_enabled=True, force=True)
    assert forced.decision is AggregateDecision.WARN_PROCEED
    # A nonzero exit status alone never blocks: only NEW_FAILURES does.
    not_blocked = aggregate_verdicts([pre_existing_verdict], block_enabled=True, force=False)
    assert not_blocked.decision is AggregateDecision.WARN_PROCEED
