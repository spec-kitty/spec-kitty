"""Re-stamp ``single_branch`` missions whose ``lanes.json`` has code lanes (#5100).

Invariant T-1 (``data-model.md``, mission single-branch-topology-honesty-01M3M22V):
``topology == single_branch`` implies ``lanes.json`` has no code lane. Before this
mission's fail-closed writer guard (:func:`mission_runtime.context.assert_topology_matches_manifest`,
wired at the two writer chokepoints in a later work package) existed, a
``single_branch`` mission's lane computation was not yet topology-aware, so its
``lanes.json`` could accumulate ordinary code lanes exactly like a ``lanes``
mission while ``meta.json`` still carried the stale ``topology: single_branch``
stamp from create time. This forward migration repairs that drift for every
already-affected mission: it changes only the stored ``topology`` field, from
``single_branch`` to ``lanes``, and touches nothing else.

See ``contracts/topology-restamp.md`` for the full selection contract.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0rc5_single_branch_code_lanes_restamp"
TARGET_VERSION = "4.0.0rc5"


def _selectable(project_path: Path) -> bool:
    from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

    results = restamp_single_branch_with_code_lanes(project_path, dry_run=True)
    return any(result.action == "restamped" for result in results)


@MigrationRegistry.register
class SingleBranchCodeLanesRestampMigration(BaseMigration):
    """Re-stamp an un-migrated ``single_branch`` + code-lane mission to ``lanes``."""

    migration_id = MIGRATION_ID
    description = "Re-stamp single_branch missions whose lanes.json has code lanes to topology: lanes (Invariant T-1 repair, #5100)."
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return _selectable(project_path)

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "no single_branch mission with a code lane found"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        from specify_cli.migration.backfill_topology import restamp_single_branch_with_code_lanes

        results = restamp_single_branch_with_code_lanes(project_path, dry_run=dry_run)
        changes = [f"{result.slug}: topology single_branch -> lanes" for result in results if result.action == "restamped"]
        errors = [f"{result.slug}: {result.reason}" for result in results if result.action == "error"]
        return MigrationResult(success=not errors, changes_made=changes, errors=errors)
