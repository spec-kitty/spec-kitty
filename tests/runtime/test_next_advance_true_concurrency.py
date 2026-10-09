"""True-concurrency proof for the run-cursor lock (WP01 T002, FR-003, SC-001).

Two advances that BOTH read the same issued step into the commit window at the
same instant (a ``threading.Barrier`` releases them together): exactly one
completes and the other is refused with :class:`StaleAdvancePlan`. This is the
TOCTOU the expected-step CAS alone cannot close -- both writers re-read the same
cursor before either writes, so only the per-run-dir LOCK (which serialises the
re-read + write) makes the loser observe the winner's advance and refuse.

Reverting the lock (leaving the CAS) turns this red: both writers re-read the
same pre-advance cursor, both pass the CAS, and both complete. ``stress``-marked
because it is parallel-unsafe (a real cross-thread race over shared run-dir
files); it runs in the serial ``-n0`` lane.
"""

from __future__ import annotations

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
    start_mission_run,
)
from runtime.next._internal_runtime.engine import (
    MissionRunRef,
    StaleAdvancePlan,
    commit_advance,
    plan_advance,
)

pytestmark = [pytest.mark.stress, pytest.mark.regression]


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


_STEPS = [
    {"id": "s1", "title": "S1", "prompt": "do"},
    {"id": "s2", "title": "S2", "prompt": "do", "depends_on": ["s1"]},
    {"id": "s3", "title": "S3", "prompt": "do", "depends_on": ["s2"]},
]


def test_two_simultaneous_advances_complete_exactly_one(tmp_path: Path) -> None:
    iterations = 25
    for i in range(iterations):
        run_dir_parent = tmp_path / f"iter-{i}"
        run_dir_parent.mkdir()
        run_ref = _start(run_dir_parent, _STEPS)
        assert next_step(run_ref, agent_id="setup").step_id == "s1"

        # Both advances evaluate the SAME issued step and plan from the SAME
        # source -- the overlapping-read scenario.
        plan = plan_advance(run_ref, "a", expected_issued_step="s1")
        barrier = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def _advance(p: Any = plan, b: Any = barrier, rr: Any = run_ref, out: Any = outcomes, lk: Any = lock) -> None:
            b.wait(timeout=10.0)
            try:
                commit_advance(rr, p, "a")
                result = "completed"
            except StaleAdvancePlan:
                result = "stale"
            with lk:
                out.append(result)

        threads = [threading.Thread(target=_advance) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15.0)

        assert sorted(outcomes) == ["completed", "stale"], f"iteration {i}: exactly one advance must complete and one refuse, got {outcomes}"
