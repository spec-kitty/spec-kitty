"""Install the lane work-tip recorder hooks for existing clones (#5115).

WP07 (single-branch-topology-honesty-01M3M22V, T030): a project upgraded from
before the lane-tip recorder existed never gets its ``post-commit`` /
``post-rewrite`` hooks installed until its next lane allocation
(``allocate_lane_worktree`` / ``implement_support.create_lane_workspace``).
For a mission created before the upgrade and never re-entered, that means no
new lane commit records a tip until the operator happens to touch it again --
a real gap in FR-018's "every commit records the tip" promise. This one-shot
migration closes it by installing the recorder into every already-cloned
project's hooks dir up front, on `spec-kitty upgrade`, exactly like an
`implement` call would.

See ``contracts/lane-work-tip.md`` for the hook contract and
:mod:`specify_cli.policy.lane_tip_recorder` for the installer this delegates
to (a SEPARATE installer from the pre-commit ownership guard's
``hook_installer.py`` -- plan.md M5).
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4_0_0rc5_install_lane_tip_recorder"
TARGET_VERSION = "4.0.0rc5"


def _pending(project_path: Path) -> list[str]:
    from specify_cli.policy.lane_tip_recorder import pending_hook_names

    return pending_hook_names(project_path)


@MigrationRegistry.register
class InstallLaneTipRecorderMigration(BaseMigration):
    """Install the lane-tip recorder into an existing clone's hooks dir (#5115)."""

    migration_id = MIGRATION_ID
    description = "Install the lane work-tip recorder (post-commit + post-rewrite) for existing clones (#5115)."
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        return bool(_pending(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if self.detect(project_path):
            return True, ""
        return False, "lane-tip recorder already installed in every hook slot (or no git repository present)"

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        pending = _pending(project_path)
        if dry_run:
            changes = [f"would install lane-tip recorder hook: {name}" for name in pending]
            return MigrationResult(success=True, changes_made=changes)

        from specify_cli.policy.lane_tip_recorder import install_lane_tip_recorder

        installed = install_lane_tip_recorder(project_path)
        changes = [f"installed lane-tip recorder hook: {path.name}" for path in installed]
        return MigrationResult(success=True, changes_made=changes)
