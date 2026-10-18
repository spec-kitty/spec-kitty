"""Backfill the explicit two-partition migration ledger (ADR 2026-10-17-1 §6).

A one-way adoption migration, ordered FIRST in the manifest so every later
selection in the same upgrade run sees a populated ledger. It reads the
existing ``ProjectMetadata.applied_migrations`` (normalizing legacy ids) and
writes records into the two ledgers:

* a **tracked-effect** record is backfilled unconditionally into the tracked
  ledger;
* a **clone-local** record is detect-gated — written into the per-clone ledger
  only when the migration's own ``detect()`` confirms the effect is present on
  THIS checkout (``detect()`` True means the old state is present, i.e. the
  effect is *absent*, so it is left pending and ledger-diff re-applies it).

WP01 scope: this writes ledger records. Permanently stripping the stale on-disk
``migrations:`` block is WP-F's concern and is deliberately not done here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.clock import datetime

from ..ledger import LedgerRecord, MigrationLedger, build_record, current_cli_version
from ..metadata import _LEGACY_MIGRATION_ID_MAP, MigrationRecord, ProjectMetadata
from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc8_backfill_migration_ledger"
TARGET_VERSION = "4.0.0rc8"
_KITTIFY_DIRNAME = ".kittify"
_SUCCESS = "success"


@dataclass(frozen=True)
class _PlanItem:
    """One record the backfill intends to write."""

    canonical_id: str
    migration: BaseMigration | None
    result: str
    applied_at: datetime
    clone_local: bool


@MigrationRegistry.register
class BackfillMigrationLedgerMigration(BaseMigration):
    """Backfill the migration ledger from ``metadata.yaml.applied_migrations``."""

    migration_id = MIGRATION_ID
    description = "Backfill the two-partition migration ledger from metadata.applied_migrations"
    target_version = TARGET_VERSION
    runs_on_worktrees = False

    def detect(self, project_path: Path) -> bool:
        """True when metadata records migrations the ledger does not yet carry."""
        return bool(self._plan(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 - always safe (idempotent)
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        plan = self._plan(project_path)
        if not plan:
            return MigrationResult(success=True, changes_made=["migration ledger already backfilled"])
        if dry_run:
            return MigrationResult(success=True, changes_made=[f"Would backfill {len(plan)} ledger record(s)"])

        ledger = MigrationLedger(project_path)
        changes: list[str] = []
        for item in plan:
            ledger.append(self._record_for(item))
            partition = "clone-local" if item.clone_local else "tracked"
            changes.append(f"Backfilled {item.canonical_id} into the {partition} ledger")
        return MigrationResult(success=True, changes_made=changes)

    # -- internals ---------------------------------------------------------- #

    @staticmethod
    def _target_for(record_id: str) -> tuple[str, BaseMigration | None, bool]:
        canonical = _LEGACY_MIGRATION_ID_MAP.get(record_id, record_id)
        migration = MigrationRegistry.get_by_id(canonical)
        clone_local = bool(getattr(migration, "clone_local_effect", False)) if migration is not None else False
        return canonical, migration, clone_local

    def _plan(self, project_path: Path) -> list[_PlanItem]:
        metadata = ProjectMetadata.load(project_path / _KITTIFY_DIRNAME)
        if metadata is None:
            return []
        ledger = MigrationLedger(project_path)
        tracked_recorded = {r.id for r in ledger.read_tracked()}
        clone_recorded = {r.id for r in ledger.read_clone_local()}

        plan: list[_PlanItem] = []
        for canonical, record in self._settling_records(metadata.applied_migrations).items():
            _, migration, clone_local = self._target_for(canonical)
            if self._should_skip(canonical, migration, clone_local, project_path, tracked_recorded, clone_recorded):
                continue
            plan.append(_PlanItem(canonical, migration, record.result, record.applied_at, clone_local))
        return plan

    @staticmethod
    def _settling_records(records: list[MigrationRecord]) -> dict[str, MigrationRecord]:
        """One record per canonical id, in first-seen order, preferring a ``success``.

        ``record_migration`` appends a new entry whenever a result changes, so a
        retried migration carries ``[skipped|failed, success]``. Keeping the
        first entry would leave it unsettled and re-selected on every upgrade.
        """
        chosen: dict[str, MigrationRecord] = {}
        for record in records:
            canonical = _LEGACY_MIGRATION_ID_MAP.get(record.id, record.id)
            if canonical not in chosen or record.result == _SUCCESS:
                chosen[canonical] = record
        return chosen

    @staticmethod
    def _should_skip(
        canonical: str,
        migration: BaseMigration | None,
        clone_local: bool,
        project_path: Path,
        tracked_recorded: set[str],
        clone_recorded: set[str],
    ) -> bool:
        if clone_local:
            # Detect-gated: only backfill when the effect is present here
            # (detect() True == old state present == effect absent).
            if migration is None or migration.detect(project_path):
                return True
            return canonical in clone_recorded
        return canonical in tracked_recorded

    @staticmethod
    def _record_for(item: _PlanItem) -> LedgerRecord:
        if item.migration is not None:
            return build_record(item.migration, item.result, applied_at=item.applied_at)
        # An id with no registered migration (retired/renamed): record it
        # faithfully, without a drift hash (there is no source to hash).
        return LedgerRecord(
            id=item.canonical_id,
            applied_at=item.applied_at,
            result=item.result,
            identity=item.canonical_id,
            content_hash="",
            cli_version=current_cli_version(),
            clone_local=item.clone_local,
        )
