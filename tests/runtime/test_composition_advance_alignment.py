"""Acceptance: a composition-backed advance records what the engine advance records (#2562).

Mission ``composition-advance-alignment-01M49EKF`` (FR-001, FR-002, FR-003).
Each test drives a real ``software-dev`` run to ``specify``, copies its run
directory into a twin, then advances the original through the pre-existing
entry point ``decide_next_via_runtime`` (composition dispatch, the composed
action's executor stubbed) and the twin through the engine's own
``next_step``. The two runs must record the same ``decisions`` and the same
run events, timestamps aside.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from runtime.next._internal_runtime import MissionRunRef
from runtime.next._internal_runtime.engine import _read_snapshot, next_step as engine_next_step
from runtime.next._internal_runtime.events import NullEmitter
from runtime.next.decision import DecisionKind

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_SLUG = "042-alignment"
_AGENT = "test"
_FROZEN_TEMPLATE = "mission_template_frozen.yaml"
_EVENTS = "run.events.jsonl"
_GATE_ID = "spec-gate"
_DIMS_LOW = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}
_DIMS_MEDIUM = {**_DIMS_LOW, "user_customer_impact": 3, "architectural_system_impact": 2, "operational_reliability_impact": 2}
_DIMS_HIGH = dict.fromkeys(_DIMS_LOW, 3)


@pytest.fixture(autouse=True)
def _local_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """Local NullEmitter, and the built-in software-dev action sequence without a live charter."""
    import charter.activation.mission_type_profiles as mission_type_profiles
    from runtime.next import runtime_bridge

    monkeypatch.setattr(runtime_bridge, "runtime_emitter_for_mission", lambda **_: NullEmitter())

    def _resolve(_repo_root: object, *, mission_type: str | None = None, feature_dir: object = None) -> SimpleNamespace:
        del feature_dir
        if mission_type != "software-dev":
            raise mission_type_profiles.UnknownMissionTypeError(mission_type)
        return SimpleNamespace(action_sequence=["specify", "plan", "tasks", "implement", "review"])

    monkeypatch.setattr(mission_type_profiles, "resolve_mission_type_context", _resolve)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True)


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A git repo holding a software-dev Mission whose spec exists (the specify guard passes)."""
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# test", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    (repo / ".kittify").mkdir()
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev"}), encoding="utf-8")
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n| FR-001 | First | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    return repo


def _run_at_specify(repo: Path) -> MissionRunRef:
    """Start the run and drive it with the engine until ``specify`` is issued."""
    from runtime.next.runtime_bridge import get_or_start_run

    run_ref = get_or_start_run(_MISSION_SLUG, repo, "software-dev")
    for _ in range(10):
        if _read_snapshot(Path(run_ref.run_dir)).issued_step_id == "specify":
            return run_ref
        engine_next_step(run_ref, agent_id=_AGENT, result="success", emitter=NullEmitter())
    raise AssertionError("could not drive the run to 'specify'")


def _gate_template(run_dir: Path, dimensions: dict[str, int]) -> None:
    """Insert a blocking audit gate with a significance block between ``specify`` and ``plan``."""
    frozen = run_dir / _FROZEN_TEMPLATE
    raw: dict[str, Any] = yaml.safe_load(frozen.read_text(encoding="utf-8"))
    for step in raw["steps"]:
        if step["id"] == "plan":
            step["depends_on"] = [*step.get("depends_on", []), _GATE_ID]
    raw["audit_steps"] = [
        {
            "id": _GATE_ID,
            "title": "Spec gate",
            "depends_on": ["specify"],
            "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
            "significance": {"dimensions": dimensions},
        }
    ]
    frozen.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")


def _twin(run_ref: MissionRunRef, tmp_path: Path) -> MissionRunRef:
    twin_dir = tmp_path / "twin" / run_ref.run_id
    shutil.copytree(run_ref.run_dir, twin_dir)
    return run_ref.model_copy(update={"run_dir": str(twin_dir)})


def _events_since(run_dir: Path, offset: int) -> list[dict[str, Any]]:
    lines = (run_dir / _EVENTS).read_text(encoding="utf-8").splitlines()[offset:]
    return [{"event_type": event["event_type"], "payload": event["payload"]} for event in map(json.loads, lines)]


def _event_count(run_dir: Path) -> int:
    return len((run_dir / _EVENTS).read_text(encoding="utf-8").splitlines())


def _state(run_dir: Path) -> dict[str, Any]:
    """``state.json`` with the per-call ``requested_at`` stamps of pending decisions removed."""
    state = _read_snapshot(run_dir).model_dump(mode="json")
    for request in state["pending_decisions"].values():
        request.pop("requested_at", None)
    return state


def _advance_both(project: Path, tmp_path: Path, dimensions: dict[str, int] | None = None) -> tuple[Any, Path, Path, int]:
    """Advance the run through composition and its twin through the engine; return the Decision and both run dirs."""
    from runtime.next.runtime_bridge import decide_next_via_runtime

    run_ref = _run_at_specify(project)
    run_dir = Path(run_ref.run_dir)
    if dimensions is not None:
        _gate_template(run_dir, dimensions)
    twin = _twin(run_ref, tmp_path)
    offset = _event_count(run_dir)

    engine_next_step(twin, agent_id=_AGENT, result="success", emitter=NullEmitter())
    executed = MagicMock(invocation_ids=("inv-001",))
    with (
        patch("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute", return_value=executed) as execute,
        patch("runtime.next.runtime_bridge.runtime_next_step") as legacy_dispatch,
    ):
        decision = decide_next_via_runtime(_AGENT, _MISSION_SLUG, "success", project)
    assert execute.call_count == 1, "the composed action must run through composition"
    legacy_dispatch.assert_not_called()
    return decision, run_dir, Path(twin.run_dir), offset


def test_composition_advance_records_the_issued_steps_raci_binding(project: Path, tmp_path: Path) -> None:
    """FR-001: issuing ``plan`` through composition records ``raci:plan`` as the engine does."""
    decision, run_dir, twin_dir, offset = _advance_both(project, tmp_path)

    assert decision.kind == DecisionKind.step
    composed = _state(run_dir)
    assert composed["issued_step_id"] == "plan"
    assert "raci:plan" in composed["decisions"], "the composition advance recorded no RACI binding for the issued step"
    assert composed == _state(twin_dir)
    assert _events_since(run_dir, offset) == _events_since(twin_dir, offset)


@pytest.mark.parametrize(
    ("dimensions", "options"),
    [(_DIMS_HIGH, ["approve", "reject"]), (_DIMS_MEDIUM, ["decide_solo", "open_stand_up", "defer"])],
    ids=["high", "medium"],
)
def test_composition_advance_evaluates_an_audit_gates_significance(project: Path, tmp_path: Path, dimensions: dict[str, int], options: list[str]) -> None:
    """FR-002: reaching a significance-declaring audit gate records the evaluation as the engine does."""
    decision, run_dir, twin_dir, offset = _advance_both(project, tmp_path, dimensions)

    assert decision.kind == DecisionKind.decision_required
    assert decision.decision_id == f"audit:{_GATE_ID}"
    assert list(decision.options or []) == options
    composed = _state(run_dir)
    assert f"significance:audit:{_GATE_ID}" in composed["decisions"]
    assert f"raci:{_GATE_ID}" in composed["decisions"]
    events = _events_since(run_dir, offset)
    assert [event["event_type"] for event in events].count("SignificanceEvaluated") == 1
    assert composed == _state(twin_dir)
    assert events == _events_since(twin_dir, offset)


def test_composition_advance_auto_proceeds_a_low_band_gate(project: Path, tmp_path: Path) -> None:
    """FR-003: a LOW-band gate reached through composition auto-completes and the next step is issued."""
    decision, run_dir, twin_dir, offset = _advance_both(project, tmp_path, _DIMS_LOW)

    assert decision.kind == DecisionKind.step
    assert decision.step_id == "plan", "the issued step must be the one the LOW re-plan resolved"
    composed = _state(run_dir)
    assert _GATE_ID in composed["completed_steps"]
    assert composed["issued_step_id"] == "plan"
    events = _events_since(run_dir, offset)
    assert "DecisionInputRequested" not in [event["event_type"] for event in events]
    assert composed == _state(twin_dir)
    assert events == _events_since(twin_dir, offset)


def test_composition_advance_refuses_a_stale_plan(project: Path) -> None:
    """FR-010: a plan the run moved past is refused, nothing is written, and the legacy dispatch is never entered."""
    from runtime.next.runtime_bridge import decide_next_via_runtime

    run_ref = _run_at_specify(project)
    run_dir = Path(run_ref.run_dir)
    state_file = run_dir / "state.json"
    events_before = (run_dir / _EVENTS).read_bytes()
    moved_on: dict[str, bytes] = {}

    def _run_moves_on(*_args: Any, **_kwargs: Any) -> None:
        # Another writer advances the run between the plan and its commit.
        snapshot = _read_snapshot(run_dir)
        state_file.write_text(
            json.dumps(snapshot.model_copy(update={"inputs": {**snapshot.inputs, "moved": True}}).model_dump(mode="json")),
            encoding="utf-8",
        )
        moved_on["state"] = state_file.read_bytes()

    executed = MagicMock(invocation_ids=("inv-001",))
    with (
        patch("specify_cli.mission_step_contracts.executor.StepContractExecutor.execute", return_value=executed),
        patch("runtime.next.runtime_bridge._resolve_planned_wp_workspace", side_effect=_run_moves_on),
        patch("runtime.next.runtime_bridge.runtime_next_step") as legacy_dispatch,
    ):
        decision = decide_next_via_runtime(_AGENT, _MISSION_SLUG, "success", project)

    legacy_dispatch.assert_not_called()
    assert decision.kind == DecisionKind.blocked
    assert state_file.read_bytes() == moved_on["state"], "the stale plan overwrote newer run state"
    assert (run_dir / _EVENTS).read_bytes() == events_before
