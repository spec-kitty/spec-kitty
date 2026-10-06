"""Acceptance coverage for canonical WP-task prompt placement (#5255)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime import MissionTopology
from runtime.next.decision import Decision, DecisionKind, _build_prompt_or_error, decide_next
from runtime.next.runtime_bridge import decide_next_via_runtime, query_current_state
from runtime.next.runtime_bridge_decision_mapping import _materialize_decision
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
_MALFORMED_WP_TASK = "---\nwork_package_id: [unterminated\n---\n"
_WP_PROMPT_START = "=" * 78 + "\n  WORK PACKAGE PROMPT BEGINS\n" + "=" * 78 + "\n\n"
_WP_PROMPT_END = "\n\n" + "=" * 78 + "\n  WORK PACKAGE PROMPT ENDS\n" + "=" * 78


def _scaffold_lanes_with_coord_mission(
    tmp_path: Path,
    *,
    lane: str,
    additional_wps: dict[str, str] | None = None,
) -> tuple[Path, str, Path, Path]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    mission_slug = f"issue-5255-{lane.replace('_', '-')}"
    wps = {"WP01": lane}
    if additional_wps:
        wps.update(additional_wps)
    primary_dir, coordination_dir = scaffold_coord_software_dev(
        repo_root,
        mission_slug,
        MissionTopology.LANES_WITH_COORD,
        wps=wps,
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

    from runtime.next.runtime_bridge_decision_mapping import _map_wp_step_decision

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


def test_status_facade_exports_frontmatter_error() -> None:
    """Runtime consumers resolve task parse failures through the status facade."""
    from specify_cli.frontmatter import FrontmatterError as FrontmatterModuleError
    from specify_cli.status import FrontmatterError as StatusFacadeError

    assert StatusFacadeError is FrontmatterModuleError


@pytest.mark.parametrize("task_problem", ["missing", "unreadable", "malformed"])
def test_unavailable_primary_task_blocks_with_actionable_reason(
    tmp_path: Path,
    task_problem: str,
) -> None:
    """A missing or unreadable canonical task never becomes a placeholder step."""
    repo_root, mission_slug, primary_dir, coordination_dir = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    task_file = primary_dir / "tasks" / "WP01.md"
    task_file.unlink()
    if task_problem == "unreadable":
        task_file.mkdir()
    elif task_problem == "malformed":
        task_file.write_text(_MALFORMED_WP_TASK, encoding="utf-8")

    prompt_file, prompt_error, _prompt_error_code = _build_prompt_or_error(
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
@pytest.mark.parametrize("task_problem", ["missing", "unreadable", "malformed"])
def test_unavailable_primary_task_blocks_public_runtime_route_after_implement(
    tmp_path: Path,
    route: str,
    task_problem: str,
) -> None:
    """An active WP with a lost task blocks before composition advances the run."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    task_file = primary_dir / "tasks" / "WP01.md"
    task_file.unlink()
    if task_problem == "unreadable":
        task_file.mkdir()
    elif task_problem == "malformed":
        task_file.write_text(_MALFORMED_WP_TASK, encoding="utf-8")

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


def test_missing_done_task_blocks_active_wp_to_preserve_board_integrity(tmp_path: Path) -> None:
    """A missing done task cannot vanish from file-derived board totals."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(
        tmp_path,
        lane="planned",
        additional_wps={"WP02": "done"},
    )
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    task_file = primary_dir / "tasks" / "WP02.md"
    task_file.unlink()
    decision = decide_next_via_runtime("codex", mission_slug, "success", repo_root)

    assert decision.kind == DecisionKind.blocked
    assert decision.action is None
    assert decision.wp_id is None
    assert decision.prompt_file is None
    assert decision.reason is not None
    assert str(task_file) in decision.reason
    assert "restore" in decision.reason.lower() or "regenerate" in decision.reason.lower()


def test_missing_canceled_task_does_not_block_active_wp(tmp_path: Path) -> None:
    """Canceling is how a deliberately removed WP is retired; it must not brick the Mission."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(
        tmp_path,
        lane="planned",
        additional_wps={"WP02": "canceled"},
    )
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    (primary_dir / "tasks" / "WP02.md").unlink()
    decision = decide_next_via_runtime("codex", mission_slug, "success", repo_root)

    _assert_task_prompt(decision, action="implement", repo_root=repo_root, mission_slug=mission_slug)


def test_missing_task_recovery_offers_cancel_for_intentional_removal(tmp_path: Path) -> None:
    """The blocked reason names the cancel route, not only restore/regenerate."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(
        tmp_path,
        lane="planned",
        additional_wps={"WP02": "done"},
    )
    (primary_dir / "tasks" / "WP02.md").unlink()

    decision = query_current_state("codex", mission_slug, repo_root)

    assert decision.reason is not None
    assert f"move-task WP02 --to canceled --mission {mission_slug}" in decision.reason


def test_query_blocks_when_finalized_status_wp_task_is_missing(tmp_path: Path) -> None:
    """Query mode must not report file-derived totals that omit a status WP."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(
        tmp_path,
        lane="planned",
        additional_wps={"WP02": "done"},
    )
    task_file = primary_dir / "tasks" / "WP02.md"
    task_file.unlink()

    decision = query_current_state("codex", mission_slug, repo_root)

    assert decision.kind == DecisionKind.query
    assert decision.mission_state == "blocked"
    assert decision.preview_step is None
    assert decision.progress is None
    assert decision.reason is not None
    assert str(task_file) in decision.reason
    assert "WP02" in decision.reason
    assert "restore" in decision.reason.lower() or "regenerate" in decision.reason.lower()


@pytest.mark.parametrize("route", ["bridge", "decision_api"], ids=["runtime-bridge", "decision-api"])
def test_wp_prompt_blocks_when_primary_task_declares_another_wp_id(
    tmp_path: Path,
    route: str,
) -> None:
    """A filename match cannot authorize embedding another WP's authored task."""
    repo_root, mission_slug, primary_dir, _ = _scaffold_lanes_with_coord_mission(tmp_path, lane="planned")
    advance_to_step(repo_root, mission_slug, "software-dev", "implement")

    task_file = primary_dir / "tasks" / "WP01.md"
    wrong_identity_task = _EXPECTED_WP_TASK.replace(
        "work_package_id: WP01",
        "work_package_id: WP02",
    ).replace("Work Package WP01:", "Work Package WP02:")
    task_file.write_text(wrong_identity_task, encoding="utf-8")

    route_callable = decide_next_via_runtime if route == "bridge" else decide_next
    decision = route_callable("codex", mission_slug, "success", repo_root)

    assert decision.kind == DecisionKind.blocked
    assert decision.action is None
    assert decision.wp_id is None
    assert decision.prompt_file is None
    assert decision.reason is not None
    assert str(task_file) in decision.reason
    assert "expected WP01" in decision.reason
    assert "found WP02" in decision.reason
    assert "restore" in decision.reason.lower() or "regenerate" in decision.reason.lower()
    assert "<subtask-ids>" not in decision.reason
