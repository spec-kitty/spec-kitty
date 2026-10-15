"""Workflow runtime integration tests (FR-013, FR-014, FR-015, Scenario 3, AC-4).

ATDD anchors
------------
* Scenario 3: ``test_non_default_workflow_id_produces_extra_design_review_step``
  covers: Scenario 3, AC-4 — expected GREEN at: WP11 final commit
* FR-015: ``test_unknown_workflow_id_in_meta_json_hard_fails``
  covers: Scenario 3, FR-015 — expected GREEN at: WP11 final commit
* NEW-2: ``test_mission_without_workflow_id_uses_software_dev_default``
  covers: FR-013 — expected GREEN at: WP11 final commit
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]



@pytest.fixture
def fixture_mission_with_workflow_id(tmp_path: Path) -> Path:
    """Scaffold a mission with meta.json::workflow_id = our-team-design-first."""
    mission_dir = tmp_path / "kitty-specs" / "demo-mission-01ABCDEF"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({
        "mission_id": "01ABCDEF000000000000000000",
        "mission_slug": "demo-mission",
        "mission_number": None,
        "friendly_name": "Demo",
        "workflow_id": "our-team-design-first",
    }))
    return mission_dir


def test_non_default_workflow_id_produces_extra_design_review_step(
    fixture_mission_with_workflow_id: Path,
) -> None:
    """Scenario 3: resolve_next_workflow_action returns commands per the new sequence."""
    from runtime.next._internal_runtime.planner import resolve_next_workflow_action

    # Assume the mission is at action=plan; expected next=design-review
    result = resolve_next_workflow_action(
        mission_dir=fixture_mission_with_workflow_id,
        current_action="plan",
    )
    assert result.next_action == "design-review"


def test_fixture_mission_with_workflow_id_produces_documented_step_diff(
    fixture_mission_with_workflow_id: Path,
) -> None:
    """AC-4: documented step diff from default."""
    from runtime.next._internal_runtime.planner import resolve_next_workflow_action

    # default would be tasks; with our-team-design-first, plan -> design-review -> tasks
    result_with_id = resolve_next_workflow_action(
        mission_dir=fixture_mission_with_workflow_id, current_action="plan",
    )
    assert result_with_id.next_action == "design-review", (
        "Expected non-default workflow to insert design-review between plan and tasks"
    )


def test_mission_without_workflow_id_uses_software_dev_default(tmp_path: Path) -> None:
    """NEW-2 permanent default: pre-Slice-F missions work unchanged."""
    mission_dir = tmp_path / "kitty-specs" / "legacy-mission-01XXXXXX"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({
        "mission_id": "01XXXXXX000000000000000000",
        "mission_slug": "legacy",
        "mission_number": None,
    }))  # no workflow_id
    from runtime.next._internal_runtime.planner import resolve_next_workflow_action

    result = resolve_next_workflow_action(mission_dir=mission_dir, current_action="plan")
    assert result.next_action == "tasks"  # byte-stable default


def test_unknown_workflow_id_in_meta_json_hard_fails(tmp_path: Path) -> None:
    """FR-015 binding: no silent fallback."""
    mission_dir = tmp_path / "kitty-specs" / "broken-mission-01ZZZZZZ"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({
        "mission_id": "01ZZZZZZ000000000000000000",
        "mission_slug": "broken",
        "mission_number": None,
        "workflow_id": "does-not-exist",
    }))
    from runtime.next._internal_runtime.planner import resolve_next_workflow_action
    from runtime.next._internal_runtime.workflow_registry import UnknownWorkflowError

    with pytest.raises(UnknownWorkflowError):
        resolve_next_workflow_action(mission_dir=mission_dir, current_action="plan")


def test_project_override_workflow_id_drives_next_action(tmp_path: Path) -> None:
    """Issue #682: project-authored `.kittify` workflow sequences are runtime-owned."""
    workflow_dir = tmp_path / ".kittify" / "overrides" / "workflows"
    workflow_dir.mkdir(parents=True)
    (workflow_dir / "solo-fast.yaml").write_text(
        """
workflow_id: solo-fast
description: Project override that skips review.
version: 1
initial: specify
actions:
  - action_name: specify
    description: Create a mission specification
    next: [plan]
  - action_name: plan
    description: Create an implementation plan
    next: [implement]
  - action_name: implement
    description: Implement directly
    next: [accept]
  - action_name: accept
    description: Accept without review
    terminal: true
""".lstrip(),
        encoding="utf-8",
    )
    mission_dir = tmp_path / "kitty-specs" / "solo-fast-mission-01YYY"
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({
        "mission_id": "01YYY000000000000000000000",
        "mission_slug": "solo-fast-mission",
        "mission_number": None,
        "workflow_id": "solo-fast",
    }))

    from runtime.next._internal_runtime.planner import resolve_next_workflow_action
    from runtime.next._internal_runtime.workflow_registry import get_workflow

    get_workflow.cache_clear()
    result = resolve_next_workflow_action(mission_dir=mission_dir, current_action="implement")

    assert result.workflow_id == "solo-fast"
    assert result.next_action == "accept"
