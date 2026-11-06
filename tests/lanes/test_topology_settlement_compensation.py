"""NFR-003 / FR-056: a failure at any settlement step leaves the Mission exactly as found (#7282).

One arm per git step of the ``lanes_with_coord`` settlement. Each arm lets the step run
for real and then fails it (the hardest undo: the step's effect is in place), through the
real ``finalize-tasks`` command. After the refusal: ``meta.json`` byte-identical, every
branch tip unchanged, no coordination worktree, the repository root checkout on the topic
branch, and the Mission still provisional. A control arm settles with no fault.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    THREE_LANES,
    _quiet_status_fanout,  # noqa: F401 -- autouse fixture re-exported into this module
    branch_tips,
    current_branch,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_STEP_METHODS = {
    "commit": "commit_mission_dir",
    "root_checkout_move": "move_root_checkout",
    "coord_worktree_materialize": "materialize_coord_worktree",
    "meta_restamp": "restamp_meta",
    "lanes_json_write": "write_lanes_json",
}


@pytest.mark.parametrize("step", list(_STEP_METHODS))
def test_settlement_fault_injection_restores_byte_identical(tmp_path: Path, step: str) -> None:
    from specify_cli.lanes.topology_settlement import _CoordPlan

    mission = make_default_mission(tmp_path, THREE_LANES)
    meta_bytes = (mission.root_mission_dir / "meta.json").read_bytes()
    tips = branch_tips(mission.root)
    method = _STEP_METHODS[step]
    real = getattr(_CoordPlan, method)

    def _apply_then_fail(self: _CoordPlan) -> None:
        real(self)
        raise RuntimeError(f"injected failure after {step}")

    with patch.object(_CoordPlan, method, _apply_then_fail):
        code, payload = run_finalize(mission)

    assert code == 1
    assert payload["error_code"] == "TOPOLOGY_SETTLEMENT_REFUSED"
    assert f"injected failure after {step}" in str(payload["error"])
    assert branch_tips(mission.root) == tips
    assert current_branch(mission.root) == mission.topic
    assert (mission.root_mission_dir / "meta.json").read_bytes() == meta_bytes
    assert not (mission.root / ".worktrees" / f"{mission.slug}-coord").exists()
    assert "coord" not in git(mission.root, "worktree", "list")
    meta = json.loads(meta_bytes)
    assert meta["topology_settled"] is False and "topology_decision" not in meta


def test_failure_after_settlement_compensates_the_settlement(tmp_path: Path) -> None:
    """A later finalize failure (its final commit) undoes the settlement too (NFR-003)."""
    from mission_runtime import MissionArtifactKind
    from specify_cli.coordination import commit_router

    mission = make_default_mission(tmp_path, THREE_LANES)
    meta_bytes = (mission.root_mission_dir / "meta.json").read_bytes()
    tips = branch_tips(mission.root)
    real = commit_router.commit_for_mission

    def _fail_final(*args: object, **kwargs: object) -> object:
        if kwargs.get("kind") is MissionArtifactKind.TASKS_INDEX:
            raise RuntimeError("simulated final commit failure")
        return real(*args, **kwargs)

    with patch("specify_cli.coordination.commit_router.commit_for_mission", side_effect=_fail_final):
        code, _payload = run_finalize(mission)

    assert code != 0
    assert branch_tips(mission.root) == tips
    assert current_branch(mission.root) == mission.topic
    assert (mission.root_mission_dir / "meta.json").read_bytes() == meta_bytes
    assert "coord" not in git(mission.root, "worktree", "list")


def test_control_without_fault_settles(tmp_path: Path) -> None:
    mission = make_default_mission(tmp_path, THREE_LANES)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    assert current_branch(mission.root) == mission.return_branch


def test_run_settlement_plan_undoes_in_reverse_and_names_failed_undo() -> None:
    from specify_cli.lanes.topology_settlement import SettlementStep, TopologySettlementRefused, run_settlement_plan

    log: list[str] = []

    def _boom() -> None:
        raise RuntimeError("boom")

    def _undo_fails() -> None:
        log.append("undo-b")
        raise RuntimeError("undo broke")

    steps = [
        SettlementStep("a", lambda: log.append("a"), lambda: log.append("undo-a")),
        SettlementStep("b", lambda: log.append("b"), _undo_fails),
        SettlementStep("c", _boom, lambda: log.append("undo-c")),
    ]
    with pytest.raises(TopologySettlementRefused) as refused:
        run_settlement_plan(steps, remedy="Retry.")
    assert log == ["a", "b", "undo-c", "undo-b", "undo-a"]
    assert "'c'" in str(refused.value) and "could not undo: b" in str(refused.value)
