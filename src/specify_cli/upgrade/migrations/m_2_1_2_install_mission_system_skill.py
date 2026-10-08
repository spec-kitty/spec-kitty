"""Migration: install the new mission-system skill for consumer projects.

The spec-kitty-mission-system skill explains how missions work, the 4 built-in
missions, template resolution, guards, and mission selection. It is a new skill
added in 2.1.2 — not a fix to an existing one.

Installs SKILL.md and references/mission-comparison-matrix.md to all configured
agent skill roots.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from ..skill_update import SKILL_ROOTS, find_skill_files
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-mission-system"

_FILES = [
    ("SKILL.md", "skills", _SKILL_NAME, "SKILL.md"),
    (
        "references/mission-comparison-matrix.md",
        "skills",
        _SKILL_NAME,
        "references/mission-comparison-matrix.md",
    ),
]


def _load_canonical(relative_path: str) -> str | None:
    """Load canonical skill file content from charter.offering package."""
    try:
        offering_root = files("charter.offering")
        canonical = offering_root.joinpath("skills", _SKILL_NAME, relative_path)
        return canonical.read_text(encoding="utf-8")
    except Exception:
        fallback = (
            Path(__file__).resolve().parents[3]
            / "doctrine"
            / "skills"
            / _SKILL_NAME
            / relative_path
        )
        if fallback.is_file():
            return fallback.read_text(encoding="utf-8")
    return None


@MigrationRegistry.register
class InstallMissionSystemSkillMigration(BaseMigration):
    """Install the mission-system skill for consumer projects."""

    migration_id = "2.1.2_install_mission_system_skill"
    description = "Install new mission-system skill explaining how missions work"
    target_version = "2.1.2"

    def detect(self, project_path: Path) -> bool:
        """Return True if the mission-system skill is not installed anywhere."""
        return len(find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"])) == 0

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable — apply() handles missing roots gracefully."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Install mission-system skill to all configured agent skill roots."""
        changes: list[str] = []
        errors: list[str] = []

        # Load canonical content
        skill_content = _load_canonical("SKILL.md")
        matrix_content = _load_canonical("references/mission-comparison-matrix.md")

        if not skill_content:
            return MigrationResult(
                success=False,
                errors=["Cannot locate canonical SKILL.md for mission-system"],
            )

        # Determine which skill roots to install to
        # Use .claude/skills and .agents/skills as the standard targets
        targets = [
            (".claude/skills", "SKILL.md"),
            (".claude/skills", "references/mission-comparison-matrix.md"),
            (".agents/skills", "SKILL.md"),
            (".agents/skills", "references/mission-comparison-matrix.md"),
        ]

        # Also check for agent-specific native roots that already have skills
        for root in SKILL_ROOTS:
            skill_dir = project_path / root
            if skill_dir.is_dir() and root not in (".claude/skills", ".agents/skills"):
                # This root has skills installed — add it
                targets.append((root, "SKILL.md"))
                if matrix_content:
                    targets.append((root, "references/mission-comparison-matrix.md"))

        for root, relative_path in targets:
            dest = project_path / root / _SKILL_NAME / relative_path
            content = skill_content if relative_path == "SKILL.md" else matrix_content

            if not content:
                continue

            if dest.exists():
                continue  # Already installed

            rel = str(dest.relative_to(project_path))

            if dry_run:
                changes.append(f"Would install {rel}")
                continue

            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                write_generated_file(dest, content)
                changes.append(f"Installed {rel}")
            except OSError as e:
                errors.append(f"Failed to install {rel}: {e}")

        if not changes and not errors:
            changes.append("Mission-system skill already installed")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )
