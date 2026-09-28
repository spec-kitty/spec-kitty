"""Acceptance coverage for canonical WP-task prompt placement (#5255)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from runtime.next.decision import Decision, DecisionKind, _build_prompt_or_error, decide_next
from runtime.next.runtime_bridge import _materialize_decision, decide_next_via_runtime
from runtime.next.runtime_bridge_cores import DecisionEnvelope
from tests.runtime._next_mission_scaffold import (
    advance_to_step,
    commit_all,
    scaffold_coord_software_dev,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_EXPECTED_WP_TASK = """---
work_package_id: WP01
title: WP01 prompt placement acceptance
dependencies: []
subtasks:
  - WP01.1
  - WP01.2
agent_profile: implementer-ivan
role: implementer
---
## Work Package WP01: Prompt placement acceptance

Use the canonical primary task body for the implementation prompt.
"""
_WP_PROMPT_START = "=" * 78 + "\n  WORK PACKAGE PROMPT BEGINS\n" + "=" * 78 + "\n\n"
_WP_PROMPT_END = "\n\n" + "=" * 78 + "\n  WORK PACKAGE PROMPT ENDS\n" + "=" * 78


def _scaffold_lanes_with_coord_mission(
    tmp_path: Path,
    *,
    lane: str,
) -> tuple[Path, str, Path, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    mission_slug = f"issue-5255-{lane.replace('_', '-')}"
    primary_dir, coordination_dir = scaffold_coord_software_dev(
        repo_root,
        mission_slug,
        MissionTopology.LANES_WITH_COORD,
        wps={"WP01": lane},
    )
    task_file = primary_dir / "tasks" / "WP01.md"
    task_file.write_text(_EXPECTED_WP_TASK, encoding="utf-8")
    commit_all(repo_root, "test: seed exact WP01 prompt task")

    mission_meta = json.loads((primary_dir / "meta.json").read_text(encoding="utf-8"))
    assert mission_meta["topology"] == MissionTopology.LANES_WITH_COORD.value
    assert task_file.is_file()
    assert not (coordination_dir / "tasks").exists()
    assert (coordination_dir / "status.events.jsonl").is_file()

    return repo_root, mission_slug, primary_dir, coordination_dir


def _assert_task_prompt(decision: Decision, *, action: str, repo_root: Path, mission_slug: str) -> str:
    assert decision.kind == DecisionKind.step
    assert decision.action == action
    assert decision.wp_id == "WP01"
    assert decision.workspace_path is not None
    assert ".worktrees" in decision.workspace_path
    assert "lane-a" in decision.workspace_path
    assert decision.prompt_file is not None

    prompt = Path(decision.prompt_file).read_text(encoding="utf-8")
    body = prompt.partition(_WP_PROMPT_START)[2].partition(_WP_PROMPT_END)[0]
    assert body == _EXPECTED_WP_TASK
    assert "agent_profile: implementer-ivan" in body
    assert "subtasks:\n  - WP01.1\n  - WP01.2" in body
    assert "<subtask-ids>" not in prompt
    assert "WP file not found" not in prompt
    assert f"Mission: {mission_slug}" in prompt
    assert str(repo_root / ".worktrees") in decision.workspace_path

    if action == "implement":
        assert "mark-status WP01.1 WP01.2 --status done" in prompt
    else:
        assert "REVIEW COMMANDS:" in prompt
        assert "APPROVE:" in prompt
    return prompt


def test_fresh_runtime_step_uses_primary_task_after_tasks_phase(tmp_path: Path) -> None:
    """The runtime-issued implement step reads its task from WORK_PACKAGE_TASK."""
    repo_root, mission_slug, _, _ = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    decision = decide_next_via_runtime("codex", mission_slug, "success", repo_root)

    _assert_task_prompt(decision, action="implement", repo_root=repo_root, mission_slug=mission_slug)


def test_fresh_step_mapping_uses_primary_task_body(tmp_path: Path) -> None:
    """The DAG materialization route also reads the primary WP task."""
    repo_root, mission_slug, _, coordination_dir = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")

    from runtime.next.runtime_bridge import _map_wp_step_decision

    decision = _map_wp_step_decision(
        step_id="implement",
        agent="codex",
        mission_slug=mission_slug,
        mission_type="software-dev",
        repo_root=repo_root,
        feature_dir=coordination_dir,
        timestamp="2026-09-28T00:00:00+00:00",
        progress=None,
        origin={},
        run_id="run-5255",
    )

    _assert_task_prompt(decision, action="implement", repo_root=repo_root, mission_slug=mission_slug)


def test_held_wp_iteration_uses_primary_task_and_review_prompt(tmp_path: Path) -> None:
    """The current-step route keeps task lookup separate from coordination status."""
    repo_root, mission_slug, _, _ = _scaffold_lanes_with_coord_mission(tmp_path, lane="for_review")
    advance_to_step(repo_root, mission_slug, "software-dev", "review")

    decision = decide_next_via_runtime("codex", mission_slug, "success", repo_root)

    _assert_task_prompt(decision, action="review", repo_root=repo_root, mission_slug=mission_slug)


@pytest.mark.parametrize("unreadable", [False, True], ids=["missing", "unreadable"])
def test_unavailable_primary_task_blocks_with_actionable_reason(
    tmp_path: Path,
    unreadable: bool,
) -> None:
    """A missing or unreadable canonical task never becomes a placeholder step."""
    repo_root, mission_slug, primary_dir, coordination_dir = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    task_file = primary_dir / "tasks" / "WP01.md"
    task_file.unlink()
    if unreadable:
        task_file.mkdir()

    prompt_file, prompt_error = _build_prompt_or_error(
        action="implement",
        feature_dir=coordination_dir,
        mission_slug=mission_slug,
        wp_id="WP01",
        agent="codex",
        repo_root=repo_root,
        mission_type="software-dev",
    )
    decision = _materialize_decision(
        DecisionEnvelope(
            kind=DecisionKind.step,
            agent="codex",
            mission_slug=mission_slug,
            mission="software-dev",
            mission_state="implement",
            timestamp="2026-09-28T00:00:00+00:00",
            action="implement",
            wp_id="WP01",
            prompt_file=prompt_file,
            reason=prompt_error or "no_prompt_template",
        )
    )

    assert decision.kind == DecisionKind.blocked
    assert decision.prompt_file is None
    assert decision.reason is not None
    assert str(primary_dir / "tasks") in decision.reason
    assert "restore" in decision.reason.lower() or "regenerate" in decision.reason.lower()


@pytest.mark.parametrize("route", ["bridge", "decision_api"], ids=["runtime-bridge", "decision-api"])
@pytest.mark.parametrize("unreadable", [False, True], ids=["missing", "unreadable"])
def test_unavailable_primary_task_blocks_public_runtime_route_after_implement(
    tmp_path: Path,
    route: str,
    unreadable: bool,
) -> None:
    """An active WP with a lost task blocks before composition advances the run."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    task_file = primary_dir / "tasks" / "WP01.md"
    task_file.unlink()
    if unreadable:
        task_file.mkdir()

    route_callable = decide_next_via_runtime if route == "bridge" else decide_next
    decision = route_callable("codex", mission_slug, "success", repo_root)

    assert decision.kind == DecisionKind.blocked
    assert decision.action is None
    assert decision.wp_id is None
    assert decision.prompt_file is None
    assert decision.reason is not None
    assert str(task_file) in decision.reason
    assert "restore" in decision.reason.lower() or "regenerate" in decision.reason.lower()
    assert "composition" not in decision.reason.lower()
    assert "<subtask-ids>" not in decision.reason
