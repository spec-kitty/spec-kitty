"""Stamp ``merged_at`` on Missions that landed before #4090 (#7433).

The status read door and ``spec-kitty next`` take "has this Mission landed" from one signal,
the reopen-aware ``merged_at`` marker (``mission_runtime.mission_has_landed``, ADR
``2026-11-06-2``, #7335). A Mission that landed before consolidation wrote that marker (#4090)
has none, so it reads as not landed; a coordination topology one then refuses with
``COORDINATION_BRANCH_DELETED`` because consolidation removed its coordination branch. This
migration stamps the marker when the Mission's committed status log, read through the status
read door, shows every work package done or canceled (at least one done) and no reopen, dated by
the latest transition to done. The rule lives in :mod:`specify_cli.status.landing_evidence`; the
backfill in :mod:`specify_cli.migration.backfill_merged_at`.

``meta.json`` is tracked, so the effect travels with the commit: the record goes to the tracked
partition (``clone_local_effect`` stays ``False``). The status read door reads the git worktree
registry and coordination refs, so the migration declares ``requires_git_repository``.
``apply()`` is idempotent: a stamped Mission is no longer selected, and a Mission without that
evidence is reported, never written.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

if TYPE_CHECKING:
    from specify_cli.migration.backfill_merged_at import MergedAtBackfillResult

MIGRATION_ID = "4.0.0rc8_backfill_merged_at"
TARGET_VERSION = "4.0.0rc8"


def _skip_warnings(results: list[MergedAtBackfillResult]) -> list[str]:
    """One warning per skip reason, naming every Mission it covers (with its detail)."""
    by_reason: dict[str, list[str]] = defaultdict(list)
    for result in results:
        if result.action != "stamped":
            by_reason[result.reason].append(f"{result.slug} ({result.detail})" if result.detail else result.slug)
    return [f"merged_at not stamped on {len(named)} Mission(s): {reason}: {'; '.join(named)}" for reason, named in sorted(by_reason.items())]


@MigrationRegistry.register
class BackfillMergedAtMigration(BaseMigration):
    """Stamp the ``merged_at`` landing marker on pre-#4090 landed Missions."""

    migration_id = MIGRATION_ID
    description = (
        "Stamp merged_at on Missions that landed before #4090 (every work package done or canceled in the committed status log, "
        "at least one done, never reopened), dated by the latest done transition, so they read as landed (#7433)."
    )
    target_version = TARGET_VERSION
    runs_on_worktrees = False
    requires_git_repository = True

    def detect(self, project_path: Path) -> bool:
        from specify_cli.migration.backfill_merged_at import has_merged_at_to_backfill

        return has_merged_at_to_backfill(project_path)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no Mission without merged_at has a status log showing every work package done or canceled"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        from specify_cli.migration.backfill_merged_at import backfill_merged_at

        results = backfill_merged_at(project_path, dry_run=dry_run)
        verb = "would stamp" if dry_run else "stamped"
        changes = [f"{result.slug}: {verb} merged_at {result.merged_at} (latest done transition)" for result in results if result.action == "stamped"]
        return MigrationResult(success=True, changes_made=changes, warnings=_skip_warnings(results))
