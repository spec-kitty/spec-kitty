"""Lane workspace context integrity tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import specify_cli.workspace.context as workspace_context_module

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from specify_cli.workspace.context import (
    WorkspaceContext,
    ActiveWPResolution,
    build_normalized_wp_index,
    build_feature_context_index,
    clear_workspace_resolution_caches,
    find_orphaned_contexts,
    list_contexts,
    load_context,
    resolve_active_wp_for_branch,
    resolve_feature_worktree,
    resolve_workspace_for_wp,
    save_context,
)


pytestmark = [pytest.mark.unit, pytest.mark.fast]

@pytest.fixture
def kittify_project(tmp_path: Path) -> Path:
    (tmp_path / ".kittify" / "workspaces").mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture(autouse=True)
def reset_workspace_caches() -> None:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _lane_manifest(mission_slug: str = "001-feature") -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=f"mission-{mission_slug}",
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id="lane-a",
                wp_ids=("WP01", "WP02"),
                write_scope=("src/**",),
                predicted_surfaces=("core",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at="2026-04-04T10:00:00Z",
        computed_from="test",
    )


def _context(*, current_wp: str = "WP02") -> WorkspaceContext:
    return WorkspaceContext(
        wp_id=current_wp,
        mission_slug="001-feature",
        worktree_path=".worktrees/001-feature-lane-a",
        branch_name="kitty/mission-001-feature-lane-a",
        base_branch="kitty/mission-001-feature",
        base_commit="abc123",
        dependencies=["WP01"],
        created_at="2026-01-25T12:00:00Z",
        created_by="implement-command-lane",
        vcs_backend="git",
        lane_id="lane-a",
        lane_wp_ids=["WP01", "WP02"],
        current_wp=current_wp,
    )


def _seed_mission(repo_root: Path, mission_slug: str = "001-feature") -> Path:
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


def _seed_lane_event(feature_dir: Path, wp_id: str, lane: Lane) -> None:
    seed_status_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane.value}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=lane,
            at="2026-01-25T12:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


class TestOrphanedContext:
    def test_orphaned_context_detected(self, kittify_project: Path) -> None:
        save_context(kittify_project, _context())

        orphaned = find_orphaned_contexts(kittify_project)

        assert len(orphaned) == 1
        assert orphaned[0][0] == "001-feature-lane-a"


class TestCorruptedContext:
    def test_invalid_json_handled(self, kittify_project: Path) -> None:
        context_file = kittify_project / ".kittify" / "workspaces" / "001-feature-lane-a.json"
        context_file.write_text("{invalid json", encoding="utf-8")

        loaded = load_context(kittify_project, "001-feature-lane-a")
        assert loaded is None
        assert list_contexts(kittify_project) == []

    def test_legacy_unknown_base_commit_normalized(self, kittify_project: Path) -> None:
        context_file = kittify_project / ".kittify" / "workspaces" / "001-feature-lane-a.json"
        context_file.write_text(
            """
{
  "wp_id": "WP01",
  "mission_slug": "001-feature",
  "worktree_path": ".worktrees/001-feature-lane-a",
  "branch_name": "kitty/mission-001-feature-lane-a",
  "base_branch": "kitty/mission-001-feature",
  "base_commit": "unknown",
  "dependencies": [],
  "created_at": "2026-01-25T12:00:00Z",
  "created_by": "recovery",
  "vcs_backend": "git",
  "lane_id": "lane-a",
  "lane_wp_ids": ["WP01"],
  "current_wp": "WP01"
}
""".lstrip(),
            encoding="utf-8",
        )

        loaded = load_context(kittify_project, "001-feature-lane-a")

        assert loaded is not None
        assert loaded.base_commit is None


class TestContextIndexAndResolution:
    def test_active_wp_resolution_uses_canonical_status_after_shared_lane_advances(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP01",
            "Previous work",
            "Update src/previous.py.",
            execution_mode="code_change",
            owned_files=["src/previous.py"],
        )
        _write_wp(
            tasks_dir,
            "WP04",
            "Active work",
            "Update src/active.py.",
            execution_mode="code_change",
            owned_files=["src/active.py"],
        )
        save_context(
            kittify_project,
            WorkspaceContext(
                wp_id="WP01",
                mission_slug="001-feature",
                worktree_path=".worktrees/001-feature-lane-a",
                branch_name="kitty/mission-001-feature-lane-a",
                base_branch="kitty/mission-001-feature",
                base_commit="abc123",
                dependencies=[],
                created_at="2026-01-25T12:00:00Z",
                created_by="implement-command-lane",
                vcs_backend="git",
                lane_id="lane-a",
                lane_wp_ids=["WP01", "WP04"],
                current_wp="WP01",
            ),
        )
        _seed_lane_event(feature_dir, "WP01", Lane.DONE)
        _seed_lane_event(feature_dir, "WP04", Lane.IN_PROGRESS)

        resolved = resolve_active_wp_for_branch(
            kittify_project,
            "kitty/mission-001-feature-lane-a",
        )

        assert resolved == ActiveWPResolution(
            mission_slug="001-feature",
            wp_id="WP04",
            owned_files=["src/active.py"],
            lane_id="lane-a",
            branch_name="kitty/mission-001-feature-lane-a",
            context_source="canonical_status",
            diagnostic_code=None,
            diagnostic_message=None,
            warnings=[
                "ACTIVE_WP_CONTEXT_STALE: workspace context current_wp=WP01, canonical active_wp=WP04; lane_id=lane-a"
            ],
        )

    def test_active_wp_resolution_diagnoses_ambiguous_status_context(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(tasks_dir, "WP01", "First", "Update src/a.py.", execution_mode="code_change", owned_files=["src/a.py"])
        _write_wp(tasks_dir, "WP02", "Second", "Update src/b.py.", execution_mode="code_change", owned_files=["src/b.py"])
        save_context(kittify_project, _context(current_wp="WP01"))
        _seed_lane_event(feature_dir, "WP01", Lane.IN_PROGRESS)
        _seed_lane_event(feature_dir, "WP02", Lane.IN_PROGRESS)

        resolved = resolve_active_wp_for_branch(
            kittify_project,
            "kitty/mission-001-feature-lane-a",
        )

        assert resolved.wp_id is None
        assert resolved.owned_files == []
        assert resolved.diagnostic_code == "ACTIVE_WP_CONTEXT_AMBIGUOUS"
        assert "active candidates: WP01, WP02" in (resolved.diagnostic_message or "")

    def test_build_normalized_wp_index_caches_inferred_execution_mode(self, kittify_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP03",
            "Planning artifact",
            "Update kitty-specs/001-feature/spec.md and plan.md.",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )

        calls = 0
        original = workspace_context_module.infer_execution_mode

        def tracking_infer(wp_content: str, wp_files: list[str]):
            nonlocal calls
            calls += 1
            return original(wp_content, wp_files)

        monkeypatch.setattr(workspace_context_module, "infer_execution_mode", tracking_infer)

        first = build_normalized_wp_index(kittify_project, "001-feature")
        second = build_normalized_wp_index(kittify_project, "001-feature")

        assert calls == 1
        assert first["WP03"].mode_source == "inferred_legacy"
        assert second["WP03"].metadata.execution_mode == "planning_artifact"

    def test_build_normalized_wp_index_refreshes_when_wp_files_change(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"

        first = build_normalized_wp_index(kittify_project, "001-feature")
        assert first == {}

        _write_wp(
            tasks_dir,
            "WP03",
            "Planning artifact",
            "Update kitty-specs/001-feature/spec.md and plan.md.",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )

        refreshed = build_normalized_wp_index(kittify_project, "001-feature")

        assert refreshed["WP03"].metadata.execution_mode == "planning_artifact"

    def test_build_normalized_wp_index_accepts_unrelated_legacy_unknown_base_commit(
        self, kittify_project: Path
    ) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        (tasks_dir / "WP01-legacy-base.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Legacy Base\nbase_commit: unknown\n---\n\nUpdate src/legacy.py.\n",
            encoding="utf-8",
        )
        _write_wp(
            tasks_dir,
            "WP04",
            "Current work",
            "Update src/current.py.",
            execution_mode="code_change",
            owned_files=["src/current.py"],
        )

        index = build_normalized_wp_index(kittify_project, "001-feature")

        assert index["WP01"].metadata.base_commit is None
        assert index["WP04"].metadata.owned_files == ["src/current.py"]

    def test_save_context_does_not_drop_normalized_wp_cache(self, kittify_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP03",
            "Planning artifact",
            "Update kitty-specs/001-feature/spec.md and plan.md.",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )

        calls = 0
        original = workspace_context_module.infer_execution_mode

        def tracking_infer(wp_content: str, wp_files: list[str]):
            nonlocal calls
            calls += 1
            return original(wp_content, wp_files)

        monkeypatch.setattr(workspace_context_module, "infer_execution_mode", tracking_infer)

        first = build_normalized_wp_index(kittify_project, "001-feature")
        save_context(kittify_project, _context())
        second = build_normalized_wp_index(kittify_project, "001-feature")

        assert calls == 1
        assert first["WP03"].metadata.execution_mode == second["WP03"].metadata.execution_mode == "planning_artifact"

    def test_build_feature_context_index_expands_lane_membership(self, kittify_project: Path) -> None:
        save_context(kittify_project, _context())

        index = build_feature_context_index(kittify_project, "001-feature")

        assert set(index) == {"WP01", "WP02"}
        assert index["WP01"].lane_id == "lane-a"
        assert index["WP02"].lane_wp_ids == ["WP01", "WP02"]

    def test_build_feature_context_index_cache_invalidated_on_save(self, kittify_project: Path) -> None:
        save_context(kittify_project, _context(current_wp="WP01"))
        initial = build_feature_context_index(kittify_project, "001-feature")
        assert set(initial) == {"WP01", "WP02"}

        second = WorkspaceContext(
            wp_id="WP03",
            mission_slug="001-feature",
            worktree_path=".worktrees/001-feature-lane-b",
            branch_name="kitty/mission-001-feature-lane-b",
            base_branch="kitty/mission-001-feature",
            base_commit="def456",
            dependencies=[],
            created_at="2026-01-25T12:02:00Z",
            created_by="implement-command-lane",
            vcs_backend="git",
            lane_id="lane-b",
            lane_wp_ids=["WP03"],
            current_wp="WP03",
        )
        save_context(kittify_project, second)

        refreshed = build_feature_context_index(kittify_project, "001-feature")
        assert set(refreshed) == {"WP01", "WP02", "WP03"}

    def test_resolve_feature_worktree_prefers_context_backed_workspace(self, kittify_project: Path) -> None:
        worktree = kittify_project / ".worktrees" / "001-feature-lane-a"
        worktree.mkdir(parents=True, exist_ok=True)
        save_context(kittify_project, _context())

        resolved = resolve_feature_worktree(kittify_project, "001-feature")

        assert resolved == worktree

    def test_resolve_feature_worktree_is_deterministic_with_multiple_contexts(self, kittify_project: Path) -> None:
        worktree_a = kittify_project / ".worktrees" / "001-feature-lane-a"
        worktree_b = kittify_project / ".worktrees" / "001-feature-lane-b"
        worktree_a.mkdir(parents=True, exist_ok=True)
        worktree_b.mkdir(parents=True, exist_ok=True)

        save_context(
            kittify_project,
            WorkspaceContext(
                wp_id="WP03",
                mission_slug="001-feature",
                worktree_path=".worktrees/001-feature-lane-b",
                branch_name="kitty/mission-001-feature-lane-b",
                base_branch="kitty/mission-001-feature",
                base_commit="def456",
                dependencies=[],
                created_at="2026-01-25T12:02:00Z",
                created_by="implement-command-lane",
                vcs_backend="git",
                lane_id="lane-b",
                lane_wp_ids=["WP03"],
                current_wp="WP03",
            ),
        )
        save_context(kittify_project, _context())

        resolved = resolve_feature_worktree(kittify_project, "001-feature")

        assert resolved == worktree_a

    def test_resolve_feature_worktree_falls_back_to_lane_manifest(self, kittify_project: Path) -> None:
        feature_dir = kittify_project / "kitty-specs" / "001-feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        write_lanes_json(feature_dir, _lane_manifest())

        lane_worktree = kittify_project / ".worktrees" / "001-feature-lane-a"
        lane_worktree.mkdir(parents=True, exist_ok=True)

        resolved = resolve_feature_worktree(kittify_project, "001-feature")

        assert resolved == lane_worktree

    def test_resolve_feature_worktree_returns_none_without_lane_manifest(self, kittify_project: Path) -> None:
        assert resolve_feature_worktree(kittify_project, "001-feature") is None

    def test_resolve_workspace_for_wp_uses_lane_manifest(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP02",
            "Code change",
            "Update src/specify_cli/workspace_context.py and tests/runtime/test_workspace_context_unit.py.",
            execution_mode="code_change",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        write_lanes_json(feature_dir, _lane_manifest())

        resolved = resolve_workspace_for_wp(kittify_project, "001-feature", "WP02")

        assert resolved.execution_mode == "code_change"
        assert resolved.mode_source == "frontmatter"
        assert resolved.resolution_kind == "lane_workspace"
        assert resolved.workspace_name == "001-feature-lane-a"
        assert resolved.branch_name == "kitty/mission-001-feature-lane-a"
        assert resolved.lane_id == "lane-a"
        assert resolved.lane_wp_ids == ["WP01", "WP02"]

    def test_resolve_workspace_for_wp_returns_repo_root_for_inferred_planning_artifact(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP05",
            "Documentation updates",
            "Refresh kitty-specs/001-feature/spec.md and docs/index.md to match the mission contract.",
            owned_files=["kitty-specs/001-feature/spec.md"],
        )

        resolved = resolve_workspace_for_wp(kittify_project, "001-feature", "WP05")

        assert resolved.execution_mode == "planning_artifact"
        assert resolved.mode_source == "inferred_legacy"
        assert resolved.resolution_kind == "repo_root"
        assert resolved.worktree_path == kittify_project
        assert resolved.branch_name is None
        assert resolved.lane_id == "lane-planning"
        assert resolved.lane_wp_ids == []

    def test_resolve_workspace_for_wp_is_deterministic_across_working_directories(self, kittify_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP02",
            "Code change",
            "Update src/specify_cli/workspace_context.py.",
            execution_mode="code_change",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        write_lanes_json(feature_dir, _lane_manifest())

        dir_a = kittify_project / "subdir-a"
        dir_b = kittify_project / "subdir-b"
        dir_a.mkdir()
        dir_b.mkdir()

        monkeypatch.chdir(dir_a)
        first = resolve_workspace_for_wp(kittify_project, "001-feature", "WP02")
        monkeypatch.chdir(dir_b)
        second = resolve_workspace_for_wp(kittify_project, "001-feature", "WP02")

        assert first.resolution_kind == second.resolution_kind == "lane_workspace"
        assert first.worktree_path == second.worktree_path == (kittify_project / ".worktrees" / "001-feature-lane-a")

    def test_resolve_workspace_for_wp_errors_when_wp_not_in_manifest(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP99",
            "Missing lane",
            "Update src/specify_cli/workspace_context.py.",
            execution_mode="code_change",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        write_lanes_json(feature_dir, _lane_manifest())

        with pytest.raises(ValueError, match="not assigned to any lane"):
            resolve_workspace_for_wp(kittify_project, "001-feature", "WP99")

    def test_resolve_workspace_for_wp_ignores_unrelated_invalid_wp(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP02",
            "Code change",
            "Update src/specify_cli/workspace_context.py.",
            execution_mode="code_change",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        _write_wp(
            tasks_dir,
            "WP09",
            "Broken work package",
            "Legacy body.",
            execution_mode="totally-invalid-mode",
            owned_files=["src/specify_cli/other.py"],
        )
        write_lanes_json(feature_dir, _lane_manifest())

        resolved = resolve_workspace_for_wp(kittify_project, "001-feature", "WP02")

        assert resolved.execution_mode == "code_change"
        assert resolved.workspace_name == "001-feature-lane-a"

    def test_resolve_workspace_for_wp_ignores_unrelated_malformed_frontmatter(self, kittify_project: Path) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP02",
            "Code change",
            "Update src/specify_cli/workspace_context.py.",
            execution_mode="code_change",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        (tasks_dir / "WP09-bad.md").write_text("---\nwork_package_id: WP09\n: bad\n---\n", encoding="utf-8")
        write_lanes_json(feature_dir, _lane_manifest())

        resolved = resolve_workspace_for_wp(kittify_project, "001-feature", "WP02")

        assert resolved.execution_mode == "code_change"
        assert resolved.workspace_name == "001-feature-lane-a"

    def test_resolve_workspace_for_wp_emits_single_compatibility_error_when_inference_fails(self, kittify_project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP07",
            "Legacy work package",
            "Legacy mission body without explicit execution mode.",
        )

        def broken_infer(_wp_content: str, _wp_files: list[str]):
            raise RuntimeError("boom")

        monkeypatch.setattr(workspace_context_module, "infer_execution_mode", broken_infer)

        with pytest.raises(ValueError, match="Could not classify execution_mode"):
            resolve_workspace_for_wp(kittify_project, "001-feature", "WP07")

    def test_resolve_workspace_for_wp_falls_back_to_code_change_when_no_signals(self, kittify_project: Path) -> None:
        """Legacy WPs without explicit execution_mode and without strong body signals
        default to ``code_change`` (FR-019: zero-migration compatibility) and are flagged
        in ``mode_source = inferred_legacy`` so callers can detect the default."""
        feature_dir = _seed_mission(kittify_project)
        tasks_dir = feature_dir / "tasks"
        _write_wp(
            tasks_dir,
            "WP08",
            "Legacy ambiguous work package",
            "Legacy body without src, tests, docs, or planning artifact references.",
            owned_files=["src/specify_cli/workspace_context.py"],
        )
        write_lanes_json(
            feature_dir,
            LanesManifest(
                version=1,
                mission_slug="001-feature",
                mission_id="mission-001-feature",
                mission_branch="kitty/mission-001-feature",
                target_branch="main",
                lanes=[
                    ExecutionLane(
                        lane_id="lane-a",
                        wp_ids=("WP08",),
                        write_scope=("src/**",),
                        predicted_surfaces=("core",),
                        depends_on_lanes=(),
                        parallel_group=0,
                    )
                ],
                computed_at="2026-04-04T10:00:00Z",
                computed_from="test",
            ),
        )

        resolved = resolve_workspace_for_wp(kittify_project, "001-feature", "WP08")

        assert resolved.execution_mode == "code_change"
        assert resolved.mode_source == "inferred_legacy"
        assert resolved.resolution_kind == "lane_workspace"
