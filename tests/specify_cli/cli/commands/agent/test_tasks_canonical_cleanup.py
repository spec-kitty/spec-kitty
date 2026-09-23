"""Tests for WP03: tasks.py canonical status model cleanup.

Covers:
- finalize-tasks calls bootstrap_canonical_state() and includes stats in output
- move_task body note does NOT contain lane=
- add_note body note does NOT contain lane=
- move_task hard-fails when WP has no canonical event (not bootstrapped)
- move_task succeeds when canonical event exists
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch, ANY

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.store import append_event
from specify_cli.status.models import StatusEvent, Lane
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_wp_lane(feature_dir: Path, wp_id: str, lane: str) -> None:
    """Seed a WP into a specific lane in the event log."""
    _lane_alias = {"doing": "in_progress"}
    canonical_lane = _lane_alias.get(lane, lane)
    event = StatusEvent(
        event_id=f"test-{wp_id}-{canonical_lane}",
        mission_slug=feature_dir.name,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=Lane(canonical_lane),
        at="2026-01-01T00:00:00+00:00",
        actor="test",
        force=True,
        execution_mode="worktree",
    )
    append_event(feature_dir, event)


def _seed_lanes_json(feature_dir: Path, mission_slug: str, wp_id: str) -> None:
    """Write a minimal ``lanes.json`` covering *wp_id*.

    #4758's ``_mt_guard_planned_boundary_lanes`` now refuses any hop OUT of
    ``planned`` when ``lanes.json`` is absent (a required precondition, not a
    behavior change under test here).
    """
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=mission_slug,
            mission_id=None,
            mission_branch=f"kitty/mission-{mission_slug}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=(wp_id,),
                    write_scope=(f"src/{wp_id.lower()}/**",),
                    predicted_surfaces=(),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="dependency_graph+ownership",
            planning_commit_sha="a" * 40,
        ),
    )


def _build_minimal_feature(tmp_path: Path, mission_slug: str = "060-test") -> Path:
    """Create minimal feature structure with tasks.md and one WP file.

    Returns feature_dir.
    """
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    (feature_dir / "tasks.md").write_text(
        "## Work Package WP01\n\n## Work Package WP02\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\n"
            f"work_package_id: {wp_id}\n"
            f"title: Test {wp_id}\n"
            f"execution_mode: code_change\n"
            f"owned_files:\n  - src/{wp_id.lower()}/**\n"
            f"authoritative_surface: src/{wp_id.lower()}/\n"
            f"---\n\n# {wp_id}\n\n## Activity Log\n",
            encoding="utf-8",
        )
    return feature_dir


def _build_wp_file(tmp_path: Path, mission_slug: str, wp_id: str, lane: str = "planned") -> Path:
    """Build a single WP file and return the feature_dir."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    wp_file = tasks_dir / f"{wp_id}-test.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Test {wp_id}\n"
        f"lane: {lane}\n"
        f"execution_mode: code_change\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir


def _build_planning_artifact_wp(tmp_path: Path, mission_slug: str, wp_id: str) -> Path:
    """Build a planning-artifact WP in repository-root mode and return feature_dir."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    wp_file = tasks_dir / f"{wp_id}-planning.md"
    wp_file.write_text(
        f"---\n"
        f"work_package_id: {wp_id}\n"
        f"title: Planning {wp_id}\n"
        f"execution_mode: planning_artifact\n"
        f"owned_files:\n  - kitty-specs/{mission_slug}/plan.md\n"
        f"authoritative_surface: kitty-specs/{mission_slug}/plan.md\n"
        f"---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )
    return feature_dir


# ---------------------------------------------------------------------------
# T006: finalize-tasks calls bootstrap_canonical_state
# ---------------------------------------------------------------------------


class TestFinalizeTasksBootstrap:
    """finalize-tasks calls bootstrap and includes stats in JSON output."""

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.bootstrap_canonical_state")
    def test_finalize_calls_bootstrap(
        self,
        mock_bootstrap: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks invokes bootstrap_canonical_state after dependency parsing."""
        mission_slug = "060-test"
        feature_dir = _build_minimal_feature(tmp_path, mission_slug)
        # rc3 M5 (FR-002/FR-003): resolve_mission_identity no longer defaults a
        # typeless/absent meta.json to "software-dev" -- give the fixture an
        # explicit canonical mission_type (mission_number is deliberately still
        # omitted, see the assertion note below).
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev"}), encoding="utf-8"
        )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        # Mock bootstrap return value
        from specify_cli.status.bootstrap import BootstrapResult

        mock_bootstrap.return_value = BootstrapResult(
            total_wps=2,
            already_initialized=0,
            newly_seeded=2,
            skipped=0,
            wp_details={"WP01": "initialized", "WP02": "initialized"},
        )

        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, f"CLI error: {result.output}"

        # bootstrap was called
        mock_bootstrap.assert_called_once_with(feature_dir, mission_slug, dry_run=False)

        # JSON output includes bootstrap stats
        data = json.loads(result.output)
        assert data["mission_slug"] == mission_slug
        # The fixture's meta.json omits mission_number, so
        # resolve_mission_identity() yields mission_number=None (JSON null).
        # Post-083, mission_number is display-only and pre-merge missions
        # legitimately have no numeric prefix. The canonical identity is
        # mission_id, which is not asserted here because the fixture omits it.
        assert data["mission_number"] is None
        assert data["mission_type"] == "software-dev"
        assert "bootstrap" in data
        assert data["bootstrap"]["total_wps"] == 2
        assert data["bootstrap"]["newly_seeded"] == 2

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.bootstrap_canonical_state")
    def test_finalize_validate_only_passes_dry_run(
        self,
        mock_bootstrap: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """--validate-only passes dry_run=True to bootstrap."""
        mission_slug = "060-test"
        feature_dir = _build_minimal_feature(tmp_path, mission_slug)
        # rc3 M5 (FR-002/FR-003): resolve_mission_identity no longer defaults a
        # typeless/absent meta.json to "software-dev" -- give the fixture an
        # explicit canonical mission_type (mission_number is deliberately still
        # omitted, see the assertion note below).
        (feature_dir / "meta.json").write_text(
            json.dumps({"mission_type": "software-dev"}), encoding="utf-8"
        )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        from specify_cli.status.bootstrap import BootstrapResult

        mock_bootstrap.return_value = BootstrapResult(
            total_wps=2,
            already_initialized=2,
            newly_seeded=0,
            skipped=0,
            wp_details={"WP01": "already_exists", "WP02": "already_exists"},
        )

        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json", "--validate-only"])
        assert result.exit_code == 0, f"CLI error: {result.output}"
        data = json.loads(result.output)
        assert data["mission_slug"] == mission_slug
        # Fixture's meta.json omits mission_number — resolves to None (JSON null)
        # per the post-083 canonical identity model (FR-044).
        assert data["mission_number"] is None
        assert data["mission_type"] == "software-dev"

        mock_bootstrap.assert_called_once_with(ANY, mission_slug, dry_run=True)


# ---------------------------------------------------------------------------
# T007 / T008: Body notes don't contain lane=
# ---------------------------------------------------------------------------


class TestBodyNotesNoLane:
    """Body notes written by move_task and add_history must NOT contain lane=."""

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_move_task_body_note_no_lane(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events_transactional: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """move_task history entry must not contain 'lane='."""
        mission_slug = "060-test"
        feature_dir = _build_wp_file(tmp_path, mission_slug, "WP01", "claimed")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        # Build a mock WP
        wp_file = feature_dir / "tasks" / "WP01-test.md"
        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="claimed",
            relative_subpath=Path("tasks/WP01-test.md"),
            frontmatter="work_package_id: WP01\ntitle: Test WP01\nlane: claimed\nagent: testbot\n",
            body="\n# WP01\n\n## Activity Log\n",
            padding="",
        )
        mock_locate_wp.return_value = mock_wp

        # Seed canonical event so hard-fail doesn't trigger
        _seed_wp_lane(feature_dir, "WP01", "claimed")

        # Build a proper mock event for read_events that returns real events
        mock_read_events_transactional.return_value = list(
            __import__("specify_cli.status.store", fromlist=["read_events"]).read_events(feature_dir)
        )

        mock_emit.return_value = MagicMock(to_lane=Lane.IN_PROGRESS)
        mock_safe_commit.return_value = True

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "in_progress",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--force",
                "--json",
                "--no-auto-commit",
            ],
        )
        assert result.exit_code == 0, f"CLI error: {result.output}"

        # Read the WP file and check the activity log
        content = wp_file.read_text(encoding="utf-8")
        assert "lane=" not in content, f"Body note should not contain 'lane=' but got:\n{content}"

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_add_history_body_note_no_lane(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """add_history entry must not contain 'lane='."""
        mission_slug = "060-test"
        feature_dir = _build_wp_file(tmp_path, mission_slug, "WP01", "in_progress")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        # Seed canonical event for add_history's lane lookup
        _seed_wp_lane(feature_dir, "WP01", "in_progress")

        wp_file = feature_dir / "tasks" / "WP01-test.md"
        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="in_progress",
            relative_subpath=Path("tasks/WP01-test.md"),
            frontmatter="work_package_id: WP01\ntitle: Test WP01\nlane: in_progress\nagent: testbot\n",
            body="\n# WP01\n\n## Activity Log\n",
            padding="",
        )
        mock_locate_wp.return_value = mock_wp

        result = runner.invoke(
            app,
            [
                "add-history",
                "WP01",
                "--note",
                "Implementation progressing",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--json",
            ],
        )
        assert result.exit_code == 0, f"CLI error: {result.output}"

        content = wp_file.read_text(encoding="utf-8")
        assert "lane=" not in content, f"Body note should not contain 'lane=' but got:\n{content}"
        # Verify note text is present
        assert "Implementation progressing" in content


# ---------------------------------------------------------------------------
# T009: move_task hard-fails when no canonical event
# ---------------------------------------------------------------------------


class TestMoveTaskHardFail:
    """move_task must raise RuntimeError when WP has no canonical status."""

    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_move_task_hard_fails_no_canonical_event(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_read_events_transactional: MagicMock,
        mock_lock: MagicMock,
        tmp_path: Path,
    ) -> None:
        """move_task exits with error when WP has no canonical status events."""
        mission_slug = "060-test"
        feature_dir = _build_wp_file(tmp_path, mission_slug, "WP01", "planned")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        # No events = no canonical state
        mock_read_events_transactional.return_value = []

        wp_file = feature_dir / "tasks" / "WP01-test.md"
        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="planned",
            relative_subpath=Path("tasks/WP01-test.md"),
            frontmatter="work_package_id: WP01\ntitle: Test WP01\nlane: planned\n",
            body="\n# WP01\n\n## Activity Log\n",
            padding="",
        )
        mock_locate_wp.return_value = mock_wp

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "claimed",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--force",
                "--no-auto-commit",
                "--json",
            ],
        )
        # Should exit with error
        assert result.exit_code != 0, f"Expected failure but got: {result.output}"

        # Error message should mention finalize-tasks
        assert "finalize-tasks" in result.output or "finalize" in result.output.lower(), f"Error should mention finalize-tasks but got:\n{result.output}"
        assert "no canonical status" in result.output.lower() or "has no canonical" in result.output.lower(), (
            f"Error should mention missing canonical status but got:\n{result.output}"
        )

    @patch("specify_cli.cli.commands.agent.tasks.commit_for_mission")
    @patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.read_events_transactional")
    @patch("specify_cli.cli.commands.agent.tasks.feature_status_lock")
    @patch("specify_cli.cli.commands.agent.tasks._validate_ready_for_review")
    @patch("specify_cli.cli.commands.agent.tasks._check_unchecked_subtasks")
    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.locate_work_package")
    def test_move_task_succeeds_with_canonical_event(
        self,
        mock_locate_wp: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        mock_unchecked: MagicMock,
        mock_review_valid: MagicMock,
        mock_lock: MagicMock,
        mock_read_events_transactional: MagicMock,
        mock_emit: MagicMock,
        mock_safe_commit: MagicMock,
        tmp_path: Path,
    ) -> None:
        """move_task succeeds when WP has canonical event."""
        mission_slug = "060-test"
        feature_dir = _build_wp_file(tmp_path, mission_slug, "WP01", "planned")

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")
        mock_unchecked.return_value = []
        mock_review_valid.return_value = (True, [])
        mock_lock.return_value.__enter__ = MagicMock()
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        # Seed canonical state
        _seed_wp_lane(feature_dir, "WP01", "planned")
        # lanes.json is now a required precondition to leave 'planned' (#4758,
        # _mt_guard_planned_boundary_lanes) -- fixture update, not a behavior
        # change: this test exercises the canonical-event success path.
        _seed_lanes_json(feature_dir, mission_slug, "WP01")

        # Return real events from the seeded store
        from specify_cli.status.store import read_events as real_read_events

        mock_read_events_transactional.return_value = list(real_read_events(feature_dir))

        wp_file = feature_dir / "tasks" / "WP01-test.md"
        from specify_cli.task_utils import WorkPackage

        mock_wp = WorkPackage(
            feature=mission_slug,
            path=wp_file,
            current_lane="planned",
            relative_subpath=Path("tasks/WP01-test.md"),
            frontmatter="work_package_id: WP01\ntitle: Test WP01\nlane: planned\nagent: testbot\n",
            body="\n# WP01\n\n## Activity Log\n",
            padding="",
        )
        mock_locate_wp.return_value = mock_wp

        mock_emit.return_value = MagicMock(to_lane=Lane.CLAIMED)
        mock_safe_commit.return_value = True

        result = runner.invoke(
            app,
            [
                "move-task",
                "WP01",
                "--to",
                "claimed",
                "--agent",
                "testbot",
                "--mission",
                mission_slug,
                "--force",
                "--json",
                "--no-auto-commit",
            ],
        )
        assert result.exit_code == 0, f"CLI error: {result.output}"

        data = json.loads(result.output)
        assert data["result"] == "success"


# ---------------------------------------------------------------------------
# Unit B: typed frontmatter migration for finalize-tasks / map-requirements
# ---------------------------------------------------------------------------


class TestTypedFrontmatterMigration:
    """finalize-tasks and map-requirements use WPMetadata for frontmatter access."""

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.bootstrap_canonical_state")
    def test_finalize_writes_dependencies_via_typed_model(
        self,
        mock_bootstrap: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """finalize-tasks writes dependencies to WP frontmatter using WPMetadata.update().

        After migration, the written frontmatter is produced by model_dump(exclude_none=True),
        so the file should contain typed fields (not arbitrary dict keys).
        """
        mission_slug = "060-typed-test"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (tmp_path / ".kittify").mkdir(exist_ok=True)

        # tasks.md with WP02 depending on WP01
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n\nSetup work.\n\n## Work Package WP02\n\nDepends on WP01\n",
            encoding="utf-8",
        )
        for wp_id in ("WP01", "WP02"):
            (tasks_dir / f"{wp_id}-test.md").write_text(
                f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n---\n\n# {wp_id}\n",
                encoding="utf-8",
            )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        from specify_cli.status.bootstrap import BootstrapResult

        mock_bootstrap.return_value = BootstrapResult(
            total_wps=2,
            already_initialized=2,
            newly_seeded=0,
            skipped=0,
            wp_details={"WP01": "exists", "WP02": "exists"},
        )

        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, f"CLI error: {result.output}"

        # Verify WP02 frontmatter has dependencies written
        from specify_cli.status.wp_metadata import read_wp_frontmatter

        wp02_meta, _ = read_wp_frontmatter(tasks_dir / "WP02-test.md")
        assert wp02_meta.dependencies == ["WP01"]

        # WP01 should have empty deps
        wp01_meta, _ = read_wp_frontmatter(tasks_dir / "WP01-test.md")
        assert wp01_meta.dependencies == []

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.bootstrap_canonical_state")
    def test_finalize_detects_dep_conflict_with_typed_access(
        self,
        mock_bootstrap: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Dependency conflict detection uses typed WPMetadata.dependencies attribute."""
        mission_slug = "060-conflict-test"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (tmp_path / ".kittify").mkdir(exist_ok=True)

        # tasks.md says WP02 depends on WP01
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n\nSetup work.\n\n## Work Package WP02\n\nDepends on WP01\n",
            encoding="utf-8",
        )
        # But WP02 frontmatter already says dependencies: [WP99]
        (tasks_dir / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Test WP01\n---\n\n# WP01\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP02-test.md").write_text(
            "---\nwork_package_id: WP02\ntitle: Test WP02\ndependencies:\n  - WP99\n---\n\n# WP02\n",
            encoding="utf-8",
        )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json"])
        # Should exit with error due to dependency conflict
        assert result.exit_code != 0, f"Expected conflict error but got: {result.output}"
        assert "Dependency disagreement" in result.output

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    @patch("specify_cli.cli.commands.agent.tasks.bootstrap_canonical_state")
    def test_finalize_preserves_existing_deps_when_parser_finds_none(
        self,
        mock_bootstrap: MagicMock,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """When tasks.md has no deps but frontmatter has existing deps, preserve them."""
        mission_slug = "060-preserve-test"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (tmp_path / ".kittify").mkdir(exist_ok=True)

        # tasks.md with no dependency info. WP03 is a real WP in the graph so
        # WP01's preserved frontmatter dep resolves — #4890 validates the
        # effective persisted graph and rejects a dep on a WP absent from it, so
        # the "preserve existing deps" behaviour this test pins must use a valid
        # target (the reject-on-unknown-WP path is covered by test_issue_4890).
        (feature_dir / "tasks.md").write_text(
            "## Work Package WP01\n\n## Work Package WP03\n\n",
            encoding="utf-8",
        )
        # WP01 frontmatter has an existing (valid) dep the parser did not re-derive
        (tasks_dir / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Test WP01\ndependencies:\n  - WP03\n---\n\n# WP01\n",
            encoding="utf-8",
        )
        (tasks_dir / "WP03-test.md").write_text(
            "---\nwork_package_id: WP03\ntitle: Test WP03\n---\n\n# WP03\n",
            encoding="utf-8",
        )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        from specify_cli.status.bootstrap import BootstrapResult

        mock_bootstrap.return_value = BootstrapResult(
            total_wps=2,
            already_initialized=2,
            newly_seeded=0,
            skipped=0,
            wp_details={"WP01": "exists", "WP03": "exists"},
        )

        result = runner.invoke(app, ["finalize-tasks", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, f"CLI error: {result.output}"

        # Verify existing deps were preserved
        from specify_cli.status.wp_metadata import read_wp_frontmatter

        wp01_meta, _ = read_wp_frontmatter(tasks_dir / "WP01-test.md")
        assert wp01_meta.dependencies == ["WP03"]

    @patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out")
    @patch("specify_cli.cli.commands.agent.tasks.locate_project_root")
    @patch("specify_cli.cli.commands.agent.tasks._find_mission_slug")
    def test_map_requirements_writes_via_typed_model(
        self,
        mock_slug: MagicMock,
        mock_root: MagicMock,
        mock_branch: MagicMock,
        tmp_path: Path,
    ) -> None:
        """map-requirements reads/writes requirement_refs via WPMetadata."""
        mission_slug = "060-reqmap-test"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        (tmp_path / ".kittify").mkdir(exist_ok=True)

        # Create spec.md with requirement IDs
        (feature_dir / "spec.md").write_text(
            "# Spec\n\n## Requirements\n\n- **FR-001**: First requirement\n- **FR-002**: Second requirement\n",
            encoding="utf-8",
        )
        # Create WP01 file
        (tasks_dir / "WP01-test.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Test WP01\n---\n\n# WP01\n",
            encoding="utf-8",
        )

        mock_root.return_value = tmp_path
        mock_slug.return_value = mission_slug
        mock_branch.return_value = (tmp_path, "main")

        result = runner.invoke(
            app,
            ["map-requirements", "--wp", "WP01", "--refs", "FR-001,FR-002", "--mission", mission_slug, "--json", "--no-auto-commit"],
        )
        assert result.exit_code == 0, f"CLI error: {result.output}"

        # Verify the refs were written to frontmatter
        from specify_cli.status.wp_metadata import read_wp_frontmatter

        wp01_meta, _ = read_wp_frontmatter(tasks_dir / "WP01-test.md")
        assert sorted(wp01_meta.requirement_refs) == ["FR-001", "FR-002"]


class TestStatusCanonicalStaleFields:
    """status --json and human output use canonical nested stale state."""

    def test_status_json_includes_nested_stale_and_legacy_fields_for_planning_artifact(
        self,
        tmp_path: Path,
    ) -> None:
        mission_slug = "077-status-json"
        feature_dir = _build_planning_artifact_wp(tmp_path, mission_slug, "WP03")

        append_event(
            feature_dir,
            StatusEvent(
                event_id="status-json-wp03",
                mission_slug=mission_slug,
                wp_id="WP03",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=False,
                execution_mode="direct_repo",
            ),
        )

        with setup_mocked_env(tmp_path, mission_slug=mission_slug):
            result = runner.invoke(app, ["status", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, f"CLI error: {result.output}"

        data = json.loads(result.output)
        wp = data["work_packages"][0]
        assert wp["stale"] == {
            "status": "not_applicable",
            "reason": "planning_artifact_repo_root_shared_workspace",
            "minutes_since_commit": None,
            "last_commit_time": None,
        }
        assert wp["is_stale"] is False
        assert wp["minutes_since_commit"] is None
        assert wp["worktree_exists"] is False

    def test_status_human_output_shows_repo_root_planning_stale_label(
        self,
        tmp_path: Path,
    ) -> None:
        mission_slug = "077-status-human"
        feature_dir = _build_planning_artifact_wp(tmp_path, mission_slug, "WP03")

        append_event(
            feature_dir,
            StatusEvent(
                event_id="status-human-wp03",
                mission_slug=mission_slug,
                wp_id="WP03",
                from_lane=Lane.PLANNED,
                to_lane=Lane.IN_PROGRESS,
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=False,
                execution_mode="direct_repo",
            ),
        )

        with setup_mocked_env(tmp_path, mission_slug=mission_slug):
            result = runner.invoke(app, ["status", "--mission", mission_slug])
        assert result.exit_code == 0, f"CLI error: {result.output}"
        assert "stale: n/a (repo-root planning work)" in result.output

    def test_status_json_falls_back_only_for_missing_lanes(
        self,
        tmp_path: Path,
    ) -> None:
        mission_slug = "077-status-missing-lanes"
        _build_wp_file(tmp_path, mission_slug, "WP01")

        with setup_mocked_env(tmp_path, mission_slug=mission_slug):
            result = runner.invoke(app, ["status", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, f"CLI error: {result.output}"

        data = json.loads(result.output)
        wp = data["work_packages"][0]
        assert wp["execution_mode"] == "code_change"
        assert wp["workspace_kind"] == "unknown"

    def test_status_json_defaults_legacy_execution_mode_to_code_change(
        self,
        tmp_path: Path,
    ) -> None:
        """Per FR-019, legacy WPs without execution_mode and without strong body
        signals default to ``code_change`` rather than hard-failing the status
        command. This preserves zero-migration compatibility for older missions.
        """
        mission_slug = "078-status-ambiguous-legacy"
        feature_dir = tmp_path / "kitty-specs" / mission_slug
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True, exist_ok=True)
        (tmp_path / ".kittify").mkdir(exist_ok=True)
        (tasks_dir / "WP01-legacy.md").write_text(
            "---\nwork_package_id: WP01\ntitle: Legacy WP01\n---\n\nLegacy body without src, tests, docs, or planning references.\n",
            encoding="utf-8",
        )

        with setup_mocked_env(tmp_path, mission_slug=mission_slug):
            result = runner.invoke(app, ["status", "--mission", mission_slug, "--json"])
        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        wp = payload["work_packages"][0]
        assert wp["execution_mode"] == "code_change"
