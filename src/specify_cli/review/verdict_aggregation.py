"""Deterministic verdict aggregation for the inverted transition-gate hook (FR-014).

This module exposes :func:`aggregate_verdicts`, a **pure function** (no I/O, no
``typer.Exit``, no console emission) that encodes the aggregation precedence the
hook (WP09, ``_mt_run_transition_gates``) orchestrates. It exists so the hook can
stay a thin orchestrator (complexity <= 15, NFR-006) and the multi-handler
precedence is unit-testable without any real gate handler.

**FR-014 synthetic seam (not dead code).** Half A ships **exactly one** production
gate binding (the Spec-Kitty pre-review handler). The N-handler aggregation
branches therefore have **no production caller** in half A -- they are a
forward-compatibility seam exercised **only** by synthetic / fabricated verdicts
in ``tests/review/test_verdict_aggregation.py`` (squad finding R-F3,
``data-model.md`` :280-285). They are deliberately retained and tested, not dead.

**Precedence (highest first), preserving the incumbent order**
(``_mt_run_pre_review_gate``, ``tasks_move_task_gates.py``: terminal check
BEFORE the block):

1. **Terminal refusal/interruption** -- if ANY verdict is
   ``SCOPE_OVERSIZED``/``TIMED_OUT``/``CANCELLED``: hard-stop,
   ``transition_applied=False`` (hook raises ``Exit(1)``). Checked BEFORE the
   block.
2. **Opt-in block** -- else block iff
   ``block_enabled AND any(v.outcome == NEW_FAILURES) AND not force`` (hook raises
   ``Exit(1)``).
3. **Warn / pass** -- else the transition completes; each verdict contributes at
   most one console warning line (rendered by the hook).

**Invariants** encoded here and asserted by the tests:

- **<=1 warning per handler** -- one warning slot per input verdict, even a
  faulting (degraded) one; :attr:`AggregateVerdict.warnings` mirrors the input
  sequence one-for-one.
- **No cross-suppression** -- a degraded verdict never removes another verdict's
  ``NEW_FAILURES`` from the block computation (US4 AS3); every verdict is read.
- **Order-preserving** -- the dispatch order is fixed by the hook's stable sort;
  this function preserves the given order and never re-sorts.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from specify_cli.review.pre_review_gate import GateOutcome, GateVerdict

# ``AggregateVerdict`` (the per-handler input row) is composed and consumed only
# within this module and its unit tests; cross-module callers pass raw verdicts
# to ``aggregate_verdicts`` and read the ``AggregateDecision`` result, so the
# input row is not exported.
__all__ = [
    "AggregateDecision",
    "aggregate_verdicts",
]

#: Terminal (hard-stop) outcomes, including deterministic pre-launch refusal.
_TERMINAL_OUTCOMES: frozenset[GateOutcome] = frozenset({GateOutcome.TIMED_OUT, GateOutcome.CANCELLED, GateOutcome.SCOPE_OVERSIZED})


class AggregateDecision(StrEnum):
    """The three mutually-exclusive aggregate decisions, in precedence order."""

    TERMINAL = "terminal"  # a TIMED_OUT/CANCELLED verdict -> hard-stop, no transition
    BLOCK = "block"  # opt-in NEW_FAILURES block engaged -> hard-stop
    WARN_PROCEED = "warn_proceed"  # transition proceeds; each verdict warns at most once


@dataclass(frozen=True)
class AggregateVerdict:
    """The value describing the aggregation decision (the hook performs the effects).

    The hook (WP09) maps this to the observable surface: it renders one console
    line per :attr:`warnings` entry, writes ``transition_applied`` into the
    transition metadata for the terminal case, and raises ``typer.Exit(1)`` when
    :attr:`should_exit` is true. This object performs none of those effects.
    """

    decision: AggregateDecision
    #: ``False`` for both hard-stops (terminal / block); ``True`` for warn-pass.
    transition_applied: bool
    #: One slot per input verdict, in the given dispatch order (never re-sorted).
    warnings: tuple[GateVerdict, ...]
    #: The ``NEW_FAILURES`` verdicts that drive (or would drive) the block; empty
    #: when none are present. Populated even on a warn-pass so callers can see
    #: why a block did/didn't engage.
    blocking_verdicts: tuple[GateVerdict, ...]
    #: The FIRST terminal verdict, or ``None`` when the decision is not terminal.
    terminal_verdict: GateVerdict | None

    @property
    def should_exit(self) -> bool:
        """True iff the hook must raise ``Exit(1)`` (terminal or engaged block)."""
        return self.decision in (AggregateDecision.TERMINAL, AggregateDecision.BLOCK)


def _first_terminal(verdicts: Sequence[GateVerdict]) -> GateVerdict | None:
    """Return the first interruption or oversized-refusal verdict, or ``None``."""
    for verdict in verdicts:
        if verdict.outcome in _TERMINAL_OUTCOMES:
            return verdict
    return None


def _should_block(*, block_enabled: bool, force: bool, blocking: Sequence[GateVerdict]) -> bool:
    """The opt-in block predicate: enabled AND >=1 NEW_FAILURES AND not forced."""
    return block_enabled and bool(blocking) and not force


def aggregate_verdicts(
    verdicts: Sequence[GateVerdict],
    *,
    block_enabled: bool,
    force: bool,
) -> AggregateVerdict:
    """Aggregate per-handler ``verdicts`` into a single deterministic decision.

    Pure: no I/O, no ``Exit``. The precedence is terminal interruption > opt-in
    block > warn/pass (see the module docstring). ``verdicts`` MUST already be in
    dispatch order; this function preserves it and never re-sorts.
    """
    ordered = tuple(verdicts)

    terminal = _first_terminal(ordered)
    if terminal is not None:
        return AggregateVerdict(
            decision=AggregateDecision.TERMINAL,
            transition_applied=False,
            warnings=ordered,
            blocking_verdicts=(),
            terminal_verdict=terminal,
        )

    blocking = tuple(v for v in ordered if v.outcome is GateOutcome.NEW_FAILURES)
    if _should_block(block_enabled=block_enabled, force=force, blocking=blocking):
        return AggregateVerdict(
            decision=AggregateDecision.BLOCK,
            transition_applied=False,
            warnings=ordered,
            blocking_verdicts=blocking,
            terminal_verdict=None,
        )

    return AggregateVerdict(
        decision=AggregateDecision.WARN_PROCEED,
        transition_applied=True,
        warnings=ordered,
        blocking_verdicts=blocking,
        terminal_verdict=None,
    )
