"""The retrospective gate runs BEFORE anything is written for a terminal advance.

Mission ``mission-writer-followups-01M4CYWW`` WP05 (FR-009, FR-010, FR-011, US5).

These tests drive the REAL engine and planner (no engine stubs) through
``_dn_decision_materialize`` on the three legacy advance paths --
``commit_advance``, the stale-plan fallback and the no-plan fallback -- with a
strict (blocking) retrospective policy. The gate is the only seam replaced: a
``refuse`` capture that records what the run files looked like at the moment
the gate ran, and optionally acts as a *foreign writer* appending to
``run.events.jsonl`` while the gate runs (injected, no threads, no sleeps).

The contract: a refused terminal step leaves ``run.events.jsonl`` and
``state.json`` exactly as other writers left them (nothing of ours appended,
nothing of theirs cut), and the refusal reads as a typed retrospective-gate
refusal on the legacy and the composition paths.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from runtime.next import runtime_bridge as rb
from runtime.next import runtime_bridge_engine as engine_adapter
from runtime.next import runtime_bridge_retrospective as retro
from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    NullEmitter,
    next_step,
    start_mission_run,
)
from runtime.next._internal_runtime.engine import MissionRunRef, plan_advance
from runtime.next._internal_runtime.events import RuntimeEventEmitter
from runtime.next.decision import DecisionKind

pytestmark = [pytest.mark.unit, pytest.mark.fast]

SLUG = "terminal-gate-mission"
NOW = "2026-10-08T00:00:00Z"
FOREIGN_LINE = b'{"event_type": "ForeignWriterEvent", "payload": {}, "timestamp": "x"}\n'
COMPLETED_MARKERS = (b"NextStepAutoCompleted", b"MissionRunCompleted")


class _CountingEmitter(NullEmitter):
    """``NullEmitter`` recording which emit methods the engine reached."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self.calls.append("emit_next_step_auto_completed")

    def emit_mission_run_completed(self, payload: Any) -> None:
        self.calls.append("emit_mission_run_completed")


def _strict_policy() -> SimpleNamespace:
    return SimpleNamespace(enabled=True, timing="before_completion", failure_policy="block")


def _best_effort_policy() -> SimpleNamespace:
    return SimpleNamespace(enabled=True, timing="after_completion", failure_policy="warn")


def _start_one_step_run(tmp_path: Path) -> tuple[MissionRunRef, Path]:
    """A real run with a single issued step: the next ``success`` is terminal."""
    raw = {
        "mission": {"key": "terminal-gate", "name": "Terminal gate", "version": "1.0.0"},
        "steps": [{"id": "only", "title": "Only", "description": "the only step", "prompt": "Do it."}],
    }
    mission_dir = tmp_path / "missions" / "terminal-gate"
    mission_dir.mkdir(parents=True)
    yaml_path = mission_dir / "mission.yaml"
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
    issued = next_step(run_ref, agent_id="agent-1", emitter=NullEmitter())
    assert issued.step_id == "only"
    return run_ref, Path(run_ref.run_dir)


def _feature_dir(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"mission_id":"01KT3YBDABCDEFGHIJKLMNOP"}', encoding="utf-8")
    return feature_dir


def _ctx(tmp_path: Path, run_ref: MissionRunRef, run_dir: Path, emitter: RuntimeEventEmitter) -> rb.DecideNextContext:
    return rb.DecideNextContext(
        agent="tester",
        mission_slug=SLUG,
        result="success",
        repo_root=tmp_path,
        feature_dir=_feature_dir(tmp_path),
        now=NOW,
        mission_type="terminal-gate",
        sync_emitter=emitter,
        emitter_for_engine=emitter,
        origin={},
        progress=None,
        run_ref=run_ref,
        run_dir=run_dir,
        current_step_id="only",
    )


def _read(path: Path) -> bytes:
    return path.read_bytes()


class _Run:
    """One real run plus the gate probe, built per test."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, path: str, policy: SimpleNamespace) -> None:
        self.run_ref, self.run_dir = _start_one_step_run(tmp_path)
        self.emitter = _CountingEmitter()
        self.ctx = _ctx(tmp_path, self.run_ref, self.run_dir, self.emitter)
        self.events = self.run_dir / "run.events.jsonl"
        self.state = self.run_dir / "state.json"
        self.gate_calls = 0
        #: run files as seen by the gate when it ran
        self.seen_by_gate: list[tuple[bytes, bytes]] = []
        #: bytes other writers left in the events log, captured right before the engine is asked to advance
        self.foreign_events: bytes = b""
        self.append_foreign_in_gate = False
        self.gate_failure: Exception = RuntimeError("gate refused")
        self.capture_blocking_flags: list[bool] = []
        monkeypatch.setattr(retro, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (policy, {}, None))
        monkeypatch.setattr(retro, "_resolve_mission_id_for_terminus", lambda feature_dir: "01KT3YBDABCDEFGHIJKLMNOP")
        monkeypatch.setattr(retro, "_run_retrospective_learning_capture", self._capture)
        self._install_path(monkeypatch, path)

    def _capture(self, **kwargs: Any) -> None:
        self.gate_calls += 1
        self.capture_blocking_flags.append(bool(kwargs["block_on_failure"]))
        if not kwargs["block_on_failure"]:
            return
        self.seen_by_gate.append((_read(self.events), _read(self.state)))
        if self.append_foreign_in_gate:
            with open(self.events, "ab") as handle:
                handle.write(FOREIGN_LINE)
        raise self.gate_failure

    def _install_path(self, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
        real_plan = engine_adapter.plan_advance

        def planning(run_ref: MissionRunRef, agent_id: str, result: str = "success") -> Any:
            plan = real_plan(run_ref, agent_id, result)
            if path == "stale_plan":
                # Another writer moves the run between plan and commit.
                snapshot = plan.source.model_copy(update={"inputs": {"moved_by": "another-writer"}})
                self.state.write_text(snapshot.model_dump_json(), encoding="utf-8")
            if path == "no_plan":
                raise OSError("advance preview unavailable")
            return plan

        monkeypatch.setattr(engine_adapter, "plan_advance", planning)

    def advance(self) -> Any:
        self.foreign_events = _read(self.events)
        return rb._dn_decision_materialize(self.ctx)


PATHS = ["commit_advance", "stale_plan", "no_plan"]


@pytest.mark.parametrize("path", PATHS)
def test_refused_terminal_step_runs_gate_before_anything_is_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """FR-009 / FR-011: at the moment the gate runs, the completion is not yet in the run files."""
    run = _Run(tmp_path, monkeypatch, path=path, policy=_strict_policy())

    decision = run.advance()

    assert decision.kind == DecisionKind.blocked
    assert run.gate_calls == 1
    events_at_gate, _state_at_gate = run.seen_by_gate[0]
    assert events_at_gate == run.foreign_events, "the gate must run before the engine appends step completion or run completion"
    assert not any(marker in events_at_gate for marker in COMPLETED_MARKERS)
    assert run.emitter.calls == [], "nothing may be emitted for a refused terminal step"


@pytest.mark.parametrize("path", PATHS)
def test_refused_terminal_step_leaves_both_files_byte_identical(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    run = _Run(tmp_path, monkeypatch, path=path, policy=_strict_policy())
    # Bytes as other writers left them: what the gate saw is what the files must still be.
    decision = run.advance()

    assert decision.kind == DecisionKind.blocked
    events_at_gate, state_at_gate = run.seen_by_gate[0]
    assert _read(run.events) == events_at_gate
    assert _read(run.state) == state_at_gate
    assert not (run.run_dir / "state.json.tmp").exists()


@pytest.mark.parametrize("path", PATHS)
def test_foreign_append_during_the_gate_survives_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    """FR-010 red proof: a record another writer appends while the gate runs is not cut.

    Before the fix the speculative capture/rollback truncated ``run.events.jsonl``
    back to the size it had before the engine ran, which removed the foreign
    line together with ours."""
    run = _Run(tmp_path, monkeypatch, path=path, policy=_strict_policy())
    run.append_foreign_in_gate = True

    decision = run.advance()

    assert decision.kind == DecisionKind.blocked
    assert _read(run.events) == run.foreign_events + FOREIGN_LINE
    assert not any(marker in _read(run.events) for marker in COMPLETED_MARKERS)


@pytest.mark.parametrize("path", PATHS)
def test_allowed_terminal_step_completes_after_the_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    run = _Run(tmp_path, monkeypatch, path=path, policy=_strict_policy())
    monkeypatch.setattr(retro, "_run_retrospective_learning_capture", lambda **kwargs: run.capture_blocking_flags.append(True))

    decision = run.advance()

    assert decision.kind == DecisionKind.terminal
    assert b"MissionRunCompleted" in _read(run.events)
    assert run.emitter.calls == ["emit_next_step_auto_completed", "emit_mission_run_completed"]


# ---------------------------------------------------------------------------
# The refusal reads as a typed retrospective-gate refusal (B6)
# ---------------------------------------------------------------------------


def _gate_decision(code: str = "no_record", detail: str = "no retrospective record") -> Any:
    """The part of a ``GateDecision`` the refusal reads: ``reason.code`` / ``reason.detail``."""
    return SimpleNamespace(allow_completion=False, reason=SimpleNamespace(code=code, detail=detail))


def _refusal_causes() -> list[Callable[[], Exception]]:
    return [
        lambda: RuntimeError("capture exploded"),
        lambda: ValueError("policy file unreadable"),
    ]


@pytest.mark.parametrize("make_exc", _refusal_causes())
def test_legacy_refusal_is_a_typed_retrospective_gate_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_exc: Callable[[], Exception]) -> None:
    run = _Run(tmp_path, monkeypatch, path="commit_advance", policy=_strict_policy())
    run.gate_failure = make_exc()

    decision = run.advance()

    assert decision.kind == DecisionKind.blocked
    assert (decision.reason or "").startswith("Retrospective gate refused completion")
    assert str(run.gate_failure) in (decision.reason or "")
    assert "Runtime engine error" not in (decision.reason or "")


def test_legacy_refusal_carries_the_gate_reason_as_guard_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next._internal_runtime.retrospective_hook import MissionCompletionBlocked

    run = _Run(tmp_path, monkeypatch, path="commit_advance", policy=_strict_policy())
    gate = _gate_decision("no_record", "no retrospective record")
    run.gate_failure = MissionCompletionBlocked(gate)

    decision = run.advance()

    assert (decision.reason or "").startswith("Retrospective gate refused completion")
    assert decision.guard_failures == ["no_record: no retrospective record"]


def test_policy_error_is_a_typed_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _Run(tmp_path, monkeypatch, path="commit_advance", policy=_strict_policy())
    policy_error = ValueError("bad retrospective policy")
    monkeypatch.setattr(retro, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (_strict_policy(), {}, policy_error))

    decision = run.advance()

    assert decision.kind == DecisionKind.blocked
    assert (decision.reason or "").startswith("Retrospective gate refused completion")
    assert "bad retrospective policy" in (decision.reason or "")
    assert run.gate_calls == 0
    assert not any(marker in _read(run.events) for marker in COMPLETED_MARKERS)


def test_composition_refusal_is_the_same_typed_decision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The composition path reads the refusal exactly as the legacy path does,
    not as the generic ``Run-state advancement after composition failed``."""
    run = _Run(tmp_path, monkeypatch, path="commit_advance", policy=_strict_policy())
    plan = plan_advance(run.run_ref, "tester", "success")
    wp_resolution = None
    before_events, before_state = _read(run.events), _read(run.state)

    with pytest.raises(retro.RetrospectiveGateRefused) as excinfo:
        engine_adapter.advance_run_state_after_composition(
            run_ref=run.run_ref,
            agent="tester",
            mission_slug=SLUG,
            mission_type="terminal-gate",
            repo_root=tmp_path,
            feature_dir=run.ctx.feature_dir,
            timestamp=NOW,
            progress=None,
            origin={},
            sync_emitter=run.emitter,
            plan=plan,
            wp_resolution=wp_resolution,
        )
    assert isinstance(excinfo.value.__cause__, RuntimeError)
    assert _read(run.events) == before_events
    assert _read(run.state) == before_state

    decision = rb._retrospective_gate_refused_decision(run.ctx, excinfo.value)
    legacy = run.advance()
    assert decision.kind == legacy.kind == DecisionKind.blocked
    assert decision.reason == legacy.reason


def test_composition_dispatch_does_not_wrap_the_refusal_as_advance_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _Run(tmp_path, monkeypatch, path="commit_advance", policy=_strict_policy())
    refusal = retro.RetrospectiveGateRefused(RuntimeError("capture exploded"))

    def refuse(**kwargs: Any) -> Any:
        raise refusal

    monkeypatch.setattr(engine_adapter, "advance_run_state_after_composition", refuse)

    decision = rb._dn_advance_composition_or_refusal(run.ctx, "accept", plan=None, wp_resolution=None)

    assert (decision.reason or "").startswith("Retrospective gate refused completion")
    assert "advancement after composition failed" not in (decision.reason or "")


# ---------------------------------------------------------------------------
# A terminal re-poll does not re-run the gate or the non-blocking capture (B7)
# ---------------------------------------------------------------------------


def _complete_run(run: _Run) -> None:
    next_step(run.run_ref, agent_id="tester", emitter=NullEmitter())


@pytest.mark.parametrize("path", ["commit_advance", "no_plan"])
def test_terminal_repoll_does_not_rerun_the_strict_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    run = _Run(tmp_path, monkeypatch, path=path, policy=_strict_policy())
    _complete_run(run)
    before_events, before_state = _read(run.events), _read(run.state)

    decision = run.advance()

    assert run.gate_calls == 0, "a run that is already terminal must not be re-gated"
    assert decision.kind == DecisionKind.terminal
    assert _read(run.events) == before_events
    assert _read(run.state) == before_state


@pytest.mark.parametrize("path", ["commit_advance", "no_plan"])
def test_non_blocking_capture_fires_only_on_the_transition_into_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
    run = _Run(tmp_path, monkeypatch, path=path, policy=_best_effort_policy())

    first = run.advance()
    assert first.kind == DecisionKind.terminal
    assert run.capture_blocking_flags == [False]

    second = run.advance()
    assert second.kind == DecisionKind.terminal
    assert run.capture_blocking_flags == [False], "a terminal re-poll must not re-run the non-blocking capture"
