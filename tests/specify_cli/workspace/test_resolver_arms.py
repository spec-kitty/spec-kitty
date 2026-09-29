"""Focused tests for the ``_resolve_workspace_for_wp_impl`` per-arm helpers.

WP01 campsite split (single-branch-topology-honesty-01M3M22V, T002/T003):
``_resolve_workspace_for_wp_impl`` was split into one private helper per
resolution arm (``_resolve_planning_artifact_arm``, ``_resolve_context_arm``,
``_resolve_planning_lane_arm``, ``_resolve_code_lane_arm``). These tests pin
each helper directly against a minimal fixture, reusing the mission-seeding
helpers from ``tests/runtime/test_workspace_context_unit.py`` where possible.
The end-to-end precedence itself stays pinned by
``tests/runtime/test_workspace_context_unit.py`` (unmodified by this WP).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.models import ExecutionLane
from specify_cli.ownership.models import WorkProductKind
from specify_cli.workspace.context import (
    WorkspaceContext,
    _resolve_code_lane_arm,
    _resolve_context_arm,
    _resolve_planning_artifact_arm,
    _resolve_planning_lane_arm,
    clear_workspace_resolution_caches,
    get_normalized_wp,
    save_context,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_SLUG = "001-feature"


@pytest.fixture
def kittify_project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def reset_workspace_caches() -> None:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _seed_mission(repo_root: Path, mission_slug: str = MISSION_SLUG) -> Path:
    feature_dir = repo_root / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    return feature_dir


def _write_wp(
    tasks_dir: Path,
    wp_id: str,
    title: str,
    body: str,
    *,
    execution_mode: str | None = None,
    owned_files: list[str] | None = None,
) -> Path:
    lines = [
        "---",
        f"work_package_id: {wp_id}",
        f"title: {title}",
        "dependencies: []",
    ]
    if execution_mode is not None:
        lines.append(f"execution_mode: {execution_mode}")
    if owned_files:
        lines.append("owned_files:")
        lines.extend(f"- {owned_file}" for owned_file in owned_files)
    lines.extend(["---", "", body, ""])
    wp_path = tasks_dir / f"{wp_id}-test.md"
    wp_path.write_text("\n".join(lines), encoding="utf-8")
    return wp_path


def _lane(lane_id: str, wp_ids: tuple[str, ...]) -> ExecutionLane:
    return ExecutionLane(
        lane_id=lane_id,
        wp_ids=wp_ids,
        write_scope=("src/**",),
        predicted_surfaces=("core",),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _context(*, wp_id: str = "WP02") -> WorkspaceContext:
    return WorkspaceContext(
        wp_id=wp_id,
        mission_slug=MISSION_SLUG,
        worktree_path=f".worktrees/{MISSION_SLUG}-lane-a",
        branch_name=f"kitty/mission-{MISSION_SLUG}-lane-a",
        base_branch=f"kitty/mission-{MISSION_SLUG}",
        base_commit="abc123",
        dependencies=["WP01"],
        created_at="2026-01-25T12:00:00Z",
        created_by="implement-command-lane",
        vcs_backend="git",
        lane_id="lane-a",
        lane_wp_ids=["WP01", "WP02"],
        current_wp=wp_id,
    )


class TestPlanningArtifactArm:
    def test_returns_repo_root_workspace_for_planning_artifact(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP05",
            "Docs",
            "Refresh kitty-specs/001-feature/spec.md.",
            execution_mode="planning_artifact",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP05")

        resolved = _resolve_planning_artifact_arm(kittify_project, MISSION_SLUG, "WP05", normalized_wp, WorkProductKind.PLANNING_ARTIFACT)

        assert resolved is not None
        assert resolved.resolution_kind == "repo_root"
        assert resolved.worktree_path == kittify_project
        assert resolved.branch_name is None
        assert resolved.lane_id == PLANNING_LANE_ID
        assert resolved.lane_wp_ids == []

    def test_returns_none_for_code_change(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP02",
            "Code change",
            "Update src/a.py.",
            execution_mode="code_change",
            owned_files=["src/a.py"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP02")

        resolved = _resolve_planning_artifact_arm(kittify_project, MISSION_SLUG, "WP02", normalized_wp, WorkProductKind.CODE_CHANGE)

        assert resolved is None


class TestContextArm:
    def test_returns_persisted_lane_workspace(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP02",
            "Code change",
            "Update src/a.py.",
            execution_mode="code_change",
            owned_files=["src/a.py"],
        )
        save_context(kittify_project, _context(wp_id="WP02"))
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP02")

        resolved = _resolve_context_arm(kittify_project, MISSION_SLUG, "WP02", normalized_wp, WorkProductKind.CODE_CHANGE)

        assert resolved is not None
        assert resolved.resolution_kind == "lane_workspace"
        assert resolved.worktree_path == kittify_project / ".worktrees" / f"{MISSION_SLUG}-lane-a"
        assert resolved.branch_name == f"kitty/mission-{MISSION_SLUG}-lane-a"
        assert resolved.lane_id == "lane-a"
        assert resolved.lane_wp_ids == ["WP01", "WP02"]

    def test_returns_none_when_no_context_persisted(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP02",
            "Code change",
            "Update src/a.py.",
            execution_mode="code_change",
            owned_files=["src/a.py"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP02")

        resolved = _resolve_context_arm(kittify_project, MISSION_SLUG, "WP02", normalized_wp, WorkProductKind.CODE_CHANGE)

        assert resolved is None


class TestPlanningLaneArm:
    def test_returns_repo_root_workspace_for_planning_lane(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP05",
            "Docs",
            "Refresh kitty-specs/001-feature/spec.md.",
            execution_mode="planning_artifact",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP05")
        lane = _lane(PLANNING_LANE_ID, ("WP05",))

        resolved = _resolve_planning_lane_arm(kittify_project, MISSION_SLUG, "WP05", normalized_wp, WorkProductKind.PLANNING_ARTIFACT, lane, "main")

        assert resolved is not None
        assert resolved.resolution_kind == "repo_root"
        assert resolved.worktree_path == kittify_project
        assert resolved.branch_name == "main"
        assert resolved.lane_id == PLANNING_LANE_ID
        assert resolved.lane_wp_ids == ["WP05"]

    def test_returns_none_for_non_planning_lane(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP02",
            "Code change",
            "Update src/a.py.",
            execution_mode="code_change",
            owned_files=["src/a.py"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP02")
        lane = _lane("lane-a", ("WP01", "WP02"))

        resolved = _resolve_planning_lane_arm(kittify_project, MISSION_SLUG, "WP02", normalized_wp, WorkProductKind.CODE_CHANGE, lane, "main")

        assert resolved is None


class TestCodeLaneArm:
    def test_returns_lane_workspace(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        _write_wp(
            feature_dir / "tasks",
            "WP02",
            "Code change",
            "Update src/a.py.",
            execution_mode="code_change",
            owned_files=["src/a.py"],
        )
        normalized_wp = get_normalized_wp(kittify_project, MISSION_SLUG, "WP02")
        lane = _lane("lane-a", ("WP01", "WP02"))

        resolved = _resolve_code_lane_arm(kittify_project, MISSION_SLUG, "WP02", normalized_wp, WorkProductKind.CODE_CHANGE, lane)

        assert resolved.resolution_kind == "lane_workspace"
        assert resolved.workspace_name == f"{MISSION_SLUG}-lane-a"
        assert resolved.worktree_path == kittify_project / ".worktrees" / f"{MISSION_SLUG}-lane-a"
        assert resolved.branch_name == f"kitty/mission-{MISSION_SLUG}-lane-a"
        assert resolved.lane_id == "lane-a"
        assert resolved.lane_wp_ids == ["WP01", "WP02"]
        assert resolved.context is None
