"""Engine-adapter tests for ``runtime_bridge_engine`` (#2531 WP03, FR-013 / FR-006).

Two independent concerns:

1. **Architecture guard** (``test_no_sibling_module_accesses_engine_planner_privates``)
   — asserts no module under ``src/runtime/next/`` other than
   ``runtime_bridge_engine.py`` accesses the 6 grep-complete
   ``_internal_runtime.engine`` / ``.planner`` privates this WP concentrates:
   ``_read_snapshot``, ``_load_frozen_template``, ``_append_event``,
   ``_write_snapshot`` (from ``.engine``), ``plan_next`` and
   ``_resolve_workflow_for_mission`` (from ``.planner``) — see
   ``data-model.md`` §Engine-adapter surface for the authoritative site
   list. Deliberately scoped to exactly those 6 names, NOT every private
   symbol in ``.engine``/``.planner`` wholesale:

   * ``planner.compose_template_with_workflow`` has no leading underscore —
     it is a *public* planner API (out of this WP's FR-013 boundary; still
     imported directly by ``runtime_bridge.py`` pending a later composition
     WP).
   * ``prompt_builder.py`` now routes ``_resolve_workflow_for_mission``
     through ``runtime_bridge_engine.resolve_workflow_for_mission`` instead
     of importing the planner private directly — the retro follow-up that
     completed the concentration this WP started.

   A non-vacuousness check (``test_adapter_defines_a_wrapper_for_each_concentrated_read_and_planner_private``)
   guards against the "no other module reaches in" assertion passing for the
   wrong reason (e.g. if the adapter itself stopped wrapping one of them). The
   two engine writers are not wrapped: since #2562 only the engine's commit
   writes a run (``test_adapter_wraps_no_engine_writer``).

2. **Focused unit tests (FR-006)** against ``_internal_runtime.engine`` /
   ``.planner`` *stubs* (monkeypatched), never the real runtime — that
   characterization is the WP01 parity oracle's job
   (``tests/runtime/test_bridge_parity.py``). These tests pin:

   * the low-level wrappers delegate via a **live module-attribute lookup**
     (not a cached ``from ... import name`` binding) — the same property the
     WP01 oracle's ``capture_side_effects`` and the WP02 compat guard rely on
     when patching ``_internal_runtime.engine``/``runtime_bridge`` directly;
   * ``advance_run_state_after_composition``'s three ``NextDecision.kind``
     branches (step / decision_required / terminal) plus the
     decision-required dedup-on-repoll path, contract-tested against a fake
     ``sync_emitter`` and stubbed ``runtime_bridge_retrospective`` callbacks.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from runtime.next import runtime_bridge_engine as engine_adapter
from runtime.next._internal_runtime import engine as internal_engine
from runtime.next._internal_runtime.engine import MissionRunRef
from runtime.next._internal_runtime.schema import MissionRunSnapshot, NextDecision
from runtime.next import runtime_bridge_decision_mapping as decision_mapping

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# 1. Architecture guard (T013)
# ---------------------------------------------------------------------------

_SRC_RUNTIME_NEXT = Path(__file__).resolve().parents[2] / "src" / "runtime" / "next"

# The grep-complete site list this WP concentrates (data-model.md
# §Engine-adapter surface) — the FR-013 boundary for WP03, plus the
# ``_resolve_workflow_for_mission`` retro follow-up. See module docstring
# for why this is NOT "every private symbol in .engine/.planner".
_ENGINE_PLANNER_PRIVATE_NAMES = frozenset(
    {
        "_read_snapshot",
        "_load_frozen_template",
        "_append_event",
        "_write_snapshot",
        "plan_next",
        "_resolve_workflow_for_mission",
    }
)


def _sibling_modules() -> list[Path]:
    """Every top-level module directly under ``src/runtime/next/`` (non-recursive
    — ``_internal_runtime/`` is the engine's own package and is exempt by
    construction), excluding the adapter itself."""
    return sorted(p for p in _SRC_RUNTIME_NEXT.glob("*.py") if p.name != "runtime_bridge_engine.py")


def _offending_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.endswith(("_internal_runtime.engine", "_internal_runtime.planner")):
                offenders.extend(f"{path.name}: from {node.module} import {alias.name}" for alias in node.names if alias.name in _ENGINE_PLANNER_PRIVATE_NAMES)
            elif node.module.endswith("_internal_runtime"):
                # Importing the ``engine``/``planner`` submodule object — or the
                # ``_internal_runtime`` package itself — grants the same ambient
                # access the 5-name check catches for the direct form (e.g.
                # ``from ..._internal_runtime import engine`` then
                # ``engine._read_snapshot(...)``). Flag the indirection.
                offenders.extend(f"{path.name}: from {node.module} import {alias.name}" for alias in node.names if alias.name in ("engine", "planner"))
            elif node.module.endswith("runtime.next"):
                # ``from runtime.next import _internal_runtime`` then
                # ``_internal_runtime.engine._read_snapshot(...)`` — the package
                # import is the reach-through vector.
                offenders.extend(f"{path.name}: from {node.module} import {alias.name}" for alias in node.names if alias.name == "_internal_runtime")
        elif isinstance(node, ast.Import):
            # Dotted module imports: ``import runtime.next._internal_runtime.engine``
            # (bound under its full dotted path) or ``import
            # runtime.next._internal_runtime`` (the package) — both bypass the
            # ``from``-only checks above.
            offenders.extend(
                f"{path.name}: import {alias.name}"
                for alias in node.names
                if alias.name.endswith(("_internal_runtime.engine", "_internal_runtime.planner", "_internal_runtime"))
            )
    return offenders


# ``_resolve_workflow_for_mission`` is re-exposed under a public name
# (``resolve_workflow_for_mission``, no leading underscore) since it is the
# adapter's externally-called entry point for ``prompt_builder.py`` rather
# than an internal delegate; the other 5 keep their original private names.
_ADAPTER_WRAPPER_NAME = {"_resolve_workflow_for_mission": "resolve_workflow_for_mission"}


# PR-BOUNDARY-001 (design-phase-orchestrator-api-01M1HE6M pre-merge review):
# the original ``_sibling_modules()`` walk covers only ``src/runtime/next/``
# itself, so it could never catch either of the two REAL offending call
# sites this finding identified -- both live one layer up, in CLI-adjacent
# modules that reach into the six concentrated privates directly instead of
# routing through this adapter or the ``next_invocation_lifecycle`` seam:
#
#   * ``next_cmd.py``'s ``_handle_answer`` (the host CLI's own pending-
#     decision auto-resolve -- pre-existing debt)
#   * ``orchestrator_api/commands.py``'s ``answer_decision`` (WP08 -- new
#     code introduced by this mission that mirrored the CLI's bypass rather
#     than closing it)
#
# Named explicitly (not a recursive repo-wide walk, which would risk
# unrelated false positives elsewhere in a large codebase) -- these are the
# two established CLI-layer entry points this concentration seam exists to
# protect. Both were fixed to route through ``next_invocation_lifecycle.
# resolve_pending_decision_id`` / ``runtime_bridge_engine._read_snapshot``
# as part of this same fix, so the guard below closes the class by
# construction: a future direct import in either file fails this test.
# The orchestrator-api side is the whole package: #5628 split ``commands.py``
# into per-concern modules (``answer_decision`` now lives in
# ``decision_verbs.py``), so every module of it stays in scope.
_CLI_ADJACENT_MODULES = (
    Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "cli" / "commands" / "next_cmd.py",
    *sorted((Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "orchestrator_api").glob("*.py")),
)


def test_no_sibling_module_accesses_engine_planner_privates() -> None:
    """No module outside this adapter reaches into the six concentrated
    ``_internal_runtime.engine``/``.planner`` privates directly (FR-013).

    Scope: every top-level sibling under ``src/runtime/next/`` PLUS the two
    named CLI-adjacent modules in ``_CLI_ADJACENT_MODULES`` (the widened
    scope from PR-BOUNDARY-001 -- see the comment above that tuple).
    """
    offenders: list[str] = []
    for path in _sibling_modules():
        offenders.extend(_offending_imports(path))
    for path in _CLI_ADJACENT_MODULES:
        offenders.extend(_offending_imports(path))
    assert not offenders, (
        "Module(s) outside the runtime_bridge_engine concentration seam "
        "import _internal_runtime.engine/.planner privates directly "
        "(route through runtime_bridge_engine or next_invocation_lifecycle "
        "instead):\n" + "\n".join(offenders)
    )


# The engine's commit writes the run-event journal and ``state.json``; since
# #2562 the adapter commits through it and wraps neither writer (a wrapper
# with no production caller is dead code). The writers stay in the
# concentrated set above, so no sibling may reach them either.
_ENGINE_WRITERS = frozenset({"_append_event", "_write_snapshot"})


def test_adapter_defines_a_wrapper_for_each_concentrated_read_and_planner_private() -> None:
    """Non-vacuousness check: the "no sibling reaches in" assertion above is
    only meaningful if the adapter itself still wraps the concentrated reads
    and planner names -- guards against it passing for the wrong reason (e.g.
    the adapter silently dropping a wrapper)."""
    for name in _ENGINE_PLANNER_PRIVATE_NAMES - _ENGINE_WRITERS:
        wrapper_name = _ADAPTER_WRAPPER_NAME.get(name, name)
        assert hasattr(engine_adapter, wrapper_name), f"runtime_bridge_engine no longer defines a wrapper for {name!r} (expected attribute {wrapper_name!r})"


def test_adapter_wraps_no_engine_writer() -> None:
    """The run is written only by the engine's commit (#2562)."""
    assert not [name for name in _ENGINE_WRITERS if hasattr(engine_adapter, name)]


# ---------------------------------------------------------------------------
# 2a. Focused unit tests — the engine/planner wrapper functions (FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_read_snapshot_delegates_via_live_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    snapshot = MissionRunSnapshot(run_id="r1", mission_key="software-dev", template_path="t", template_hash="h")
    calls: list[Path] = []

    def _fake(run_dir: Path) -> MissionRunSnapshot:
        calls.append(run_dir)
        return snapshot

    # String-path form (not a static ``engine_adapter._engine`` attribute
    # expression) — mypy's implicit-reexport rule blocks cross-module dotted
    # access to a *private import alias* like ``_engine``; monkeypatch's
    # string-target form resolves it at runtime instead, sidestepping that
    # (correct) static check without weakening what actually gets patched.
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._read_snapshot", _fake)
    result = engine_adapter._read_snapshot(tmp_path)
    assert result is snapshot
    assert calls == [tmp_path]


@pytest.mark.unit
def test_load_frozen_template_delegates_via_live_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sentinel = object()
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._load_frozen_template", lambda run_dir: sentinel)
    assert engine_adapter._load_frozen_template(tmp_path) is sentinel


@pytest.mark.unit
def test_plan_next_delegates_via_live_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    sentinel: Any = object()
    captured: dict[str, Any] = {}

    def _fake(snapshot: Any, template: Any, policy: Any, actor_context: Any = None, live_template_path: Any = None) -> Any:
        captured["args"] = (snapshot, template, policy, actor_context, live_template_path)
        return sentinel

    monkeypatch.setattr("runtime.next.runtime_bridge_engine._planner.plan_next", _fake)
    snap: Any = object()
    template: Any = object()
    policy: Any = object()
    result = engine_adapter.plan_next(snap, template, policy, actor_context={"a": 1}, live_template_path=tmp_path)
    assert result is sentinel
    assert captured["args"] == (snap, template, policy, {"a": 1}, tmp_path)


# ---------------------------------------------------------------------------
# 2b. Focused unit tests — ``advance_run_state_after_composition`` (FR-006)
# ---------------------------------------------------------------------------


class _FakeSyncEmitter:
    """Records calls; stands in for ``SyncRuntimeEventEmitter`` (FR-006 stub).
    ``order`` records every call name in sequence (seed and emits)."""

    def __init__(self) -> None:
        self.order: list[str] = []
        self.seeded: list[Any] = []
        self.auto_completed: list[Any] = []
        self.step_issued: list[Any] = []
        self.decision_requested: list[Any] = []
        self.significance: list[Any] = []
        self.run_completed: list[Any] = []

    def seed_from_snapshot(self, snapshot: Any) -> None:
        self.order.append("seed")
        self.seeded.append(snapshot)

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self.order.append("NextStepAutoCompleted")
        self.auto_completed.append(payload)

    def emit_significance_evaluated(self, payload: Any) -> None:
        self.order.append("SignificanceEvaluated")
        self.significance.append(payload)

    def emit_next_step_issued(self, payload: Any) -> None:
        self.order.append("NextStepIssued")
        self.step_issued.append(payload)

    def emit_decision_input_requested(self, payload: Any) -> None:
        self.order.append("DecisionInputRequested")
        self.decision_requested.append(payload)

    def emit_mission_run_completed(self, payload: Any) -> None:
        self.order.append("MissionRunCompleted")
        self.run_completed.append(payload)


@dataclass
class _MapDecisionRecorder:
    """``calls`` records each ``_map_runtime_decision`` invocation's positional
    args; ``sentinel`` is the opaque value the stub returns, so tests can
    assert the adapter's return value flows through by identity — comparing
    it to a plain string would be comparing the (real) declared ``Decision``
    return type to ``str``, which is meaningless and mypy correctly rejects."""

    calls: list[tuple[Any, ...]]
    sentinel: Any


@pytest.fixture()
def _stub_map_runtime_decision(monkeypatch: pytest.MonkeyPatch) -> _MapDecisionRecorder:
    """Stub ``decision_mapping._map_runtime_decision``.

    The adapter maps its result through ``runtime_bridge_decision_mapping``
    (see the ``runtime_bridge_engine.py`` module docstring), so patching it on
    that module is the correct seam to stub for these contract tests.
    """

    recorder = _MapDecisionRecorder(calls=[], sentinel=object())

    def _fake(
        decision: Any, agent: Any, mission_slug: Any, mission_type: Any, repo_root: Any, feature_dir: Any, timestamp: Any, progress: Any, origin: Any, **_kw: Any
    ) -> Any:
        recorder.calls.append((decision, agent, mission_slug, mission_type, repo_root, feature_dir, timestamp, progress, origin))
        return recorder.sentinel

    monkeypatch.setattr(decision_mapping, "_map_runtime_decision", _fake)
    return recorder


#: A minimal real frozen template (#2562 re-seam): the engine's
#: ``plan_advance`` loads and walks the frozen template itself, so these tests
#: run on a real one instead of an ``object()`` stand-in.
_MINIMAL_TEMPLATE: dict[str, Any] = {
    "mission": {"key": "software-dev", "name": "Test", "version": "1.0.0"},
    "steps": [{"id": "plan", "title": "Plan"}, {"id": "implement", "title": "Implement"}, {"id": "review", "title": "Review"}],
}
_STATE_FILE = "state.json"
_EVENTS_FILE = "run.events.jsonl"
_LOW_DIMENSIONS = {
    "user_customer_impact": 0,
    "architectural_system_impact": 0,
    "data_security_compliance_impact": 0,
    "operational_reliability_impact": 0,
    "financial_commercial_impact": 0,
    "cross_team_blast_radius": 0,
}


def _write_run(run_dir: Path, snapshot: MissionRunSnapshot, template: dict[str, Any] | None = None) -> None:
    """Persist ``snapshot`` as ``state.json`` and a real frozen template in ``run_dir``."""
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / _STATE_FILE).write_text(json.dumps(snapshot.model_dump(mode="json")), encoding="utf-8")
    (run_dir / "mission_template_frozen.yaml").write_text(yaml.safe_dump(template or _MINIMAL_TEMPLATE, sort_keys=False), encoding="utf-8")


def _event_types(run_dir: Path) -> list[str]:
    events_file = run_dir / _EVENTS_FILE
    if not events_file.exists():
        return []
    return [json.loads(line)["event_type"] for line in events_file.read_text(encoding="utf-8").splitlines() if line.strip()]


@dataclass
class _RunRecorder:
    """What the engine commit persisted (spied, then passed through to disk)
    and the arguments the planner stub ran with."""

    written: list[Any]
    appended: list[tuple[Any, ...]]
    planned: list[tuple[Any, ...]]


def _real_run_with_planned_decision(
    monkeypatch: pytest.MonkeyPatch,
    run_dir: Path,
    *,
    snapshot: MissionRunSnapshot,
    plan_next_returns: NextDecision,
) -> _RunRecorder:
    """Write a real run (snapshot + minimal frozen template) and stub only the
    planner's decision: ``plan_next`` as bound in the engine module, which is
    the name ``plan_advance`` calls. ``_write_snapshot`` / ``_append_event``
    are spied and still write to disk."""
    _write_run(run_dir, snapshot)
    recorder = _RunRecorder(written=[], appended=[], planned=[])
    real_write = internal_engine._write_snapshot
    real_append = internal_engine._append_event

    def _write(target: Path, snap: MissionRunSnapshot) -> None:
        recorder.written.append(snap)
        real_write(target, snap)

    def _append(*args: Any) -> None:
        recorder.appended.append(args)
        real_append(*args)

    def _plan_next(*args: Any, **_kwargs: Any) -> NextDecision:
        recorder.planned.append(args)
        return plan_next_returns

    monkeypatch.setattr("runtime.next._internal_runtime.engine._write_snapshot", _write)
    monkeypatch.setattr("runtime.next._internal_runtime.engine._append_event", _append)
    monkeypatch.setattr("runtime.next._internal_runtime.engine.plan_next", _plan_next)
    return recorder


def _advance(run_ref: MissionRunRef, tmp_path: Path, sync_emitter: Any, **overrides: Any) -> Any:
    """Plan with the engine (as the bridge does), then commit through the adapter."""
    kwargs: dict[str, Any] = {
        "run_ref": run_ref,
        "agent": "agent-1",
        "mission_slug": "mission-1",
        "mission_type": "software-dev",
        "repo_root": tmp_path,
        "feature_dir": tmp_path,
        "timestamp": "2026-01-01T00:00:00Z",
        "progress": None,
        "origin": {},
        "sync_emitter": sync_emitter,
    }
    kwargs.update(overrides)
    if "plan" not in kwargs:
        kwargs["plan"] = engine_adapter.plan_advance(run_ref, "agent-1", "success")
    return engine_adapter.advance_run_state_after_composition(**kwargs)


@pytest.mark.unit
def test_advance_run_state_step_decision_no_prior_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder) -> None:
    """No step was in flight (``issued_step_id`` is None) — nothing to
    auto-complete; the ``step`` decision stamps the new ``issued_step_id`` and
    emits ``NextStepIssued`` only."""
    run_dir = tmp_path / "run-1"
    snapshot_in = MissionRunSnapshot(run_id="run-1", mission_key="software-dev", template_path="", template_hash="h")
    decision = NextDecision(kind="step", run_id="run-1", mission_key="software-dev", step_id="implement")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    written, appended = rec.written, rec.appended

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-1", run_dir=str(run_dir), mission_key="software-dev")

    result = _advance(
        run_ref,
        tmp_path,
        sync_emitter,
        wp_resolution=("implement", "WP01", "/ws", "lane-a", "wp"),  # the bridge resolved this before the advance
    )

    assert rec.planned, "the plan_next stub never ran"
    assert result is _stub_map_runtime_decision.sentinel
    assert sync_emitter.seeded == [snapshot_in]
    assert sync_emitter.auto_completed == []
    assert len(sync_emitter.step_issued) == 1
    assert len(appended) == 1  # only NextStepIssued
    assert written[-1].issued_step_id == "implement"
    assert _stub_map_runtime_decision.calls[0][0] is decision


@pytest.mark.unit
def test_advance_run_state_marks_prior_step_complete_then_decision_required(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """A step WAS in flight — it gets auto-completed first (NextStepAutoCompleted),
    then the ``decision_required`` branch persists + emits DecisionInputRequested."""
    run_dir = tmp_path / "run-2"
    snapshot_in = MissionRunSnapshot(run_id="run-2", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="implement")
    decision = NextDecision(
        kind="decision_required",
        run_id="run-2",
        mission_key="software-dev",
        decision_id="audit:review",
        step_id="review",
        question="Proceed?",
        options=["yes", "no"],
    )
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    written, appended = rec.written, rec.appended

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-2", run_dir=str(run_dir), mission_key="software-dev")

    _advance(run_ref, tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert len(sync_emitter.auto_completed) == 1
    assert sync_emitter.auto_completed[0].step_id == "implement"
    assert len(sync_emitter.decision_requested) == 1
    assert len(appended) == 2  # NextStepAutoCompleted + DecisionInputRequested
    assert written[-1].completed_steps == ["implement"]
    assert written[-1].pending_decisions.get("audit:review") is not None


@pytest.mark.unit
def test_advance_run_state_decision_required_dedups_on_repoll(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """A decision already pending must not be re-emitted/re-persisted on re-poll."""
    run_dir = tmp_path / "run-3"
    snapshot_in = MissionRunSnapshot(
        run_id="run-3",
        mission_key="software-dev",
        template_path="",
        template_hash="h",
        pending_decisions={"audit:review": {"already": "there"}},
    )
    decision = NextDecision(kind="decision_required", run_id="run-3", mission_key="software-dev", decision_id="audit:review", step_id="review")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    written, appended = rec.written, rec.appended

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-3", run_dir=str(run_dir), mission_key="software-dev")

    _advance(run_ref, tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert sync_emitter.decision_requested == []
    assert appended == []  # no step was in flight, and the decision is a dedup no-op
    assert written[-1].pending_decisions == {"audit:review": {"already": "there"}}


@pytest.mark.unit
def test_advance_run_state_terminal_runs_retrospective_gate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """The ``terminal`` branch (after a step genuinely completed) consults the
    retrospective policy/terminus helpers on ``runtime_bridge_retrospective``
    — stubbed here with a patch on that seam, which is where they live."""
    from runtime.next import runtime_bridge_retrospective as retrospective_seam

    run_dir = tmp_path / "run-4"
    snapshot_in = MissionRunSnapshot(
        run_id="run-4",
        mission_key="software-dev",
        template_path="",
        template_hash="h",
        issued_step_id="review",
        completed_steps=["implement"],
    )
    decision = NextDecision(kind="terminal", run_id="run-4", mission_key="software-dev")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)

    # A non-blocking policy: ``enabled`` but neither ``timing="before_completion"``
    # nor ``failure_policy="block"``, so the REAL ``_retrospective_blocks_completion``
    # returns False on its own (getattr-default None on both). We deliberately do
    # NOT monkeypatch ``_retrospective_blocks_completion``: driving the real
    # predicate is stronger coverage.
    class _Policy:
        enabled = True
        timing = "post_completion"
        failure_policy = "warn"

    retro_calls: list[dict[str, Any]] = []
    monkeypatch.setattr(retrospective_seam, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (_Policy(), {}, None))
    monkeypatch.setattr(retrospective_seam, "_resolve_mission_id_for_terminus", lambda feature_dir: "mission-id-4")
    monkeypatch.setattr(retrospective_seam, "_run_retrospective_learning_capture", lambda **kwargs: retro_calls.append(kwargs))

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-4", run_dir=str(run_dir), mission_key="software-dev")

    _advance(run_ref, tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert len(sync_emitter.run_completed) == 1
    assert len(retro_calls) == 1
    assert retro_calls[0]["mission_id"] == "mission-id-4"
    assert retro_calls[0]["block_on_failure"] is False


@pytest.mark.unit
def test_advance_run_state_terminal_skipped_when_no_step_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """A ``terminal`` decision on a re-poll (no step just completed) must NOT
    re-emit ``MissionRunCompleted`` or re-run the retrospective gate."""
    from runtime.next import runtime_bridge_retrospective as retrospective_seam

    run_dir = tmp_path / "run-5"
    snapshot_in = MissionRunSnapshot(run_id="run-5", mission_key="software-dev", template_path="", template_hash="h", issued_step_id=None)
    decision = NextDecision(kind="terminal", run_id="run-5", mission_key="software-dev")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)

    monkeypatch.setattr(
        retrospective_seam,
        "_resolve_retrospective_policy_for_runtime",
        lambda repo_root: (_ for _ in ()).throw(AssertionError("must not consult retrospective policy")),
    )

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-5", run_dir=str(run_dir), mission_key="software-dev")

    _advance(run_ref, tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert sync_emitter.run_completed == []


@pytest.mark.unit
def test_adapter_never_resolves_a_wp_workspace_itself_and_refuses_before_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """Review cycle 2 note 4: resolution belongs to the bridge, BEFORE the
    advance. The adapter must not resolve (and so write-then-resolve) on its
    own: a WP-iteration plan handed over without the bridge's resolution is
    refused with nothing persisted."""
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "run-wp"
    snapshot_in = MissionRunSnapshot(run_id="run-wp", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="tasks")
    decision = NextDecision(kind="step", run_id="run-wp", mission_key="software-dev", step_id="implement")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    written, appended = rec.written, rec.appended
    resolved: list[str] = []
    monkeypatch.setattr(rb, "_resolve_planned_wp_workspace", lambda *a, **k: resolved.append("resolved"))
    run_ref = MissionRunRef(run_id="run-wp", run_dir=str(run_dir), mission_key="software-dev")
    plan = engine_adapter.plan_advance(run_ref, "agent-1", "success")
    state_before = (run_dir / _STATE_FILE).read_bytes()

    with pytest.raises(ValueError, match="wp_resolution"):
        _advance(run_ref, tmp_path, _FakeSyncEmitter(), plan=plan)

    assert rec.planned, "the plan_next stub never ran"
    assert resolved == [], "the adapter must not resolve the workspace itself"
    assert written == [] and appended == [], "nothing may be persisted"
    assert (run_dir / _STATE_FILE).read_bytes() == state_before
    assert not (run_dir / _EVENTS_FILE).exists()


# ---------------------------------------------------------------------------
# 2c. The composition commit is the engine's commit (#2562, FR-008..FR-010)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_composition_commit_seeds_the_emitter_before_the_first_emit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """FR-009: the emitter is seeded from the persisted run before any event is emitted."""
    run_dir = tmp_path / "run-seed"
    snapshot_in = MissionRunSnapshot(run_id="run-seed", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="implement")
    decision = NextDecision(
        kind="decision_required", run_id="run-seed", mission_key="software-dev", decision_id="input:x", step_id="review", input_key="x", question="Value?"
    )
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    sync_emitter = _FakeSyncEmitter()

    _advance(MissionRunRef(run_id="run-seed", run_dir=str(run_dir), mission_key="software-dev"), tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert sync_emitter.order == ["seed", "NextStepAutoCompleted", "DecisionInputRequested"]
    assert sync_emitter.seeded == [snapshot_in]


class _StrictPolicy:
    enabled = True
    timing = "before_completion"
    failure_policy = "block"


@pytest.mark.unit
def test_raising_strict_capture_aborts_before_run_completed_and_state_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """FR-008: the blocking capture is the engine's ``before_run_completed``
    guard. When it raises, ``MissionRunCompleted`` is neither appended nor
    emitted and ``state.json`` is not written."""
    from runtime.next import runtime_bridge_retrospective as retrospective_seam

    run_dir = tmp_path / "run-strict"
    snapshot_in = MissionRunSnapshot(
        run_id="run-strict", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="review", completed_steps=["plan", "implement"]
    )
    decision = NextDecision(kind="terminal", run_id="run-strict", mission_key="software-dev")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    state_before = (run_dir / _STATE_FILE).read_bytes()

    def _refuse(**_kwargs: Any) -> None:
        raise RuntimeError("capture refused")

    monkeypatch.setattr(retrospective_seam, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (_StrictPolicy(), {}, None))
    monkeypatch.setattr(retrospective_seam, "_resolve_mission_id_for_terminus", lambda feature_dir: "mission-id")
    monkeypatch.setattr(retrospective_seam, "_run_retrospective_learning_capture", _refuse)
    sync_emitter = _FakeSyncEmitter()

    with pytest.raises(RuntimeError, match="capture refused"):
        _advance(MissionRunRef(run_id="run-strict", run_dir=str(run_dir), mission_key="software-dev"), tmp_path, sync_emitter)

    assert rec.planned, "the plan_next stub never ran"
    assert rec.written == [], "state.json must not be written when the strict capture refuses"
    assert (run_dir / _STATE_FILE).read_bytes() == state_before
    assert "MissionRunCompleted" not in _event_types(run_dir)
    assert sync_emitter.run_completed == []
    assert _stub_map_runtime_decision.calls == []


@pytest.mark.unit
@pytest.mark.parametrize("owned", [False, True], ids=["repo-root", "owned-checkout"])
def test_retrospective_policy_root_is_the_owned_root_when_owned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder, owned: bool
) -> None:
    """FR-009 (owned-checkout-lifecycle-authority WP11): the guard resolves the
    retrospective policy, and both captures run, at the owned root when there is one."""
    from runtime.next import runtime_bridge_retrospective as retrospective_seam

    run_dir = tmp_path / "run-root"
    snapshot_in = MissionRunSnapshot(run_id="run-root", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="review")
    decision = NextDecision(kind="terminal", run_id="run-root", mission_key="software-dev")
    rec = _real_run_with_planned_decision(monkeypatch, run_dir, snapshot=snapshot_in, plan_next_returns=decision)
    owned_root = tmp_path / "owned"
    policy_roots: list[Path] = []
    captures: list[dict[str, Any]] = []

    def _resolve(root: Path) -> tuple[Any, dict[str, str], None]:
        policy_roots.append(root)
        return _StrictPolicy(), {}, None

    monkeypatch.setattr(retrospective_seam, "_resolve_retrospective_policy_for_runtime", _resolve)
    monkeypatch.setattr(retrospective_seam, "_resolve_mission_id_for_terminus", lambda feature_dir: "mission-id")
    monkeypatch.setattr(retrospective_seam, "_run_retrospective_learning_capture", lambda **kwargs: captures.append(kwargs))
    overrides: dict[str, Any] = {"owned": SimpleNamespace(owned_root=owned_root)} if owned else {}

    _advance(MissionRunRef(run_id="run-root", run_dir=str(run_dir), mission_key="software-dev"), tmp_path, _FakeSyncEmitter(), **overrides)

    expected_root = owned_root if owned else tmp_path
    assert rec.planned, "the plan_next stub never ran"
    assert policy_roots == [expected_root]
    assert [capture["repo_root"] for capture in captures] == [expected_root]
    assert captures[0]["block_on_failure"] is True


@pytest.mark.unit
def test_low_band_replan_to_terminal_runs_the_retrospective_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _stub_map_runtime_decision: _MapDecisionRecorder
) -> None:
    """A LOW-band gate whose re-plan reaches terminal completes the run through
    the composition commit: significance recorded, ``MissionRunCompleted``
    emitted, then the default (non-blocking) capture. Real planner, no stub."""
    from runtime.next import runtime_bridge_retrospective as retrospective_seam

    template = {
        "mission": {"key": "software-dev", "name": "Test", "version": "1.0.0"},
        "steps": [{"id": "plan", "title": "Plan"}],
        "audit_steps": [
            {
                "id": "gate",
                "title": "Gate",
                "depends_on": ["plan"],
                "audit": {"trigger_mode": "manual", "enforcement": "blocking"},
                "significance": {"dimensions": _LOW_DIMENSIONS},
            }
        ],
    }
    run_dir = tmp_path / "run-low"
    _write_run(run_dir, MissionRunSnapshot(run_id="run-low", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="plan"), template)

    class _DefaultPolicy:
        enabled = True

    captures: list[dict[str, Any]] = []
    sync_emitter = _FakeSyncEmitter()

    def _capture(**kwargs: Any) -> None:
        captures.append(kwargs)
        sync_emitter.order.append("capture")

    monkeypatch.setattr(retrospective_seam, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (_DefaultPolicy(), {}, None))
    monkeypatch.setattr(retrospective_seam, "_resolve_mission_id_for_terminus", lambda feature_dir: "mission-id")
    monkeypatch.setattr(retrospective_seam, "_run_retrospective_learning_capture", _capture)
    run_ref = MissionRunRef(run_id="run-low", run_dir=str(run_dir), mission_key="software-dev")
    plan = engine_adapter.plan_advance(run_ref, "agent-1", "success")
    assert plan.decision.kind == "terminal", "the LOW re-plan must reach terminal"

    _advance(run_ref, tmp_path, sync_emitter, plan=plan)

    assert sync_emitter.order == ["seed", "NextStepAutoCompleted", "SignificanceEvaluated", "MissionRunCompleted", "capture"]
    assert _event_types(run_dir) == ["NextStepAutoCompleted", "SignificanceEvaluated", "MissionRunCompleted"]
    assert captures[0]["block_on_failure"] is False
    persisted = internal_engine._read_snapshot(run_dir)
    assert persisted.completed_steps == ["plan", "gate"]
    assert "significance:audit:gate" in persisted.decisions


# ---------------------------------------------------------------------------
# 2d. AST shape gate (FR-004 / FR-005 / SC-002): one planning authority
# ---------------------------------------------------------------------------

_ADAPTER_PATH = _SRC_RUNTIME_NEXT / "runtime_bridge_engine.py"
#: Event payloads and requests the engine commit builds; the adapter must not
#: mention them at all (a constructor, ``model_validate``, an alias).
_ENGINE_OWNED_CONSTRUCTIONS = frozenset(
    {
        "NextStepAutoCompletedPayload",
        "NextStepIssuedPayload",
        "DecisionInputRequestedPayload",
        "MissionRunCompletedPayload",
        "SignificanceEvaluatedPayload",
        "DecisionRequest",
    }
)
#: The ONLY engine / planner attributes the adapter reaches, exactly the set it
#: uses today. Anything else (``next_step``, ``_commit_advance``, ``apply_result``,
#: a writer, a new planner) is a new door and must be added here deliberately.
_ALLOWED_ENGINE_ACCESS: dict[str, frozenset[str]] = {
    "_engine": frozenset({"_read_snapshot", "_load_frozen_template", "plan_advance", "commit_advance", "StaleAdvancePlan"}),
    "_planner": frozenset({"plan_next", "_resolve_workflow_for_mission"}),
}
#: Type-only imports the adapter may take from the engine submodule.
_TYPE_ONLY_ENGINE_IMPORTS = frozenset({"AdvancePlan", "ResultType"})
#: Names the adapter may take from the ``_internal_runtime`` package itself (type-only today).
_ALLOWED_PACKAGE_IMPORTS = frozenset({"MissionRunRef", "NextDecision"})
_FORBIDDEN_REFERENCES = _ENGINE_OWNED_CONSTRUCTIONS | _ENGINE_WRITERS | {"apply_result", "model_copy", "import_module", "__import__"}


def _call_name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _is_private_runtime_module(module: str) -> bool:
    return module.split(".")[-2:] in (["_internal_runtime", "engine"], ["_internal_runtime", "planner"])


def _import_violations(tree: ast.Module) -> list[str]:
    """Imports that reach past the two aliased modules: a name taken straight from
    the engine/planner submodule (aliased or not) or from the events package."""
    type_only = {
        id(node)
        for block in tree.body
        if isinstance(block, ast.If) and isinstance(block.test, ast.Name) and block.test.id == "TYPE_CHECKING"
        for node in block.body
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                f"imports {alias.name}" for alias in node.names if _is_private_runtime_module(alias.name) or alias.name.startswith("spec_kitty_events")
            )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith("spec_kitty_events"):
                violations.append(f"imports from {module}")
            elif _is_private_runtime_module(module):
                if id(node) not in type_only or not {alias.name for alias in node.names} <= _TYPE_ONLY_ENGINE_IMPORTS:
                    violations.append(f"imports from {module}")
            elif module.endswith("_internal_runtime"):
                for alias in node.names:
                    if alias.name in ("engine", "planner"):
                        if alias.asname != f"_{alias.name}":
                            violations.append(f"imports {alias.name} as {alias.asname}")
                    elif alias.name not in _ALLOWED_PACKAGE_IMPORTS:
                        violations.append(f"imports {alias.name} from {module}")
            elif any(alias.name == "_internal_runtime" for alias in node.names):
                violations.append(f"imports _internal_runtime from {module}")
    return violations


def _access_violations(tree: ast.Module) -> list[str]:
    """``_engine`` / ``_planner`` are reached only as ``<alias>.<allowlisted attr>``."""
    violations: list[str] = []
    attribute_bases: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in _ALLOWED_ENGINE_ACCESS:
            attribute_bases.add(id(node.value))
            if node.attr not in _ALLOWED_ENGINE_ACCESS[node.value.id]:
                violations.append(f"reaches {node.value.id}.{node.attr}, which is not on the allowlist")
    violations.extend(
        f"uses {node.id} other than as {node.id}.<attr>"
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id in _ALLOWED_ENGINE_ACCESS and id(node) not in attribute_bases
    )
    return violations


def _reference_violations(tree: ast.Module) -> list[str]:
    """Names the adapter must never mention: engine events and writers, ``apply_result``,
    ``model_copy`` (editing a plan) and any ``emit_*`` (emitting an event itself)."""
    violations: list[str] = []
    for node in ast.walk(tree):
        name = node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else None
        if name is None:
            continue
        if name in _FORBIDDEN_REFERENCES:
            violations.append(f"references {name}")
        elif name.startswith("emit_"):
            violations.append(f"calls {name}")
    return violations


def _plan_next_violations(tree: ast.Module) -> list[str]:
    """``plan_next`` is called only inside its own pinned wrapper."""
    wrapper_calls = sum(
        1
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "plan_next"
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and _call_name(call.func) == "plan_next"
    )
    all_calls = sum(1 for call in ast.walk(tree) if isinstance(call, ast.Call) and _call_name(call.func) == "plan_next")
    return ["calls plan_next outside its pinned wrapper"] if all_calls > wrapper_calls else []


def _adapter_shape_violations(source: str) -> list[str]:
    """Every way ``source`` re-grows a parallel planner, writer or event code."""
    tree = ast.parse(source)
    return [*_import_violations(tree), *_access_violations(tree), *_reference_violations(tree), *_plan_next_violations(tree)]


def test_adapter_has_no_parallel_planner_or_event_code() -> None:
    """The adapter commits the engine's plan: it reaches only the allowlisted engine
    and planner attributes, applies no result, emits nothing and builds none of the
    engine's events."""
    assert _adapter_shape_violations(_ADAPTER_PATH.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize(
    ("planted", "expected"),
    [
        # The writer / constructor / planner bans the gate always had.
        ("payload = NextStepIssuedPayload(run_id='r')\n", "references NextStepIssuedPayload"),
        ("def f(run_dir, snapshot):\n    _write_snapshot(run_dir, snapshot)\n", "references _write_snapshot"),
        ("def advance(snapshot):\n    return plan_next(snapshot, None, None)\n", "calls plan_next outside its pinned wrapper"),
        # Bypasses of the old name-matching denylist.
        (
            "from runtime.next._internal_runtime.engine import apply_result as _ar\n\ndef f(s):\n    return _ar(s, 'success')\n",
            "imports from runtime.next._internal_runtime.engine",
        ),
        ("def f(r, p, a, e):\n    return _engine._commit_advance(r, p, a, e)\n", "_engine._commit_advance"),
        ("def f(sync_emitter, p):\n    sync_emitter.emit_next_step_issued(p)\n", "calls emit_next_step_issued"),
        ("payload = NextStepIssuedPayload.model_validate({'run_id': 'r'})\n", "references NextStepIssuedPayload"),
        ("def f(r, plan, a, e):\n    return commit_advance(r, plan.model_copy(update={'issued_step_id': None}), a, e)\n", "references model_copy"),
        ("def f(r, a):\n    return _engine.next_step(r, a)\n", "_engine.next_step"),
        ("def f(snapshot):\n    return getattr(_planner, 'plan_next')(snapshot)\n", "uses _planner other than as"),
        ("from spec_kitty_events.mission_next import NextStepIssuedPayload as _P\n", "imports from spec_kitty_events.mission_next"),
        ("from runtime.next._internal_runtime import next_step as _ns\n", "imports next_step from runtime.next._internal_runtime"),
        ("from runtime.next import _internal_runtime as _ir\n", "imports _internal_runtime from runtime.next"),
        ("import importlib\n\ndef f():\n    return importlib.import_module('x')\n", "references import_module"),
    ],
)
def test_adapter_shape_gate_reports_a_planted_violation(planted: str, expected: str) -> None:
    """Self-mutation row: each planted bypass is reported by the rule meant to catch it
    (the gate is not vacuous, and not satisfied by an unrelated rule)."""
    wrapper = "def plan_next(snapshot):\n    return _planner.plan_next(snapshot)\n"
    assert _adapter_shape_violations(wrapper) == [], "the pinned plan_next wrapper itself is allowed"
    assert any(expected in violation for violation in _adapter_shape_violations(wrapper + planted))
