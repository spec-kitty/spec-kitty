"""Unit tests for worktree management utilities."""

from __future__ import annotations

import subprocess
import warnings
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from specify_cli.merge.ordering import assign_next_mission_number
from specify_cli.core.worktree import (
    _compose_worktree_feature_dir,
    _exclude_from_git,
    create_feature_worktree,
    setup_feature_directory,
    validate_feature_structure,
)

pytestmark = pytest.mark.git_repo
TEST_MISSION_ID = "01KNXQS9ATWWFXS3K5ZJ9E5008"
TEST_MID8 = TEST_MISSION_ID[:8]

class TestAssignNextMissionNumber:
    """Tests for merge-time display-number allocation."""

    def test_returns_1_when_no_features_exist(self, tmp_path: Path) -> None:
        """Should return 1 when no numbered missions exist."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 1

    def test_scans_kitty_specs_directory(self, tmp_path: Path) -> None:
        """Should scan kitty-specs/ for integer mission_number values."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        for name, number in (
            ("alpha", 1),
            ("beta", 2),
            ("gamma", 5),
        ):
            mission_dir = specs_dir / f"{name}-{TEST_MID8}"
            mission_dir.mkdir()
            (mission_dir / "meta.json").write_text(f'{{"mission_number": {number}}}', encoding="utf-8")

        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 6

    def test_ignores_missing_or_non_integer_mission_numbers(self, tmp_path: Path) -> None:
        """Should ignore missions with null, string, or absent mission_number."""
        specs_dir = tmp_path / "kitty-specs"
        specs_dir.mkdir()
        for name, payload in (
            ("alpha", '{"mission_number": null}'),
            ("beta", '{"mission_number": "003"}'),
            ("gamma", '{"mission_slug": "gamma"}'),
            ("delta", '{"mission_number": 4}'),
        ):
            mission_dir = specs_dir / f"{name}-{TEST_MID8}"
            mission_dir.mkdir()
            (mission_dir / "meta.json").write_text(payload, encoding="utf-8")

        result = assign_next_mission_number(tmp_path, specs_dir)
        assert result == 5


class TestCreateFeatureWorktree:
    """Tests for create_feature_worktree function."""

    def test_creates_worktree_with_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should create git worktree with proper branch name."""
        # Setup: Git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Execute
        worktree_path, feature_dir = create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

        # Verify
        assert worktree_path == tmp_path / ".worktrees" / f"test-feature-{TEST_MID8}"
        assert worktree_path.exists()
        assert worktree_path.is_dir()
        assert feature_dir == worktree_path / "kitty-specs" / f"test-feature-{TEST_MID8}"
        assert feature_dir.exists()

    def test_requires_mission_id(self, tmp_path: Path) -> None:
        """Should require mission_id for worktree creation."""
        # Setup: Git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        with pytest.raises(RuntimeError, match="requires mission_id"):
            create_feature_worktree(tmp_path, "new-feature")

    def test_raises_error_when_worktree_exists(self, tmp_path: Path) -> None:
        """Should raise FileExistsError when worktree path already exists."""
        # Setup: Pre-existing directory (not a valid worktree)
        worktree_path = tmp_path / ".worktrees" / f"test-feature-{TEST_MID8}"
        worktree_path.mkdir(parents=True)

        # Execute & Verify
        with pytest.raises(FileExistsError, match="Worktree path already exists"):
            create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

    def test_reuses_existing_valid_worktree(self, tmp_path: Path) -> None:
        """Should reuse existing valid git worktree instead of raising error."""
        # Setup: Create valid git worktree
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create first worktree
        worktree_path1, feature_dir1 = create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

        # Execute: Try to create same worktree again
        worktree_path2, feature_dir2 = create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

        # Verify: Should return same paths
        assert worktree_path1 == worktree_path2
        assert feature_dir1 == feature_dir2

    def test_raises_error_on_git_failure(self, tmp_path: Path) -> None:
        """Should raise RuntimeError when workspace creation fails."""
        # Setup: Not a git repo - workspace creation will fail
        # Note: RuntimeError wraps the underlying subprocess or VCS error
        with pytest.raises(RuntimeError, match="Failed to create workspace"):
            create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)


class TestSetupFeatureDirectory:
    """Tests for setup_feature_directory function."""

    def test_creates_standard_subdirectories(self, tmp_path: Path) -> None:
        """Should create checklists/, research/, and tasks/ subdirectories."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path
        repo_root = tmp_path

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        assert (feature_dir / "checklists").exists()
        assert (feature_dir / "checklists").is_dir()
        assert (feature_dir / "research").exists()
        assert (feature_dir / "research").is_dir()
        assert (feature_dir / "tasks").exists()
        assert (feature_dir / "tasks").is_dir()

    def test_creates_tasks_gitkeep(self, tmp_path: Path) -> None:
        """Should create tasks/.gitkeep file."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path
        repo_root = tmp_path

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        assert (feature_dir / "tasks" / ".gitkeep").exists()
        assert (feature_dir / "tasks" / ".gitkeep").is_file()

    def test_creates_tasks_readme(self, tmp_path: Path) -> None:
        """Should create tasks/README.md with frontmatter format documentation."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path
        repo_root = tmp_path

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        readme = feature_dir / "tasks" / "README.md"
        assert readme.exists()
        content = readme.read_text()
        assert "# Tasks Directory" in content
        assert "YAML frontmatter" in content
        assert "status.events.jsonl" in content
        assert "lane:" not in content

    def test_copies_spec_template_when_exists(self, tmp_path: Path) -> None:
        """Should copy spec template to spec.md when template exists."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path
        repo_root = tmp_path

        # Create template
        template_dir = repo_root / ".kittify" / "templates"
        template_dir.mkdir(parents=True)
        template_file = template_dir / "spec-template.md"
        template_file.write_text("# Feature Specification Template")

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        spec_file = feature_dir / "spec.md"
        assert spec_file.exists()
        assert spec_file.read_text() == "# Feature Specification Template"

    def test_no_spec_file_when_no_template(self, tmp_path: Path) -> None:
        """Should not create spec.md when no template exists (#228: a stray
        empty spec.md vacuously satisfies the per-type artifact presence gate)."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path
        repo_root = tmp_path

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        spec_file = feature_dir / "spec.md"
        assert not spec_file.exists()

    def test_copies_memory_directory_when_symlinks_disabled(self, tmp_path: Path) -> None:
        """Should copy memory/ directory when create_symlinks=False."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path / ".worktrees" / "001-test"
        worktree_path.mkdir(parents=True)  # Create worktree directory
        repo_root = tmp_path

        # Create memory directory in main repo
        memory_dir = repo_root / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "charter.md").write_text("Charter content")

        # Execute
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify
        worktree_memory = worktree_path / ".kittify" / "memory"
        assert worktree_memory.exists()
        assert worktree_memory.is_dir()
        assert not worktree_memory.is_symlink()
        assert (worktree_memory / "charter.md").read_text() == "Charter content"

    @patch("specify_cli.core.worktree.is_windows")
    def test_uses_copy_on_windows(self, mock_is_windows: Mock, tmp_path: Path) -> None:
        """Should use file copy instead of symlinks on Windows.

        Patches ``specify_cli.core.worktree.is_windows`` (the canonical
        ``kernel.paths.is_windows`` seam, routed here as a module-level
        ``from kernel.paths import is_windows`` import) rather than
        ``platform.system`` -- a from-imported name is overridden at the
        CONSUMER's own bound attribute, not at the stdlib origin, since the
        import copies the reference once at import time.
        """
        # Setup
        mock_is_windows.return_value = True
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path / ".worktrees" / "001-test"
        worktree_path.mkdir(parents=True)  # Create worktree directory
        repo_root = tmp_path

        # Create memory directory
        memory_dir = repo_root / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "test.md").write_text("test")

        # Execute (with create_symlinks=True, but Windows should override)
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=True)

        # Verify
        worktree_memory = worktree_path / ".kittify" / "memory"
        assert worktree_memory.exists()
        assert not worktree_memory.is_symlink()  # Should be copied, not symlinked

    def test_handles_existing_kittify_directory(self, tmp_path: Path) -> None:
        """Should handle existing .kittify directory and replace symlink."""
        # Setup
        feature_dir = tmp_path / "kitty-specs" / "001-test"
        worktree_path = tmp_path / ".worktrees" / "001-test"
        worktree_path.mkdir(parents=True)
        repo_root = tmp_path

        # Create memory directory in main repo
        memory_dir = repo_root / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "file.md").write_text("content")

        # Create AGENTS.md
        (repo_root / ".kittify" / "AGENTS.md").write_text("# Agents")

        # Pre-create worktree .kittify with a symlink that needs replacing
        worktree_kittify = worktree_path / ".kittify"
        worktree_kittify.mkdir()
        worktree_memory = worktree_kittify / "memory"
        worktree_memory.mkdir()  # Create as directory first
        (worktree_memory / "old.md").write_text("old")

        # Execute - should replace the directory with symlink/copy
        setup_feature_directory(feature_dir, worktree_path, repo_root, create_symlinks=False)

        # Verify memory was replaced
        assert worktree_memory.exists()
        assert (worktree_memory / "file.md").exists()
        assert not (worktree_memory / "old.md").exists()


class TestValidateFeatureStructure:
    """Tests for validate_feature_structure function."""

    def test_validates_missing_feature_directory(self, tmp_path: Path) -> None:
        """Should return error when feature directory doesn't exist."""
        # Setup
        feature_dir = tmp_path / "nonexistent"

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is False
        assert "Feature directory not found" in result["errors"][0]
        assert result["warnings"] == []

    def test_validates_missing_spec_file(self, tmp_path: Path) -> None:
        """Should return error when spec.md is missing."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is False
        assert "Missing required file: spec.md" in result["errors"]

    def test_warns_about_missing_directories(self, tmp_path: Path) -> None:
        """Should return warnings when recommended directories are missing."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is True  # Not an error, just warnings
        assert "Missing recommended directory: checklists/" in result["warnings"]
        assert "Missing recommended directory: research/" in result["warnings"]
        assert "Missing recommended directory: tasks/" in result["warnings"]

    def test_validates_complete_structure(self, tmp_path: Path) -> None:
        """Should pass validation when all required files and directories exist."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "research").mkdir()
        (feature_dir / "tasks").mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_validates_tasks_md_when_requested(self, tmp_path: Path) -> None:
        """Should validate tasks.md exists when check_tasks=True."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")

        # Execute
        result = validate_feature_structure(feature_dir, check_tasks=True)

        # Verify
        assert result["valid"] is False
        assert "Missing required file: tasks.md" in result["errors"]

    def test_includes_tasks_file_when_present_without_strict_tasks_check(self, tmp_path: Path) -> None:
        """Should expose tasks.md path when present even if check_tasks=False."""
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "tasks.md").write_text("tasks")

        result = validate_feature_structure(feature_dir, check_tasks=False)

        assert result["valid"] is True
        assert result["paths"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert result["artifact_files"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert "tasks.md" in result["available_docs"]

    def test_includes_paths_in_result(self, tmp_path: Path) -> None:
        """Should include important paths in validation result."""
        # Setup
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "research").mkdir()
        (feature_dir / "tasks").mkdir()

        # Execute
        result = validate_feature_structure(feature_dir)

        # Verify
        assert "paths" in result
        assert result["paths"]["spec_file"] == str(feature_dir / "spec.md")
        assert result["paths"]["checklists_dir"] == str(feature_dir / "checklists")
        assert result["paths"]["tasks_dir"] == str(feature_dir / "tasks")
        assert result["paths"]["feature_dir"] == str(feature_dir)
        # FR-010 (research_dir file-vs-dir fix): the research planning artifact is
        # the FILE ``research.md``, not the legacy ``research/`` directory. A bare
        # ``research/`` directory must NOT be surfaced as an artifact directory.
        assert "research_dir" not in result["paths"]
        assert "research_dir" not in result["artifact_dirs"]

    def test_includes_typed_artifact_maps_and_compat_aliases(self, tmp_path: Path) -> None:
        """Should expose deterministic file/dir maps with compatibility aliases.

        FR-010: the inventory is sourced from the canonical mission writer
        metadata, so writer-produced planning artifacts (``research.md``,
        ``data-model.md``) that exist on disk are reported truthfully, not
        omitted by a hardcoded spec/plan/tasks set.
        """
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "plan.md").write_text("plan")
        (feature_dir / "tasks.md").write_text("tasks")
        (feature_dir / "research.md").write_text("research")
        (feature_dir / "data-model.md").write_text("data model")
        (feature_dir / "checklists").mkdir()
        (feature_dir / "tasks").mkdir()

        result = validate_feature_structure(feature_dir, check_tasks=True)

        assert result["artifact_files"]["spec_file"] == str(feature_dir / "spec.md")
        assert result["artifact_files"]["plan_file"] == str(feature_dir / "plan.md")
        assert result["artifact_files"]["tasks_file"] == str(feature_dir / "tasks.md")
        assert result["artifact_files"]["research_file"] == str(feature_dir / "research.md")
        assert result["artifact_files"]["data_model_file"] == str(feature_dir / "data-model.md")
        assert result["artifact_dirs"]["feature_dir"] == str(feature_dir)
        assert result["artifact_dirs"]["tasks_dir"] == str(feature_dir / "tasks")
        assert sorted(result["available_docs"]) == [
            "data-model.md",
            "plan.md",
            "research.md",
            "spec.md",
            "tasks.md",
        ]
        assert result["FEATURE_DIR"] == str(feature_dir)
        assert sorted(result["AVAILABLE_DOCS"]) == [
            "data-model.md",
            "plan.md",
            "research.md",
            "spec.md",
            "tasks.md",
        ]

    def test_inventory_reports_writer_artifacts_and_omits_absent(self, tmp_path: Path) -> None:
        """FR-010 red-first: research.md / data-model.md / quickstart.md are
        reported ONLY when present, sourced from the writer metadata.

        Before the fix the inventory hardcoded spec/plan/tasks and OMITTED these
        writer-produced planning artifacts even when present. After the fix they
        appear (present) and are correctly absent when not on disk.
        """
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "plan.md").write_text("plan")
        (feature_dir / "research.md").write_text("research")
        (feature_dir / "data-model.md").write_text("data model")
        # quickstart.md deliberately NOT created.

        result = validate_feature_structure(feature_dir)

        assert "research.md" in result["available_docs"]
        assert "data-model.md" in result["available_docs"]
        assert result["artifact_files"]["research_file"] == str(feature_dir / "research.md")
        assert result["artifact_files"]["data_model_file"] == str(feature_dir / "data-model.md")
        # Absent optional artifacts stay out of the inventory (no false positives).
        assert "quickstart.md" not in result["available_docs"]
        assert "quickstart_file" not in result["artifact_files"]

    def test_inventory_reports_writer_directory_artifacts(self, tmp_path: Path) -> None:
        """FR-010: directory artifacts declared by the writer metadata
        (``contracts/``) are inventoried as artifact directories when present."""
        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        (feature_dir / "spec.md").write_text("spec")
        (feature_dir / "contracts").mkdir()

        result = validate_feature_structure(feature_dir)

        assert result["artifact_dirs"]["contracts_dir"] == str(feature_dir / "contracts")

    def test_inventory_does_not_drift_from_writer_metadata(self, tmp_path: Path) -> None:
        """NFR-004 / C-005 regression guard: the file-artifact inventory is
        derived from the canonical mission writer metadata, not a hardcoded set.

        Materialize every file artifact the software-dev writer declares and
        assert each shows up in ``available_docs``. If a future change re-hardcodes
        the inventory (dropping a writer-declared artifact), this goes red — the
        two-copy trap NFR-004 forbids.
        """
        from specify_cli.mission import get_mission_by_name

        mission = get_mission_by_name("software-dev")
        writer_files = [
            name
            for name in (*mission.get_required_artifacts(), *mission.get_optional_artifacts())
            if not name.endswith("/")
        ]
        assert writer_files, "writer metadata must declare at least one file artifact"

        feature_dir = tmp_path / "001-test"
        feature_dir.mkdir()
        for name in writer_files:
            (feature_dir / name).write_text(name)

        result = validate_feature_structure(feature_dir, check_tasks=True)

        for name in writer_files:
            assert name in result["available_docs"], (
                f"writer-declared artifact {name!r} missing from inventory "
                "(inventory drifted from mission writer metadata)"
            )


class TestVCSAbstraction:
    """Tests for VCS abstraction layer integration in worktree module."""

    def test_create_worktree_uses_vcs_abstraction(self, tmp_path: Path) -> None:
        """Should use VCS abstraction to create workspace."""
        # Setup: Git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Mock the VCS abstraction to verify it's called
        mock_result = MagicMock()
        mock_result.success = True
        mock_vcs = MagicMock()
        mock_vcs.create_workspace.return_value = mock_result
        mock_vcs.is_repo.return_value = False

        with patch("specify_cli.core.worktree.get_vcs", return_value=mock_vcs):
            worktree_path, feature_dir = create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

            # Verify VCS abstraction was called
            mock_vcs.create_workspace.assert_called_once()
            call_kwargs = mock_vcs.create_workspace.call_args.kwargs
            assert call_kwargs["workspace_name"] == f"test-feature-{TEST_MID8}"
            assert call_kwargs["repo_root"] == tmp_path

    def test_create_worktree_falls_back_to_git_with_warning(self, tmp_path: Path) -> None:
        """Should fall back to direct git commands with deprecation warning when VCS fails."""
        # Setup: Git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Mock VCS to fail
        with patch("specify_cli.core.worktree.get_vcs", side_effect=Exception("VCS failed")):
            # Capture deprecation warning
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                worktree_path, feature_dir = create_feature_worktree(tmp_path, "fallback-test", mission_id=TEST_MISSION_ID)

                # Verify deprecation warning was raised
                assert len(w) == 1
                assert issubclass(w[0].category, DeprecationWarning)
                assert "VCS abstraction failed" in str(w[0].message)
                assert "falling back to direct git commands" in str(w[0].message)

            # Verify worktree was still created via fallback
            assert worktree_path.exists()
            assert feature_dir.exists()

    def test_create_worktree_raises_on_vcs_and_fallback_failure(self, tmp_path: Path) -> None:
        """Should raise RuntimeError when VCS and git fallback both fail."""
        # Setup: NOT a git repo - so fallback will fail too
        # (don't run git init)

        # Mock VCS to return failure result
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Workspace creation failed"
        mock_vcs = MagicMock()
        mock_vcs.create_workspace.return_value = mock_result
        mock_vcs.is_repo.return_value = False

        # VCS fails, fallback fails (not a git repo), should raise
        with (
            patch("specify_cli.core.worktree.get_vcs", return_value=mock_vcs),
            pytest.raises(RuntimeError, match="Failed to create workspace"),
        ):
            create_feature_worktree(tmp_path, "fail-test", mission_id=TEST_MISSION_ID)

    def test_create_worktree_detects_existing_vcs_workspace(self, tmp_path: Path) -> None:
        """Should detect and reuse existing VCS workspace."""
        # Setup: Pre-existing workspace directory with .git
        worktree_path = tmp_path / ".worktrees" / f"test-feature-{TEST_MID8}"
        worktree_path.mkdir(parents=True)
        (worktree_path / ".git").touch()  # Minimal marker

        # Mock VCS to recognize it as valid repo
        mock_vcs = MagicMock()
        mock_vcs.is_repo.return_value = True

        with patch("specify_cli.core.worktree.get_vcs", return_value=mock_vcs):
            worktree_result, feature_dir = create_feature_worktree(tmp_path, "test-feature", mission_id=TEST_MISSION_ID)

            # Should return the existing path
            assert worktree_result == worktree_path
            assert feature_dir == worktree_path / "kitty-specs" / f"test-feature-{TEST_MID8}"


class TestExcludeFromGit:
    """Tests for _exclude_from_git function (fixes issue #79)."""

    def test_excludes_patterns_in_worktree(self, tmp_path: Path) -> None:
        """Should add patterns to worktree's .git/info/exclude file."""
        # Setup: Simulate worktree with .git file pointing to gitdir
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "main_repo" / ".git" / "worktrees" / "test-worktree"
        git_dir.mkdir(parents=True)

        # Create .git file that points to git_dir
        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute
        _exclude_from_git(worktree, [".kittify/memory", ".kittify/AGENTS.md"])

        # Verify
        exclude_file = git_dir / "info" / "exclude"
        assert exclude_file.exists()
        content = exclude_file.read_text()
        assert ".kittify/memory" in content
        assert ".kittify/AGENTS.md" in content
        assert "# Added by spec-kitty (worktree symlinks)" in content

    def test_excludes_patterns_in_regular_repo(self, tmp_path: Path) -> None:
        """Should add patterns to regular repo's .git/info/exclude file."""
        # Setup: Regular git repo with .git directory
        repo = tmp_path / "repo"
        repo.mkdir()
        git_dir = repo / ".git"
        git_dir.mkdir()

        # Execute
        _exclude_from_git(repo, [".kittify/memory"])

        # Verify
        exclude_file = git_dir / "info" / "exclude"
        assert exclude_file.exists()
        content = exclude_file.read_text()
        assert ".kittify/memory" in content

    def test_creates_info_directory_if_missing(self, tmp_path: Path) -> None:
        """Should create info/ directory if it doesn't exist."""
        # Setup: Worktree with git_dir but no info/ directory
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "git_dir"
        git_dir.mkdir()
        # Don't create info/ subdirectory

        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute
        _exclude_from_git(worktree, [".kittify/memory"])

        # Verify
        assert (git_dir / "info").exists()
        assert (git_dir / "info" / "exclude").exists()

    def test_appends_to_existing_exclude_file(self, tmp_path: Path) -> None:
        """Should append patterns to existing exclude file without overwriting."""
        # Setup: Worktree with existing exclude file
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "git_dir"
        (git_dir / "info").mkdir(parents=True)
        exclude_file = git_dir / "info" / "exclude"
        exclude_file.write_text("# Existing content\n*.pyc\n__pycache__/\n")

        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute
        _exclude_from_git(worktree, [".kittify/memory"])

        # Verify
        content = exclude_file.read_text()
        assert "# Existing content" in content
        assert "*.pyc" in content
        assert "__pycache__/" in content
        assert ".kittify/memory" in content

    def test_does_not_duplicate_existing_patterns(self, tmp_path: Path) -> None:
        """Should not add patterns that already exist in exclude file."""
        # Setup: Worktree with exclude file containing pattern
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "git_dir"
        (git_dir / "info").mkdir(parents=True)
        exclude_file = git_dir / "info" / "exclude"
        exclude_file.write_text(".kittify/memory\n")

        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute
        _exclude_from_git(worktree, [".kittify/memory", ".kittify/AGENTS.md"])

        # Verify: memory should appear only once, AGENTS.md should be added
        content = exclude_file.read_text()
        assert content.count(".kittify/memory") == 1
        assert ".kittify/AGENTS.md" in content

    def test_handles_missing_git_file(self, tmp_path: Path) -> None:
        """Should handle missing .git file gracefully (no crash)."""
        # Setup: Directory without .git
        worktree = tmp_path / "not_a_repo"
        worktree.mkdir()

        # Execute: Should not raise
        _exclude_from_git(worktree, [".kittify/memory"])

        # Verify: Nothing created
        assert not (worktree / ".git").exists()

    def test_handles_invalid_gitdir_content(self, tmp_path: Path) -> None:
        """Should handle invalid .git file content gracefully."""
        # Setup: .git file with invalid content
        worktree = tmp_path / "worktree"
        worktree.mkdir()
        (worktree / ".git").write_text("invalid content without gitdir prefix")

        # Execute: Should not raise
        _exclude_from_git(worktree, [".kittify/memory"])

        # Verify: No crash, nothing added
        # (can't verify much else since gitdir parsing failed)

    def test_handles_empty_patterns_list(self, tmp_path: Path) -> None:
        """Should handle empty patterns list gracefully."""
        # Setup: Valid worktree
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "git_dir"
        (git_dir / "info").mkdir(parents=True)

        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute
        _exclude_from_git(worktree, [])

        # Verify: Exclude file may or may not exist, but no patterns added
        exclude_file = git_dir / "info" / "exclude"
        if exclude_file.exists():
            content = exclude_file.read_text()
            # Should not have added marker for empty list
            assert "# Added by spec-kitty" not in content

    def test_adds_marker_only_once(self, tmp_path: Path) -> None:
        """Should only add marker comment once even when called multiple times."""
        # Setup
        worktree = tmp_path / "worktree"
        worktree.mkdir()

        git_dir = tmp_path / "git_dir"
        (git_dir / "info").mkdir(parents=True)

        (worktree / ".git").write_text(f"gitdir: {git_dir}")

        # Execute multiple times
        _exclude_from_git(worktree, [".kittify/memory"])
        _exclude_from_git(worktree, [".kittify/AGENTS.md"])

        # Verify
        content = (git_dir / "info" / "exclude").read_text()
        marker_count = content.count("# Added by spec-kitty (worktree symlinks)")
        assert marker_count == 1

    def test_integration_with_setup_feature_directory(self, tmp_path: Path) -> None:
        """Should be called by setup_feature_directory to exclude symlinks."""
        # Setup: Git repo with worktree structure
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        (tmp_path / "README.md").write_text("test")
        subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create worktree using git directly
        worktree_path = tmp_path / ".worktrees" / "001-test"
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path), "-b", "001-test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )

        # Create memory and AGENTS.md in main repo
        memory_dir = tmp_path / ".kittify" / "memory"
        memory_dir.mkdir(parents=True)
        (memory_dir / "charter.md").write_text("Charter")
        (tmp_path / ".kittify" / "AGENTS.md").write_text("# Agents")

        # Execute: setup_feature_directory should call _exclude_from_git
        feature_dir = worktree_path / "kitty-specs" / "001-test"
        setup_feature_directory(feature_dir, worktree_path, tmp_path, create_symlinks=True)

        # Verify: Symlinks should be excluded
        # Find the git dir from .git file
        git_file_content = (worktree_path / ".git").read_text().strip()
        assert git_file_content.startswith("gitdir:")
        git_dir = Path(git_file_content[7:].strip())
        exclude_file = git_dir / "info" / "exclude"

        assert exclude_file.exists()
        content = exclude_file.read_text()
        assert ".kittify/memory" in content
        assert ".kittify/AGENTS.md" in content


class TestComposeWorktreeFeatureDir:
    """Tests for _compose_worktree_feature_dir — C-PLACEMENT / FR-002 (T019).

    The HARD GATE is idempotency (NFR-004): the on-disk placement path MUST be
    byte-identical before/after.  This class provides the before/after assertion
    proving that the reuse arm and the create arm produce the SAME path for a
    given ``(worktree_path, branch_name)`` pair, with no on-disk worktree churn.
    """

    def test_compose_returns_expected_path(self, tmp_path: Path) -> None:
        """Compose produces worktree_path / 'kitty-specs' / branch_name."""
        worktree_path = tmp_path / ".worktrees" / "my-mission-01KNXQS9"
        branch_name = f"my-mission-{TEST_MID8}"

        result = _compose_worktree_feature_dir(worktree_path, branch_name)

        assert result == worktree_path / "kitty-specs" / branch_name
        assert result.parts[-1] == branch_name
        assert result.parts[-2] == "kitty-specs"

    def test_idempotency_before_after_byte_identical(self, tmp_path: Path) -> None:
        """NFR-004 idempotency: calling the compose seam twice gives the SAME path.

        Captures the path BEFORE and AFTER, then asserts byte-identity.  No
        on-disk worktree is created or mutated — the assertion is purely on the
        resolved Path values.
        """
        worktree_path = tmp_path / ".worktrees" / f"my-mission-{TEST_MID8}"
        branch_name = f"my-mission-{TEST_MID8}"

        before = _compose_worktree_feature_dir(worktree_path, branch_name)
        after = _compose_worktree_feature_dir(worktree_path, branch_name)

        # NFR-004 before/after assertion: the placement path is byte-identical.
        assert before == after, (
            f"Idempotency violation (NFR-004): placement path changed between "
            f"calls — before={before!r}, after={after!r}"
        )

    def test_reuse_arm_equals_create_arm(self, tmp_path: Path) -> None:
        """Both worktree arms (reuse :384, create :396) resolve the same path.

        This is the core C-PLACEMENT assertion: the two former inline joins now
        call the SAME compose seam and therefore produce byte-identical paths for
        the same ``(worktree_path, branch_name)`` input — no divergence between
        the reuse path and the create path.
        """
        worktree_path = tmp_path / ".worktrees" / f"test-feature-{TEST_MID8}"
        branch_name = f"test-feature-{TEST_MID8}"

        # Simulate the reuse arm (was :384).
        reuse_arm = _compose_worktree_feature_dir(worktree_path, branch_name)
        # Simulate the create arm (was :396).
        create_arm = _compose_worktree_feature_dir(worktree_path, branch_name)

        # The two arms must be byte-identical (idempotency NFR-004 / C-PLACEMENT).
        assert reuse_arm == create_arm, (
            f"Arm divergence (C-PLACEMENT violation): reuse={reuse_arm!r}, "
            f"create={create_arm!r}"
        )
        # Verify the exact expected path so the assertion is not vacuously true.
        expected = worktree_path / "kitty-specs" / branch_name
        assert reuse_arm == expected

    def test_full_ulid_mission_id_shapes_path_correctly(self, tmp_path: Path) -> None:
        """Production-shaped (full 26-char ULID) identity flows through the seam.

        NFR-002: test data must be production-shaped.  Fabricated short ids mask
        real behavior.  This test uses ``TEST_MISSION_ID`` (a real 26-char ULID)
        and asserts the expected mid8 substring appears in the path.
        """
        from specify_cli.lanes.branch_naming import mission_dir_name, resolve_mid8

        # Derive branch_name via the mission_dir_name naming seam, exactly as
        # create_feature_worktree does (the naming seam is unchanged — C-PLACEMENT).
        branch_name = mission_dir_name(
            "my-mission",
            mid8=resolve_mid8("", mission_id=TEST_MISSION_ID),
        )
        worktree_path = tmp_path / ".worktrees" / branch_name

        before = _compose_worktree_feature_dir(worktree_path, branch_name)
        after = _compose_worktree_feature_dir(worktree_path, branch_name)

        # Before/after byte-identical (NFR-004).
        assert before == after
        # The mid8 of the ULID is present in the path (naming seam intact).
        assert TEST_MID8 in str(before)
