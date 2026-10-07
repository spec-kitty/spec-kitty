"""The engine is the single authority for "apply the result and plan the next
step" (owned-checkout-lifecycle-authority WP11, review cycle 1 findings 3/4).

``plan_advance`` computes what ``next_step`` will issue -- including the
audit-significance LOW re-plan -- WITHOUT writing anything, so the bridge can
resolve a planned WP-iteration step's workspace BEFORE the advance is
persisted. ``next_step`` is plan + commit over the same plan, so the two can
never diverge. These tests use the REAL engine and planner (no stubs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    NullEmitter,
    next_step,
    start_mission_run,
)
from runtime.next._internal_runtime.engine import _read_snapshot, apply_result, commit_advance, existing_template_path, plan_advance
from runtime.next._internal_runtime.schema import MissionRunSnapshot

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_LOW_DIMENSIONS = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}


def _start_run(tmp_path: Path, *, low_significance_gate: bool) -> Any:
    steps: list[dict[str, Any]] = [
        {"id": "lead_in", "title": "Lead-in", "description": "before the gate", "prompt": "Do the lead-in."},
    ]
    raw: dict[str, Any] = {"mission": {"key": "plan-advance", "name": "Plan advance", "version": "1.0.0"}}
    if low_significance_gate:
        raw["audit_steps"] = [
            {
                "id": "review_gate",
                "title": "Review gate",
                "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
                "depends_on": ["lead_in"],
                "significance": {"dimensions": _LOW_DIMENSIONS, "hard_triggers": []},
            }
        ]
        steps.append({"id": "after_gate", "title": "After the gate", "description": "x", "prompt": "Go on.", "depends_on": ["review_gate"]})
    else:
        steps.append({"id": "second", "title": "Second", "description": "x", "prompt": "Go on.", "depends_on": ["lead_in"]})
    raw["steps"] = steps
    mission_dir = tmp_path / "missions" / "plan-advance"
    mission_dir.mkdir(parents=True)
    yaml_path = mission_dir / "mission.yaml"
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={"mission_owner_id": "owner-1"},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )
    first = next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())
    assert first.step_id == "lead_in"
    return run_ref


def _run_files(run_ref: Any) -> dict[str, bytes]:
    run_dir = Path(run_ref.run_dir)
    return {path.name: path.read_bytes() for path in sorted(run_dir.iterdir()) if path.is_file()}


def test_plan_advance_writes_nothing(tmp_path: Path) -> None:
    run_ref = _start_run(tmp_path, low_significance_gate=False)
    before = _run_files(run_ref)

    plan = plan_advance(run_ref, "agent-1", "success")

    assert plan.decision.kind == "step"
    assert _run_files(run_ref) == before, "planning must not write or emit anything"


def test_plan_advance_is_exactly_what_next_step_then_issues(tmp_path: Path) -> None:
    run_ref = _start_run(tmp_path, low_significance_gate=False)

    plan = plan_advance(run_ref, "agent-1", "success")
    issued = next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())

    assert (plan.decision.kind, plan.decision.step_id) == (issued.kind, issued.step_id) == ("step", "second")
    assert plan.completed_step_id == "lead_in"


def test_plan_advance_includes_the_significance_low_replan(tmp_path: Path) -> None:
    """The divergence the review found in the bridge's mirror: an audit gate
    whose significance band is LOW auto-proceeds and the engine re-plans to
    the NEXT step. The plan must already contain that re-plan."""
    run_ref = _start_run(tmp_path, low_significance_gate=True)
    before = _run_files(run_ref)

    plan = plan_advance(run_ref, "agent-1", "success")

    assert _run_files(run_ref) == before
    assert (plan.decision.kind, plan.decision.step_id) == ("step", "after_gate")
    assert {"lead_in", "review_gate"} <= set(plan.snapshot.completed_steps)
    assert plan.significance is not None

    issued = next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())
    assert (issued.kind, issued.step_id) == ("step", "after_gate")
    assert _read_snapshot(Path(run_ref.run_dir)).issued_step_id == "after_gate"


@pytest.mark.parametrize("result", ["failed", "blocked"])
def test_apply_result_records_a_non_success_result_as_blocked(tmp_path: Path, result: Any) -> None:
    run_ref = _start_run(tmp_path, low_significance_gate=False)
    snapshot = _read_snapshot(Path(run_ref.run_dir))

    applied, completed_step_id = apply_result(snapshot, result)

    assert completed_step_id == "lead_in"
    assert applied.issued_step_id is None
    assert "lead_in" not in applied.completed_steps
    assert applied.blocked_reason is not None and "lead_in" in applied.blocked_reason
    assert plan_advance(run_ref, "agent-1", result).decision.kind == "blocked"


def test_apply_result_success_completes_the_issued_step_and_is_pure(tmp_path: Path) -> None:
    run_ref = _start_run(tmp_path, low_significance_gate=False)
    snapshot = _read_snapshot(Path(run_ref.run_dir))

    applied, completed_step_id = apply_result(snapshot, "success")

    assert completed_step_id == "lead_in"
    assert applied.issued_step_id is None
    assert applied.completed_steps == ["lead_in"]
    assert snapshot.issued_step_id == "lead_in", "the input snapshot is frozen and untouched"
    assert apply_result(applied, "success") == (applied, None), "nothing issued -> nothing to complete"


def test_commit_advance_issues_the_plan_it_is_given_without_replanning(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A caller that pre-planned commits THAT plan: the engine does not plan again."""
    from runtime.next._internal_runtime import engine

    run_ref = _start_run(tmp_path, low_significance_gate=False)
    plan = plan_advance(run_ref, "agent-1", "success")

    def _no_replan(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("commit_advance must not plan again")

    monkeypatch.setattr(engine, "plan_advance", _no_replan)

    issued = commit_advance(run_ref, plan, "agent-1", NullEmitter())

    assert issued is plan.decision
    assert (issued.kind, issued.step_id) == ("step", "second")
    assert _read_snapshot(Path(run_ref.run_dir)).issued_step_id == "second"


def test_commit_advance_leaves_the_same_run_state_and_events_as_next_step(tmp_path: Path) -> None:
    """``next_step`` stays plan + commit: pre-planning changes nothing durable."""
    import json

    committed = _start_run(tmp_path / "a", low_significance_gate=True)
    stepped = _start_run(tmp_path / "b", low_significance_gate=True)

    commit_advance(committed, plan_advance(committed, "agent-1", "success"), "agent-1", NullEmitter())
    next_step(stepped, agent_id="agent-1", emitter=NullEmitter())

    def _event_types(run_ref: Any) -> list[str]:
        lines = (Path(run_ref.run_dir) / "run.events.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(line)["event_type"] for line in lines]

    def _state(run_ref: Any) -> tuple[Any, ...]:
        snap = _read_snapshot(Path(run_ref.run_dir))
        return (snap.issued_step_id, sorted(snap.completed_steps), sorted(snap.decisions), sorted(snap.pending_decisions), snap.blocked_reason)

    assert _event_types(committed) == _event_types(stepped)
    assert _state(committed) == _state(stepped)


@pytest.mark.parametrize("on_disk", ["blank", "missing", "present"])
def test_existing_template_path_is_the_live_template_only_while_it_exists(tmp_path: Path, on_disk: str) -> None:
    """The plan hands the planner a live template path for drift detection only when the file still exists."""
    template_file = tmp_path / "template.yaml"
    template_path = {"blank": "", "missing": str(tmp_path / "does-not-exist.yaml"), "present": str(template_file)}[on_disk]
    template_file.write_text("x", encoding="utf-8")
    snapshot = MissionRunSnapshot(run_id="r", mission_key="m", template_path=template_path, template_hash="h")

    assert existing_template_path(snapshot) == (template_file if on_disk == "present" else None)
