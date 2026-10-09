"""Engine-level serialisation of the run-cursor advance (WP01 T001).

Red-first pins for three of the five fix parts, all deterministic (injected
interleaves / a holder thread + barrier, never a sleep):

* **Expected-step CAS** (T005, closes #5682): a plan carrying a
  caller-evaluated ``expected_issued_step`` that no longer matches the on-disk
  cursor is refused with :class:`StaleAdvancePlan`, writing nothing -- even
  when the plan's own ``source`` still matches live state (so the refusal is
  the CAS, not the pre-existing ``!= plan.source`` check).
* **Commit under the run-cursor lock** (T006): a held lock makes the commit
  path time out, proving ``commit_advance`` really takes the lock; a
  same-fixture lock-free control commits and issues the next step.
* **Unique snapshot temp** (T004, FR-006): two writers driven into the shared
  staging window both complete under unique temp names (they collide and lose a
  write under a fixed ``state.json.tmp``).

The ``provide_decision_answer`` held-lock pin (T006/FR-004) lives here too.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import pytest
import yaml

from kernel.locks import LockAcquireTimeout
from runtime.next import run_lock
from runtime.next._internal_runtime import (
    DiscoveryContext,
    MissionPolicySnapshot,
    NullEmitter,
    next_step,
    provide_decision_answer,
    start_mission_run,
)
from runtime.next._internal_runtime import engine as _engine
from runtime.next._internal_runtime.engine import (
    MissionRunRef,
    StaleAdvancePlan,
    commit_advance,
    plan_advance,
)
from runtime.next._internal_runtime.schema import ActorIdentity

pytestmark = [pytest.mark.regression]


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


_TWO_STEPS = [
    {"id": "s1", "title": "S1", "prompt": "do"},
    {"id": "s2", "title": "S2", "prompt": "do", "depends_on": ["s1"]},
]


def _issued(run_ref: MissionRunRef) -> str | None:
    return json.loads((Path(run_ref.run_dir) / "state.json").read_text(encoding="utf-8"))["issued_step_id"]


def _files(run_dir: Path) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in run_dir.iterdir() if p.is_file()}


# ---------------------------------------------------------------------------
# T005 — expected-step compare-and-swap (closes #5682)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_cas_refuses_when_live_issued_step_differs_from_caller_evaluated(tmp_path: Path) -> None:
    """A plan whose caller-evaluated ``expected_issued_step`` no longer matches
    the live cursor is refused, nothing written -- the on-disk state still
    equals ``plan.source`` so ONLY the CAS can fire."""
    run_ref = _start(tmp_path, _TWO_STEPS)
    assert next_step(run_ref, agent_id="a").step_id == "s1"
    run_dir = Path(run_ref.run_dir)
    assert _issued(run_ref) == "s1"

    # Caller evaluated a DIFFERENT step at bootstrap than the one live on disk.
    plan = plan_advance(run_ref, "a", expected_issued_step="some-other-step")
    before = _files(run_dir)

    with pytest.raises(StaleAdvancePlan):
        commit_advance(run_ref, plan, "a")

    assert _files(run_dir) == before, "a stale CAS must write nothing"


@pytest.mark.regression
def test_cas_matching_expected_step_commits_and_issues_next(tmp_path: Path) -> None:
    """Same-fixture positive control: the matching caller-evaluated step commits."""
    run_ref = _start(tmp_path, _TWO_STEPS)
    assert next_step(run_ref, agent_id="a").step_id == "s1"

    plan = plan_advance(run_ref, "a", expected_issued_step="s1")
    decision = commit_advance(run_ref, plan, "a")

    assert decision.step_id == "s2"
    assert _issued(run_ref) == "s2"


@pytest.mark.regression
def test_cas_default_none_preserves_todays_behaviour(tmp_path: Path) -> None:
    """A caller that passes no expected step keeps the pre-existing contract."""
    run_ref = _start(tmp_path, _TWO_STEPS)
    assert next_step(run_ref, agent_id="a").step_id == "s1"

    decision = commit_advance(run_ref, plan_advance(run_ref, "a"), "a")
    assert decision.step_id == "s2"
    assert _issued(run_ref) == "s2"


# ---------------------------------------------------------------------------
# T006 — the commit path takes the run-cursor lock
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_commit_advance_blocks_while_the_run_cursor_lock_is_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Holding the run-cursor lock makes ``commit_advance`` time out -- proving
    it really acquires the lock -- then the SAME plan commits once released
    (same-fixture positive control: the negative assertion proves the lock, not
    an unrelated timeout)."""
    monkeypatch.setattr(run_lock, "_LOCK_TIMEOUT_S", 0.3)
    run_ref = _start(tmp_path, _TWO_STEPS)
    assert next_step(run_ref, agent_id="a").step_id == "s1"
    run_dir = Path(run_ref.run_dir)
    plan = plan_advance(run_ref, "a", expected_issued_step="s1")

    with run_lock.run_cursor_lock(run_dir), pytest.raises(LockAcquireTimeout):
        commit_advance(run_ref, plan, "a")
    assert _issued(run_ref) == "s1", "the timed-out commit must write nothing"

    # Lock free now: the very same plan commits and issues the next step.
    decision = commit_advance(run_ref, plan, "a")
    assert decision.step_id == "s2"
    assert _issued(run_ref) == "s2"


@pytest.mark.regression
def test_provide_decision_answer_blocks_while_the_run_cursor_lock_is_held(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``provide_decision_answer`` takes the same lock (FR-004): held -> timeout;
    free -> the answer is recorded."""
    monkeypatch.setattr(run_lock, "_LOCK_TIMEOUT_S", 0.3)
    raw_steps = [{"id": "s1", "title": "S1", "prompt": "do", "requires_inputs": ["topic"]}]
    run_ref = _start(tmp_path, raw_steps)
    decision = next_step(run_ref, agent_id="a")
    assert decision.decision_id == "input:topic"
    run_dir = Path(run_ref.run_dir)
    actor = ActorIdentity(actor_id="a", actor_type="human", provider=None, model=None, tool=None)

    with run_lock.run_cursor_lock(run_dir), pytest.raises(LockAcquireTimeout):
        provide_decision_answer(run_ref, "input:topic", "the-answer", actor)

    # Lock free: the answer records into inputs.
    provide_decision_answer(run_ref, "input:topic", "the-answer", actor)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert state["inputs"]["topic"] == "the-answer"
    assert "input:topic" not in state["pending_decisions"]


# ---------------------------------------------------------------------------
# T004 — unique snapshot staging temp (FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.regression
def test_two_snapshot_writers_into_the_staging_window_both_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two writers driven into the stage-then-replace window of one run_dir both
    complete and leave a valid ``state.json`` (one of the two). Under the FIXED
    ``state.json.tmp`` name they share one staging path, so the second
    ``os.replace`` finds it already gone and raises -- RED. Unique temps let
    both publish."""
    run_ref = _start(tmp_path, _TWO_STEPS)
    assert next_step(run_ref, agent_id="a").step_id == "s1"
    run_dir = Path(run_ref.run_dir)

    base = _engine._read_snapshot(run_dir)
    snap_a = base.model_copy(update={"issued_step_id": "s1"})
    snap_b = base.model_copy(update={"issued_step_id": "s2"})

    # Synchronise both writers AT the publish step so they are both staged
    # before either replaces -- the discriminating collision window.
    barrier = threading.Barrier(2)
    real_replace = _engine.os.replace

    def _synced_replace(src: Any, dst: Any) -> Any:
        if str(dst).endswith("state.json"):
            barrier.wait(timeout=5.0)
        return real_replace(src, dst)

    monkeypatch.setattr(_engine.os, "replace", _synced_replace)

    errors: list[BaseException] = []

    def _write(snap: Any) -> None:
        try:
            _engine._write_snapshot(run_dir, snap)
        except BaseException as exc:  # noqa: BLE001 - surfaced via errors
            errors.append(exc)

    threads = [threading.Thread(target=_write, args=(s,)) for s in (snap_a, snap_b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert not errors, f"a staging collision lost/corrupted a write: {errors}"
    # The published state.json is a complete, valid snapshot (one of the two).
    final = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    assert final["issued_step_id"] in {"s1", "s2"}
