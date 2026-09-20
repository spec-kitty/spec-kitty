"""Unit tests for lane-only implement command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.implement import (
    _ensure_vcs_in_meta,
    detect_feature_context,
    find_wp_file,
    implement,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bypass the charter preflight gate for these implement-flow tests.

    None of these fixtures stage a charter; without the bypass the gate
    returns ``Error: charter_source missing`` before reaching the
    lane-workspace creation / JSON-output paths the tests exercise.
    Patch the hook boundary directly instead of relying on a production
    environment bypass.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    # Fixtures run implement on a protected ``main`` branch; the documented
    # operator escape hatch is the ONE sanctioned waiver (SPEC_KITTY_TEST_MODE
    # no longer waives the pre-check — PR #1850 guard-bypass fix).
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )


def create_meta_json(feature_dir: Path, vcs: str = "git") -> Path:
    meta_path = feature_dir / "meta.json"
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_content = {
        "feature_number": feature_dir.name.split("-")[0],
        "mission_slug": feature_dir.name,
        "created_at": "2026-01-17T00:00:00Z",
        "friendly_name": feature_dir.name,
        "mission_type": "software-dev",
        "slug": feature_dir.name,
        "target_branch": "main",
    }
    if vcs:
        meta_content["vcs"] = vcs
    meta_path.write_text(json.dumps(meta_content, indent=2))
    return meta_path


def create_lanes_json(feature_dir: Path, wp_ids: tuple[str, ...] = ("WP01",)) -> None:
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=feature_dir.name,
            mission_id=f"mission-{feature_dir.name}",
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=wp_ids,
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


def _append_lane_event(feature_dir: Path, wp_id: str, lane: str) -> None:
    from specify_cli.status.models import Lane, StatusEvent
    from specify_cli.status.store import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=feature_dir.name,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-05-30T08:30:00+00:00",
            actor="fixture",
            force=True,
            execution_mode="worktree",
        ),
    )


from tests.status.conftest import seed_wp_to_planned as _seed_planned_shared


def _seed_planned(feature_dir: Path, wp_id: str) -> None:
    """Seed a WP out of the non-display 'genesis' state into 'planned'."""
    _seed_planned_shared(feature_dir, wp_id, slug=feature_dir.name)


class TestDetectFeatureContext:
    def test_detect_with_explicit_flag(self) -> None:
        number, slug = detect_feature_context("010-lane-only-runtime")
        assert number == "010"
        assert slug == "010-lane-only-runtime"

    def test_detect_failure_no_flag(self) -> None:
        with pytest.raises(typer.Exit):
            detect_feature_context(None)

    def test_detect_invalid_format(self) -> None:
        number, slug = detect_feature_context("lane-only-runtime")
        assert number is None
        assert slug == "lane-only-runtime"


class TestFindWpFile:
    def test_find_wp_file_success(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "kitty-specs" / "010-feature" / "tasks"
        tasks_dir.mkdir(parents=True)
        wp_file = tasks_dir / "WP01-setup.md"
        wp_file.write_text("# WP01")

        result = find_wp_file(tmp_path, "010-feature", "WP01")
        assert result == wp_file

    def test_find_wp_file_not_found(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "kitty-specs" / "010-feature" / "tasks"
        tasks_dir.mkdir(parents=True)
        with pytest.raises(FileNotFoundError, match="WP file not found"):
            find_wp_file(tmp_path, "010-feature", "WP01")


class TestEnsureVcsInMeta:
    def test_existing_vcs_is_preserved(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir, vcs="git")
        assert _ensure_vcs_in_meta(feature_dir, tmp_path).value == "git"

    def test_missing_meta_errors(self, tmp_path: Path) -> None:
        with pytest.raises(typer.Exit):
            _ensure_vcs_in_meta(tmp_path / "kitty-specs" / "010-feature", tmp_path)


class TestImplementCommand:
    def test_implement_requires_lanes_json(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01",
            encoding="utf-8",
        )

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
        ):
            with pytest.raises(typer.Exit):
                implement("WP01", mission="010-feature", recover=False)

    def test_implement_json_output_is_clean(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        create_lanes_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01",
            encoding="utf-8",
        )
        _seed_planned(feature_dir, "WP01")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
            ) as mock_ensure_vcs,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
        ):
            mock_ensure_vcs.return_value = MagicMock(value="git")
            mock_create_lane_workspace.return_value = MagicMock(
                workspace_path=tmp_path / ".worktrees" / "010-feature-lane-a",
                branch_name="kitty/mission-010-feature-lane-a",
                lane_id="lane-a",
                mission_branch="kitty/mission-010-feature",
                is_reuse=False,
            )

            implement("WP01", mission="010-feature", json_output=True, recover=False)

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["workspace"] == ".worktrees/010-feature-lane-a"
        assert payload["branch"] == "kitty/mission-010-feature-lane-a"
        assert payload["lane_id"] == "lane-a"
        assert payload["mission_slug"] == "010-feature"
        assert payload["mission_number"] is None
        assert payload["mission_type"] == "software-dev"

    def test_implement_json_error_output_is_clean(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01",
            encoding="utf-8",
        )
        _seed_planned(feature_dir, "WP01")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ),
        ):
            with pytest.raises(typer.Exit):
                implement("WP01", mission="010-feature", json_output=True, recover=False)

        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["status"] == "error"
        assert payload["wp_id"] == "WP01"
        assert payload["error"] != "implement command failed"
        assert "lanes.json is required" in payload["error"]

    def test_implement_creates_lane_workspace(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        create_lanes_json(feature_dir, wp_ids=("WP01", "WP02"))
        wp_file = feature_dir / "tasks" / "WP02-api.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP02\n"
            "dependencies: [WP01]\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp02/**\n"
            "authoritative_surface: src/wp02/\n"
            "---\n# WP02",
            encoding="utf-8",
        )
        _seed_planned(feature_dir, "WP02")
        _append_lane_event(feature_dir, "WP01", "done")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
            ) as mock_ensure_vcs,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
        ):
            mock_ensure_vcs.return_value = MagicMock(value="git")
            mock_create_lane_workspace.return_value = MagicMock(
                workspace_path=tmp_path / ".worktrees" / "010-feature-lane-a",
                branch_name="kitty/mission-010-feature-lane-a",
                lane_id="lane-a",
                mission_branch="kitty/mission-010-feature",
                is_reuse=True,
            )

            implement("WP02", mission="010-feature", recover=False)

            kwargs = mock_create_lane_workspace.call_args.kwargs
            assert kwargs["wp_id"] == "WP02"
            assert kwargs["declared_deps"] == ["WP01"]

    def test_implement_rejects_dependency_before_workspace_creation(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        create_lanes_json(feature_dir, wp_ids=("WP01", "WP02"))
        wp_file = feature_dir / "tasks" / "WP02-api.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP02\n"
            "dependencies: [WP01]\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp02/**\n"
            "authoritative_surface: src/wp02/\n"
            "---\n# WP02",
            encoding="utf-8",
        )
        # WP02 is seeded past genesis so the dependency gate (not genesis gate) fires.
        # WP01 is intentionally left unapproved so the dependency check rejects.
        _seed_planned(feature_dir, "WP02")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ) as mock_commit_planning,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
        ):
            with pytest.raises(typer.Exit):
                implement("WP02", mission="010-feature", auto_commit=True, recover=False)

        assert mock_commit_planning.call_count == 0
        assert mock_create_lane_workspace.call_count == 0
        out = capsys.readouterr().out
        assert "dependencies_not_satisfied" in out
        assert "all dependencies must be approved or done" in out

    def test_implement_auto_commit_allows_safe_coordination_branch_when_target_is_protected(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("SPEC_KITTY_TEST_MODE", raising=False)
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        create_lanes_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01",
            encoding="utf-8",
        )
        _seed_planned(feature_dir, "WP01")

        # Stub the policy resolver so the protection decision is deterministic
        # and the resolver is the ONLY read-I/O boundary (NFR-003).
        mock_policy = MagicMock()
        mock_policy.is_protected.return_value = False  # non-protected lane branch

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement.get_current_branch",
                return_value="kitty/mission-010-feature-01ABCDEF",
            ),
            patch(
                "specify_cli.cli.commands.implement.ProtectionPolicy.resolve",
                return_value=mock_policy,
            ) as mock_resolver,
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ) as mock_commit_planning,
            patch(
                "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
            ) as mock_ensure_vcs,
            patch(
                "specify_cli.cli.commands.implement.resolve_workspace_for_wp",
            ) as mock_resolve_workspace,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
            patch(
                "specify_cli.cli.commands.implement.start_implementation_status",
                return_value=MagicMock(status_changed=False),
            ),
            patch(
                # FR-012 alignment: a non-bulk_edit mission's gate now yields
                # change_mode=None (legacy values collapse; invariant is
                # {"bulk_edit", None}). change_mode != "bulk_edit" runs the
                # inference scan, which no-ops here (no bulk-edit spec.md). Not a
                # behavior regression.
                "specify_cli.bulk_edit.gate.ensure_occurrence_classification_ready",
                return_value=MagicMock(passed=True, change_mode=None),
            ),
        ):
            mock_ensure_vcs.return_value = MagicMock(value="git")
            mock_resolve_workspace.return_value = MagicMock(
                execution_mode="code_change",
                worktree_path=tmp_path / ".worktrees" / "010-feature-lane-a",
                workspace_name="010-feature-lane-a",
                branch_name="kitty/mission-010-feature-lane-a",
                lane_id="lane-a",
                lane_wp_ids=["WP01"],
                resolution_kind="lane_workspace",
                exists=True,
            )
            mock_create_lane_workspace.return_value = MagicMock(
                workspace_path=tmp_path / ".worktrees" / "010-feature-lane-a",
                branch_name="kitty/mission-010-feature-lane-a",
                lane_id="lane-a",
                mission_branch="kitty/mission-010-feature",
                is_reuse=False,
                execution_mode="code_change",
                resolution_kind="lane_workspace",
            )

            implement("WP01", mission="010-feature", auto_commit=True, recover=False)

        mock_commit_planning.assert_called_once()
        # NFR-003: the resolver must have been invoked (not vacuous)
        assert mock_resolver.called, "ProtectionPolicy.resolve must be invoked for the protection decision"

    def test_implement_status_emit_uses_transport_execution_mode(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        create_lanes_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "dependencies: []\n"
            "execution_mode: code_change\n"
            "owned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n"
            "---\n# WP01",
            encoding="utf-8",
        )
        _seed_planned(feature_dir, "WP01")

        captured: dict[str, str] = {}

        def fake_start_status(**kwargs: object) -> MagicMock:
            captured["execution_mode"] = str(kwargs["execution_mode"])
            captured["workspace_context"] = str(kwargs["workspace_context"])
            return MagicMock(status_changed=False)

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
            ) as mock_ensure_vcs,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
            patch(
                "specify_cli.cli.commands.implement.start_implementation_status",
                side_effect=fake_start_status,
            ),
        ):
            mock_ensure_vcs.return_value = MagicMock(value="git")
            mock_create_lane_workspace.return_value = MagicMock(
                workspace_path=tmp_path / ".worktrees" / "010-feature-lane-a",
                branch_name="kitty/mission-010-feature-lane-a",
                lane_id="lane-a",
                mission_branch="kitty/mission-010-feature",
                is_reuse=False,
                execution_mode="code_change",
                resolution_kind="lane_workspace",
            )

            implement("WP01", mission="010-feature", auto_commit=False, recover=False)

        assert captured["execution_mode"] == "worktree"
        assert captured["workspace_context"].startswith("worktree:")

    def test_implement_allows_planning_artifact_in_lane_planning(self, tmp_path: Path) -> None:
        feature_dir = tmp_path / "kitty-specs" / "010-feature"
        create_meta_json(feature_dir)
        wp_file = feature_dir / "tasks" / "WP02-plan.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\n"
            "work_package_id: WP02\n"
            "dependencies: []\n"
            "execution_mode: planning_artifact\n"
            "owned_files:\n"
            "  - kitty-specs/010-feature/**\n"
            "authoritative_surface: kitty-specs/010-feature/\n"
            "---\n"
            "# WP02\n"
        )
        _seed_planned(feature_dir, "WP02")

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", "010-feature"),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git",
            ),
            patch(
                "specify_cli.cli.commands.implement._ensure_vcs_in_meta",
            ) as mock_ensure_vcs,
            patch(
                "specify_cli.cli.commands.implement.resolve_workspace_for_wp",
            ) as mock_resolve_workspace,
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
            ) as mock_create_lane_workspace,
        ):
            mock_ensure_vcs.return_value = MagicMock(value="git")
            from specify_cli.lanes.compute import PLANNING_LANE_ID
            mock_resolve_workspace.return_value = MagicMock(
                execution_mode="planning_artifact",
                worktree_path=tmp_path,
                workspace_name=f"010-feature-{PLANNING_LANE_ID}",
                branch_name="main",
                lane_id=PLANNING_LANE_ID,
                lane_wp_ids=["WP02"],
                resolution_kind="repo_root",
                exists=True,
            )
            mock_create_lane_workspace.return_value = MagicMock(
                workspace_path=tmp_path,
                branch_name=None,
                workspace_name=f"010-feature-{PLANNING_LANE_ID}",
                lane_id=PLANNING_LANE_ID,
                mission_branch=None,
                is_reuse=False,
                execution_mode="planning_artifact",
                resolution_kind="repo_root",
            )

            implement("WP02", mission="010-feature", auto_commit=False, recover=False)

            kwargs = mock_create_lane_workspace.call_args.kwargs
            assert kwargs["lanes_manifest"] is None
            assert kwargs["resolved_workspace"].execution_mode == "planning_artifact"


class TestImplementPrimaryTopologyLanesJson:
    """Regression tests for #3371: lanes.json read from the primary partition.

    LANE_STATE is PRIMARY-partition authority. The implement validate block
    must read it from the primary placement surface even when STATUS remains
    coord-owned.
    """

    def test_lanes_json_read_from_primary_dir_not_coord(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """lanes.json in primary only — implement must NOT fail with MissingLanesError."""
        mission_slug = "010-feature"

        # Primary checkout: meta.json + WP file + canonical lanes.json.
        primary_dir = tmp_path / "kitty-specs" / mission_slug
        create_meta_json(primary_dir)
        create_lanes_json(primary_dir, wp_ids=("WP01",))
        wp_file = primary_dir / "tasks" / "WP01-setup.md"
        wp_file.parent.mkdir(parents=True)
        wp_file.write_text(
            "---\nwork_package_id: WP01\ndependencies: []\n"
            "execution_mode: code_change\nowned_files:\n  - src/wp01/**\n"
            "authoritative_surface: src/wp01/\n---\n# WP01",
            encoding="utf-8",
        )
        _seed_planned(primary_dir, "WP01")

        # Coord dir: status only — LANE_STATE remains primary-owned.
        coord_dir = tmp_path / ".worktrees" / f"{mission_slug}-coord" / "kitty-specs" / mission_slug
        coord_dir.mkdir(parents=True)
        _seed_planned(coord_dir, "WP01")

        # Status surface points to coord (finalize-tasks seeds events there)
        class _FakeStatusSurface:
            read_dir = coord_dir

        # Non-planning ResolvedWorkspace — causes require_lanes_json to be called
        from specify_cli.workspace.context import ResolvedWorkspace

        fake_workspace = ResolvedWorkspace(
            mission_slug=mission_slug,
            wp_id="WP01",
            execution_mode="code_change",
            mode_source="frontmatter",
            resolution_kind="lane_workspace",
            workspace_name=f"{mission_slug}-lane-a",
            worktree_path=tmp_path / ".worktrees" / f"{mission_slug}-lane-a",
            branch_name=f"kitty/mission-{mission_slug}-lane-a",
            lane_id="lane-a",
            lane_wp_ids=["WP01"],
            context=None,
        )

        mock_gate = MagicMock()
        mock_gate.passed = True
        # FR-012 alignment: change_mode=None (a non-bulk_edit mission) means
        # change_mode != "bulk_edit", so the inference scan runs — it no-ops here
        # (no bulk-edit spec.md) and the flow proceeds to the workspace-create
        # sentinel below. Not a behavior regression.
        mock_gate.change_mode = None

        with (
            patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
            patch(
                "specify_cli.cli.commands.implement.detect_feature_context",
                return_value=("010", mission_slug),
            ),
            # read-surface-ssot-closeout WP05 / FR-001 / NFR-001: ``feature_dir``
            # now routes through the kind-aware placement seam
            # (``read_dir(SPEC)``), which is topology-blind and resolves the
            # primary dir directly (``tmp_path/kitty-specs/010-feature``,
            # exercised for real — no stub needed). ``_lanes_feature_dir``
            # independently resolves through LANE_STATE placement authority,
            # while the status surface remains ``coord_dir`` (#3371).
            patch(
                "specify_cli.cli.commands.implement.resolve_feature_target_branch",
                return_value="main",
            ),
            patch("specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git"),
            patch("specify_cli.cli.commands.implement._resolve_placement_ref", return_value=None),
            patch(
                "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
                return_value=_FakeStatusSurface(),
            ),
            patch(
                "specify_cli.bulk_edit.gate.ensure_occurrence_classification_ready",
                return_value=mock_gate,
            ),
            patch(
                "runtime.next.runtime_bridge.build_operational_context_for_claim",
                return_value=MagicMock(),
            ),
            patch(
                "specify_cli.cli.commands.implement.resolve_workspace_for_wp",
                return_value=fake_workspace,
            ),
            # Fail at workspace creation with a sentinel — not a lanes.json error
            patch(
                "specify_cli.cli.commands.implement.create_lane_workspace",
                side_effect=RuntimeError("__workspace_create_sentinel__"),
            ),
        ):
            with pytest.raises(typer.Exit):
                implement("WP01", mission=mission_slug, json_output=True, recover=False)

        payload = json.loads(capsys.readouterr().out.strip())
        error = payload.get("error", "")

        # KEY assertion: the pre-fix error must NOT appear
        assert "lanes.json is required" not in error, (
            f"Implement failed to read primary-partition lanes.json while STATUS "
            f"was coord-owned — #3371 regression. Got: {error!r}"
        )
        # We reached the workspace-create step, which confirms lanes.json was found
        assert "__workspace_create_sentinel__" in error, (
            f"Expected to pass lanes.json validation and reach workspace creation. Got: {error!r}"
        )


# ---------------------------------------------------------------------------
# T013 — NFR-003 spy: ProtectionPolicy.resolve reads I/O once at the boundary;
# is_protected() and commit_guard.evaluate() make ZERO further I/O reads.
# ---------------------------------------------------------------------------


class TestNFR003ProtectionPolicySingleBoundaryRead:
    """NFR-003: the protection decision I/O boundary is ProtectionPolicy.resolve (T013).

    Verifies that:
    - ``_load_kittify_config`` is called exactly ONCE (the config read) inside ``resolve``
    - ``_remote_default_branch`` is called at most ONCE inside ``resolve`` (only on absent key path)
    - Neither ``is_protected`` nor ``commit_guard.evaluate`` trigger additional I/O reads
    """

    def test_protection_decision_io_confined_to_resolve_boundary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Drive _protected_branch_status_commit_error and assert single-boundary I/O (T013)."""
        from specify_cli.cli.commands.implement import _protected_branch_status_commit_error
        from specify_cli.git import protection_policy as _pp_module

        # The autouse fixture sets SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1.
        # For this test we need the hatch OFF so we can observe the real protection decision.
        monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)

        # Spy: track calls to the two internal I/O helpers inside ProtectionPolicy.resolve
        kittify_read_count: list[int] = [0]
        remote_read_count: list[int] = [0]

        _real_load_kittify_config = _pp_module._load_kittify_config
        _real_remote_default_branch = _pp_module._remote_default_branch

        def _spy_load_kittify_config(repo_root: Path) -> dict:  # type: ignore[type-arg]
            kittify_read_count[0] += 1
            return _real_load_kittify_config(repo_root)

        def _spy_remote_default_branch(repo_root: Path) -> str | None:
            remote_read_count[0] += 1
            return _real_remote_default_branch(repo_root)

        with (
            patch.object(_pp_module, "_load_kittify_config", _spy_load_kittify_config),
            patch.object(_pp_module, "_remote_default_branch", _spy_remote_default_branch),
        ):
            # Call the decision function — "main" should be protected (no .kittify/config.yaml
            # override, so the default set includes "main"; hatch is OFF).
            result = _protected_branch_status_commit_error("main", tmp_path)

        # Config read happens exactly ONCE at the resolve boundary — not per is_protected call
        assert kittify_read_count[0] == 1, (
            f"_load_kittify_config called {kittify_read_count[0]} times; "
            "expected exactly 1 (boundary-resolved value, NFR-003)"
        )
        # Remote read happens at most ONCE (only on the absent-key path)
        assert remote_read_count[0] <= 1, (
            f"_remote_default_branch called {remote_read_count[0]} times; "
            "expected at most 1 (boundary-resolved value, NFR-003)"
        )
        # The decision itself: "main" is in the default protected set, no hatch active
        assert result is not None, "Expected a refusal message for protected branch 'main'"

    def test_is_protected_makes_no_io_after_resolve(
        self, tmp_path: Path
    ) -> None:
        """is_protected() is pure after resolve — zero filesystem/env reads (T013)."""
        from specify_cli.git.protection_policy import ProtectionPolicy
        from specify_cli.git import protection_policy as _pp_module

        io_call_count: list[int] = [0]

        def _counting_load(repo_root: Path) -> dict:  # type: ignore[type-arg]
            io_call_count[0] += 1
            return {}

        with patch.object(_pp_module, "_load_kittify_config", _counting_load):
            policy = ProtectionPolicy.resolve(tmp_path)
            count_after_resolve = io_call_count[0]
            # Call is_protected multiple times — must NOT trigger further I/O
            policy.is_protected("main")
            policy.is_protected("master")
            policy.is_protected("some-branch")

        assert io_call_count[0] == count_after_resolve, (
            f"is_protected triggered {io_call_count[0] - count_after_resolve} additional I/O read(s); "
            "expected zero (NFR-003: value object is I/O-free after resolve)"
        )
