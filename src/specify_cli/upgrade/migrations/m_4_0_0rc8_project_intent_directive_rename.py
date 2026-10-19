"""Migration: rename the legacy ``mission-type-scope-directive`` to ``project-intent-directive`` (FR-008, #6443).

Synthesis now names the always-synthesized directive ``project-intent-directive`` and
no longer links it to a mission type. An existing project still carries the old slug in
its artifact file, harness input, provenance, synthesis manifest, overlay and activation
stems. This migration delegates the whole conversion to the one charter-layer helper
that ``charter synthesize`` / ``resynthesize`` also call before they write
(:func:`charter.activation.api.rename_legacy_project_intent_directive`); it spells no
charter path itself.

The ledger-committed effect (``clone_local_effect = False``) travels with the commit, so a
fresh clone of an upgraded project needs no re-run. The helper is idempotent, so a repeat
run changes nothing.
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.api import (
    LegacyRenameRefusedError,
    rename_legacy_project_intent_directive,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


@MigrationRegistry.register
class ProjectIntentDirectiveRenameMigration(BaseMigration):
    """Move a legacy ``mission-type-scope-directive`` onto ``project-intent-directive``."""

    migration_id = "4.0.0rc8_project_intent_directive_rename"
    description = "Rename the mission-type-scope-directive to project-intent-directive and drop its dead mission-type edge (#6443)"
    target_version = "4.0.0rc8"

    def detect(self, project_path: Path) -> bool:
        try:
            pending: bool = rename_legacy_project_intent_directive(project_path, dry_run=True).pending
            return pending
        except LegacyRenameRefusedError:
            # A refusal is not "nothing to do": route it through apply() so the runner records the reason.
            return True

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        try:
            report = rename_legacy_project_intent_directive(project_path, dry_run=dry_run)
        except LegacyRenameRefusedError as exc:
            return MigrationResult(success=False, errors=[str(exc)])
        prefix = "Would " if dry_run else ""
        return MigrationResult(success=True, changes_made=[f"{prefix}{action}" for action in report.actions])
