"""Acceptance tests for adopting the package decision-significance models (#6445).

Core builds its ``SignificanceEvaluated`` payload, resolved RACI snapshots and
soft-gate actors from ``spec_kitty_events``; every resolved or persisted RACI
role carries an actor id. When no id resolves from the runtime inputs, a human
role takes ``HUMAN_IN_CHARGE_ACTOR_ID`` and an llm or service role takes
``UNKNOWN_ACTOR_ID`` (operator ruling on #6445, 2026-10-19).

Every test drives an existing entry point: ``infer_raci``, ``resolve_raci``,
the engine's audit-gate planning (``next_step``) and its soft-gate recording.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import pytest
import yaml
from spec_kitty_events import (
    HUMAN_IN_CHARGE_ACTOR_ID,
    UNKNOWN_ACTOR_ID,
    ResolvedRaciSnapshot,
)
from spec_kitty_events.conformance import validate_event

from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    MissionRunRef,
    NullEmitter,
    next_step,
    start_mission_run,
)
from runtime.next._internal_runtime import engine as engine_mod
from runtime.next._internal_runtime import schema as schema_mod
from runtime.next._internal_runtime import significance as sig_mod
from runtime.next._internal_runtime.raci import infer_raci, resolve_raci
from runtime.next._internal_runtime.schema import (
    ActorIdentity,
    AuditConfig,
    AuditStep,
    MissionRuntimeError,
    PromptStep,
)
from runtime.next._internal_runtime.significance import evaluate_significance

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SENTINEL_BY_TYPE = {
    "human": HUMAN_IN_CHARGE_ACTOR_ID,
    "llm": UNKNOWN_ACTOR_ID,
    "service": UNKNOWN_ACTOR_ID,
}

_LOW_DIMS = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}
_MEDIUM_DIMS = {
    **_LOW_DIMS,
    "user_customer_impact": 3,
    "operational_reliability_impact": 3,
    "architectural_system_impact": 2,
}
_HIGH_DIMS = dict.fromkeys(_LOW_DIMS, 3)


def _audit_step(enforcement: Literal["blocking", "advisory"]) -> AuditStep:
    return AuditStep(
        id="gate",
        title="Gate",
        audit=AuditConfig(trigger_mode="manual", enforcement=enforcement),
    )


def _all_roles(snapshot: ResolvedRaciSnapshot) -> list[tuple[str, str]]:
    roles = [snapshot.responsible, snapshot.accountable, *snapshot.consulted, *snapshot.informed]
    return [(role.actor_type, role.actor_id) for role in roles]


# ---------------------------------------------------------------------------
# (a) infer_raci returns a package snapshot whose every role holds a sentinel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("step", "rule"),
    [
        (PromptStep(id="p1", title="P1"), "prompt_default"),
        (_audit_step("advisory"), "audit_advisory"),
        (_audit_step("blocking"), "audit_blocking"),
    ],
    ids=["prompt", "advisory-audit", "blocking-audit"],
)
def test_infer_raci_returns_package_snapshot_with_sentinels(step: PromptStep | AuditStep, rule: str) -> None:
    snapshot = infer_raci(step, MissionPolicySnapshot())

    assert isinstance(snapshot, ResolvedRaciSnapshot)
    assert snapshot.source == "inferred"
    assert snapshot.inferred_rule == rule
    for actor_type, actor_id in _all_roles(snapshot):
        assert actor_id == _SENTINEL_BY_TYPE[actor_type]


def test_infer_raci_resolves_known_agent_and_keeps_sentinel_for_unknown_owner() -> None:
    """FR-005: the fallback records a known actor before any sentinel applies."""
    snapshot = infer_raci(PromptStep(id="p1", title="P1"), MissionPolicySnapshot(), {"agent_id": "claude"})

    assert (snapshot.responsible.actor_type, snapshot.responsible.actor_id) == ("llm", "claude")
    assert (snapshot.accountable.actor_type, snapshot.accountable.actor_id) == ("human", HUMAN_IN_CHARGE_ACTOR_ID)


def test_infer_raci_resolves_mission_owner_for_blocking_audit() -> None:
    snapshot = infer_raci(_audit_step("blocking"), MissionPolicySnapshot(), {"mission_owner_id": "alice"})

    assert (snapshot.responsible.actor_type, snapshot.responsible.actor_id) == ("human", "alice")
    assert (snapshot.accountable.actor_type, snapshot.accountable.actor_id) == ("human", "alice")


@pytest.mark.parametrize("inputs", [None, {}], ids=["none", "empty"])
def test_infer_raci_without_inputs_records_sentinels(inputs: dict[str, Any] | None) -> None:
    snapshot = infer_raci(PromptStep(id="p1", title="P1"), MissionPolicySnapshot(), inputs)

    for actor_type, actor_id in _all_roles(snapshot):
        assert actor_id == _SENTINEL_BY_TYPE[actor_type]


# ---------------------------------------------------------------------------
# (b) resolve_raci: inputs first, sentinels for unresolved C/I, R/A fail closed
# ---------------------------------------------------------------------------


def test_resolve_raci_records_input_ids_not_sentinels() -> None:
    step = PromptStep(id="p1", title="P1")
    inputs = {"mission_owner_id": "owner-42", "agent_id": "claude"}

    snapshot = resolve_raci(step, inputs, MissionPolicySnapshot())

    assert isinstance(snapshot, ResolvedRaciSnapshot)
    assert snapshot.responsible.actor_id == "claude"
    assert snapshot.accountable.actor_id == "owner-42"


def test_resolve_raci_explicit_unresolved_consulted_and_informed_get_sentinels() -> None:
    explicit = schema_mod.RACIAssignment.model_validate(
        {
            "responsible": {"actor_type": "llm", "actor_id": "claude"},
            "accountable": {"actor_type": "human", "actor_id": "owner-42"},
            "consulted": [{"actor_type": "human"}],
            "informed": [{"actor_type": "llm"}],
        }
    )
    step = PromptStep(id="p1", title="P1", raci=explicit, raci_override_reason="expert oversight")

    snapshot = resolve_raci(step, {}, MissionPolicySnapshot())

    assert isinstance(snapshot, ResolvedRaciSnapshot)
    assert snapshot.responsible.actor_id == "claude"
    assert snapshot.accountable.actor_id == "owner-42"
    assert [c.actor_id for c in snapshot.consulted] == [HUMAN_IN_CHARGE_ACTOR_ID]
    assert [i.actor_id for i in snapshot.informed] == [UNKNOWN_ACTOR_ID]


def test_resolve_raci_missing_owner_for_accountable_human_still_fails_closed() -> None:
    step = PromptStep(id="p1", title="P1")

    with pytest.raises(MissionRuntimeError, match="RACI escalation"):
        resolve_raci(step, {"agent_id": "claude"}, MissionPolicySnapshot())


def _explicit_step(*, responsible_id: str, accountable_id: str, consulted: list[dict[str, str]], informed: list[dict[str, str]]) -> PromptStep:
    assignment = schema_mod.RACIAssignment.model_validate(
        {
            "responsible": {"actor_type": "llm", "actor_id": responsible_id},
            "accountable": {"actor_type": "human", "actor_id": accountable_id},
            "consulted": consulted,
            "informed": informed,
        }
    )
    return PromptStep(id="p1", title="P1", raci=assignment, raci_override_reason="expert oversight")


@pytest.mark.parametrize(("responsible_id", "accountable_id"), [("  ", ""), ("", "   ")], ids=["ws-r", "ws-a"])
def test_resolve_raci_blank_template_ra_ids_resolve_from_inputs(responsible_id: str, accountable_id: str) -> None:
    step = _explicit_step(responsible_id=responsible_id, accountable_id=accountable_id, consulted=[], informed=[])

    snapshot = resolve_raci(step, {"agent_id": "claude", "mission_owner_id": "owner-42"}, MissionPolicySnapshot())

    assert snapshot.responsible.actor_id == "claude"
    assert snapshot.accountable.actor_id == "owner-42"


@pytest.mark.parametrize(("responsible_id", "accountable_id"), [("  ", ""), ("claude", "   ")], ids=["blank-r", "blank-a"])
def test_resolve_raci_blank_template_ra_ids_without_inputs_fail_closed(responsible_id: str, accountable_id: str) -> None:
    """A blank R/A id with nothing in the inputs escalates (``MissionRuntimeError``),
    never a pydantic ``ValidationError`` from the package's non-empty ``actor_id``."""
    step = _explicit_step(responsible_id=responsible_id, accountable_id=accountable_id, consulted=[], informed=[])

    with pytest.raises(MissionRuntimeError, match="RACI escalation"):
        resolve_raci(step, {}, MissionPolicySnapshot())


@pytest.mark.parametrize("actor_type", ["human", "llm", "service"])
@pytest.mark.parametrize("blank_id", ["", "   "], ids=["empty", "blank"])
def test_resolve_raci_blank_template_ci_ids_get_sentinel(actor_type: str, blank_id: str) -> None:
    role = {"actor_type": actor_type, "actor_id": blank_id}
    step = _explicit_step(responsible_id="claude", accountable_id="owner-42", consulted=[role], informed=[role])

    snapshot = resolve_raci(step, {}, MissionPolicySnapshot())

    assert [c.actor_id for c in snapshot.consulted] == [_SENTINEL_BY_TYPE[actor_type]]
    assert [i.actor_id for i in snapshot.informed] == [_SENTINEL_BY_TYPE[actor_type]]


# ---------------------------------------------------------------------------
# (c) engine audit-gate run: the SignificanceEvaluated row validates with the package
# ---------------------------------------------------------------------------


def _start_audit_run(
    tmp_path: Path,
    *,
    dimensions: dict[str, int],
    inputs: dict[str, Any],
    agent_id: str = "agent-1",
) -> MissionRunRef:
    """A run planned up to its ``audit:review_gate`` decision."""
    yaml_path = tmp_path / "missions" / "m" / "mission.yaml"
    yaml_path.parent.mkdir(parents=True)
    raw = {
        "mission": {"key": "m", "name": "M", "version": "1.0.0"},
        "steps": [{"id": "lead_in", "title": "Lead-in", "description": "d", "prompt": "Run it."}],
        "audit_steps": [
            {
                "id": "review_gate",
                "title": "Review Gate",
                "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
                "depends_on": ["lead_in"],
                "significance": {"dimensions": dimensions, "hard_triggers": []},
            }
        ],
    }
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs=inputs,
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )
    next_step(run_ref, agent_id=agent_id, emitter=NullEmitter())
    next_step(run_ref, agent_id=agent_id, emitter=NullEmitter())
    return run_ref


def _significance_rows(run_ref: MissionRunRef) -> list[dict[str, Any]]:
    lines = (Path(run_ref.run_dir) / "run.events.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines if line.strip()]
    return [row for row in rows if row["event_type"] == "SignificanceEvaluated"]


def _decisions(run_ref: MissionRunRef) -> dict[str, Any]:
    state: dict[str, Any] = json.loads((Path(run_ref.run_dir) / "state.json").read_text(encoding="utf-8"))
    decisions: dict[str, Any] = state["decisions"]
    return decisions


def test_audit_gate_significance_row_validates_with_package(tmp_path: Path) -> None:
    run_ref = _start_audit_run(tmp_path, dimensions=_HIGH_DIMS, inputs={"mission_owner_id": "owner-1"})

    rows = _significance_rows(run_ref)

    assert len(rows) == 1
    result = validate_event(rows[0]["payload"], "SignificanceEvaluated")
    assert result.valid, result
    assert rows[0]["payload"]["actor"] == {"actor_type": "service", "actor_id": "runtime"}


def test_audit_gate_fallback_raci_record_validates_with_package(tmp_path: Path) -> None:
    """No ``mission_owner_id``: ``resolve_raci`` fails closed and the engine
    persists the inferred fallback, which now carries sentinels."""
    run_ref = _start_audit_run(tmp_path, dimensions=_HIGH_DIMS, inputs={"topic": "x"})

    record = _decisions(run_ref)["raci:review_gate"]

    snapshot = ResolvedRaciSnapshot.model_validate(record)
    assert snapshot.inferred_rule == "audit_blocking"
    for actor_type, actor_id in _all_roles(snapshot):
        assert actor_id == _SENTINEL_BY_TYPE[actor_type]


def test_issued_step_fallback_raci_records_known_agent(tmp_path: Path) -> None:
    """No ``mission_owner_id``: the engine's fallback still records the agent
    the runtime knows and the sentinel only for the unresolved owner (FR-005)."""
    run_ref = _start_audit_run(tmp_path, dimensions=_HIGH_DIMS, inputs={"topic": "x"}, agent_id="claude")

    snapshot = ResolvedRaciSnapshot.model_validate(_decisions(run_ref)["raci:lead_in"])

    assert snapshot.source == "inferred"
    assert (snapshot.responsible.actor_type, snapshot.responsible.actor_id) == ("llm", "claude")
    assert (snapshot.accountable.actor_type, snapshot.accountable.actor_id) == ("human", HUMAN_IN_CHARGE_ACTOR_ID)


# ---------------------------------------------------------------------------
# (d) medium-band soft gate answered by an actor with no id records the sentinel
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("blank_id", ["", "   "], ids=["empty", "blank"])
def test_soft_gate_actor_without_id_records_sentinel(blank_id: str) -> None:
    score = evaluate_significance(dimension_scores=_MEDIUM_DIMS)
    assert score.effective_band.name == "medium"
    decisions: dict[str, Any] = {"significance:audit:g": score.model_dump(mode="json")}
    # Calls ``_record_soft_gate`` directly: the sentinel branch is defensive and
    # unreachable through ``provide_decision_answer``, because the validated
    # actor identity refuses an empty id and an audit answer requires
    # ``actor_id == mission_owner_id``. ``model_construct`` models an upstream
    # actor whose id never resolved.
    actor = ActorIdentity.model_construct(actor_id=blank_id, actor_type="human", provider=None, model=None, tool=None)

    engine_mod._record_soft_gate(decisions, "audit:g", "decide_solo", actor)

    assert decisions["soft_gate:audit:g"]["actor"] == {
        "actor_type": "human",
        "actor_id": HUMAN_IN_CHARGE_ACTOR_ID,
    }


# ---------------------------------------------------------------------------
# (e) the local copies are gone
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "name"),
    [
        (sig_mod, "SignificanceEvaluatedPayload"),
        (sig_mod, "TimeoutExpiredPayload"),
        (schema_mod, "ResolvedRACIBinding"),
        (schema_mod, "RACIRoleBinding"),
    ],
)
def test_local_model_copies_are_deleted(module: object, name: str) -> None:
    assert not hasattr(module, name)
