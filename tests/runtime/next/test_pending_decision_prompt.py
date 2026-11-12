"""FR-010 by construction, and the additive ``next_command`` (next-lifecycle-integrity WP01).

Covers T020 (``PendingDecisionPrompt`` and the ``Decision`` prompt invariant), T002 (the
``next_command`` / ``suppress_step_pairing`` fields threaded through ``step_or_blocked``) and
T004 (``to_dict`` byte-identity).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next.decision import (
    Decision,
    DecisionKind,
    InvalidDecisionPrompt,
    PendingDecisionPrompt,
)
from runtime.next.runtime_bridge_cores import DecisionEnvelope, step_or_blocked

pytestmark = pytest.mark.fast

_BASE: dict[str, Any] = {
    "agent": "claude",
    "mission_slug": "demo-mission",
    "mission": "software-dev",
    "mission_state": "implement",
    "timestamp": "2026-11-12T09:00:00+00:00",
}


def _decision(kind: str, **fields: Any) -> Decision:
    return Decision(kind=kind, **_BASE, **fields)


def _envelope(kind: str, **fields: Any) -> DecisionEnvelope:
    return DecisionEnvelope(kind=kind, **_BASE, **fields)


# ---------------------------------------------------------------------------
# T020 -- the value object
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"decision_id": "", "question": "q", "options": ["a"]}, "decision_id"),
        ({"decision_id": "d", "question": "", "options": ["a"]}, "question"),
        ({"decision_id": "d", "question": "q"}, "options or an input_key"),
        ({"decision_id": "d", "question": "q", "options": []}, "options or an input_key"),
        ({"decision_id": "d", "question": "q", "input_key": ""}, "options or an input_key"),
        ({"decision_id": "d", "question": "q", "options": [], "input_key": ""}, "options or an input_key"),
    ],
)
def test_prompt_rejects_invalid_shapes(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(InvalidDecisionPrompt, match=message):
        PendingDecisionPrompt(**fields)


def test_invalid_prompt_is_a_value_error() -> None:
    assert issubclass(InvalidDecisionPrompt, ValueError)


@pytest.mark.parametrize("fields", [{"options": ["approve", "reject"]}, {"input_key": "k"}, {"options": ["x"], "input_key": "k"}])
def test_prompt_accepts_an_answerable_prompt(fields: dict[str, Any]) -> None:
    prompt = PendingDecisionPrompt(decision_id="d", question="q", **fields)
    assert prompt.decision_id == "d"


# ---------------------------------------------------------------------------
# T020 -- the Decision construction-time invariant
# ---------------------------------------------------------------------------


_PROMPT_KINDS = [DecisionKind.query, DecisionKind.decision_required]


@pytest.mark.parametrize("kind", _PROMPT_KINDS)
@pytest.mark.parametrize(
    ("fields", "message"),
    [
        pytest.param({"question": "q", "decision_id": None, "options": ["a"]}, "half-built prompt", id="question-without-decision-id"),
        pytest.param({"question": None, "decision_id": "d", "input_key": "k"}, "half-built prompt", id="decision-id-without-question"),
    ],
)
def test_half_built_prompt_raises(kind: str, fields: dict[str, Any], message: str) -> None:
    with pytest.raises(InvalidDecisionPrompt, match=message):
        _decision(kind, **fields)


@pytest.mark.parametrize("fields", [{}, {"options": []}, {"input_key": ""}])
def test_unanswerable_prompt_raises(fields: dict[str, Any]) -> None:
    with pytest.raises(InvalidDecisionPrompt, match="not answerable"):
        _decision(DecisionKind.decision_required, question="q", decision_id="d", **fields)


def test_query_without_a_prompt_is_fine() -> None:
    decision = _decision(DecisionKind.query, question=None, decision_id=None)
    assert decision.question is None


def test_decision_required_with_an_input_key_is_fine() -> None:
    decision = _decision(DecisionKind.decision_required, question="q", decision_id="d", input_key="k")
    assert decision.input_key == "k"


@pytest.mark.parametrize("kind", [DecisionKind.blocked, DecisionKind.terminal])
def test_other_kinds_are_not_judged(kind: str) -> None:
    decision = _decision(kind, question="q", decision_id=None)
    assert decision.question == "q"


def test_envelope_with_prompt_sets_all_four_fields() -> None:
    prompt = PendingDecisionPrompt(decision_id="input:x", question="Provide x", input_key="x")
    decision = step_or_blocked(_envelope(DecisionKind.query).with_prompt(prompt), None, prompt_exists=lambda _p: False)
    assert (decision.decision_id, decision.question, decision.input_key, decision.options) == ("input:x", "Provide x", "x", None)


def test_envelope_with_no_prompt_clears_all_four_fields() -> None:
    envelope = _envelope(DecisionKind.query, decision_id="d", question="q", options=["a"]).with_prompt(None)
    decision = step_or_blocked(envelope, None, prompt_exists=lambda _p: False)
    assert (decision.decision_id, decision.question, decision.input_key, decision.options) == (None, None, None, None)


def test_step_or_blocked_refuses_a_half_built_envelope() -> None:
    with pytest.raises(InvalidDecisionPrompt):
        step_or_blocked(_envelope(DecisionKind.query, question="q"), None, prompt_exists=lambda _p: False)


# ---------------------------------------------------------------------------
# T002 -- next_command / suppress_step_pairing threaded through every branch
# ---------------------------------------------------------------------------

_EXTRA = {"next_command": "spec-kitty accept --mission demo-mission", "suppress_step_pairing": True}


@pytest.mark.parametrize(
    ("kind", "prompt", "prompt_exists", "fields", "expected_kind", "expected_reason"),
    [
        pytest.param(DecisionKind.blocked, None, False, {}, DecisionKind.blocked, None, id="blocked"),
        pytest.param(DecisionKind.terminal, None, False, {}, DecisionKind.terminal, None, id="terminal"),
        pytest.param(DecisionKind.query, None, False, {}, DecisionKind.query, None, id="query"),
        pytest.param(DecisionKind.step, "present", True, {}, DecisionKind.step, None, id="step"),
        pytest.param(DecisionKind.step, None, False, {"reason": "no_prompt_template"}, DecisionKind.blocked, None, id="step-without-prompt-degrades-to-blocked"),
        pytest.param(DecisionKind.step, "gone", True, {}, DecisionKind.blocked, "prompt_file_not_resolvable", id="step-whose-prompt-vanished-degrades-to-blocked"),
    ],
)
def test_every_branch_threads_new_fields(
    kind: str, prompt: str | None, prompt_exists: bool, fields: dict[str, Any], expected_kind: str, expected_reason: str | None, tmp_path: Path
) -> None:
    if prompt is not None:
        prompt_file = tmp_path / f"{prompt}.md"
        if prompt == "present":
            prompt_file.write_text("x", encoding="utf-8")
        fields = {**fields, "prompt_file": str(prompt_file)}
    decision = step_or_blocked(_envelope(kind, **fields, **_EXTRA), None, prompt_exists=lambda _p: prompt_exists)
    assert decision.kind == expected_kind
    if expected_reason is not None:
        assert decision.reason == expected_reason
    assert decision.next_command == _EXTRA["next_command"]
    assert decision.suppress_step_pairing is True


def test_new_fields_survive_with_remediation() -> None:
    decision = _decision(DecisionKind.blocked, **_EXTRA)
    attached = rb._with_remediation(decision, {"kind": "materialized_coordination_worktree", "path": "/x"})
    assert attached.next_command == _EXTRA["next_command"]
    assert attached.suppress_step_pairing is True
    assert attached.to_dict()["remediation"] == {"kind": "materialized_coordination_worktree", "path": "/x"}


# ---------------------------------------------------------------------------
# T004 -- to_dict byte-identity
# ---------------------------------------------------------------------------


def test_to_dict_without_next_command_is_unchanged() -> None:
    payload = _decision(DecisionKind.blocked, suppress_step_pairing=True).to_dict()
    assert "next_command" not in payload
    assert "suppress_step_pairing" not in payload
    baseline = _decision(DecisionKind.blocked).to_dict()
    assert json.dumps(payload, sort_keys=True) == json.dumps(baseline, sort_keys=True)


def test_to_dict_with_next_command_adds_exactly_one_key() -> None:
    baseline = _decision(DecisionKind.blocked).to_dict()
    payload = _decision(DecisionKind.blocked, next_command="spec-kitty consolidate --mission demo-mission", suppress_step_pairing=True).to_dict()
    assert set(payload) - set(baseline) == {"next_command"}
    assert set(baseline) <= set(payload)
    assert payload["next_command"] == "spec-kitty consolidate --mission demo-mission"
    assert "suppress_step_pairing" not in payload
