"""Migration: move the activation keys into the activation ledger (FR-003/FR-004, ADR 2026-10-19-1).

``.kittify/charter/activation.yaml`` is the single authority for charter
activation. A project an earlier CLI wrote keeps its ``activated_<kind>``,
``activated_kinds`` and ``mission_type_activations`` keys on the legacy
surface: the ``charter.yaml`` the ``config.yaml`` ``charter:`` pointer names,
else ``config.yaml`` itself, sometimes with a leftover ``config.yaml`` copy.
This migration moves them, verbatim, and re-stamps the synthesis manifest.

It is a thin shell over the activation seam's planner and apply functions
(:func:`charter.activation.api.plan_ledger_migration` /
:func:`~charter.activation.api.apply_ledger_migration`), the same pair
``spec-kitty migrate activation-ledger`` runs:

* it refuses, writing nothing, when the legacy surfaces disagree with each
  other or with an existing ledger, or when one holds a ``deactivated_<kind>``
  key (no migration ever writes a deny list);
* each step is idempotent, so a run that stopped between steps is completed
  by the next one, and a second run changes zero bytes (NFR-002);
* a refusal is a failed result, so no ``success`` record settles it and the
  next upgrade retries once the operator made the files agree.

Tracked effect (``clone_local_effect = False``): the moved keys travel with the
commit. The main checkout only (``runs_on_worktrees = False``).
"""

from __future__ import annotations

from pathlib import Path

from charter.activation.api import (
    ActiveCharterConfigError,
    LedgerMigrationPlan,
    apply_ledger_migration,
    plan_ledger_migration,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult, MigrationStateUnreadableError

__all__ = ["ActivationLedgerMigration"]


def _describe_moves(project_path: Path, plan: LedgerMigrationPlan) -> list[str]:
    """One human line per ``(key, from-file, to-file)`` move, paths relative to *project_path*."""
    return [f"{move.key}: {_relative(project_path, move.source)} -> {_relative(project_path, move.target)}" for move in plan.moves]


def _relative(project_path: Path, path: Path) -> str:
    try:
        return path.relative_to(project_path).as_posix()
    except ValueError:
        return str(path)


@MigrationRegistry.register
class ActivationLedgerMigration(BaseMigration):
    """Move the legacy activation keys into ``.kittify/charter/activation.yaml``."""

    migration_id = "4.0.0rc8_activation_ledger"
    description = "Move charter activation keys into the activation ledger (.kittify/charter/activation.yaml)"
    target_version = "4.0.0rc8"
    runs_on_worktrees = False

    def _plan(self, project_path: Path) -> LedgerMigrationPlan:
        try:
            return plan_ledger_migration(project_path)
        except ActiveCharterConfigError as exc:
            raise MigrationStateUnreadableError(exc.body) from exc

    def detect(self, project_path: Path) -> bool:
        """True when there is something to move, strip or re-stamp, or a refusal to report."""
        return not self._plan(project_path).noop

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Always applicable: a refusal is reported by :meth:`apply`, as a failure."""
        del project_path
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Move the keys (or, on a dry run, list the moves); a refusal fails and writes nothing."""
        plan = self._plan(project_path)
        if plan.refusal is not None:
            return MigrationResult(success=False, errors=[plan.refusal.message])
        moves = _describe_moves(project_path, plan)
        if dry_run:
            return MigrationResult(success=True, changes_made=[f"Would move {line}" for line in moves])
        written = apply_ledger_migration(project_path, plan)
        changes = [f"Moved {line}" for line in moves]
        changes.extend(f"Wrote {_relative(project_path, path)}" for path in written)
        return MigrationResult(success=True, changes_made=changes)
