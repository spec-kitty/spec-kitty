"""Tests for specify_cli.runtime.migrate -- migration classification and execution.

Covers:
- T020: classify_asset() classification accuracy
- T021: execute_migration() dry-run and actual execution
- T023: Dry-run correctness and idempotency (G3, 1A-03, 1A-04)
- T024: Customized files moved to overrides (F-Legacy-003, 1A-05)
- T025: SUPERSEDED disposition and version-skew regression
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.runtime.migrate import (

    AssetDisposition,
    MigrationReport,
    classify_asset,
    execute_migration,
)

import pytest

pytestmark = pytest.mark.git_repo

# ---------------------------------------------------------------------------
# Helpers: package asset setup
# ---------------------------------------------------------------------------

def _setup_package_assets(package_root: Path, mission: str = "software-dev") -> None:
    """Create a minimal package asset tree (immutable comparison target)."""
    mission_dir = package_root / mission
    (mission_dir / "templates").mkdir(parents=True, exist_ok=True)
    (mission_dir / "templates" / "spec.md").write_text("package spec content v2")
    (mission_dir / "templates" / "plan.md").write_text("package plan content v2")
    (mission_dir / "command-templates").mkdir(parents=True, exist_ok=True)
    (mission_dir / "command-templates" / "implement.md").write_text("package implement content v2")
    (package_root / "AGENTS.md").write_text("package agents content v2")
    (mission_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (mission_dir / "scripts" / "deploy.sh").write_text("package deploy script v2")

# ---------------------------------------------------------------------------
# Helpers: set up project and global directory structures
# ---------------------------------------------------------------------------

def _setup_global(global_home: Path, mission: str = "software-dev") -> None:
    """Create a minimal global runtime directory with sample shared assets."""
    mission_dir = global_home / "missions" / mission
    # templates/spec.md
    (mission_dir / "templates").mkdir(parents=True, exist_ok=True)
    (mission_dir / "templates" / "spec.md").write_text("global spec content")
    # templates/plan.md
    (mission_dir / "templates" / "plan.md").write_text("global plan content")
    # command-templates/implement.md
    (mission_dir / "command-templates").mkdir(parents=True, exist_ok=True)
    (mission_dir / "command-templates" / "implement.md").write_text(
        "global implement content"
    )
    # AGENTS.md at global root and under missions/ (for package_root compatibility)
    (global_home / "AGENTS.md").write_text("global agents content")
    missions_dir = global_home / "missions"
    (missions_dir / "AGENTS.md").write_text("global agents content")
    # scripts/deploy.sh
    (mission_dir / "scripts").mkdir(parents=True, exist_ok=True)
    (mission_dir / "scripts" / "deploy.sh").write_text("global deploy script")

def _setup_project_kittify(
    project_dir: Path,
    *,
    identical_files: dict[str, str] | None = None,
    customized_files: dict[str, str] | None = None,
    project_specific_files: dict[str, str] | None = None,
    unknown_files: dict[str, str] | None = None,
) -> Path:
    """Create a per-project .kittify/ directory with controlled content.

    Args:
        identical_files: rel_path -> content matching global exactly
        customized_files: rel_path -> content differing from global
        project_specific_files: rel_path -> content in project-specific paths
        unknown_files: rel_path -> content in unknown paths

    Returns:
        Path to the .kittify/ directory.
    """
    kittify = project_dir / ".kittify"
    for file_map in [
        identical_files,
        customized_files,
        project_specific_files,
        unknown_files,
    ]:
        if file_map:
            for rel, content in file_map.items():
                p = kittify / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(content)
    return kittify

# ---------------------------------------------------------------------------
# T020: classify_asset() tests
# ---------------------------------------------------------------------------

class TestClassifyAsset:
    """Test the classify_asset() function for all disposition types."""

    def test_project_specific_config_yaml(self, tmp_path: Path) -> None:
        """config.yaml is always PROJECT_SPECIFIC."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "config.yaml"
        f.parent.mkdir(parents=True)
        f.write_text("agents:\n  available:\n    - claude\n")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_project_specific_metadata_yaml(self, tmp_path: Path) -> None:
        """metadata.yaml is always PROJECT_SPECIFIC."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "metadata.yaml"
        f.parent.mkdir(parents=True)
        f.write_text("version: 1.0\n")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_project_specific_memory_dir(self, tmp_path: Path) -> None:
        """Files under memory/ are always PROJECT_SPECIFIC."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "memory" / "notes.md"
        f.parent.mkdir(parents=True)
        f.write_text("some notes")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_project_specific_workspaces(self, tmp_path: Path) -> None:
        """Files under workspaces/ are always PROJECT_SPECIFIC."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "workspaces" / "state.json"
        f.parent.mkdir(parents=True)
        f.write_text("{}")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_project_specific_logs(self, tmp_path: Path) -> None:
        """Files under logs/ are always PROJECT_SPECIFIC."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "logs" / "2026-02-09.log"
        f.parent.mkdir(parents=True)
        f.write_text("log entry")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_project_specific_overrides(self, tmp_path: Path) -> None:
        """Files under overrides/ are always PROJECT_SPECIFIC (already migrated)."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "overrides" / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("custom override")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.PROJECT_SPECIFIC

    def test_identical_file(self, tmp_path: Path) -> None:
        """File byte-identical to global counterpart is IDENTICAL."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("global spec content")  # Same as global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

    def test_customized_file(self, tmp_path: Path) -> None:
        """File differing from global counterpart is CUSTOMIZED."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("customized spec content")  # Differs from global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.CUSTOMIZED

    def test_customized_file_no_global_counterpart(self, tmp_path: Path) -> None:
        """Shared asset with no global counterpart is CUSTOMIZED."""
        global_home = tmp_path / "global"
        global_home.mkdir()

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "custom-template.md"
        f.parent.mkdir(parents=True)
        f.write_text("user-created template")

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.CUSTOMIZED

    def test_agents_md_identical(self, tmp_path: Path) -> None:
        """AGENTS.md byte-identical to global is IDENTICAL."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "AGENTS.md"
        f.parent.mkdir(parents=True)
        f.write_text("global agents content")  # Same as global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

    def test_agents_md_customized(self, tmp_path: Path) -> None:
        """AGENTS.md differing from global is CUSTOMIZED."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "AGENTS.md"
        f.parent.mkdir(parents=True)
        f.write_text("my custom agents list")  # Differs from global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.CUSTOMIZED

    def test_command_templates_identical(self, tmp_path: Path) -> None:
        """command-templates file identical to global is IDENTICAL."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "command-templates" / "implement.md"
        f.parent.mkdir(parents=True)
        f.write_text("global implement content")  # Same as global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

    def test_scripts_identical(self, tmp_path: Path) -> None:
        """scripts/ file identical to global is IDENTICAL."""
        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "scripts" / "deploy.sh"
        f.parent.mkdir(parents=True)
        f.write_text("global deploy script")  # Same as global

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

    def test_unknown_path(self, tmp_path: Path) -> None:
        """File in an unrecognized path is UNKNOWN."""
        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "random-stuff" / "notes.txt"
        f.parent.mkdir(parents=True)
        f.write_text("something")
        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.UNKNOWN

    def test_filecmp_uses_shallow_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify filecmp.cmp is called with shallow=False (byte comparison, not just stat)."""
        import filecmp as _filecmp

        calls: list[dict] = []
        original_cmp = _filecmp.cmp

        def tracking_cmp(f1, f2, shallow=True):
            calls.append({"f1": f1, "f2": f2, "shallow": shallow})
            return original_cmp(f1, f2, shallow=shallow)

        monkeypatch.setattr("specify_cli.runtime.migrate.filecmp.cmp", tracking_cmp)

        global_home = tmp_path / "global"
        _setup_global(global_home)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("global spec content")

        classify_asset(f, global_home, kittify)

        assert len(calls) == 1
        assert calls[0]["shallow"] is False

# ---------------------------------------------------------------------------
# T021: execute_migration() tests
# ---------------------------------------------------------------------------

class TestExecuteMigration:
    """Test the execute_migration() function."""

    def test_returns_migration_report(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """execute_migration returns a MigrationReport instance."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        _setup_project_kittify(
            project,
            project_specific_files={"config.yaml": "agents: [claude]"},
        )

        report = execute_migration(project, dry_run=True)
        assert isinstance(report, MigrationReport)

    def test_mixed_dispositions(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reports correct counts for mixed file types."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={
                "templates/spec.md": "global spec content",
                "templates/plan.md": "global plan content",
            },
            customized_files={
                "templates/tasks.md": "my custom tasks template",
            },
            project_specific_files={
                "config.yaml": "agents: [claude]",
                "memory/notes.md": "project notes",
            },
            unknown_files={
                "random/stuff.txt": "mystery file",
            },
        )

        report = execute_migration(project, dry_run=True)
        # Report lists are populated in sorted-path scan order (execute_migration
        # walks `sorted(kittify_dir.rglob("*"))`); pinning the exact members (not
        # just the count) makes an add/rename/drop of any tracked file fail here.
        assert report.removed == [
            kittify / "templates" / "plan.md", kittify / "templates" / "spec.md"
        ]  # spec.md + plan.md are identical
        assert report.moved == [
            (kittify / "templates" / "tasks.md", kittify / "overrides" / "templates" / "tasks.md")
        ]  # tasks.md is customized
        assert report.kept == [
            kittify / "config.yaml", kittify / "memory" / "notes.md"
        ]  # config.yaml + memory/notes.md
        assert report.unknown == [kittify / "random" / "stuff.txt"]

    def test_actual_execution_removes_identical(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-dry-run removes identical files from filesystem."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={"templates/spec.md": "global spec content"},
            project_specific_files={"config.yaml": "keep me"},
        )

        report = execute_migration(project, dry_run=False)

        assert report.removed == [kittify / "templates" / "spec.md"]
        # Identical file should be gone from filesystem
        assert not (kittify / "templates" / "spec.md").exists()
        # Project-specific file should still exist
        assert (kittify / "config.yaml").exists()

    def test_actual_execution_moves_customized_to_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-dry-run moves customized files to overrides/.

        Uses a file with no package counterpart (user-created template)
        to trigger the CUSTOMIZED disposition.
        """
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={"templates/my-custom-template.md": "customized content"},
        )

        report = execute_migration(project, dry_run=False)

        assert report.moved == [
            (
                kittify / "templates" / "my-custom-template.md",
                kittify / "overrides" / "templates" / "my-custom-template.md",
            )
        ]
        # Original should be gone
        assert not (kittify / "templates" / "my-custom-template.md").exists()
        # Override should exist with correct content
        override = kittify / "overrides" / "templates" / "my-custom-template.md"
        assert override.exists()
        assert override.read_text() == "customized content"

    def test_cleanup_empty_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After removing all files, empty shared asset dirs are cleaned up."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={"templates/spec.md": "global spec content"},
        )

        execute_migration(project, dry_run=False)

        # templates/ dir should be cleaned up (it's empty now)
        assert not (kittify / "templates").exists()

    def test_cleanup_does_not_remove_project_specific_dirs(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Cleanup does NOT remove project-specific directories even if empty."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            project_specific_files={"config.yaml": "keep me"},
        )
        # Create an empty project-specific dir
        (kittify / "memory").mkdir(exist_ok=True)

        execute_migration(project, dry_run=False)

        # memory/ should still exist even though it's empty
        assert (kittify / "memory").exists()

# ---------------------------------------------------------------------------
# T023: Dry-run and idempotency tests (G3, 1A-03, 1A-04)
# ---------------------------------------------------------------------------

class TestMigrateDryRun:
    """Dry-run reports correct dispositions without modifying FS (G3, 1A-03)."""

    def test_dry_run_no_filesystem_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dry-run must not modify any files on the filesystem."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={"templates/spec.md": "global spec content"},
            customized_files={"templates/tasks.md": "my custom tasks"},
            project_specific_files={"config.yaml": "keep me"},
        )

        # Capture filesystem state before
        files_before = set(kittify.rglob("*"))

        report = execute_migration(project, dry_run=True)

        # Verify report has correct dispositions
        assert report.removed == [kittify / "templates" / "spec.md"]
        assert report.moved == [
            (kittify / "templates" / "tasks.md", kittify / "overrides" / "templates" / "tasks.md")
        ]
        assert report.kept == [kittify / "config.yaml"]
        assert report.dry_run is True

        # Verify filesystem is UNCHANGED
        files_after = set(kittify.rglob("*"))
        assert files_before == files_after

        # Verify all original files still exist with original content
        assert (kittify / "templates" / "spec.md").read_text() == "global spec content"
        assert (kittify / "templates" / "tasks.md").read_text() == "my custom tasks"
        assert (kittify / "config.yaml").read_text() == "keep me"

class TestMigrateIdempotent:
    """Running migrate twice produces identical outcome (G3, 1A-04)."""

    def test_migrate_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Second run on already-migrated project is a no-op."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={
                "templates/spec.md": "global spec content",
                "templates/plan.md": "global plan content",
            },
            customized_files={
                "templates/tasks.md": "my custom tasks",
            },
            project_specific_files={
                "config.yaml": "keep me",
            },
        )

        # First migration
        report1 = execute_migration(project, dry_run=False)
        assert report1.removed == [
            kittify / "templates" / "plan.md", kittify / "templates" / "spec.md"
        ]
        assert report1.moved == [
            (kittify / "templates" / "tasks.md", kittify / "overrides" / "templates" / "tasks.md")
        ]

        # Capture state after first migration
        kittify = project / ".kittify"
        state_after_first = {
            str(p.relative_to(kittify)): p.read_text()
            for p in kittify.rglob("*")
            if p.is_file()
        }

        # Second migration: should be a no-op
        report2 = execute_migration(project, dry_run=False)

        # No files should be removed or moved on second run
        assert len(report2.removed) == 0
        assert len(report2.moved) == 0
        # The override is now project-specific (under overrides/)
        # config.yaml is project-specific
        assert len(report2.kept) >= 1

        # Filesystem state should be identical
        state_after_second = {
            str(p.relative_to(kittify)): p.read_text()
            for p in kittify.rglob("*")
            if p.is_file()
        }
        assert state_after_first == state_after_second

    def test_no_errors_on_empty_kittify(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Migration on an empty .kittify/ dir produces no errors."""
        global_home = tmp_path / "global"
        global_home.mkdir()
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        (project / ".kittify").mkdir(parents=True)

        report = execute_migration(project, dry_run=False)
        assert len(report.removed) == 0
        assert len(report.moved) == 0
        assert len(report.kept) == 0
        assert len(report.unknown) == 0

# ---------------------------------------------------------------------------
# T024: Customized files moved to overrides (F-Legacy-003, 1A-05)
# ---------------------------------------------------------------------------

class TestCustomizedFilesMovedToOverrides:
    """Customized files moved to .kittify/overrides/ (F-Legacy-003, 1A-05)."""

    def test_customized_files_moved_to_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """User-created files (no package counterpart) end up in .kittify/overrides/."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={"templates/my-custom.md": "customized content"},
        )

        report = execute_migration(project)

        # Verify: customized file moved to overrides
        assert report.moved == [
            (kittify / "templates" / "my-custom.md", kittify / "overrides" / "templates" / "my-custom.md")
        ]

        # Verify on filesystem
        assert (kittify / "overrides" / "templates" / "my-custom.md").exists()
        assert (
            (kittify / "overrides" / "templates" / "my-custom.md").read_text()
            == "customized content"
        )
        # Verify: original location removed
        assert not (kittify / "templates" / "my-custom.md").exists()

    def test_multiple_customized_files_preserve_hierarchy(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Multiple user-created files maintain their directory hierarchy under overrides/."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={
                "templates/my-custom.md": "custom template",
                "command-templates/my-workflow.md": "custom workflow",
                "scripts/custom-script.sh": "custom script",
            },
        )

        report = execute_migration(project)

        assert report.moved == [
            (
                kittify / "command-templates" / "my-workflow.md",
                kittify / "overrides" / "command-templates" / "my-workflow.md",
            ),
            (kittify / "scripts" / "custom-script.sh", kittify / "overrides" / "scripts" / "custom-script.sh"),
            (kittify / "templates" / "my-custom.md", kittify / "overrides" / "templates" / "my-custom.md"),
        ]

        # All should exist under overrides/
        assert (kittify / "overrides" / "templates" / "my-custom.md").exists()
        assert (kittify / "overrides" / "command-templates" / "my-workflow.md").exists()
        assert (kittify / "overrides" / "scripts" / "custom-script.sh").exists()

        # Content preserved
        assert (
            (kittify / "overrides" / "templates" / "my-custom.md").read_text()
            == "custom template"
        )
        assert (
            (kittify / "overrides" / "command-templates" / "my-workflow.md").read_text()
            == "custom workflow"
        )
        assert (
            (kittify / "overrides" / "scripts" / "custom-script.sh").read_text()
            == "custom script"
        )

    def test_outdated_agents_md_superseded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """AGENTS.md with a package counterpart but different content is SUPERSEDED.

        Corrected contract (#4961): a differing counterpart is content-
        indistinguishable from a team customisation, so the ownership guard
        cannot prove ownership and PRESERVES it in place (never moved to
        overrides, never deleted).
        """
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={"AGENTS.md": "old agents content v1"},
        )

        report = execute_migration(project)

        # AGENTS.md differs from its package counterpart -> preserved in place.
        assert report.superseded == [kittify / "AGENTS.md"]
        assert len(report.moved) == 0
        assert (kittify / "AGENTS.md").exists()
        assert (kittify / "AGENTS.md").read_text() == "old agents content v1"
        assert not (kittify / "overrides" / "AGENTS.md").exists()

    def test_mix_of_identical_customized_and_superseded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Identical removed, superseded removed, customized moved; project-specific untouched."""
        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(global_home / "missions"))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={"templates/spec.md": "global spec content"},
            customized_files={
                "templates/plan.md": "old plan content v1",  # Has package counterpart → superseded
                "templates/my-custom.md": "user-created content",  # No counterpart → customized
            },
            project_specific_files={"config.yaml": "my config"},
        )

        report = execute_migration(project)

        # Identical removed (byte-identical to the shipped counterpart)
        assert report.removed == [kittify / "templates" / "spec.md"]
        assert not (kittify / "templates" / "spec.md").exists()

        # Superseded (differs from counterpart) -> PRESERVED in place, not removed (#4961)
        assert report.superseded == [kittify / "templates" / "plan.md"]
        assert (kittify / "templates" / "plan.md").exists()
        assert (kittify / "templates" / "plan.md").read_text() == "old plan content v1"

        # Customized moved (user-created, no package counterpart)
        assert report.moved == [
            (kittify / "templates" / "my-custom.md", kittify / "overrides" / "templates" / "my-custom.md")
        ]
        assert (kittify / "overrides" / "templates" / "my-custom.md").exists()
        assert (kittify / "overrides" / "templates" / "my-custom.md").read_text() == "user-created content"

        # Project-specific kept
        assert report.kept == [kittify / "config.yaml"]
        assert (kittify / "config.yaml").exists()
        assert (kittify / "config.yaml").read_text() == "my config"

# ---------------------------------------------------------------------------
# T020 extended: classify_asset with global fallback path
# ---------------------------------------------------------------------------

class TestClassifyAssetGlobalFallback:
    """Test classify_asset falls back to direct global path when mission path missing."""

    def test_falls_back_to_global_root(self, tmp_path: Path) -> None:
        """When mission-specific path doesn't exist, tries global root."""
        global_home = tmp_path / "global"
        # Put AGENTS.md only at global root (not under missions/)
        (global_home / "AGENTS.md").parent.mkdir(parents=True, exist_ok=True)
        (global_home / "AGENTS.md").write_text("global agents")

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "AGENTS.md"
        f.parent.mkdir(parents=True)
        f.write_text("global agents")  # Identical

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

    def test_mission_path_takes_precedence(self, tmp_path: Path) -> None:
        """Mission-specific path is checked before global root."""
        global_home = tmp_path / "global"
        # Same filename at both locations with different content
        mission_dir = global_home / "missions" / "software-dev" / "templates"
        mission_dir.mkdir(parents=True)
        (mission_dir / "spec.md").write_text("mission version")
        (global_home / "templates").mkdir(parents=True)
        (global_home / "templates" / "spec.md").write_text("root version")

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("mission version")  # Matches mission-specific

        result = classify_asset(f, global_home, kittify)
        assert result == AssetDisposition.IDENTICAL

# ---------------------------------------------------------------------------
# MigrationReport dataclass tests
# ---------------------------------------------------------------------------

class TestMigrationReport:
    """Test MigrationReport dataclass defaults and behavior."""

    def test_default_values(self) -> None:
        """Report has empty lists and dry_run=False by default."""
        report = MigrationReport()
        assert report.removed == []
        assert report.moved == []
        assert report.kept == []
        assert report.unknown == []
        assert report.dry_run is False

    def test_dry_run_flag(self) -> None:
        """dry_run flag can be set at construction."""
        report = MigrationReport(dry_run=True)
        assert report.dry_run is True

    def test_superseded_field_default(self) -> None:
        """superseded list defaults to empty."""
        report = MigrationReport()
        assert report.superseded == []

# ---------------------------------------------------------------------------
# T025: SUPERSEDED disposition tests
# ---------------------------------------------------------------------------

class TestClassifyAssetSuperseded:
    """Test SUPERSEDED disposition when package_root is provided."""

    def test_superseded_when_differs_from_package(self, tmp_path: Path) -> None:
        """File with package counterpart but different content is SUPERSEDED."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("old spec content v1")  # Differs from package v2

        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify, package_root=package_root)
        assert result == AssetDisposition.SUPERSEDED

    def test_identical_when_matches_package(self, tmp_path: Path) -> None:
        """File matching package default is IDENTICAL even with package_root."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "spec.md"
        f.parent.mkdir(parents=True)
        f.write_text("package spec content v2")  # Matches package exactly

        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify, package_root=package_root)
        assert result == AssetDisposition.IDENTICAL

    def test_customized_when_no_package_counterpart(self, tmp_path: Path) -> None:
        """File with no package counterpart is CUSTOMIZED (genuinely user-created)."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "templates" / "user-template.md"
        f.parent.mkdir(parents=True)
        f.write_text("user-created template")

        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify, package_root=package_root)
        assert result == AssetDisposition.CUSTOMIZED

    def test_project_specific_still_kept_with_package_root(self, tmp_path: Path) -> None:
        """Project-specific files are unaffected by package_root."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)

        kittify = tmp_path / "project" / ".kittify"
        f = kittify / "config.yaml"
        f.parent.mkdir(parents=True)
        f.write_text("agents: [claude]")

        global_home = tmp_path / "global"
        global_home.mkdir()

        result = classify_asset(f, global_home, kittify, package_root=package_root)
        assert result == AssetDisposition.PROJECT_SPECIFIC

class TestExecuteMigrationSuperseded:
    """Test that execute_migration() removes superseded files."""

    def test_superseded_files_preserved_not_moved_to_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Superseded (differing) files are preserved in place, NOT moved to overrides/.

        Corrected contract (#4961): a file that differs from the shipped
        counterpart is unprovable, so the ownership guard preserves it exactly
        where it lives — it is neither deleted nor relocated to overrides/.
        """
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            # Old default content that differs from both global and package
            customized_files={
                "templates/spec.md": "old spec content v1",
                "templates/plan.md": "old plan content v1",
            },
            project_specific_files={"config.yaml": "keep me"},
        )

        report = execute_migration(project, dry_run=False)

        # Differing files are classified superseded and preserved in place.
        assert report.superseded == [kittify / "templates" / "plan.md", kittify / "templates" / "spec.md"]
        assert len(report.moved) == 0  # NOT moved to overrides

        # Files survive in place with content intact.
        assert (kittify / "templates" / "spec.md").read_text() == "old spec content v1"
        assert (kittify / "templates" / "plan.md").read_text() == "old plan content v1"

        # No overrides created
        assert not (kittify / "overrides").exists()

    @pytest.mark.regression
    def test_superseded_marker_bearing_file_is_preserved_not_deleted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A DIFFERING shared asset that embeds the version-marker literal is preserved (#5050).

        Regression for the marker-branch escape hatch: ``CanonicalContentProver``
        checks the version marker before the byte-match and would return
        ``owned=True`` for any file merely containing the marker literal — so a
        customised (differing) ``templates/`` file that pastes a generated
        command's ``<!-- spec-kitty-command-version: -->`` line was DELETED,
        silently destroying operator content and violating the "differing files
        are preserved, never deleted" invariant. The removal site now uses
        ``check_marker=False`` (byte-identity is the only ownership signal for a
        shared source asset), so the file must survive.

        RED before the fix (guard proves owned via the marker → file removed);
        GREEN after (differs from counterpart → unprovable → preserved).
        """
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        # A customised template that DIFFERS from the shipped counterpart AND
        # embeds the version-marker literal (the exact escape-hatch trigger).
        marker_bearing = "# my customised spec template\n<!-- spec-kitty-command-version: 9.9 -->\nEXTRA USER CONTENT\n"
        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={"templates/spec.md": marker_bearing},
            project_specific_files={"config.yaml": "keep me"},
        )

        report = execute_migration(project, dry_run=False)

        # The differing marker-bearing file is preserved in place with content intact.
        assert (kittify / "templates" / "spec.md").exists()
        assert (kittify / "templates" / "spec.md").read_text() == marker_bearing
        assert (kittify / "templates" / "spec.md") in report.superseded
        assert (kittify / "templates" / "spec.md") not in report.removed

    def test_genuine_customization_still_moved_to_overrides(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Files with no package counterpart are still moved to overrides/."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={
                "templates/my-custom-template.md": "user-created content",
            },
        )

        report = execute_migration(project, dry_run=False)

        assert report.moved == [
            (
                kittify / "templates" / "my-custom-template.md",
                kittify / "overrides" / "templates" / "my-custom-template.md",
            )
        ]
        assert (kittify / "overrides" / "templates" / "my-custom-template.md").exists()

    def test_version_skew_scenario_end_to_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulate upgrade where global is newer than project files.

        This is the exact scenario from issue #285: ensure_runtime() has
        already updated ~/.kittify/ to v2, but project files are still v1.

        Deliberate #4961/#285 trade-off: old defaults are classified SUPERSEDED
        (they differ from the shipped counterpart) but are now PRESERVED in
        place rather than deleted. An old default is content-indistinguishable
        from a team customisation, and the preservation contract fails closed
        toward keeping the bytes — a stale default lingering in place is
        recoverable; a deleted customisation is not.
        """
        # Package assets represent the NEW version (immutable truth)
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        # Global home (~/.kittify/) already updated to new version
        # (this is what ensure_runtime() does before migration runs)
        global_home = tmp_path / "global"
        mission_dir = global_home / "missions" / "software-dev"
        (mission_dir / "templates").mkdir(parents=True, exist_ok=True)
        (mission_dir / "templates" / "spec.md").write_text("package spec content v2")
        (mission_dir / "templates" / "plan.md").write_text("package plan content v2")
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        # Project still has OLD version content
        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={
                "templates/spec.md": "old spec content v1",
                "templates/plan.md": "old plan content v1",
            },
            project_specific_files={"config.yaml": "keep me"},
        )

        report = execute_migration(project, dry_run=False)

        # Key assertion: old defaults are SUPERSEDED, not moved to overrides
        assert report.superseded == [kittify / "templates" / "plan.md", kittify / "templates" / "spec.md"]
        assert len(report.moved) == 0
        assert not (kittify / "overrides").exists()

        # Files preserved in place (fail-closed; not deleted) with content intact
        assert (kittify / "templates" / "spec.md").read_text() == "old spec content v1"
        assert (kittify / "templates" / "plan.md").read_text() == "old plan content v1"

        # Project-specific files untouched
        assert (kittify / "config.yaml").exists()

    def test_superseded_count_in_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MigrationReport.superseded tracks superseded files separately from removed."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={
                # Matches package default exactly
                "templates/spec.md": "package spec content v2",
            },
            customized_files={
                # Old default, differs from package
                "templates/plan.md": "old plan content v1",
            },
        )

        report = execute_migration(project, dry_run=False)

        assert report.removed == [kittify / "templates" / "spec.md"]  # identical
        assert report.superseded == [kittify / "templates" / "plan.md"]  # superseded (old default)

# ---------------------------------------------------------------------------
# T001 (#4961): red-first regression — a customised shipped template survives
# ---------------------------------------------------------------------------

class TestMigratePreservesCustomisedTemplate:
    """Red-first regression for #4961.

    A shipped template that a team has customised (package bytes + an appended
    team section) differs from the shipped counterpart, so ``classify_asset``
    labels it SUPERSEDED. Before the fix ``execute_migration`` ``unlink()``ed
    SUPERSEDED files unconditionally, silently deleting the team's work. The fix
    routes the removal through the ownership guard, which cannot prove ownership
    of the differing bytes and therefore PRESERVES the file in place.
    """

    def test_customised_shipped_template_survives_migration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A customised shipped template survives execute_migration(dry_run=False).

        RED before the fix (differing SUPERSEDED file is unlinked); GREEN after
        (the guard preserves it in place). #4961.
        """
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        # Shipped package bytes + an appended team customisation section.
        package_bytes = (
            package_root / "software-dev" / "templates" / "spec.md"
        ).read_text()
        team_section = "\n\n## Team Section\nOur team's required spec addendum.\n"
        customised = package_bytes + team_section

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            customized_files={"templates/spec.md": customised},
        )
        target = kittify / "templates" / "spec.md"

        report = execute_migration(project, dry_run=False)

        # The customised template SURVIVES in place with the team section intact.
        assert target.exists(), "customised shipped template must not be deleted (#4961)"
        assert team_section.strip() in target.read_text()
        assert target.read_text() == customised

        # Reported as preserved (differs from the package default), NOT removed,
        # and NOT relocated to overrides/ — it survives exactly where it lived.
        assert target not in report.removed
        assert target in report.superseded
        assert not (kittify / "overrides" / "templates" / "spec.md").exists()

    def test_identical_shipped_template_still_removed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A byte-identical shipped default is STILL removed (no NFR-004 regression)."""
        package_root = tmp_path / "pkg"
        _setup_package_assets(package_root)
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_root))

        global_home = tmp_path / "global"
        _setup_global(global_home)
        monkeypatch.setenv("SPEC_KITTY_HOME", str(global_home))

        package_bytes = (
            package_root / "software-dev" / "templates" / "spec.md"
        ).read_text()

        project = tmp_path / "project"
        kittify = _setup_project_kittify(
            project,
            identical_files={"templates/spec.md": package_bytes},
        )
        target = kittify / "templates" / "spec.md"

        report = execute_migration(project, dry_run=False)

        assert not target.exists()
        assert target in report.removed
        assert target not in report.superseded
