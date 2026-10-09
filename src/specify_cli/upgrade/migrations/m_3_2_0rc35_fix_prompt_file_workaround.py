"""Migration: remove the ``prompt_file == null`` workaround text from the
runtime-next skill (issues #336 / #844).

After WP06 of mission ``charter-e2e-hardening-tranche-2-01KQ9NVQ`` the
runtime guarantees that every ``kind: step`` decision carries a non-empty
``prompt_file`` resolvable on disk; otherwise it emits a structured
``kind: blocked`` decision with a populated ``reason``. The SKILL.md text
that previously instructed agents to defensively null-check ``prompt_file``
is now stale and removed from the source.

This migration mirrors :mod:`m_2_1_2_fix_runtime_next_skill` and uses the
shared :func:`find_skill_files` helper to refresh every installed copy of
``spec-kitty-runtime-next/SKILL.md`` across all known agent skill roots.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from ..registry import MigrationRegistry
from ..skill_update import file_contains_any, find_skill_files, write_skill_text
from .base import BaseMigration, MigrationResult

_SKILL_NAME = "spec-kitty-runtime-next"

# Match the pre-WP06 markers that we just removed from the canonical SKILL.md.
# Any installed copy still containing one of these strings is stale.
_OLD_MARKERS = [
    "Check `prompt_file` is not null, then read and execute",
    "Workaround #336: treat null prompt as blocked",
    "#336 — `prompt_file` can be `null` on `step` decisions",
    "Treat a null `prompt_file` as a blocked state",
]


@MigrationRegistry.register
class FixPromptFileWorkaroundMigration(BaseMigration):
    """Refresh runtime-next SKILL.md copies after the WP06 contract change."""

    migration_id = "3.2.0rc35_fix_prompt_file_workaround"
    description = (
        "Remove `prompt_file == null` workaround text from runtime-next skill; "
        "kind=step now always carries a resolvable prompt_file (#336 / #844)."
    )
    target_version = "3.2.0rc35"

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
