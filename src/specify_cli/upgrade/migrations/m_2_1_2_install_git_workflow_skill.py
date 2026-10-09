"""Migration: install the new git-workflow skill for consumer projects.

The spec-kitty-git-workflow skill documents the boundary between Python-managed
git operations (worktrees, auto-commits, merges) and agent-expected git
operations (implementation commits, rebases, conflict resolution). New skill
added in 2.1.2.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from ..skill_update import SKILL_ROOTS, find_skill_files
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-git-workflow"

_SKILL_FILES = ["SKILL.md", "references/git-operations-matrix.md"]


def _load_canonical(relative_path: str) -> str | None:
    """Load canonical skill file content from charter.offering package."""
    try:
        offering_root = files("charter.offering")
        canonical = offering_root.joinpath("skills", _SKILL_NAME, relative_path)
        return canonical.read_text(encoding="utf-8")
    except Exception:  # the packaged skill is unreadable; the caller reports it
        return None


@MigrationRegistry.register
class InstallGitWorkflowSkillMigration(BaseMigration):
    """Install the git-workflow skill for consumer projects."""

    migration_id = "2.1.2_install_git_workflow_skill"
    description = "Install new git-workflow skill documenting git operation boundaries"
    target_version = "2.1.2"

    def detect(self, project_path: Path) -> bool:
        """Return True if the git-workflow skill is not installed."""
        return len(find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"])) == 0

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable — apply() handles missing roots gracefully."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Install git-workflow skill to all configured agent skill roots."""
        changes: list[str] = []
        errors: list[str] = []

        # Load canonical content
        file_contents: dict[str, str | None] = {}
        for rel in _SKILL_FILES:
            file_contents[rel] = _load_canonical(rel)

        if not file_contents.get("SKILL.md"):
            return MigrationResult(
                success=False,
                errors=["Cannot locate canonical SKILL.md for git-workflow"],
            )

        # Install to standard roots + any active native roots
        target_roots = [".claude/skills", ".agents/skills"]
        for root in SKILL_ROOTS:
            skill_dir = project_path / root
            if skill_dir.is_dir() and root not in target_roots:
                target_roots.append(root)

        for root in target_roots:
            for rel, content in file_contents.items():
                if not content:
                    continue
                dest = project_path / root / _SKILL_NAME / rel
                if dest.exists():
                    continue
                rel_display = str(dest.relative_to(project_path))
                if dry_run:
                    changes.append(f"Would install {rel_display}")
                    continue
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    write_generated_file(dest, content)
                    changes.append(f"Installed {rel_display}")
                except OSError as e:
                    errors.append(f"Failed to install {rel_display}: {e}")

        if not changes and not errors:
            changes.append("Git-workflow skill already installed")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )
