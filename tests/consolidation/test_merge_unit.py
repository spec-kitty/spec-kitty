"""Tests for specify_cli.runtime.merge — asset merging logic.

Covers:
- T009: merge_package_assets() correctly overwrites managed dirs/files
        while preserving user-owned data (config.yaml, missions/custom/).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.runtime.merge import MANAGED_DIRS, MANAGED_FILES, merge_package_assets

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T009: merge_package_assets() tests
# ---------------------------------------------------------------------------


class TestMergePackageAssets:
    """merge_package_assets() overwrites managed assets, preserves user data."""

    def test_managed_dir_overwritten(self, tmp_path: Path) -> None:
        """Managed directory in dest is replaced by source version."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Create source with a managed directory
        (source / "missions" / "software-dev").mkdir(parents=True)
        (source / "missions" / "software-dev" / "mission.yaml").write_text("new")

        # Create dest with stale managed directory
        (dest / "missions" / "software-dev").mkdir(parents=True)
        (dest / "missions" / "software-dev" / "mission.yaml").write_text("stale")
        (dest / "missions" / "software-dev" / "old-file.txt").write_text("leftover")

        merge_package_assets(source, dest)

        # Verify overwritten
        assert (dest / "missions" / "software-dev" / "mission.yaml").read_text() == "new"
        # Verify stale file removed (rmtree + copytree)
        assert not (dest / "missions" / "software-dev" / "old-file.txt").exists()

    def test_user_directory_preserved(self, tmp_path: Path) -> None:
        """missions/custom/ is NEVER touched by merge (user-owned)."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Source has a managed directory (but NOT missions/custom/)
        (source / "missions" / "software-dev").mkdir(parents=True)
        (source / "missions" / "software-dev" / "mission.yaml").write_text("new")

        # Dest has user-owned missions/custom/
        (dest / "missions" / "custom").mkdir(parents=True)
        (dest / "missions" / "custom" / "my-mission.yaml").write_text("user data")

        merge_package_assets(source, dest)

        # User data preserved
        assert (dest / "missions" / "custom" / "my-mission.yaml").read_text() == "user data"

    def test_config_yaml_preserved(self, tmp_path: Path) -> None:
        """config.yaml in dest is never touched by merge."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Source has a managed directory
        (source / "missions" / "software-dev").mkdir(parents=True)
        (source / "missions" / "software-dev" / "mission.yaml").write_text("new")

        # Dest has config.yaml (user-owned)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / "config.yaml").write_text("user config")

        merge_package_assets(source, dest)

        # config.yaml untouched
        assert (dest / "config.yaml").read_text() == "user config"

    def test_agents_md_overwritten(self, tmp_path: Path) -> None:
        """AGENTS.md in dest is overwritten with source version."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Source has AGENTS.md
        source.mkdir(parents=True)
        (source / "AGENTS.md").write_text("# New agents")

        # Dest has stale AGENTS.md
        dest.mkdir(parents=True)
        (dest / "AGENTS.md").write_text("# Old agents")

        merge_package_assets(source, dest)

        assert (dest / "AGENTS.md").read_text() == "# New agents"

    def test_missing_source_dir_no_error(self, tmp_path: Path) -> None:
        """Missing source directory does not raise an error."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Source has nothing (empty)
        source.mkdir(parents=True)
        dest.mkdir(parents=True)

        # Should not raise
        merge_package_assets(source, dest)

    def test_parent_dirs_created(self, tmp_path: Path) -> None:
        """Dest parent directories are created if they don't exist."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        # Source has a managed directory
        (source / "missions" / "software-dev").mkdir(parents=True)
        (source / "missions" / "software-dev" / "mission.yaml").write_text("data")

        # Dest does not exist at all
        assert not dest.exists()

        merge_package_assets(source, dest)

        assert (dest / "missions" / "software-dev" / "mission.yaml").read_text() == "data"

    def test_scripts_dir_overwritten(self, tmp_path: Path) -> None:
        """scripts/ directory is a managed dir and gets overwritten."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        (source / "scripts").mkdir(parents=True)
        (source / "scripts" / "validate.py").write_text("new script")

        (dest / "scripts").mkdir(parents=True)
        (dest / "scripts" / "validate.py").write_text("old script")
        (dest / "scripts" / "legacy.sh").write_text("leftover")

        merge_package_assets(source, dest)

        assert (dest / "scripts" / "validate.py").read_text() == "new script"
        assert not (dest / "scripts" / "legacy.sh").exists()

    def test_all_managed_dirs_listed(self) -> None:
        """Verify MANAGED_DIRS contains the expected entries."""
        expected = {
            "missions/software-dev",
            "missions/research",
            "missions/documentation",
            "missions/plan",
            "missions/audit",
            "missions/refactor",
            "scripts",
        }
        assert set(MANAGED_DIRS) == expected

    def test_missions_custom_not_in_managed_dirs(self) -> None:
        """missions/custom/ must NEVER be in MANAGED_DIRS."""
        assert "missions/custom" not in MANAGED_DIRS
        assert "missions/custom/" not in MANAGED_DIRS

    def test_managed_files_contains_agents_md(self) -> None:
        """AGENTS.md is listed in MANAGED_FILES."""
        assert "AGENTS.md" in MANAGED_FILES

    def test_multiple_managed_dirs(self, tmp_path: Path) -> None:
        """Multiple managed directories are all overwritten in one merge."""
        source = tmp_path / "source"
        dest = tmp_path / "dest"

        for managed_dir in ["missions/software-dev", "missions/research", "scripts"]:
            (source / managed_dir).mkdir(parents=True)
            (source / managed_dir / "file.txt").write_text(f"new-{managed_dir}")

            (dest / managed_dir).mkdir(parents=True)
            (dest / managed_dir / "file.txt").write_text(f"old-{managed_dir}")

        merge_package_assets(source, dest)

        for managed_dir in ["missions/software-dev", "missions/research", "scripts"]:
            assert (dest / managed_dir / "file.txt").read_text() == f"new-{managed_dir}"
