"""FR-033 integration: branch-strategy gate for PR-bound missions.

Authority: ``kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/spec.md``
section FR-033 and ``research.md`` D15.

The gate fires only when:
  * the mission is declared PR-bound (``meta.json``'s ``pr_bound: true``), AND
  * the operator's cwd branch == ``merge_target_branch``.

It is suppressed by ``--branch-strategy already-confirmed`` and is a
no-op for non-PR-bound missions or when the operator is on a feature
branch. We exercise the pure-function gate
(:func:`evaluate_branch_strategy`) so the assertions are deterministic
and don't require a live git repo or Typer prompt loop.
"""

from __future__ import annotations

from typing import Iterator

import pytest

from specify_cli.cli.commands._branch_strategy_gate import (
    ALREADY_CONFIRMED,
    BranchStrategyGateError,
    evaluate_branch_strategy,
)


pytestmark = [pytest.mark.integration]

class _RecordingPrompt:
    """Mock prompt that records every prompt call and returns a scripted answer."""

    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.calls: list[str] = []

    def __call__(self, message: str) -> bool:
        self.calls.append(message)
        return self.answer


def test_pr_bound_on_target_branch_prompts_for_confirmation() -> None:
    prompt = _RecordingPrompt(answer=True)
    outcome = evaluate_branch_strategy(
        pr_bound=True,
        current_branch="main",
        merge_target_branch="main",
        branch_strategy=None,
        prompt=prompt,
    )

    assert outcome.prompted is True
    assert outcome.decision.proceed is True
    assert outcome.decision.reason == "operator-confirmed"
    assert len(prompt.calls) == 1
    assert "main" in prompt.calls[0]


def test_pr_bound_on_target_branch_operator_declines() -> None:
    prompt = _RecordingPrompt(answer=False)
    outcome = evaluate_branch_strategy(
        pr_bound=True,
        current_branch="main",
        merge_target_branch="main",
        branch_strategy=None,
        prompt=prompt,
    )

    assert outcome.prompted is True
    assert outcome.decision.proceed is False
    assert outcome.decision.reason == "operator-aborted"


def test_pr_bound_with_already_confirmed_suppresses_prompt() -> None:
    prompt = _RecordingPrompt(answer=False)  # would block if called
    outcome = evaluate_branch_strategy(
        pr_bound=True,
        current_branch="main",
        merge_target_branch="main",
        branch_strategy=ALREADY_CONFIRMED,
        prompt=prompt,
    )

    assert outcome.prompted is False
    assert outcome.decision.proceed is True
    assert outcome.decision.reason == "already-confirmed"
    assert prompt.calls == []


def test_non_pr_bound_mission_is_a_no_op_even_on_main() -> None:
    """Existing non-PR-bound flow must continue without prompting (legacy)."""
    prompt = _RecordingPrompt(answer=False)
    outcome = evaluate_branch_strategy(
        pr_bound=False,
        current_branch="main",
        merge_target_branch="main",
        branch_strategy=None,
        prompt=prompt,
    )

    assert outcome.prompted is False
    assert outcome.decision.proceed is True
    assert prompt.calls == []


def test_pr_bound_on_feature_branch_is_a_no_op() -> None:
    prompt = _RecordingPrompt(answer=False)
    outcome = evaluate_branch_strategy(
        pr_bound=True,
        current_branch="feature/widen",
        merge_target_branch="main",
        branch_strategy=None,
        prompt=prompt,
    )

    assert outcome.prompted is False
    assert outcome.decision.proceed is True
    assert prompt.calls == []


def test_pr_bound_with_detached_head_skips_gate() -> None:
    """A None ``current_branch`` (detached HEAD) cannot match the target."""
    prompt = _RecordingPrompt(answer=False)
    outcome = evaluate_branch_strategy(
        pr_bound=True,
        current_branch=None,
        merge_target_branch="main",
        branch_strategy=None,
        prompt=prompt,
    )

    assert outcome.prompted is False
    assert outcome.decision.proceed is True


def test_gate_without_prompt_callable_is_a_programmer_error() -> None:
    with pytest.raises(BranchStrategyGateError):
        evaluate_branch_strategy(
            pr_bound=True,
            current_branch="main",
            merge_target_branch="main",
            branch_strategy=None,
            prompt=None,
        )
