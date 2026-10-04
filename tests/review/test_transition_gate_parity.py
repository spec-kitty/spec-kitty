"""Decision-table contract tests for the pre-review transition gate (NFR-001).

Replays the golden fixtures under ``tests/review/fixtures/parity/`` -- each a
recorded ``(outcome, scope, metadata, block/exit, console)`` tuple for one
cell of the gate decision table -- and proves the aggregation engine and the
transition-gate hook reproduce every field exactly (not "outcome matches"
alone). The fixtures are frozen expectations; they are never regenerated from
the code under test. The capture harness is retired, so a new decision-table fixture
must be hand-authored from the contract, not recorded from the code.

Two arms, deliberately:

- :func:`test_aggregation_reproduces_base_decision_and_surface` drives
  :func:`aggregate_verdicts` for the terminal/block/warn decision plus the
  metadata / console rendering helpers, and asserts the result equals each
  recorded tuple.
- :func:`test_through_the_inverted_hook_reproduces_base` drives the same
  fixtures through the hook's dispatch and translation seams
  (``_mt_dispatch_transition_gates`` / ``_mt_translate_gate_verdicts``), proving
  the contract holds through the hook, not just the engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.cli.commands.agent import tasks_move_task as tmt
from specify_cli.review.baseline import BaselineFailure
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

_FIXTURES_DIR = Path(__file__).parent / "fixtures" / "parity"


def _load_fixtures() -> list[tuple[str, dict[str, Any]]]:
    cases = [(path.name, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(_FIXTURES_DIR.glob("*.json"))]
    assert cases, f"no parity fixtures found under {_FIXTURES_DIR}"
    return cases


_FIXTURES = _load_fixtures()
_IDS = [name for name, _ in _FIXTURES]
_CASES = [case for _, case in _FIXTURES]


def _failures(items: list[dict[str, str]]) -> tuple[BaselineFailure, ...]:
    return tuple(BaselineFailure(test=i["test"], error=i["error"], file=i["file"]) for i in items)


def _rebuild_verdict(data: dict[str, Any]) -> GateVerdict:
    """Reconstruct the exact ``GateVerdict`` recorded in a fixture."""
    scope = data["scope"]
    return GateVerdict(
        outcome=GateOutcome(data["outcome"]),
        scope=ScopeResult(
            test_targets=tuple(scope["test_targets"]),
            matched_shard_groups=tuple(scope["matched_shard_groups"]),
            matched_composite_dirs=tuple(scope["matched_composite_dirs"]),
            empty_cone_composite_dirs=tuple(scope["empty_cone_composite_dirs"]),
            excluded_scope_files=tuple(scope["excluded_scope_files"]),
        ),
        reason=data["reason"],
        new_failures=_failures(data["new_failures"]),
        pre_existing_failures=_failures(data["pre_existing_failures"]),
        run_state=HeadRunState(data["run_state"]),
    )


def _actual_tuple(aggregate: AggregateVerdict, verdict: GateVerdict, *, block_enabled: bool, force: bool) -> dict[str, Any]:
    """Map the aggregate decision + verdict onto the observable parity tuple.

    This is the mapping the hook performs: derive the metadata block/force
    flags FROM the aggregate result (proving it carries enough information), then
    render metadata + console via the helpers the hook reuses.
    """
    terminal = aggregate.decision is AggregateDecision.TERMINAL
    blocked = aggregate.decision is AggregateDecision.BLOCK
    force_bypassed = block_enabled and force and bool(aggregate.blocking_verdicts)
    metadata = tmt._mt_pre_review_gate_metadata(
        verdict,
        block_enabled=block_enabled,
        blocked=blocked,
        force_bypassed=force_bypassed,
    )
    if terminal:
        metadata["transition_applied"] = False
    console = tmt._mt_pre_review_gate_console_warning(verdict, block_enabled=block_enabled)
    return {
        "outcome": verdict.outcome.value,
        "metadata": metadata,
        "console": console,
        "blocked": blocked,
        "force_bypassed": force_bypassed,
        "terminal": terminal,
        "exit_code": 1 if aggregate.should_exit else None,
        "transition_applied": aggregate.transition_applied,
    }


def test_oracle_covers_a_non_empty_shard_group_scope() -> None:
    """Coverage-gap guard (mission ``doctrine-controlled-transition-gates-01KY51Z7``
    WP09 remediation): at least one fixture MUST carry a non-empty
    ``matched_shard_groups`` so the metadata's ``matched_shard_groups`` /
    ``affected_shard_count`` fields are parity-checked at all.

    Before this guard every fixture used a ``ScopeResult.from_override`` scope,
    which zeroes the shard breakdown — so the inverted ``ScopeSource``
    reconstruction could silently drop ``matched_shard_groups`` and the oracle
    would never notice. Removing the shard fixture re-opens that gap and this
    test fails."""
    shard_carrying = [case for case in _CASES if case["verdict"]["scope"]["matched_shard_groups"]]
    assert shard_carrying, "parity oracle lost its non-empty matched_shard_groups coverage"
    for case in shard_carrying:
        assert case["expected"]["metadata"]["affected_shard_count"] >= 1
        assert case["expected"]["metadata"]["matched_shard_groups"]


def test_override_nonempty_golden_drives_a_non_empty_scope() -> None:
    """NFR-006 guard (mission ``scopesource-gate-followup-01KY6S9P`` WP01
    T003/T004): the FR-004 override-tier golden must NOT be vacuous.

    A vacuous golden would be captured from an EMPTY override scope, which
    short-circuits *inside*
    ``tasks_move_task._mt_pre_review_gate_with_override_scope`` before
    ``evaluate_with_scope``/``run_scoped_tests_at_head`` ever run (B-vacuous,
    post-plan squad finding) -- degrading "functional preservation" coverage
    to an import check. This asserts every ``override_nonempty__*`` fixture
    carries (a) a non-empty ``test_targets`` scope and (b) a ``completed``
    ``run_state`` -- i.e. the real head run actually executed, not the
    empty-scope short-circuit.
    """
    override_cases = [case for name, case in zip(_IDS, _CASES, strict=True) if name.startswith("override_nonempty__")]
    assert override_cases, "no override_nonempty__* fixtures found -- T003 must capture at least one non-empty FR-004 override-tier golden"
    for case in override_cases:
        scope = case["verdict"]["scope"]
        assert scope["test_targets"], "override_nonempty golden captured an EMPTY scope (vacuous, B-vacuous): run_scoped_tests_at_head never executed"
        assert case["verdict"]["run_state"] == "completed", (
            "override_nonempty golden's run_state is not 'completed' -- the override scope short-circuited instead of driving a real head run"
        )


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_aggregation_reproduces_base_decision_and_surface(case: dict[str, Any]) -> None:
    """The aggregation decision surface reproduces every recorded decision-table tuple."""
    verdict = _rebuild_verdict(case["verdict"])
    block_enabled = case["block_enabled"]
    force = case["force"]
    aggregate = aggregate_verdicts([verdict], block_enabled=block_enabled, force=force)
    actual = _actual_tuple(aggregate, verdict, block_enabled=block_enabled, force=force)
    expected = case["expected"]
    # Strict field-by-field comparison: metadata payload + console line + block/exit,
    # never a loose "outcome matches" (NFR-001).
    assert actual["outcome"] == expected["outcome"]
    assert actual["metadata"] == expected["metadata"]
    assert actual["console"] == expected["console"]
    assert actual["blocked"] == expected["blocked"]
    assert actual["force_bypassed"] == expected["force_bypassed"]
    assert actual["terminal"] == expected["terminal"]
    assert actual["exit_code"] == expected["exit_code"]
    assert actual["transition_applied"] == expected["transition_applied"]


def _drive_through_hook(case: dict[str, Any]) -> dict[str, Any]:
    """Drive one fixture THROUGH the hook's dispatch + aggregation seams.

    Assert the surface the way the CLI observes it: register a synthetic binding
    whose handler returns the recorded verdict, dispatch it through the
    hook's own :func:`_mt_dispatch_transition_gates` (exercising the FR-013
    per-handler fail-open path with a clean verdict — identity), then aggregate +
    render through the hook's :func:`_mt_translate_gate_verdicts`. Both are the
    real functions ``_mt_run_transition_gates`` calls, so this proves the
    contract THROUGH the hook (not against the engine in isolation) -- NFR-001.
    """
    verdict = _rebuild_verdict(case["verdict"])
    block_enabled = case["block_enabled"]
    force = case["force"]

    @dataclass(frozen=True)
    class _FixtureBinding:
        handler: str = "spec-kitty-pre-review"
        on_transition: str = "in_progress->for_review"

    def _handler_lookup(name: str) -> Any:
        return SimpleNamespace(name=name, run=lambda _ctx: verdict)

    ctx = SimpleNamespace(changed_files=("src/example.py",))
    bindings: list[Any] = [_FixtureBinding()]
    verdicts = tmt._mt_dispatch_transition_gates(bindings, ctx, handler_lookup=_handler_lookup)
    effect = tmt._mt_translate_gate_verdicts(verdicts, block_enabled=block_enabled, force=force)
    console = effect.console_lines[0] if effect.console_lines else ""
    return {
        "outcome": effect.representative.outcome.value,
        "metadata": effect.metadata,
        "console": console,
        "exit_code": 1 if effect.should_exit else None,
    }


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_through_the_inverted_hook_reproduces_base(case: dict[str, Any]) -> None:
    """The hook reproduces every recorded decision-table tuple."""
    actual = _drive_through_hook(case)
    expected = case["expected"]
    assert actual["outcome"] == expected["outcome"]
    assert actual["metadata"] == expected["metadata"]
    assert actual["console"] == expected["console"]
    assert actual["exit_code"] == expected["exit_code"]
