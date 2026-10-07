"""Characterisation of ``provide_decision_answer`` (#2562, WP01).

Pins every branch of the engine's answer flow -- the persisted ``decisions``
record, ``completed_steps``, ``blocked_reason``, ``pending_decisions``,
``inputs`` and the appended event -- so the function can be refactored without
changing behaviour. It stays as the permanent regression net for the answer flow:
each authority denial, each audit band and each input-decision branch is pinned
with exact messages and persisted state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    NullEmitter,
    next_step,
    provide_decision_answer,
    start_mission_run,
)
from runtime.next._internal_runtime.schema import ActorIdentity, MissionRuntimeError
from runtime.next._internal_runtime.significance import HARD_TRIGGER_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_LOW_DIMS = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}
_MEDIUM_DIMS = {**_LOW_DIMS, "user_customer_impact": 3, "operational_reliability_impact": 3, "architectural_system_impact": 2}

_OWNER = "owner-1"
_AUDIT_ID = "audit:review_gate"


def _human(actor_id: str = _OWNER) -> ActorIdentity:
    return ActorIdentity(actor_id=actor_id, actor_type="human", provider=None, model=None, tool=None)


def _llm(actor_id: str = "bot") -> ActorIdentity:
    return ActorIdentity(actor_id=actor_id, actor_type="llm", provider=None, model=None, tool=None)


def _start(tmp_path: Path, raw: dict[str, Any], inputs: dict[str, Any]) -> Any:
    yaml_path = tmp_path / "missions" / "m" / "mission.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    return start_mission_run(
        template_key=str(yaml_path),
        inputs=inputs,
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )


def _audit_run(tmp_path: Path, *, significance: dict[str, Any] | None, inputs: dict[str, Any] | None = None) -> Any:
    """A run parked on the ``audit:review_gate`` decision."""
    audit: dict[str, Any] = {
        "id": "review_gate",
        "title": "Review Gate",
        "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
        "depends_on": ["lead_in"],
    }
    if significance is not None:
        audit["significance"] = significance
    raw = {
        "mission": {"key": "m", "name": "M", "version": "1.0.0"},
        "steps": [{"id": "lead_in", "title": "Lead-in", "description": "d", "prompt": "Run it."}],
        "audit_steps": [audit],
    }
    run_ref = _start(tmp_path, raw, {"mission_owner_id": _OWNER} if inputs is None else inputs)
    next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())
    decision = next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())
    assert decision.decision_id == _AUDIT_ID
    return run_ref


def _input_run(tmp_path: Path, inputs: dict[str, Any] | None = None) -> Any:
    """A run parked on the ``input:topic`` decision."""
    raw = {
        "mission": {"key": "m", "name": "M", "version": "1.0.0"},
        "steps": [{"id": "s1", "title": "S1", "prompt": "do", "requires_inputs": ["topic"]}],
    }
    run_ref = _start(tmp_path, raw, inputs or {})
    decision = next_step(run_ref, agent_id="a", emitter=NullEmitter())
    assert decision.decision_id == "input:topic"
    return run_ref


def _state(run_ref: Any) -> dict[str, Any]:
    state: dict[str, Any] = json.loads((Path(run_ref.run_dir) / "state.json").read_text(encoding="utf-8"))
    return state


def _write_state(run_ref: Any, state: dict[str, Any]) -> None:
    (Path(run_ref.run_dir) / "state.json").write_text(json.dumps(state), encoding="utf-8")


def _events(run_ref: Any) -> list[dict[str, Any]]:
    lines = (Path(run_ref.run_dir) / "run.events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def _event_types(run_ref: Any) -> list[str]:
    return [e["event_type"] for e in _events(run_ref)]


def _answer(run_ref: Any, decision_id: str, answer: str, actor: ActorIdentity) -> None:
    provide_decision_answer(run_ref, decision_id, answer, actor, emitter=NullEmitter())


# ---------------------------------------------------------------------------
# Unknown decision
# ---------------------------------------------------------------------------


def test_unknown_decision_id_raises_and_writes_nothing(tmp_path: Path) -> None:
    run_ref = _input_run(tmp_path)
    before_state, before_events = _state(run_ref), _events(run_ref)
    run_id = before_state["run_id"]
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, "input:nope", "x", _human())
    assert str(exc.value) == f"Decision 'input:nope' not found in pending_decisions for run '{run_id}'"
    assert _state(run_ref) == before_state
    assert _events(run_ref) == before_events


# ---------------------------------------------------------------------------
# Input decisions
# ---------------------------------------------------------------------------


def test_input_decision_human_answer_writes_inputs_and_event(tmp_path: Path) -> None:
    run_ref = _input_run(tmp_path)
    before = _state(run_ref)
    n_events = len(_events(run_ref))
    _answer(run_ref, "input:topic", "alpha", _human("someone"))

    after = _state(run_ref)
    assert after["inputs"] == {"topic": "alpha"}
    assert after["pending_decisions"] == {}
    assert after["completed_steps"] == before["completed_steps"]
    assert after["blocked_reason"] == before["blocked_reason"]
    assert after["issued_step_id"] == before["issued_step_id"]
    record = after["decisions"]["input:topic"]
    assert record["decision_id"] == "input:topic"
    assert record["answer"] == "alpha"
    assert record["actor_type"] == "human"
    assert record["actor_id"] == "someone"
    assert record["authority_role"] == "human"
    assert record["rationale_linkage"] is None
    assert "raci_source" not in record
    assert "override_reason" not in record
    assert record["answered_by"]["actor_id"] == "someone"

    new = _events(run_ref)[n_events:]
    assert [e["event_type"] for e in new] == ["DecisionInputAnswered"]
    assert new[0]["payload"]["decision_id"] == "input:topic"
    assert new[0]["payload"]["answer"] == "alpha"
    assert new[0]["payload"]["actor"]["actor_id"] == "someone"


def test_input_decision_takes_raci_source_from_issued_step(tmp_path: Path) -> None:
    run_ref = _input_run(tmp_path)
    state = _state(run_ref)
    state["issued_step_id"] = "s1"
    state["decisions"]["raci:s1"] = {"source": "explicit", "override_reason": "because"}
    _write_state(run_ref, state)

    _answer(run_ref, "input:topic", "beta", _human("someone"))

    record = _state(run_ref)["decisions"]["input:topic"]
    assert record["raci_source"] == "explicit"
    assert record["override_reason"] == "because"
    assert _state(run_ref)["inputs"]["topic"] == "beta"


# ---------------------------------------------------------------------------
# LLM delegation
# ---------------------------------------------------------------------------


def test_llm_not_delegated_raises(tmp_path: Path) -> None:
    run_ref = _input_run(tmp_path)
    before = _state(run_ref)
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, "input:topic", "x", _llm())
    assert str(exc.value) == "LLM actor 'bot' is not delegated for decision 'input:topic'"
    assert _state(run_ref) == before


@pytest.mark.parametrize("rationale", ["", "   ", None, 7])
def test_llm_delegation_without_rationale_raises(tmp_path: Path, rationale: Any) -> None:
    record: dict[str, Any] = {"authority_role": "delegated_llm"}
    if rationale is not None:
        record["rationale_linkage"] = rationale
    run_ref = _input_run(tmp_path, {"llm_delegations": {"*": record}})
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, "input:topic", "x", _llm())
    assert str(exc.value) == "LLM delegation for decision 'input:topic' must include non-empty rationale_linkage"


def test_llm_delegated_records_authority_role_and_rationale(tmp_path: Path) -> None:
    delegations = {"input:topic": {"authority_role": "trusted_bot", "rationale_linkage": "  owner approved  "}}
    run_ref = _input_run(tmp_path, {"llm_delegations": delegations})
    _answer(run_ref, "input:topic", "gamma", _llm())

    state = _state(run_ref)
    record = state["decisions"]["input:topic"]
    assert record["authority_role"] == "trusted_bot"
    assert record["rationale_linkage"] == "owner approved"
    assert record["actor_type"] == "llm"
    assert state["inputs"]["topic"] == "gamma"
    assert state["pending_decisions"] == {}
    assert "DecisionInputAnswered" in _event_types(run_ref)


def test_llm_delegation_non_string_role_falls_back_to_delegated_llm(tmp_path: Path) -> None:
    delegations = {"*": {"authority_role": 5, "rationale_linkage": "ok"}}
    run_ref = _input_run(tmp_path, {"llm_delegations": delegations})
    _answer(run_ref, "input:topic", "gamma", _llm())
    assert _state(run_ref)["decisions"]["input:topic"]["authority_role"] == "delegated_llm"


# ---------------------------------------------------------------------------
# Audit: authority denials
# ---------------------------------------------------------------------------


def _assert_denied(run_ref: Any, before: dict[str, Any], actor: ActorIdentity, reason: str) -> None:
    n_events = len(_events(run_ref))
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, _AUDIT_ID, "approve", actor)
    assert str(exc.value) == reason
    assert _state(run_ref) == before
    new = _events(run_ref)[n_events:]
    assert [e["event_type"] for e in new] == ["DecisionAuthorityDenied"]
    payload = new[0]["payload"]
    assert payload["decision_id"] == _AUDIT_ID
    assert payload["actor_type"] == actor.actor_type
    assert payload["actor_id"] == actor.actor_id
    assert payload["authority_role"] == "mission_owner"
    assert payload["rationale_linkage"] is None
    assert payload["reason"] == reason
    assert payload["run_id"] == before["run_id"]
    assert "raci_source" in payload
    assert "override_reason" in payload


def test_audit_non_human_actor_denied(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    _assert_denied(run_ref, _state(run_ref), _llm(), "Audit decisions require a human actor")


def test_audit_missing_mission_owner_denied(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None, inputs={})
    _assert_denied(run_ref, _state(run_ref), _human(), "Audit decisions require mission_owner_id to be set in inputs")


def test_audit_wrong_owner_denied(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    _assert_denied(run_ref, _state(run_ref), _human("intruder"), f"Audit decisions require mission owner '{_OWNER}'")


def test_audit_denial_carries_raci_source_when_recorded(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    state = _state(run_ref)
    state["decisions"]["raci:review_gate"] = {"source": "inferred", "override_reason": "why"}
    _write_state(run_ref, state)
    with pytest.raises(MissionRuntimeError):
        _answer(run_ref, _AUDIT_ID, "approve", _llm())
    payload = _events(run_ref)[-1]["payload"]
    assert payload["raci_source"] == "inferred"
    assert payload["override_reason"] == "why"


# ---------------------------------------------------------------------------
# Audit: no significance
# ---------------------------------------------------------------------------


def test_audit_no_significance_approve_completes_step(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    n_events = len(_events(run_ref))
    _answer(run_ref, _AUDIT_ID, "approve", _human())

    state = _state(run_ref)
    assert "review_gate" in state["completed_steps"]
    assert state["blocked_reason"] is None
    assert _AUDIT_ID not in state["pending_decisions"]
    record = state["decisions"][_AUDIT_ID]
    assert record["answer"] == "approve"
    assert record["authority_role"] == "mission_owner"
    assert record["rationale_linkage"] is None
    assert record["actor_id"] == _OWNER
    assert not any(k.startswith("soft_gate:") for k in state["decisions"])
    new = _events(run_ref)[n_events:]
    assert [e["event_type"] for e in new] == ["DecisionInputAnswered"]
    assert new[0]["payload"]["answer"] == "approve"


def test_audit_no_significance_reject_blocks_run(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    before = _state(run_ref)
    _answer(run_ref, _AUDIT_ID, "reject", _human())

    state = _state(run_ref)
    assert state["blocked_reason"] == f"Audit step 'review_gate' rejected by {_OWNER}"
    assert state["completed_steps"] == before["completed_steps"]
    assert _AUDIT_ID not in state["pending_decisions"]
    assert state["decisions"][_AUDIT_ID]["answer"] == "reject"
    assert _event_types(run_ref)[-1] == "DecisionInputAnswered"


def test_audit_no_significance_invalid_answer_raises(tmp_path: Path) -> None:
    run_ref = _audit_run(tmp_path, significance=None)
    before = _state(run_ref)
    n_events = len(_events(run_ref))
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, _AUDIT_ID, "yolo", _human())
    assert str(exc.value) == "Invalid audit answer 'yolo': must be 'approve' or 'reject'"
    assert _state(run_ref) == before
    assert len(_events(run_ref)) == n_events


# ---------------------------------------------------------------------------
# Audit: HIGH band
# ---------------------------------------------------------------------------


def _high_run(tmp_path: Path) -> Any:
    hard_id = next(iter(HARD_TRIGGER_REGISTRY))
    run_ref = _audit_run(tmp_path, significance={"dimensions": _LOW_DIMS, "hard_triggers": [hard_id]})
    assert _state(run_ref)["decisions"][f"significance:{_AUDIT_ID}"]["effective_band"]["name"] == "high"
    return run_ref


def test_audit_high_band_approve_accepted(tmp_path: Path) -> None:
    run_ref = _high_run(tmp_path)
    _answer(run_ref, _AUDIT_ID, "approve", _human())
    state = _state(run_ref)
    assert "review_gate" in state["completed_steps"]
    assert not any(k.startswith("soft_gate:") for k in state["decisions"])


def test_audit_high_band_reject_accepted(tmp_path: Path) -> None:
    run_ref = _high_run(tmp_path)
    _answer(run_ref, _AUDIT_ID, "reject", _human())
    assert _state(run_ref)["blocked_reason"] == f"Audit step 'review_gate' rejected by {_OWNER}"


def test_audit_high_band_rejects_other_answers(tmp_path: Path) -> None:
    run_ref = _high_run(tmp_path)
    before = _state(run_ref)
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, _AUDIT_ID, "decide_solo", _human())
    assert str(exc.value) == "High-band decision requires one of {'approve', 'reject'}, got: 'decide_solo'"
    assert _state(run_ref) == before


# ---------------------------------------------------------------------------
# Audit: MEDIUM band
# ---------------------------------------------------------------------------


def _medium_run(tmp_path: Path) -> Any:
    run_ref = _audit_run(tmp_path, significance={"dimensions": _MEDIUM_DIMS, "hard_triggers": []})
    assert _state(run_ref)["decisions"][f"significance:{_AUDIT_ID}"]["effective_band"]["name"] == "medium"
    return run_ref


def test_audit_medium_decide_solo_records_soft_gate_and_completes(tmp_path: Path) -> None:
    run_ref = _medium_run(tmp_path)
    _answer(run_ref, _AUDIT_ID, "decide_solo", _human())

    state = _state(run_ref)
    gate = state["decisions"][f"soft_gate:{_AUDIT_ID}"]
    assert gate["action"] == "decide_solo"
    assert gate["outcome"] == "decide_solo"
    assert gate["decision_id"] == _AUDIT_ID
    assert gate["actor"] == {"actor_type": "human", "actor_id": _OWNER}
    assert "review_gate" in state["completed_steps"]
    assert _AUDIT_ID not in state["pending_decisions"]
    assert state["blocked_reason"] is None
    assert state["decisions"][_AUDIT_ID]["answer"] == "decide_solo"
    assert _event_types(run_ref)[-1] == "DecisionInputAnswered"


@pytest.mark.parametrize("answer", ["open_stand_up", "defer"])
def test_audit_medium_open_gate_readds_original_pending(tmp_path: Path, answer: str) -> None:
    run_ref = _medium_run(tmp_path)
    before = _state(run_ref)
    original = before["pending_decisions"][_AUDIT_ID]
    _answer(run_ref, _AUDIT_ID, answer, _human())

    state = _state(run_ref)
    assert state["pending_decisions"][_AUDIT_ID] == original
    gate = state["decisions"][f"soft_gate:{_AUDIT_ID}"]
    assert gate["action"] == answer
    assert gate["outcome"] is None
    assert state["completed_steps"] == before["completed_steps"]
    assert state["blocked_reason"] is None
    assert state["decisions"][_AUDIT_ID]["answer"] == answer
    assert _event_types(run_ref)[-1] == "DecisionInputAnswered"


def test_audit_medium_rejects_approve(tmp_path: Path) -> None:
    run_ref = _medium_run(tmp_path)
    before = _state(run_ref)
    with pytest.raises(MissionRuntimeError) as exc:
        _answer(run_ref, _AUDIT_ID, "approve", _human())
    assert str(exc.value) == "Medium-band decision requires one of ['decide_solo', 'defer', 'open_stand_up'], got: 'approve'"
    assert _state(run_ref) == before
