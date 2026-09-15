"""Decision events reach the decision log on every engine-facing path.

Regression tests for ``contracts/decision-log-flush.md`` (mission
``dead-port-disposition-01M1VRA2``, ADR ``2026-09-06-2`` §"A latent
correctness bug" / "A second bypass"). Two paths in the ``next`` bridge
handed decision-request events to the plain no-op seam
(``ctx.sync_emitter``) instead of the ``DecisionGitLog``-wrapped engine
emitter (``ctx.emitter_for_engine``), so a ``DecisionInputRequested``
raised on those paths never reached
``kitty-specs/<mission>/decisions.events.jsonl``:

* F1 — the strict-retrospective-policy buffer flush
  (``_dn_decision_materialize``).
* F2 — composition dispatch (``_dn_composition_dispatch`` ->
  ``_advance_run_state_after_composition``).

The harness is engine-free: the engine step / advancement helper are
replaced by fakes that emit into whichever emitter the bridge hands them,
and the oracle is the decision-log file written by a **real**
``DecisionGitLog``. ``ctx.sync_emitter`` is a distinct plain emitter from
the log's ``inner`` on purpose — that asymmetry is what makes the wrong
flush target observable.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from spec_kitty_events.mission_next import (
    DecisionInputRequestedPayload,
    RuntimeActorIdentity,
)

from runtime.next import runtime_bridge as rb
from runtime.next import runtime_bridge_retrospective as _retrospective_seam
from runtime.next._internal_runtime.engine import MissionRunRef
from runtime.next._internal_runtime.events import NullEmitter
from runtime.next._internal_runtime.schema import NextDecision
from runtime.next.decision import Decision, DecisionKind
from specify_cli.events.decision_log import DecisionGitLog

pytestmark = [pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]

SLUG = "flush-target-mission"
RUN_ID = "run-1"
NOW = "2026-09-06T00:00:00Z"
MISSION_TYPE = "software-dev"
DECISION_ID = "audit:review"
REQUESTED_EVENT_TYPE = "DecisionInputRequested"


# ---------------------------------------------------------------------------
# T007 — fixtures
# ---------------------------------------------------------------------------


class _RecordingNullEmitter(NullEmitter):
    """``NullEmitter`` that records the emit method names it receives, in order."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def emit_next_step_auto_completed(self, payload: Any) -> None:
        self.calls.append("emit_next_step_auto_completed")

    def emit_decision_input_requested(self, payload: Any) -> None:
        self.calls.append("emit_decision_input_requested")

    def emit_mission_run_completed(self, payload: Any) -> None:
        self.calls.append("emit_mission_run_completed")


@pytest.fixture(autouse=True)
def _no_git() -> Any:
    """Never let ``DecisionGitLog`` shell out to git from this module."""
    with patch("specify_cli.events.decision_log.safe_commit") as commit:
        yield commit


def _strict_policy() -> SimpleNamespace:
    return SimpleNamespace(enabled=True, timing="before_completion", failure_policy="block")


def _mission(tmp_path: Path, slug: str = SLUG) -> tuple[Path, Path]:
    """Coord-shaped mission dir plus a minimal run dir; returns ``(feature_dir, run_dir)``."""
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        '{"coordination_branch":"kitty/mission-' + slug + '","mission_id":"01KT3YBDABCDEFGHIJKLMNOP"}',
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / rb.STATE_FILE).write_text("{}", encoding="utf-8")
    (run_dir / "run.events.jsonl").write_text("", encoding="utf-8")
    return feature_dir, run_dir


def _decision_log(tmp_path: Path, inner: NullEmitter, slug: str = SLUG) -> DecisionGitLog:
    return DecisionGitLog(
        repo_root=tmp_path,
        worktree_root=tmp_path,
        destination_ref=f"kitty/mission-{slug}",
        mission_slug=slug,
        inner=inner,
    )


def _decisions_file(tmp_path: Path, slug: str = SLUG) -> Path:
    return tmp_path / "kitty-specs" / slug / "decisions.events.jsonl"


def _ctx(
    tmp_path: Path,
    *,
    feature_dir: Path,
    run_dir: Path,
    log: DecisionGitLog,
    sync_emitter: NullEmitter,
) -> rb.DecideNextContext:
    return rb.DecideNextContext(
        agent="tester",
        mission_slug=SLUG,
        result="success",
        repo_root=tmp_path,
        feature_dir=feature_dir,
        now=NOW,
        mission_type=MISSION_TYPE,
        sync_emitter=sync_emitter,
        emitter_for_engine=log,
        origin={},
        progress=None,
        run_ref=MissionRunRef(run_id=RUN_ID, run_dir=str(run_dir), mission_key=MISSION_TYPE),
        run_dir=run_dir,
        current_step_id="plan",
    )


def _requested_payload(*, run_id: str = RUN_ID, decision_id: str = DECISION_ID) -> DecisionInputRequestedPayload:
    return DecisionInputRequestedPayload(
        run_id=run_id,
        decision_id=decision_id,
        step_id="review",
        question="Proceed?",
        options=("yes", "no"),
        actor=RuntimeActorIdentity(actor_id="tester", actor_type="llm"),
    )


def _count_requests(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and json.loads(line)["event_type"] == REQUESTED_EVENT_TYPE)


class _Harness:
    """Everything one gated advance needs, built once per test."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.feature_dir, self.run_dir = _mission(tmp_path)
        self.inner = _RecordingNullEmitter()
        self.plain = _RecordingNullEmitter()
        self.log = _decision_log(tmp_path, self.inner)
        self.ctx = _ctx(
            tmp_path,
            feature_dir=self.feature_dir,
            run_dir=self.run_dir,
            log=self.log,
            sync_emitter=self.plain,
        )
        self.decisions_file = _decisions_file(tmp_path)

    def request_count(self) -> int:
        return _count_requests(self.decisions_file)


@pytest.fixture
def strict_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub the bridge so ``_dn_decision_materialize`` runs the strict gate path
    without touching the retrospective package or mission metadata."""
    monkeypatch.setattr(rb, "_resolve_retrospective_policy_for_runtime", lambda repo_root: (_strict_policy(), {}, None))
    monkeypatch.setattr(rb, "_resolve_mission_id_for_terminus", lambda feature_dir: None)
    monkeypatch.setattr(rb, "_run_retrospective_learning_capture", lambda **kwargs: None)


def _decision_required(run_id: str = RUN_ID) -> NextDecision:
    return NextDecision(
        kind="decision_required",
        run_id=run_id,
        mission_key=MISSION_TYPE,
        decision_id=DECISION_ID,
        step_id="review",
        question="Proceed?",
        options=["yes", "no"],
    )


def _install_decision_required_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fake ``runtime_next_step``: one non-decision moment, then the decision
    request, into whichever emitter the bridge hands it."""

    def fake_next_step(run_ref: MissionRunRef, *, agent_id: str, result: str, emitter: Any) -> NextDecision:
        emitter.emit_next_step_auto_completed(SimpleNamespace(run_id=run_ref.run_id, step_id="plan"))
        emitter.emit_decision_input_requested(_requested_payload(run_id=run_ref.run_id))
        return _decision_required(run_ref.run_id)

    monkeypatch.setattr(rb, "runtime_next_step", fake_next_step)


def test_fixture_policy_is_strict() -> None:
    assert _retrospective_seam._retrospective_blocks_completion(_strict_policy()) is True


# ---------------------------------------------------------------------------
# T008 — F1: strict-policy decision_required reaches the decision log
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("strict_bridge")
def test_strict_policy_decision_required_reaches_decision_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F1: under the strict retrospective policy the engine writes into the
    buffer; the flush must replay into the decision-log wrap, not the plain
    seam. F5: the buffered non-decision moment still reaches ``inner``, in
    original order, exactly once."""
    h = _Harness(tmp_path)
    _install_decision_required_engine(monkeypatch)

    decision = rb._dn_decision_materialize(h.ctx)

    assert decision.kind == DecisionKind.decision_required
    assert h.request_count() == 1, "buffered DecisionInputRequested must be appended to the decision log exactly once"
    assert h.inner.calls == ["emit_next_step_auto_completed", "emit_decision_input_requested"]
    assert h.plain.calls == [], "the plain seam must not be the flush target"


# ---------------------------------------------------------------------------
# T009 — F2: composition dispatch reaches the decision log
# ---------------------------------------------------------------------------


def test_composition_dispatch_decision_required_reaches_decision_log(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F2: ``_dn_composition_dispatch`` must hand the decision-log wrap to
    ``_advance_run_state_after_composition`` regardless of policy. The spy
    mirrors the real helper's first two emitter calls (seed, then the
    decision request raised by ``_emit_decision_required``)."""
    h = _Harness(tmp_path)
    monkeypatch.setattr(rb, "_should_dispatch_via_composition", lambda *args, **kwargs: True)
    monkeypatch.setattr(rb, "_normalize_action_for_composition", lambda step_id: step_id)
    monkeypatch.setattr(rb._composition, "_composition_dispatch_inputs", lambda **kwargs: (None, None))
    monkeypatch.setattr(rb, "_dispatch_via_composition", lambda **kwargs: [])

    expected = Decision(
        kind=DecisionKind.decision_required,
        agent="tester",
        mission_slug=SLUG,
        mission=MISSION_TYPE,
        mission_state="review",
        timestamp=NOW,
        decision_id=DECISION_ID,
    )
    seen: dict[str, Any] = {}

    def spy_advance(**kwargs: Any) -> Decision:
        emitter = kwargs["sync_emitter"]
        seen["emitter"] = emitter
        emitter.seed_from_snapshot(SimpleNamespace(run_id=RUN_ID))
        emitter.emit_decision_input_requested(_requested_payload())
        return expected

    monkeypatch.setattr(rb, "_advance_run_state_after_composition", spy_advance)

    decision = rb._dn_composition_dispatch(h.ctx)

    assert seen["emitter"] is h.ctx.emitter_for_engine, "composition dispatch must emit through the decision-log wrap"
    assert h.request_count() == 1
    assert decision is expected, f"advancement helper must not be short-circuited into a blocked decision: {decision.reason!r}"
    assert h.inner.calls == ["emit_decision_input_requested"]
    assert h.plain.calls == []


# ---------------------------------------------------------------------------
# T012 — F3: refused terminal gate writes nothing; F4: no duplicate entry
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("strict_bridge")
def test_strict_policy_refused_terminal_gate_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F3: when the strict gate refuses a terminal advance, the buffer is
    discarded — zero decision-log writes, no ``MissionRunCompleted`` released
    to any sink — and run state is rolled back."""
    h = _Harness(tmp_path)

    def fake_terminal_step(run_ref: MissionRunRef, *, agent_id: str, result: str, emitter: Any) -> NextDecision:
        emitter.emit_decision_input_requested(_requested_payload(run_id=run_ref.run_id))
        emitter.emit_mission_run_completed(SimpleNamespace(run_id=run_ref.run_id))
        return NextDecision(kind="terminal", run_id=run_ref.run_id, mission_key=MISSION_TYPE)

    def refuse(**kwargs: Any) -> None:
        raise RuntimeError("gate refused")

    rollbacks: list[tuple[Any, ...]] = []
    monkeypatch.setattr(rb, "runtime_next_step", fake_terminal_step)
    monkeypatch.setattr(rb, "_run_retrospective_learning_capture", refuse)
    monkeypatch.setattr(rb, "_dn_rollback_buffered_run_state", lambda *args: rollbacks.append(args))

    decision = rb._dn_decision_materialize(h.ctx)

    assert decision.kind == DecisionKind.blocked
    assert "gate refused" in (decision.reason or "")
    assert h.request_count() == 0, "a refused gate must not write to the decision log"
    assert rollbacks == [(h.run_dir, b"{}", 0)]
    assert "emit_mission_run_completed" not in h.inner.calls
    assert h.inner.calls == []
    assert h.plain.calls == []


@pytest.mark.usefixtures("strict_bridge")
def test_gated_flush_does_not_duplicate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """F4 / NFR-004: one gated ``decision_required`` advance yields exactly one
    decision-log entry, and the one-shot buffer cannot replay a second time."""
    h = _Harness(tmp_path)
    _install_decision_required_engine(monkeypatch)
    buffers: list[Any] = []

    class _SpyBuffer(rb._BufferingRuntimeEmitter):
        def __init__(self) -> None:
            super().__init__()
            buffers.append(self)

    monkeypatch.setattr(rb, "_BufferingRuntimeEmitter", _SpyBuffer)

    rb._dn_decision_materialize(h.ctx)

    assert h.request_count() == 1
    assert len(buffers) == 1  # (exactly one buffer per gated advance)
    buffers[0].flush(h.log)
    assert h.request_count() == 1, "re-flushing the one-shot buffer must not duplicate the entry"
    assert buffers[0].call_count() == 0


@pytest.mark.parametrize("seed_mode", ["missing", "raises", "lookup_raises"])
def test_real_composition_advances_and_logs_despite_optional_seed_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed_mode: str, caplog: pytest.LogCaptureFixture
) -> None:
    from runtime.next import runtime_bridge_engine as engine
    from runtime.next._internal_runtime.schema import MissionRunSnapshot

    h = _Harness(tmp_path)

    class Producer:
        def __getattr__(self, name: str) -> Any:
            if name == "seed_from_snapshot":
                if seed_mode == "lookup_raises":
                    raise RuntimeError("seed lookup failed")
                if seed_mode == "raises":

                    def fail(snapshot: Any) -> None:
                        raise RuntimeError("seed failed")

                    return fail
                raise AttributeError(name)
            return getattr(h.inner, name)

    h.log._inner = Producer()
    monkeypatch.setattr(rb, "_should_dispatch_via_composition", lambda *args, **kwargs: True)
    monkeypatch.setattr(rb, "_normalize_action_for_composition", lambda step_id: step_id)
    monkeypatch.setattr(rb._composition, "_composition_dispatch_inputs", lambda **kwargs: (None, None))
    monkeypatch.setattr(rb, "_dispatch_via_composition", lambda **kwargs: [])
    snapshot = MissionRunSnapshot(run_id=RUN_ID, mission_key=MISSION_TYPE, template_path="", template_hash="h", issued_step_id="plan")
    monkeypatch.setattr(engine, "_read_snapshot", lambda _: snapshot)
    monkeypatch.setattr(engine, "_load_frozen_template", lambda _: object())
    monkeypatch.setattr(
        engine,
        "plan_next",
        lambda *args, **kwargs: NextDecision(
            kind=DecisionKind.decision_required,
            run_id=RUN_ID,
            mission_key=MISSION_TYPE,
            step_id="review",
            decision_id=DECISION_ID,
            question="Proceed?",
            options=["yes", "no"],
        ),
    )
    persisted: list[Any] = []
    monkeypatch.setattr(engine, "_write_snapshot", lambda _, value: persisted.append(value))
    monkeypatch.setattr(
        rb,
        "_map_runtime_decision",
        lambda decision, *args: Decision(
            kind=decision.kind,
            agent="tester",
            mission_slug=SLUG,
            mission=MISSION_TYPE,
            mission_state="review",
            timestamp=NOW,
            decision_id=DECISION_ID,
        ),
    )
    decision = rb._dn_composition_dispatch(h.ctx)
    assert decision is not None
    assert decision.kind == DecisionKind.decision_required
    assert h.request_count() == 1, "real composition must durably record its decision request once"
    assert h.inner.calls == ["emit_next_step_auto_completed", "emit_decision_input_requested"]
    assert persisted[0].completed_steps == ["plan"]
    assert DECISION_ID in persisted[0].pending_decisions
    if seed_mode != "missing":
        assert "seed" in caplog.text
