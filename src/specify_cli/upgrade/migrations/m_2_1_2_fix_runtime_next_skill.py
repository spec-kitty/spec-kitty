"""Migration: expand runtime-next skill with decision algorithm and WP iteration docs.

The original skill documented the basic workflow but not the internals. This adds
the decision algorithm, WP iteration logic (CLI bridge vs runtime), mission
runtime YAML schema, 6 guard primitives, prompt file generation, run persistence,
feature detection, decision output fields, and the complete agent loop pattern.

Uses the reusable skill_update utility to find and replace skill files across
all agent skill roots.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..registry import MigrationRegistry
from ..skill_update import file_contains_any, find_skill_files, write_skill_text
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-runtime-next"

# The old SKILL.md lacks "## How the Runtime-Next System Works" and goes
# straight to "## Step 1: Load Runtime Context".
_OLD_MARKERS = [
    "## Step 1: Load Runtime Context\n\nBefore invoking the runtime, gather",
]


@MigrationRegistry.register
class FixRuntimeNextSkillMigration(BaseMigration):
    """Expand runtime-next skill with decision algorithm and WP iteration docs."""

    migration_id = "2.1.2_fix_runtime_next_skill"
    description = (
        "Expand runtime-next skill with decision algorithm, WP iteration logic, "
        "guard primitives, prompt generation, and agent loop pattern"
    )
    target_version = "2.1.2"

    def detect(self, project_path: Path) -> bool:
        """Return True if any runtime-next SKILL.md lacks the new docs."""
        for info in find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"]):
            if file_contains_any(info.path, _OLD_MARKERS):
                return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if project has runtime-next skill files."""
        files_found = find_skill_files(project_path, _SKILL_NAME)
        if not files_found:
            return True, ""  # apply() handles missing files gracefully
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Replace runtime-next SKILL.md with expanded version."""
        changes: list[str] = []
        errors: list[str] = []

        try:
            offering_root = files("charter.offering")
            canonical_path = offering_root.joinpath(
                "skills", _SKILL_NAME, "SKILL.md"
            )
            new_content = canonical_path.read_text(encoding="utf-8")
        except Exception:
            return MigrationResult(
                success=False,
                errors=["Cannot locate canonical SKILL.md for runtime-next"],
            )

        for info in find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"]):
            if not file_contains_any(info.path, _OLD_MARKERS):
                continue
            rel = str(info.path.relative_to(project_path))
            if dry_run:
                changes.append(f"Would replace {rel}")
            else:
                try:
                    wrote, warning = write_skill_text(
                        info.path, new_content, project_path
                    )
                    if wrote:
                        changes.append(f"Replaced {rel}")
                    elif warning is not None:
                        changes.append(warning)
                except OSError as e:
                    errors.append(f"Failed to write {rel}: {e}")

        if not changes and not errors:
            changes.append("All runtime-next skill files already up to date")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )
