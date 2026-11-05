"""Real-Git boundary coverage for move-task's absent and unreadable lane windows (#7120).

The pure move-gate suite owns its shared fixture. These cases need actual local ref states,
so they live under git_ops without inheriting that suite's no-subprocess unit marker.
Detailed recovery wording belongs to the consolidation evidence suite; these cases verify
that move-task routes the right window and retains the fail-closed diagnostic boundary.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mission_runtime import ActionContextError
from specify_cli.cli.commands.agent import tasks_move_task as move_task_module
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.status.models import Lane
from tests.specify_cli.cli.commands.agent.test_move_task_evidence_gate import _Facts, _state
from tests.specify_cli.cli.commands.agent.test_move_task_evidence_gate import lanes_mission as lanes_mission

pytestmark = [pytest.mark.git_repo]


def _gate_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    config = (("init", "-q", "-b", "main"), ("config", "user.name", "QA"), ("config", "user.email", "qa@example.invalid"), ("config", "commit.gpgsign", "false"))
    for args in config:
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "seed"], cwd=repo, check=True, capture_output=True)
    return repo


def _absent_branch_state(repo: Path) -> move_task_module._MoveTaskState:
    state = _state(Lane.FOR_REVIEW)
    state.main_repo_root = repo
    return state


def test_a_never_created_lane_branch_names_the_shape_and_the_escalation(tmp_path: Path, lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _gate_repo(tmp_path)

    def _unreadable(*_args: object, **_kwargs: object) -> frozenset[str]:
        raise GitProbeError("git diff --name-status plan..kitty/mission-fx-lane-b failed (exit 128): fatal: bad revision")

    monkeypatch.setattr(move_task_module, "_mt_lane_window_paths", _unreadable)
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_absent_branch_state(repo))

    message = str(refused.value)
    assert refused.value.code == "IMPLEMENTATION_UNREADABLE"
    assert message.startswith("IMPLEMENTATION_UNREADABLE: WP02's evidence window plan0000..kitty/mission-fx-lane-b (lane-b) cannot be read: ")
    assert "no lane of this Mission has a branch here" in message
    assert "Make the lane branch and the recorded planning commit readable" not in message


def test_a_missing_lane_with_a_sibling_names_conditional_restore(tmp_path: Path, lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _gate_repo(tmp_path)
    subprocess.run(["git", "branch", "kitty/mission-fx-lane-a"], cwd=repo, check=True, capture_output=True)

    def _unreadable(*_args: object, **_kwargs: object) -> frozenset[str]:
        raise GitProbeError("bad revision")

    monkeypatch.setattr(move_task_module, "_mt_lane_window_paths", _unreadable)
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_absent_branch_state(repo))

    message = str(refused.value)
    assert refused.value.code == "IMPLEMENTATION_UNREADABLE"
    assert "refs/spec-kitty/lane-tip/kitty/mission-fx-lane-b" in message
    assert "If it did exist" in message
    assert "no lane of this Mission has a branch here" not in message


def test_a_present_ref_that_cannot_be_read_is_still_unreadable(tmp_path: Path, lanes_mission: _Facts, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _gate_repo(tmp_path)
    (repo / ".git" / "refs" / "heads" / "kitty").mkdir(parents=True, exist_ok=True)
    (repo / ".git" / "refs" / "heads" / "kitty" / "mission-fx-lane-b").write_text("1" * 40 + "\n", encoding="utf-8")

    def _unreadable(*_args: object, **_kwargs: object) -> frozenset[str]:
        raise GitProbeError("bad object")

    monkeypatch.setattr(move_task_module, "_mt_lane_window_paths", _unreadable)
    with pytest.raises(ActionContextError) as refused:
        move_task_module._mt_require_implementation_evidence(_absent_branch_state(repo))

    message = str(refused.value)
    assert refused.value.code == "IMPLEMENTATION_UNREADABLE"
    assert "could not be diffed" in message
    assert "no lane of this Mission has a branch here" not in message
