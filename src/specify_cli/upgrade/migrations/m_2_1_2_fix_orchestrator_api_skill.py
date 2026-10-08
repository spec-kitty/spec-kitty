"""Migration: expand orchestrator-api skill with output examples and internals.

Adds JSON output examples for feature-state and list-ready, error code catalog,
start-implementation idempotency table, workspace_path creation responsibility,
start-review --review-ref requirement, merge preflight details, policy secret
validation, full lane list including blocked/canceled, list-ready examples,
and correlation_id explanation.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..registry import MigrationRegistry
from ..skill_update import file_contains_any, find_skill_files, write_skill_text
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-orchestrator-api-operator"

# The old SKILL.md lacks "## How the Orchestrator API Works" and goes
# straight to "## When to Use This Skill" then "## Step 1".
_OLD_MARKERS = [
    "## Step 1: Verify the API Contract\n\n```bash\nspec-kitty orchestrator-api contract-version",
]


@MigrationRegistry.register
class FixOrchestratorApiSkillMigration(BaseMigration):
    """Expand orchestrator-api skill with output examples and internals."""

    migration_id = "2.1.2_fix_orchestrator_api_skill"
    description = (
        "Expand orchestrator-api skill with JSON output examples, error codes, "
        "idempotency behavior, and preflight details"
    )
    target_version = "2.1.2"

    def detect(self, project_path: Path) -> bool:
        for info in find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"]):
            if file_contains_any(info.path, _OLD_MARKERS):
                return True
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        files_found = find_skill_files(project_path, _SKILL_NAME)
        if not files_found:
            return True, ""  # apply() handles missing files gracefully
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        errors: list[str] = []

        try:
            offering_root = files("charter.offering")
            canonical_path = offering_root.joinpath(
                "skills", _SKILL_NAME, "SKILL.md"
            )
            new_content = canonical_path.read_text(encoding="utf-8")
        except Exception:
            fallback = (
                Path(__file__).resolve().parents[3]
                / "doctrine"
                / "skills"
                / _SKILL_NAME
                / "SKILL.md"
            )
            if fallback.is_file():
                new_content = fallback.read_text(encoding="utf-8")
            else:
                return MigrationResult(
                    success=False,
                    errors=["Cannot locate canonical SKILL.md for orchestrator-api"],
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
            changes.append("All orchestrator-api skill files already up to date")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )
