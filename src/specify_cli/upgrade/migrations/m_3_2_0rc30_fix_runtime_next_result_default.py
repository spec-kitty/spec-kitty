"""Migration: correct stale runtime-next ``--result`` default docs.

The runtime-next skill used to claim that omitting ``--result`` defaults to
``success``. The CLI contract is the opposite: a bare ``spec-kitty next`` call
is read-only query mode and does not advance the DAG.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..registry import MigrationRegistry
from ..skill_update import file_contains_any, find_skill_files, write_skill_text
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-runtime-next"

_OLD_MARKERS = [
    "Defaults to `success` if omitted.",
]


@MigrationRegistry.register
class FixRuntimeNextResultDefaultMigration(BaseMigration):
    """Refresh runtime-next SKILL.md copies with correct query-mode docs."""

    migration_id = "3.2.0rc30_fix_runtime_next_result_default"
    description = (
        "Correct runtime-next skill docs: omitted --result is query mode, "
        "not success (#1456)."
    )
    target_version = "3.2.0rc30"

    def detect(self, project_path: Path) -> bool:
        return any(
            file_contains_any(info.path, _OLD_MARKERS)
            for info in find_skill_files(project_path, _SKILL_NAME, ["SKILL.md"])
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
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
                except OSError as exc:
                    errors.append(f"Failed to write {rel}: {exc}")

        if not changes and not errors:
            changes.append("All runtime-next skill files already up to date")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            errors=errors,
        )
