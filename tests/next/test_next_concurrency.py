"""Bridge-level concurrency repros for the serialised run-cursor advance
(WP01 T002, FR-001/FR-002, SC-001/SC-002).

Deterministic (synchronous injected interleaves / a two-thread barrier, never a
sleep):

* **#5682 composition window**: a peer advance landing in the bootstrap->plan
  window makes the composition path refuse with a ``blocked`` Decision and not
  double-complete the stolen step.
* **#5854 engine path**: a peer advance landing in the engine path's window
  makes ``_dn_decision_materialize`` refuse with ``blocked`` and never re-plan
  through ``runtime_next_step`` (which would re-apply ``success``), writing
  nothing of its own.
* **answer-vs-next**: a ``provide_decision_answer`` racing a peer ``next_step``
  never loses the recorded answer -- the per-run-dir lock serialises them.
"""

from __future__ import annotations

import json
import threading
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
from runtime.next._internal_runtime import engine as _engine
from runtime.next._internal_runtime.schema import ActorIdentity, MissionRuntimeError
from runtime.next.decision import DecisionKind

pytestmark = [pytest.mark.regression]


def _issued(run_dir: Path) -> str | None:
    return json.loads((run_dir / "state.json").read_text(encoding="utf-8"))["issued_step_id"]


# ---------------------------------------------------------------------------
# #5682 composition window + #5854 engine path (real-engine scaffold)
# ---------------------------------------------------------------------------


def _scaffold_at_implement(tmp_path: Path) -> tuple[Any, str, Path]:
    from runtime.next import runtime_bridge as rb
    from tests.runtime._next_mission_scaffold import advance_to_step, scaffold_software_dev

    repo = tmp_path / "repo"
    slug = "090-serialise-next"
    scaffold_software_dev(repo, slug, with_spec=True, with_plan=True, with_tasks_md=True, wps={"WP01": "for_review"})
    advance_to_step(repo, slug, "software-dev", "implement")
    return rb, slug, repo


def test_composition_window_peer_advance_refuses_blocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5682: a peer advance that lands after dispatch but before this call's
    plan is committed makes the composition path refuse (``blocked``) and never
    double-completes the stolen ``implement`` step."""
    from runtime.next import runtime_bridge_composition as composition
    from runtime.next.runtime_bridge import get_or_start_run

    rb, slug, repo = _scaffold_at_implement(tmp_path)
    run_ref = get_or_start_run(slug, repo, "software-dev")
    run_dir = Path(run_ref.run_dir)
    assert _issued(run_dir) == "implement"

    real_dispatch = composition._dispatch_via_composition
    peer_done: list[int] = []

    def _dispatch_then_peer(*args: Any, **kwargs: Any) -> Any:
        failures = real_dispatch(*args, **kwargs)
        if not failures and not peer_done:
            peer_done.append(1)
            peer_ref = get_or_start_run(slug, repo, "software-dev")
            _engine.next_step(peer_ref, agent_id="peer", result="success", emitter=NullEmitter())
        return failures

    monkeypatch.setattr(composition, "_dispatch_via_composition", _dispatch_then_peer)

    decision = rb.decide_next_via_runtime("claude", slug, "success", repo)

    assert peer_done == [1], "the peer advance must have run in the window"
    assert decision.kind == DecisionKind.blocked
    # The peer advanced implement -> review exactly once; this stale call must
    # have added nothing on top (the cursor still sits at the peer's step).
    assert _issued(run_dir) == "review", "the peer's issued step must stand; the stale advance wrote nothing"


def test_engine_path_peer_advance_refuses_blocked_and_never_replans(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5854: driven through the engine path (``_dn_decision_materialize``
    directly), a peer advance in the commit window makes the call refuse with
    ``blocked`` and never re-plan through ``runtime_next_step``."""
    from runtime.next.runtime_bridge import get_or_start_run

    rb, slug, repo = _scaffold_at_implement(tmp_path)
    ctx, early = rb._dn_bootstrap("claude", slug, "success", repo)
    assert early is None and ctx is not None
    run_dir = Path(ctx.run_ref.run_dir)
    assert _issued(run_dir) == "implement"

    real_commit = rb._engine_adapter.commit_advance
    peer_done: list[int] = []
    next_step_calls: list[int] = []

    def _commit_after_peer(run_ref: Any, plan: Any, agent: str, emitter: Any = None, **kw: Any) -> Any:
        if not peer_done:
            peer_done.append(1)
            peer_ref = get_or_start_run(slug, repo, "software-dev")
            _engine.next_step(peer_ref, agent_id="peer", result="success", emitter=NullEmitter())
        return real_commit(run_ref, plan, agent, emitter, **kw)

    def _counting_next_step(*_a: Any, **_k: Any) -> Any:  # pragma: no cover - must not run
        next_step_calls.append(1)
        raise AssertionError("runtime_next_step must not be called on a stale engine advance")

    monkeypatch.setattr(rb._engine_adapter, "commit_advance", _commit_after_peer)
    monkeypatch.setattr(rb, "runtime_next_step", _counting_next_step)

    decision = rb._dn_decision_materialize(ctx)

    assert peer_done == [1]
    assert decision.kind == DecisionKind.blocked
    assert next_step_calls == []
    assert _issued(run_dir) == "review", "the peer's issued step must stand; the stale advance wrote nothing"


# ---------------------------------------------------------------------------
# answer-vs-next: the lock serialises a decision answer and a peer advance
# ---------------------------------------------------------------------------


def _input_run(tmp_path: Path) -> Any:
    raw = {
        "mission": {"key": "m", "name": "M", "version": "1.0.0"},
        "steps": [{"id": "s1", "title": "S1", "prompt": "do", "requires_inputs": ["topic"]}],
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
    decision = next_step(run_ref, agent_id="a")
    assert decision.decision_id == "input:topic"
    return run_ref


def test_two_concurrent_answers_serialise_exactly_one_records(tmp_path: Path) -> None:
    """Two ``provide_decision_answer`` calls on the SAME pending decision,
    released together, are serialised by the per-run-dir lock: exactly one
    records its answer and the other observes the decision already answered
    (``MissionRuntimeError``). Under no lock both read the decision still
    pending and both record -- a lost update / double answer. A short loop
    keeps the revert-to-red witness reliable."""
    actor = ActorIdentity(actor_id="a", actor_type="human", provider=None, model=None, tool=None)
    for i in range(12):
        run_ref = _input_run(tmp_path / f"iter-{i}")
        run_dir = Path(run_ref.run_dir)
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def _answer(tag: str, b: Any = barrier, rr: Any = run_ref, out: Any = outcomes, lk: Any = lock) -> None:
            b.wait(timeout=10.0)
            try:
                provide_decision_answer(rr, "input:topic", tag, actor)
                result = f"recorded:{tag}"
            except MissionRuntimeError:
                result = "already-answered"
            with lk:
                out.append(result)

        threads = [threading.Thread(target=_answer, args=(tag,)) for tag in ("alpha", "beta")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)

        recorded = [o for o in outcomes if o.startswith("recorded:")]
        assert len(recorded) == 1, f"iteration {i}: exactly one answer must record, got {outcomes}"
        assert outcomes.count("already-answered") == 1, f"iteration {i}: the loser must see the decision answered, got {outcomes}"
        state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
        assert state["inputs"]["topic"] == recorded[0].split(":", 1)[1]
        assert "input:topic" not in state["pending_decisions"]
