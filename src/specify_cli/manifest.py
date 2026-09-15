"""
Manifest system for spec-kitty file verification.
This module generates and checks expected files based on the mission context.
"""

from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.missions._read_path_resolver import candidate_feature_dir_for_mission
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional
import subprocess


class FileManifest:
    """Manages the expected file manifest for spec-kitty missions.

    The mission context must be provided explicitly via *mission_type*.
    There is no project-level fallback -- callers should resolve the
    mission from feature-level ``meta.json`` before constructing a
    manifest.
    """

    def __init__(self, kittify_dir: Path, *, mission_type: str | None = None):
        self.kittify_dir = kittify_dir
        self.mission_dir = (
            kittify_dir / "missions" / mission_type if mission_type else None
        )

    def get_expected_files(self) -> dict[str, list[str]]:
        """
        Get a categorized list of expected files for the active mission.

        Returns:
            Dict with categories as keys and file paths as values
        """
        if not self.mission_dir or not self.mission_dir.exists():
            return {}

        manifest = {
            "commands": [],
            "templates": [],
            "scripts": [],
            "mission_files": []
        }

        # Mission config file
        mission_yaml = self.mission_dir / "mission.yaml"
        if mission_yaml.exists():
            manifest["mission_files"].append(str(mission_yaml.relative_to(self.kittify_dir)))

        # Commands
        commands_dir = self.mission_dir / "command-templates"
        if commands_dir.exists():
            for cmd_file in commands_dir.glob("*.md"):
                manifest["commands"].append(str(cmd_file.relative_to(self.kittify_dir)))

        # Templates
        templates_dir = self.mission_dir / "templates"
        if templates_dir.exists():
            for tmpl_file in templates_dir.glob("*.md"):
                manifest["templates"].append(str(tmpl_file.relative_to(self.kittify_dir)))

        # Scripts referenced in commands
        manifest["scripts"] = self._get_referenced_scripts()

        return manifest

    @staticmethod
    def _canonical_script_path(script_path: str) -> str | None:
        """Return a canonical scripts-relative path, or reject unsafe input."""
        prefix = ".kittify/scripts/"
        if not script_path.startswith(prefix):
            return None

        relative_path = script_path.removeprefix(prefix)
        parsed_path = PurePosixPath(relative_path)
        if (
            not relative_path
            or "\\" in relative_path
            or parsed_path.is_absolute()
            or any(part in {".", ".."} for part in parsed_path.parts)
        ):
            return None
        return str(PurePosixPath("scripts") / parsed_path)

    @staticmethod
    def _parse_frontmatter_scripts(content: str, script_key: str) -> set[str]:
        """Extract .kittify/scripts/ paths from a command file's YAML frontmatter."""
        scripts: set[str] = set()
        in_frontmatter = False
        for line in content.split("\n"):
            if line.strip() == "---":
                if in_frontmatter:
                    break  # end of frontmatter
                in_frontmatter = True
                continue
            if not in_frontmatter or script_key not in line:
                continue
            parts = line.split(":", 1)
            if len(parts) != 2:
                continue
            script_path = parts[1].strip().strip('"').strip("'").split()[0] if parts[1].strip() else ""
            canonical_path = FileManifest._canonical_script_path(script_path)
            if canonical_path is not None:
                scripts.add(canonical_path)
        return scripts

    def _get_referenced_scripts(self) -> list[str]:
        """Extract script references from command files, filtered by platform."""
        import platform

        if not self.mission_dir:
            return []
        commands_dir = self.mission_dir / "command-templates"
        if not commands_dir.exists():
            return []

        script_key = "ps:" if platform.system() == "Windows" else "sh:"
        scripts: set[str] = set()
        for cmd_file in commands_dir.glob("*.md"):
            scripts |= self._parse_frontmatter_scripts(cmd_file.read_text(encoding="utf-8-sig"), script_key)
        return sorted(scripts)

    def check_files(self) -> dict[str, dict[str, str]]:
        """
        Check which expected files exist and which are missing.

        Returns:
            Dict with 'present', 'missing', and 'extra' keys
        """
        expected = self.get_expected_files()
        result = {
            "present": {},
            "missing": {},
            "modified": {},
            "extra": []
        }

        # Check each category
        for category, files in expected.items():
            for file_path in files:
                full_path = self.kittify_dir / file_path
                if full_path.exists():
                    result["present"][file_path] = category
                else:
                    result["missing"][file_path] = category

        # TODO: Check for modifications using git or checksums
        # TODO: Find extra files not in manifest

        return result


class WorktreeStatus:
    """Manages worktree and feature branch status."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def _get_features_from_branches(self) -> set[str]:
        """Return feature names discovered from local git branches."""
        try:
            result = subprocess.run(
                ["git", "branch", "-a"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
        except subprocess.CalledProcessError:
            return set()
        from specify_cli.lanes.branch_naming import parse_mission_slug_from_branch

        features = set()
        for line in result.stdout.split("\n"):
            stripped = line.strip().replace("* ", "")
            if not stripped or stripped.startswith("remotes/"):
                continue
            # Canonical mission/lane branches (``kitty/mission-…``) carry the
            # slug in either legacy ``NNN-slug`` or mid8-era ``<slug>-<mid8>``
            # form. Route through the dual-era parser so mid8 missions are
            # discovered too — the old ``branch[0].isdigit()`` test silently
            # excluded every mid8 branch (#1860 class).
            parsed = parse_mission_slug_from_branch(stripped)
            if parsed is not None:
                features.add(parsed.slug)
                continue
            # Legacy bare feature branch (``NNN-slug``, no ``kitty/mission-``).
            branch = stripped.split("/")[-1]
            if branch and branch[0].isdigit() and "-" in branch:
                features.add(branch)
        return features

    def get_all_features(self) -> list[str]:
        """Get all feature branches and directories."""
        features = self._get_features_from_branches()

        # Get features from kitty-specs
        mission_specs = self.repo_root / KITTY_SPECS_DIR
        if mission_specs.exists():
            for feature_dir in mission_specs.iterdir():
                if feature_dir.is_dir() and feature_dir.name[0].isdigit() and "-" in feature_dir.name:
                    features.add(feature_dir.name)

        return sorted(list(features))

    def _check_branch_exists(self, feature: str) -> bool:
        """Return True if the local branch ref exists."""
        try:
            result = subprocess.run(
                ["git", "show-ref", f"refs/heads/{feature}"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def _check_branch_merged(self, feature: str) -> bool:
        """Return True if the branch has been merged into the primary branch."""
        try:
            from specify_cli.core.git_ops import resolve_primary_branch
            primary = resolve_primary_branch(self.repo_root)
            result = subprocess.run(
                ["git", "branch", "--merged", primary],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )
            return feature in result.stdout
        except subprocess.CalledProcessError:
            return False

    @staticmethod
    def _determine_feature_state(status: dict) -> str:
        """Derive the lifecycle state label from collected status flags."""
        if not status["branch_exists"] and not status["artifacts_in_main"]:
            return "not_started"
        if status["branch_merged"] and status["artifacts_in_main"]:
            return "merged"
        if status["worktree_exists"] or status["artifacts_in_worktree"]:
            return "in_development"
        if status["branch_exists"] and not status["worktree_exists"]:
            return "ready_to_merge"
        if not status["branch_exists"] and status["artifacts_in_main"]:
            return "merged"  # branch deleted after merge
        return "unknown"

    def get_feature_status(self, feature: str) -> dict[str, Any]:
        """Get comprehensive status for a feature."""
        status: dict[str, Any] = {
            "name": feature,
            "branch_exists": self._check_branch_exists(feature),
            "branch_merged": False,
            "worktree_exists": False,
            "worktree_path": None,
            "artifacts_in_main": [],
            "artifacts_in_worktree": [],
            "last_activity": None,
            "state": "unknown",
        }

        if status["branch_exists"]:
            status["branch_merged"] = self._check_branch_merged(feature)

        worktree_path = self.repo_root / ".worktrees" / feature
        if worktree_path.exists():
            status["worktree_exists"] = True
            status["worktree_path"] = str(worktree_path)

        # WP09/FR-001 (kind-correct): lists top-level ``*.md`` files (spec/
        # plan/tasks/research/data-model) — all PRIMARY-partition kinds that
        # co-resolve to the same dir. Route through the seam on
        # ``PRIMARY_METADATA`` rather than the kind-blind resolver (NFR-001).
        from mission_runtime import MissionArtifactKind, placement_seam

        main_artifacts_path = placement_seam(self.repo_root, feature).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        if main_artifacts_path.exists():
            status["artifacts_in_main"] = [a.name for a in main_artifacts_path.glob("*.md")]

        if status["worktree_exists"]:
            wt_artifacts = candidate_feature_dir_for_mission(worktree_path, feature)
            if wt_artifacts.exists():
                status["artifacts_in_worktree"] = [a.name for a in wt_artifacts.glob("*.md")]

        status["state"] = self._determine_feature_state(status)
        return status

    def get_worktree_summary(self) -> dict[str, int]:
        """Get summary counts of worktree states."""
        features = self.get_all_features()
        summary = {
            "total_features": len(features),
            "active_worktrees": 0,
            "merged_features": 0,
            "in_development": 0,
            "not_started": 0
        }

        for feature in features:
            status = self.get_feature_status(feature)
            if status["worktree_exists"]:
                summary["active_worktrees"] += 1
            if status["state"] == "merged":
                summary["merged_features"] += 1
            elif status["state"] == "in_development":
                summary["in_development"] += 1
            elif status["state"] == "not_started":
                summary["not_started"] += 1

        return summary
