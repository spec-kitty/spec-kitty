"""Printed completion advice binds reused subtask labels to their owning WP."""

from __future__ import annotations

import json
import shlex
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner
from ulid import ULID

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_transition_core import Emit, _guard_subtasks, decide_transition
from specify_cli.status import InnerStateChanged, Lane, StatusEvent, WPInnerStateDelta, wp_snapshot_state
from specify_cli.status.store import append_annotations_atomic_verified
from tests._support.status_seed import seed_status_event
from tests._support.tasks_transition_request import base_request

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()
_SLUG = "port-completion-01M6FZ0K"


@pytest.mark.parametrize("mission_slug", [_SLUG, None])
def test_refusal_recipes_preserve_available_mission_context(mission_slug: str | None) -> None:
    refusal = _guard_subtasks(base_request(task_id="WP02", unchecked_subtasks=("T001", "T002"), mission_slug=mission_slug))
    assert refusal is not None
    recipes = [shlex.split(line) for line in refusal.error.splitlines() if line.strip().startswith("spec-kitty agent tasks mark-status ")]
    assert recipes
    for argv in recipes:
        if mission_slug is None:
            assert "--mission" not in argv
            assert "None" not in argv
        else:
            assert argv[argv.index("--mission") + 1] == mission_slug


def _write_shared_id_mission(repo: Path, slug: str) -> Path:
    """Two authored WPs with genuinely incomplete event-sourced T001/T002 slots."""
    mission_dir = repo / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01TESTMISSION", "status_phase": "1"}), encoding="utf-8")
    (mission_dir / "tasks.md").write_text("# Tasks\n\n## WP01\nSubtasks: T001, T002\n\n## WP02\nSubtasks: T001, T002\n", encoding="utf-8")
    for wp_id in ("WP01", "WP02"):
        (mission_dir / "tasks" / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\nsubtasks:\n  - T001\n  - T002\n---\n\n# {wp_id}\n", encoding="utf-8"
        )
        seed_status_event(
            mission_dir,
            StatusEvent(
                event_id=str(ULID()),
                mission_slug=slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
                reason="incomplete shared-id fixture",
            ),
        )
        append_annotations_atomic_verified(
            mission_dir,
            [
                InnerStateChanged(
                    event_id=str(ULID()),
                    wp_id=wp_id,
                    at="2026-01-01T00:01:00+00:00",
                    actor="test",
                    delta=WPInnerStateDelta(subtasks={"T001": Lane.IN_PROGRESS, "T002": Lane.IN_PROGRESS}),
                )
            ],
        )
    return mission_dir


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str) -> Iterator[None]:
    del repo_root, mission_slug
    yield


def _run_recipe(repo: Path, slug: str, recipe: str) -> tuple[int, str]:
    """Run the printed command through the actual mark-status app, not a renderer mock."""
    argv = shlex.split(recipe)
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(repo, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = runner.invoke(app, [*argv[3:], "--json", "--no-auto-commit"])
    return result.exit_code, result.output


def test_emitted_recipes_clear_the_event_sourced_review_gate(tmp_path: Path) -> None:
    """Actual CLI writes clear the actual transition decision, without touching WP01.

    This proves the subtask gate and its transition plan, not a full Git/lane
    materialization workflow (that consumer is covered by the existing #2684 test).
    """
    slug = "7108-shared-ids"
    mission_dir = _write_shared_id_mission(tmp_path, slug)
    req = base_request(task_id="WP02", mission_slug=slug, feature_dir=mission_dir, unchecked_subtasks=())
    # The legacy tuple is empty: this refusal must come from the real snapshot.
    refusal = _guard_subtasks(req)
    assert refusal is not None
    recipes = [line.strip() for line in refusal.error.splitlines() if line.strip().startswith("spec-kitty agent tasks mark-status ")]
    assert recipes
    sibling_before = wp_snapshot_state(mission_dir, "WP01")

    for recipe in recipes:
        exit_code, output = _run_recipe(tmp_path, slug, recipe)
        assert exit_code == 0, output

    state = wp_snapshot_state(mission_dir, "WP02")
    assert state is not None
    assert state["subtasks"] == {"T001": "done", "T002": "done"}
    assert wp_snapshot_state(mission_dir, "WP01") == sibling_before
    transition = decide_transition(req)
    assert isinstance(transition, Emit)
    assert transition.plan.canonical_lane == "for_review"
