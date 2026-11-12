"""Full outcome x precedence matrix for :func:`aggregate_verdicts` (WP08 / FR-014).

These tests are the ONLY exercise the multi-handler aggregation branches get in
half A: the mission ships exactly ONE production gate binding (the Spec-Kitty
pre-review handler), so the N-handler precedence paths have no production caller
and are a forward-compatibility seam driven **only** by the synthetic /
fabricated ``GateVerdict`` values below (squad finding R-F3, ``data-model.md``
:280-285). No real gate handler is imported or run here.

The precedence under test (highest first), preserving the incumbent
``_mt_run_pre_review_gate`` order (``tasks_move_task.py`` terminal check at
:1270 BEFORE the block at :1298):

    1. terminal refusal/interruption (SCOPE_OVERSIZED / TIMED_OUT / CANCELLED)
       -> hard-stop, no transition
    2. opt-in block (block_enabled AND any NEW_FAILURES AND not force) -> hard-stop
    3. warn / pass -> transition proceeds, one warning slot per verdict
"""

from __future__ import annotations

import pytest

from specify_cli.review.pre_review_gate import (
    GateOutcome,
    GateVerdict,
    HeadRunState,
    ScopeResult,
)
from specify_cli.review.verdict_aggregation import (
    AggregateDecision,
    AggregateVerdict,
    aggregate_verdicts,
)

pytestmark = [pytest.mark.fast]

_EMPTY_SCOPE = ScopeResult.from_override(())

_NON_TERMINAL = (
    GateOutcome.NO_COVERAGE,
    GateOutcome.NO_NEW_FAILURES,
    GateOutcome.NEW_FAILURES,
    GateOutcome.UNVERIFIED_BASELINE,
)
_TERMINAL = (GateOutcome.TIMED_OUT, GateOutcome.CANCELLED)


def _verdict(outcome: GateOutcome, *, reason: str | None = None) -> GateVerdict:
    """Fabricate a minimal ``GateVerdict`` for the given outcome (no real handler)."""
    run_state = HeadRunState.COMPLETED
    if outcome is GateOutcome.TIMED_OUT:
        run_state = HeadRunState.TIMED_OUT
    elif outcome is GateOutcome.CANCELLED:
        run_state = HeadRunState.CANCELLED
    elif outcome is GateOutcome.SCOPE_OVERSIZED:
        run_state = HeadRunState.NOT_STARTED
    return GateVerdict(
        outcome=outcome,
        scope=_EMPTY_SCOPE,
        reason=reason,
        run_state=run_state,
    )


# ---------------------------------------------------------------------------
# Single-handler arm: every outcome x {block_enabled} x {force}
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", _NON_TERMINAL)
@pytest.mark.parametrize("block_enabled", [True, False])
@pytest.mark.parametrize("force", [True, False])
def test_single_non_terminal_blocks_only_on_new_failures(outcome: GateOutcome, block_enabled: bool, force: bool) -> None:
    result = aggregate_verdicts([_verdict(outcome)], block_enabled=block_enabled, force=force)
    should_block = outcome is GateOutcome.NEW_FAILURES and block_enabled and not force
    if should_block:
        assert result.decision is AggregateDecision.BLOCK
        assert result.should_exit is True
        assert result.transition_applied is False
        assert result.terminal_verdict is None
        assert len(result.blocking_verdicts) == 1
    else:
        assert result.decision is AggregateDecision.WARN_PROCEED
        assert result.should_exit is False
        assert result.transition_applied is True
        assert result.terminal_verdict is None
    # invariant: exactly one warning slot per input verdict
    assert len(result.warnings) == 1


@pytest.mark.parametrize("outcome", _TERMINAL)
@pytest.mark.parametrize("block_enabled", [True, False])
@pytest.mark.parametrize("force", [True, False])
def test_single_terminal_is_hard_stop_regardless_of_block_or_force(outcome: GateOutcome, block_enabled: bool, force: bool) -> None:
    verdict = _verdict(outcome)
    result = aggregate_verdicts([verdict], block_enabled=block_enabled, force=force)
    assert result.decision is AggregateDecision.TERMINAL
    assert result.should_exit is True
    assert result.transition_applied is False
    assert result.terminal_verdict is verdict
    assert result.blocking_verdicts == ()
    assert len(result.warnings) == 1


def test_scope_oversized_is_terminal_and_never_transitions() -> None:
    """Pre-launch refusal has the same no-transition authority as interruption."""
    verdict = _verdict(GateOutcome.SCOPE_OVERSIZED)
    result = aggregate_verdicts([verdict], block_enabled=False, force=True)

    assert result.decision is AggregateDecision.TERMINAL
    assert result.should_exit is True
    assert result.transition_applied is False
    assert result.terminal_verdict is verdict


def test_new_failures_force_bypasses_block() -> None:
    result = aggregate_verdicts([_verdict(GateOutcome.NEW_FAILURES)], block_enabled=True, force=True)
    assert result.decision is AggregateDecision.WARN_PROCEED
    assert result.should_exit is False
    assert result.transition_applied is True


def test_new_failures_without_block_enabled_only_warns() -> None:
    result = aggregate_verdicts([_verdict(GateOutcome.NEW_FAILURES)], block_enabled=False, force=False)
    assert result.decision is AggregateDecision.WARN_PROCEED


def test_empty_verdicts_is_warn_pass() -> None:
    result = aggregate_verdicts([], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.WARN_PROCEED
    assert result.warnings == ()
    assert result.blocking_verdicts == ()
    assert result.transition_applied is True


# ---------------------------------------------------------------------------
# Synthetic multi-handler arm (FR-014 seam, squad R-F3)
#
# These cases fabricate 2-3 GateVerdicts to exercise the N-handler precedence
# branches that have NO production caller in half A (one real binding ships).
# They are the sole coverage of that forward-compatibility seam.
# ---------------------------------------------------------------------------


def test_multi_terminal_beats_block() -> None:
    """A co-firing TIMED_OUT verdict wins over a NEW_FAILURES block (terminal is tier 1)."""
    timed_out = _verdict(GateOutcome.TIMED_OUT)
    new_failures = _verdict(GateOutcome.NEW_FAILURES)
    result = aggregate_verdicts([new_failures, timed_out], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.TERMINAL
    assert result.terminal_verdict is timed_out
    assert result.transition_applied is False
    # every verdict still contributes exactly one warning slot
    assert len(result.warnings) == 2


def test_multi_block_survives_a_faulting_sibling() -> None:
    """NEW_FAILURES + a NO_COVERAGE-degraded (faulting) sibling still BLOCKS.

    US4 AS3 / NFR-002: a faulting handler's degraded verdict must NOT remove a
    co-firing handler's NEW_FAILURES from the block computation (no
    cross-suppression). Aggregation reads EVERY verdict.
    """
    degraded = _verdict(GateOutcome.NO_COVERAGE, reason="handler raised — unverified")
    new_failures = _verdict(GateOutcome.NEW_FAILURES)
    result = aggregate_verdicts([degraded, new_failures], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.BLOCK
    assert result.should_exit is True
    assert new_failures in result.blocking_verdicts
    assert len(result.warnings) == 2


def test_multi_two_warn_shaped_verdicts_never_block() -> None:
    a = _verdict(GateOutcome.NO_NEW_FAILURES)
    b = _verdict(GateOutcome.UNVERIFIED_BASELINE)
    result = aggregate_verdicts([a, b], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.WARN_PROCEED
    assert result.blocking_verdicts == ()
    assert len(result.warnings) == 2


def test_warnings_preserve_dispatch_order_and_do_not_resort() -> None:
    """``aggregate_verdicts`` consumes an already-ordered sequence and preserves it."""
    a = _verdict(GateOutcome.NEW_FAILURES)
    b = _verdict(GateOutcome.NO_COVERAGE)
    c = _verdict(GateOutcome.NO_NEW_FAILURES)
    result = aggregate_verdicts([a, b, c], block_enabled=False, force=False)
    assert result.warnings == (a, b, c)


def test_at_most_one_warning_per_handler_across_matrix() -> None:
    """The ``<=1 warning per handler`` invariant holds for every arm size."""
    for size in range(0, 4):
        verdicts = [_verdict(GateOutcome.NO_COVERAGE) for _ in range(size)]
        result = aggregate_verdicts(verdicts, block_enabled=True, force=False)
        assert len(result.warnings) == size


# ---------------------------------------------------------------------------
# T039 - fail-open fault-injection at the aggregation boundary (NFR-002)
#
# The try/except dispatch wrapping (the three-catch mirror) is WP09's; here we
# simulate its OUTPUT: a raising handler maps to a NO_COVERAGE "unverified"
# verdict, a KeyboardInterrupt maps to the terminal CANCELLED. We prove the
# aggregation half never blocks or crashes on a degraded verdict, and never
# suppresses a co-firing verdict.
# ---------------------------------------------------------------------------


def _fail_open_verdict(exc: BaseException, *, handler: str) -> GateVerdict:
    """Mirror the incumbent per-handler fail-open contract (tasks_move_task.py:1241/1248)."""
    if isinstance(exc, KeyboardInterrupt):
        return GateVerdict(
            outcome=GateOutcome.CANCELLED,
            scope=_EMPTY_SCOPE,
            reason="scoped test run cancelled",
            run_state=HeadRunState.CANCELLED,
        )
    return GateVerdict(
        outcome=GateOutcome.NO_COVERAGE,
        scope=_EMPTY_SCOPE,
        reason=f"{handler} evaluation failed — unverified: {exc}",
    )


def test_fault_injected_verdict_yields_exactly_one_warning_no_cross_suppression() -> None:
    faulting = _fail_open_verdict(RuntimeError("boom"), handler="h_bad")
    normal = _verdict(GateOutcome.NO_NEW_FAILURES)
    result = aggregate_verdicts([faulting, normal], block_enabled=True, force=False)
    # (a) transition still aggregates / completes
    assert result.decision is AggregateDecision.WARN_PROCEED
    assert result.transition_applied is True
    # (b) the faulting verdict yields exactly one warning slot
    assert result.warnings.count(faulting) == 1
    # (c) the co-firing verdict's outcome is untouched
    assert normal in result.warnings


def test_fault_injected_verdict_does_not_remove_a_block() -> None:
    """NEW_FAILURES + a fault-degraded sibling still blocks (fault never lifts the block)."""
    faulting = _fail_open_verdict(RuntimeError("boom"), handler="h_bad")
    new_failures = _verdict(GateOutcome.NEW_FAILURES)
    result = aggregate_verdicts([faulting, new_failures], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.BLOCK
    assert new_failures in result.blocking_verdicts


def test_keyboard_interrupt_fault_is_terminal() -> None:
    cancelled = _fail_open_verdict(KeyboardInterrupt(), handler="h_bad")
    normal = _verdict(GateOutcome.NEW_FAILURES)
    result = aggregate_verdicts([normal, cancelled], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.TERMINAL
    assert result.terminal_verdict is cancelled
    assert result.transition_applied is False


def test_result_type_and_should_exit_property() -> None:
    warn = aggregate_verdicts([], block_enabled=False, force=False)
    assert isinstance(warn, AggregateVerdict)
    assert warn.should_exit is False
    blocked = aggregate_verdicts([_verdict(GateOutcome.NEW_FAILURES)], block_enabled=True, force=False)
    assert blocked.should_exit is True


# ---------------------------------------------------------------------------
# Refusal tier (#7547 WP03): a proven foreign evidence tree refuses unless forced
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("block_enabled", [True, False])
def test_foreign_tree_refuses_when_not_forced_regardless_of_block(block_enabled: bool) -> None:
    foreign = _verdict(GateOutcome.FOREIGN_TREE)
    result = aggregate_verdicts([foreign], block_enabled=block_enabled, force=False)
    assert result.decision is AggregateDecision.REFUSE
    assert result.should_exit is True
    assert result.transition_applied is False
    assert result.refusing_verdicts == (foreign,)
    assert result.terminal_verdict is None


@pytest.mark.parametrize("block_enabled", [True, False])
def test_foreign_tree_forced_proceeds_and_still_lists_the_refusing_verdict(block_enabled: bool) -> None:
    foreign = _verdict(GateOutcome.FOREIGN_TREE)
    result = aggregate_verdicts([foreign], block_enabled=block_enabled, force=True)
    assert result.decision is AggregateDecision.WARN_PROCEED
    assert result.should_exit is False
    assert result.transition_applied is True
    assert result.refusing_verdicts == (foreign,)


@pytest.mark.parametrize("terminal", _TERMINAL + (GateOutcome.SCOPE_OVERSIZED,))
def test_terminal_beats_foreign_tree(terminal: GateOutcome) -> None:
    stop = _verdict(terminal)
    result = aggregate_verdicts([_verdict(GateOutcome.FOREIGN_TREE), stop], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.TERMINAL
    assert result.terminal_verdict is stop


def test_refusal_precedes_block() -> None:
    foreign = _verdict(GateOutcome.FOREIGN_TREE)
    result = aggregate_verdicts([_verdict(GateOutcome.NEW_FAILURES), foreign], block_enabled=True, force=False)
    assert result.decision is AggregateDecision.REFUSE
    assert result.refusing_verdicts == (foreign,)


@pytest.mark.parametrize("outcome", _NON_TERMINAL)
@pytest.mark.parametrize("block_enabled", [True, False])
@pytest.mark.parametrize("force", [True, False])
def test_only_foreign_tree_reaches_the_refusal_tier(outcome: GateOutcome, block_enabled: bool, force: bool) -> None:
    result = aggregate_verdicts([_verdict(outcome)], block_enabled=block_enabled, force=force)
    assert result.decision is not AggregateDecision.REFUSE
    assert result.refusing_verdicts == ()
