"""Parity oracle replay harness (WP08 / T038, NFR-001).

Replays the golden fixtures under ``tests/review/fixtures/parity/`` -- captured
from **base commit ``7081cf053``** (mission ``scopesource-gate-followup-01KY6S9P``
WP01 re-pin -- this lane's HEAD, byte-identical to the mission's nominal base
``eb06ca176`` under ``src/specify_cli/review/`` and ``tests/review/``) against
the **incumbent** ``_mt_run_pre_review_gate`` (see ``fixtures/parity/_capture.py``)
-- and proves the post-refactor path reproduces the base ``(outcome, scope,
metadata, block/exit, console)`` tuple **field-by-field** (not "outcome
matches" alone).

**Oracle provenance (anti-circular, squad R-F2).** The expected values are NEVER
regenerated from HEAD; every fixture carries a machine-emitted ``base_commit``
header equal to ``7081cf053``. This harness asserts that provenance before
trusting any fixture.

**Two arms, deliberately:**

- :func:`test_aggregation_reproduces_base_decision_and_surface` (GREEN now) drives
  the WP08-owned decision surface -- :func:`aggregate_verdicts` for the
  terminal/block/warn decision plus the (unchanged-since-base) incumbent
  ``_mt_pre_review_gate_metadata`` / ``_mt_pre_review_gate_console_warning``
  helpers -- and asserts it equals each base-captured tuple. This proves the new
  aggregation reproduces the base *decision* and that the metadata/console
  surface has not drifted from base.
- :func:`test_through_the_inverted_hook_reproduces_base` drives the fixtures
  **through** the refactored hook ``_mt_run_transition_gates``, the surface
  under test for full NFR-001 parity. WP09 has landed that symbol and this
  arm is a plain, unconditional assertion (no ``xfail`` marker) proving
  parity through the hook, not just the engine.
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

# WP09 lands ``_mt_run_transition_gates`` (generalizes ``_mt_run_pre_review_gate``,
# tasks_move_task.py:1160) -- the surface the through-hook arm proves parity for.
_WP09_HOOK = "_mt_run_transition_gates"

#: Re-pinned by mission ``scopesource-gate-followup-01KY6S9P`` WP01 (see the
#: matching constant + rationale in ``fixtures/parity/_capture.py``): this is
#: this lane's actual HEAD, not the mission's nominal base ``eb06ca176``
#: literal -- the two are byte-identical under ``src/specify_cli/review/`` and
#: ``tests/review/``, so this SHA IS the incumbent for gate-behaviour purposes.
BASE_COMMIT = "7081cf0537c6d2b7cddde3b1bd3c09be2dc61e41"
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

    This is the mapping the WP09 hook performs: derive the metadata block/force
    flags FROM the aggregate result (proving it carries enough information), then
    render metadata + console via the incumbent helpers the hook reuses.
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
def test_fixture_provenance_is_machine_emitted_base_commit(case: dict[str, Any]) -> None:
    """Every fixture must carry the base-commit provenance header (anti-circular)."""
    assert case["base_commit"] == BASE_COMMIT
    assert BASE_COMMIT in case["oracle_provenance"]


@pytest.mark.parametrize("case", _CASES, ids=_IDS)
def test_aggregation_reproduces_base_decision_and_surface(case: dict[str, Any]) -> None:
    """The WP08 decision surface reproduces every base-captured parity tuple."""
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
    """Drive one fixture THROUGH the inverted hook's dispatch + aggregation (WP09).

    Assert the surface the way the CLI observes it: register a synthetic binding
    whose handler returns the base-captured verdict, dispatch it through the
    hook's own :func:`_mt_dispatch_transition_gates` (exercising the FR-013
    per-handler fail-open path with a clean verdict — identity), then aggregate +
    render through the hook's :func:`_mt_translate_gate_verdicts`. Both are the
    real functions ``_mt_run_transition_gates`` calls, so this proves parity
    THROUGH the hook (not against the engine in isolation) — the NFR-001 guard
    WP08 authored red and WP09 turns green.
    """
    # WP09 lands ``_mt_run_transition_gates``; assert its presence (the symbol the
    # through-hook parity is defined against) before driving its dispatch seam.
    assert hasattr(tmt, _WP09_HOOK), f"WP09 must land {_WP09_HOOK!r}"

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
    """WP09: parity THROUGH the inverted hook reproduces every base-captured tuple."""
    actual = _drive_through_hook(case)
    expected = case["expected"]
    assert actual["outcome"] == expected["outcome"]
    assert actual["metadata"] == expected["metadata"]
    assert actual["console"] == expected["console"]
    assert actual["exit_code"] == expected["exit_code"]
