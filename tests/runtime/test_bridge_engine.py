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

   A non-vacuousness check (``test_adapter_defines_all_six_engine_planner_wrappers``)
   guards against the "no other module reaches in" assertion passing for the
   wrong reason (e.g. if the adapter itself stopped wrapping one of the 6).

2. **Focused unit tests (FR-006)** against ``_internal_runtime.engine`` /
   ``.planner`` *stubs* (monkeypatched), never the real runtime — that
   characterization is the WP01 parity oracle's job
   (``tests/runtime/test_bridge_parity.py``). These tests pin:

   * the 5 low-level wrappers delegate via a **live module-attribute lookup**
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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from runtime.next import runtime_bridge_engine as engine_adapter
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


def test_adapter_defines_all_six_engine_planner_wrappers() -> None:
    """Non-vacuousness check: the "no sibling reaches in" assertion above is
    only meaningful if the adapter itself still wraps all 6 concentrated
    names -- guards against it passing for the wrong reason (e.g. the
    adapter silently dropping a wrapper)."""
    for name in _ENGINE_PLANNER_PRIVATE_NAMES:
        wrapper_name = _ADAPTER_WRAPPER_NAME.get(name, name)
        assert hasattr(engine_adapter, wrapper_name), f"runtime_bridge_engine no longer defines a wrapper for {name!r} (expected attribute {wrapper_name!r})"


# ---------------------------------------------------------------------------
# 2a. Focused unit tests — the 5 wrapper functions (FR-006)
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
def test_append_event_delegates_via_live_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._append_event", lambda *a: calls.append(a))
    engine_adapter._append_event(tmp_path, "SomeEvent", {"k": "v"})
    assert calls == [(tmp_path, "SomeEvent", {"k": "v"})]


@pytest.mark.unit
def test_write_snapshot_delegates_via_live_lookup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    snapshot = MissionRunSnapshot(run_id="r1", mission_key="software-dev", template_path="t", template_hash="h")
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._write_snapshot", lambda rd, s: calls.append((rd, s)))
    engine_adapter._write_snapshot(tmp_path, snapshot)
    assert calls == [(tmp_path, snapshot)]


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


@pytest.mark.unit
def test_live_template_path_none_when_blank() -> None:
    snapshot = MissionRunSnapshot(run_id="r", mission_key="m", template_path="", template_hash="h")
    assert engine_adapter._live_template_path(snapshot) is None


@pytest.mark.unit
def test_live_template_path_none_when_missing_on_disk(tmp_path: Path) -> None:
    snapshot = MissionRunSnapshot(run_id="r", mission_key="m", template_path=str(tmp_path / "does-not-exist.yaml"), template_hash="h")
    assert engine_adapter._live_template_path(snapshot) is None


@pytest.mark.unit
def test_live_template_path_present_when_exists(tmp_path: Path) -> None:
    template_file = tmp_path / "template.yaml"
    template_file.write_text("x", encoding="utf-8")
    snapshot = MissionRunSnapshot(run_id="r", mission_key="m", template_path=str(template_file), template_hash="h")
    assert engine_adapter._live_template_path(snapshot) == template_file


# ---------------------------------------------------------------------------
# 2b. Focused unit tests — ``advance_run_state_after_composition`` (FR-006)
# ---------------------------------------------------------------------------


class _FakeSyncEmitter:
    """Records calls; stands in for ``SyncRuntimeEventEmitter`` (FR-006 stub)."""

    def __init__(self) -> None:
        self.seeded: list[Any] = []
        self.auto_completed: list[Any] = []
        self.step_issued: list[Any] = []
        self.decision_requested: list[Any] = []
        self.run_completed: list[Any] = []

    def seed_from_snapshot(self, snapshot: Any) -> None:
        self.seeded.append(snapshot)

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self.auto_completed.append(payload)

    def emit_next_step_issued(self, payload: Any) -> None:
        self.step_issued.append(payload)

    def emit_decision_input_requested(self, payload: Any) -> None:
        self.decision_requested.append(payload)

    def emit_mission_run_completed(self, payload: Any) -> None:
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

    The adapter calls back into ``runtime_bridge`` via a deferred module
    import for this symbol (it is not an engine-private and stays owned by
    ``runtime_bridge.py`` — see ``runtime_bridge_engine.py`` module
    docstring), so patching it on the ``runtime_bridge`` module is the
    correct seam to stub for these contract tests.
    """

    recorder = _MapDecisionRecorder(calls=[], sentinel=object())

    def _fake(
        decision: Any, agent: Any, mission_slug: Any, mission_type: Any, repo_root: Any, feature_dir: Any, timestamp: Any, progress: Any, origin: Any, **_kw: Any
    ) -> Any:
        recorder.calls.append((decision, agent, mission_slug, mission_type, repo_root, feature_dir, timestamp, progress, origin))
        return recorder.sentinel

    monkeypatch.setattr(decision_mapping, "_map_runtime_decision", _fake)
    return recorder


def _stub_engine_and_planner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    read_snapshot_returns: MissionRunSnapshot,
    plan_next_returns: NextDecision,
) -> tuple[list[Any], list[tuple[Any, ...]]]:
    """Patch the adapter's engine/planner module references (via monkeypatch's
    string-path form — see the delegation tests above for why); return
    (written_snapshots, appended_events) recorder lists."""
    written: list[Any] = []
    appended: list[tuple[Any, ...]] = []
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._read_snapshot", lambda run_dir: read_snapshot_returns)
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._load_frozen_template", lambda run_dir: object())
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._write_snapshot", lambda run_dir, snap: written.append(snap))
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._engine._append_event", lambda *a: appended.append(a))
    monkeypatch.setattr("runtime.next.runtime_bridge_engine._planner.plan_next", lambda *a, **k: plan_next_returns)
    return written, appended


@pytest.mark.unit
def test_advance_run_state_step_decision_no_prior_step(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, _stub_map_runtime_decision: _MapDecisionRecorder) -> None:
    """No step was in flight (``issued_step_id`` is None) — nothing to
    auto-complete; the ``step`` decision stamps the new ``issued_step_id`` and
    emits ``NextStepIssued`` only."""
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    snapshot_in = MissionRunSnapshot(run_id="run-1", mission_key="software-dev", template_path="", template_hash="h")
    decision = NextDecision(kind="step", run_id="run-1", mission_key="software-dev", step_id="implement")
    written, appended = _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-1", run_dir=str(run_dir), mission_key="software-dev")

    result = engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=sync_emitter,
        plan=engine_adapter.plan_composition_advance(run_ref, "agent-1"),
        wp_resolution=("implement", "WP01", "/ws", "lane-a", "wp"),  # the bridge resolved this before the advance
    )

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
    run_dir.mkdir()
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
    written, appended = _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-2", run_dir=str(run_dir), mission_key="software-dev")

    engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=sync_emitter,
        plan=engine_adapter.plan_composition_advance(run_ref, "agent-1"),
    )

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
    run_dir.mkdir()
    snapshot_in = MissionRunSnapshot(
        run_id="run-3",
        mission_key="software-dev",
        template_path="",
        template_hash="h",
        pending_decisions={"audit:review": {"already": "there"}},
    )
    decision = NextDecision(kind="decision_required", run_id="run-3", mission_key="software-dev", decision_id="audit:review", step_id="review")
    written, appended = _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-3", run_dir=str(run_dir), mission_key="software-dev")

    engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=sync_emitter,
        plan=engine_adapter.plan_composition_advance(run_ref, "agent-1"),
    )

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
    run_dir.mkdir()
    snapshot_in = MissionRunSnapshot(
        run_id="run-4",
        mission_key="software-dev",
        template_path="",
        template_hash="h",
        issued_step_id="review",
        completed_steps=["implement"],
    )
    decision = NextDecision(kind="terminal", run_id="run-4", mission_key="software-dev")
    _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)

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

    engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=sync_emitter,
        plan=engine_adapter.plan_composition_advance(run_ref, "agent-1"),
    )

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
    run_dir.mkdir()
    snapshot_in = MissionRunSnapshot(run_id="run-5", mission_key="software-dev", template_path="", template_hash="h", issued_step_id=None)
    decision = NextDecision(kind="terminal", run_id="run-5", mission_key="software-dev")
    _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)

    monkeypatch.setattr(
        retrospective_seam,
        "_resolve_retrospective_policy_for_runtime",
        lambda repo_root: (_ for _ in ()).throw(AssertionError("must not consult retrospective policy")),
    )

    sync_emitter = _FakeSyncEmitter()
    run_ref = MissionRunRef(run_id="run-5", run_dir=str(run_dir), mission_key="software-dev")

    engine_adapter.advance_run_state_after_composition(
        run_ref=run_ref,
        agent="agent-1",
        mission_slug="mission-1",
        mission_type="software-dev",
        repo_root=tmp_path,
        feature_dir=tmp_path,
        timestamp="2026-01-01T00:00:00Z",
        progress=None,
        origin={},
        sync_emitter=sync_emitter,
        plan=engine_adapter.plan_composition_advance(run_ref, "agent-1"),
    )

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
    run_dir.mkdir()
    snapshot_in = MissionRunSnapshot(run_id="run-wp", mission_key="software-dev", template_path="", template_hash="h", issued_step_id="tasks")
    decision = NextDecision(kind="step", run_id="run-wp", mission_key="software-dev", step_id="implement")
    written, appended = _stub_engine_and_planner(monkeypatch, read_snapshot_returns=snapshot_in, plan_next_returns=decision)
    resolved: list[str] = []
    monkeypatch.setattr(rb, "_resolve_planned_wp_workspace", lambda *a, **k: resolved.append("resolved"))
    run_ref = MissionRunRef(run_id="run-wp", run_dir=str(run_dir), mission_key="software-dev")
    plan = engine_adapter.plan_composition_advance(run_ref, "agent-1")

    with pytest.raises(ValueError, match="wp_resolution"):
        engine_adapter.advance_run_state_after_composition(
            run_ref=run_ref,
            agent="agent-1",
            mission_slug="mission-1",
            mission_type="software-dev",
            repo_root=tmp_path,
            feature_dir=tmp_path,
            timestamp="2026-01-01T00:00:00Z",
            progress=None,
            origin={},
            sync_emitter=_FakeSyncEmitter(),
            plan=plan,
        )

    assert resolved == [], "the adapter must not resolve the workspace itself"
    assert written == [] and appended == [], "nothing may be persisted"
