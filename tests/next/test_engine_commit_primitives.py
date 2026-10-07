"""Engine commit primitives and the ``before_run_completed`` guard (#2562, WP01)."""

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
    start_mission_run,
)
from runtime.next._internal_runtime.engine import (
    MissionRunRef,
    StaleAdvancePlan,
    commit_advance,
    plan_advance,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _RecordingEmitter(NullEmitter):
    """Records the order of emitted events by method name."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self.calls.append("completed")

    def emit_significance_evaluated(self, payload: Any) -> None:
        self.calls.append("significance")

    def emit_next_step_issued(self, payload: Any) -> None:
        self.calls.append("issued")

    def emit_decision_input_requested(self, payload: Any) -> None:
        self.calls.append("requested")

    def emit_mission_run_completed(self, payload: Any) -> None:
        self.calls.append("run_completed")


def _start(tmp_path: Path, steps: list[dict[str, Any]]) -> MissionRunRef:
    yaml_path = tmp_path / "missions" / "m" / "mission.yaml"
    yaml_path.parent.mkdir(parents=True)
    raw = {"mission": {"key": "m", "name": "M", "version": "1.0.0"}, "steps": steps}
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    return start_mission_run(
        template_key=str(yaml_path),
        inputs={},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )


_ONE_STEP = [{"id": "s1", "title": "S1", "prompt": "do"}]


def _at_last_step(tmp_path: Path) -> MissionRunRef:
    """A one-step run with ``s1`` issued: the next success advance is terminal."""
    run_ref = _start(tmp_path, _ONE_STEP)
    assert next_step(run_ref, agent_id="a").kind == "step"
    return run_ref


def _state_text(run_ref: MissionRunRef) -> str:
    return (Path(run_ref.run_dir) / "state.json").read_text(encoding="utf-8")


def _event_types(run_ref: MissionRunRef) -> list[str]:
    lines = (Path(run_ref.run_dir) / "run.events.jsonl").read_text(encoding="utf-8").splitlines()
    return [json.loads(line)["event_type"] for line in lines if line.strip()]


def test_commit_order_completed_issued_then_snapshot(tmp_path: Path) -> None:
    run_ref = _start(tmp_path, [{"id": "s1", "title": "S1", "prompt": "do"}, {"id": "s2", "title": "S2", "prompt": "do", "depends_on": ["s1"]}])
    next_step(run_ref, agent_id="a")
    emitter = _RecordingEmitter()
    decision = next_step(run_ref, agent_id="a", emitter=emitter)

    assert decision.step_id == "s2"
    assert emitter.calls == ["completed", "issued"]
    assert _event_types(run_ref)[-2:] == ["NextStepAutoCompleted", "NextStepIssued"]
    assert json.loads(_state_text(run_ref))["issued_step_id"] == "s2"


def test_commit_order_terminal_runs_completed_then_run_completed(tmp_path: Path) -> None:
    run_ref = _at_last_step(tmp_path)
    emitter = _RecordingEmitter()
    decision = next_step(run_ref, agent_id="a", emitter=emitter)

    assert decision.kind == "terminal"
    assert emitter.calls == ["completed", "run_completed"]
    assert _event_types(run_ref)[-2:] == ["NextStepAutoCompleted", "MissionRunCompleted"]
    assert json.loads(_state_text(run_ref))["issued_step_id"] is None


def test_commit_order_significance_between_completed_and_requested(tmp_path: Path) -> None:
    raw = {
        "mission": {"key": "m", "name": "M", "version": "1.0.0"},
        "steps": [{"id": "lead_in", "title": "Lead", "prompt": "do"}],
        "audit_steps": [
            {
                "id": "gate",
                "title": "Gate",
                "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
                "depends_on": ["lead_in"],
                "significance": {
                    "dimensions": {
                        "user_customer_impact": 3,
                        "architectural_system_impact": 3,
                        "data_security_compliance_impact": 3,
                        "operational_reliability_impact": 3,
                        "financial_commercial_impact": 3,
                        "cross_team_blast_radius": 3,
                    },
                    "hard_triggers": [],
                },
            }
        ],
    }
    yaml_path = tmp_path / "missions" / "m" / "mission.yaml"
    yaml_path.parent.mkdir(parents=True)
    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=True), encoding="utf-8")
    ctx = DiscoveryContext(explicit_paths=[yaml_path], builtin_roots=[yaml_path], user_home=tmp_path / "home")
    run_ref = start_mission_run(
        template_key=str(yaml_path),
        inputs={},
        policy_snapshot=MissionPolicySnapshot(),
        context=ctx,
        run_store=tmp_path / "runs",
        emitter=NullEmitter(),
    )
    next_step(run_ref, agent_id="a")
    emitter = _RecordingEmitter()
    decision = next_step(run_ref, agent_id="a", emitter=emitter)

    assert decision.kind == "decision_required"
    assert emitter.calls == ["completed", "significance", "requested"]
    assert _event_types(run_ref)[-3:] == ["NextStepAutoCompleted", "SignificanceEvaluated", "DecisionInputRequested"]
    assert decision.decision_id in json.loads(_state_text(run_ref))["pending_decisions"]


def test_guard_runs_before_the_commit_writes_anything(tmp_path: Path) -> None:
    run_ref = _at_last_step(tmp_path)
    before = _event_types(run_ref)
    seen: list[list[str]] = []
    plan = plan_advance(run_ref, "a")
    commit_advance(run_ref, plan, "a", before_run_completed=lambda: seen.append(_event_types(run_ref)))

    assert seen == [before]
    assert _event_types(run_ref)[-2:] == ["NextStepAutoCompleted", "MissionRunCompleted"]


def test_raising_guard_aborts_before_anything_is_written(tmp_path: Path) -> None:
    """A strict retrospective capture that raises writes and emits nothing (operator ruling 2026-10-07).

    The guard runs before the first journal append, so a retry does not stack a
    second ``NextStepAutoCompleted`` on the journal of a run that never advanced.
    """
    run_ref = _at_last_step(tmp_path)
    journal = Path(run_ref.run_dir) / "run.events.jsonl"
    state_before, journal_before = _state_text(run_ref), journal.read_bytes()
    plan = plan_advance(run_ref, "a")
    emitter = _RecordingEmitter()

    def _boom() -> None:
        raise RuntimeError("retrospective capture failed")

    for _attempt in range(2):
        with pytest.raises(RuntimeError, match="retrospective capture failed"):
            commit_advance(run_ref, plan, "a", emitter, before_run_completed=_boom)

    assert journal.read_bytes() == journal_before
    assert _state_text(run_ref) == state_before
    assert emitter.calls == []


def test_guard_not_called_on_terminal_repoll_without_completed_step(tmp_path: Path) -> None:
    run_ref = _at_last_step(tmp_path)
    assert next_step(run_ref, agent_id="a").kind == "terminal"
    plan = plan_advance(run_ref, "a")
    assert plan.decision.kind == "terminal"
    assert plan.completed_step_id is None
    calls: list[int] = []
    commit_advance(run_ref, plan, "a", before_run_completed=lambda: calls.append(1))
    assert calls == []


def test_guard_not_called_for_non_terminal_advance(tmp_path: Path) -> None:
    run_ref = _start(tmp_path, [{"id": "s1", "title": "S1", "prompt": "do"}, {"id": "s2", "title": "S2", "prompt": "do", "depends_on": ["s1"]}])
    next_step(run_ref, agent_id="a")
    calls: list[int] = []
    commit_advance(run_ref, plan_advance(run_ref, "a"), "a", before_run_completed=lambda: calls.append(1))
    assert calls == []


def test_stale_plan_raises_and_writes_nothing(tmp_path: Path) -> None:
    """The run moved on after the plan was computed: the plan is refused before the
    guard, any append or any emission, with every file of the run untouched.

    The plan is terminal with a completed step, the one case the guard fires for, so
    ``called == []`` goes red if the stale check ever moves after the guard."""
    run_ref = _at_last_step(tmp_path)
    plan = plan_advance(run_ref, "a")
    assert plan.decision.kind == "terminal"
    assert plan.completed_step_id is not None
    # Another actor advances the run after planning.
    next_step(run_ref, agent_id="a")
    run_dir = Path(run_ref.run_dir)
    files_before = {path.name: path.read_bytes() for path in run_dir.iterdir() if path.is_file()}
    called: list[int] = []
    emitter = _RecordingEmitter()

    with pytest.raises(StaleAdvancePlan):
        commit_advance(run_ref, plan, "a", emitter, before_run_completed=lambda: called.append(1))

    assert called == []
    assert emitter.calls == []
    assert {path.name: path.read_bytes() for path in run_dir.iterdir() if path.is_file()} == files_before
