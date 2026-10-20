"""Backfill the explicit two-partition migration ledger (ADR 2026-10-17-1 §6).

A one-way adoption migration, ordered FIRST in the manifest so every later
selection in the same upgrade run sees a populated ledger. It reads the
existing ``ProjectMetadata.applied_migrations`` (normalizing legacy ids) and
writes records into the two ledgers:

* a **tracked-effect** record is backfilled unconditionally into the tracked
  ledger;
* a **clone-local** record is detect-gated — written into the per-clone ledger
  only when the effect is verifiably present on THIS checkout
  (:func:`~specify_cli.upgrade.ledger.clone_local_effect_in_place`: a git
  repository exists and ``detect()`` is False); otherwise it is left pending
  and ledger-diff re-applies it.

**Adoption baseline (#6431).** Before the ledger, a migration whose
``target_version`` was below the recorded ``spec_kitty.version`` was never
selected (the retired version window; one AT the version was still selected
when its ``detect()`` held), whether or not ``applied_migrations`` listed it: a project whose list is empty or partial had still had those
migrations' effects settled by the version stamp. Ledger-diff selection reads no
version, so backfilling the list alone left those migrations pending, and the
first ledger-era upgrade replayed them against a current project (rewriting
Mission ``meta.json`` / ``status.json`` and undoing a forced lane transition).
On FIRST adoption only -- until this migration itself is recorded as applied --
the backfill therefore also stamps every registered migration with
``target_version`` below both the recorded version and this migration's own
4.0.0rc8, and no ``applied_migrations`` or ledger entry, as settled, with the
same partition rule (tracked unconditionally, clone-local only when its effect
is in place here). This is the one-time adoption counterpart of
the init seed (``upgrade/init_seed.py``), not a revived selection window: once
this migration is settled, nothing is stamped from the version, and a migration with a
recorded ``skipped`` / ``failed`` result keeps that result (ADR 2026-10-17-1
§3: a failed one is retried).

Permanently stripping the stale on-disk ``migrations:`` block is done by
``ProjectMetadata.save`` once the ledger is adopted, not here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from kernel.clock import datetime, now_utc
from packaging.version import InvalidVersion, Version

from ..ledger import LedgerRecord, MigrationLedger, build_record, clone_local_effect_in_place, current_cli_version
from ..metadata import _LEGACY_MIGRATION_ID_MAP, MigrationRecord, ProjectMetadata
from ..registry import MigrationRegistry, migration_settled
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
    ledger_adoption = True

    def adoption_settled_ids(self, project_path: Path) -> frozenset[str]:
        """The ids :meth:`apply` will record as ``success`` (selection treats them as settled)."""
        return frozenset(item.canonical_id for item in self._plan(project_path) if item.result == _SUCCESS)

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

        # One atomic write per partition: an interrupted adoption leaves no
        # partial record set behind.
        MigrationLedger(project_path).append_many([self._record_for(item) for item in plan])
        changes = [f"Backfilled {item.canonical_id} into the {'clone-local' if item.clone_local else 'tracked'} ledger" for item in plan]
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
        settling = self._settling_records(metadata.applied_migrations)
        for canonical, record in settling.items():
            _, migration, clone_local = self._target_for(canonical)
            if self._should_skip(canonical, migration, clone_local, project_path, tracked_recorded, clone_recorded):
                continue
            plan.append(_PlanItem(canonical, migration, record.result, record.applied_at, clone_local))
        if not migration_settled(ledger, self):
            recorded = tracked_recorded | clone_recorded | set(settling)
            plan.extend(self._baseline_items(metadata.version, recorded, project_path))
        return plan

    def _baseline_items(self, recorded_version: str, recorded: set[str], project_path: Path) -> list[_PlanItem]:
        """Settled records for migrations the pre-ledger version stamp had already settled.

        Every registered migration whose ``target_version`` is below both the
        recorded version and this migration's own version, and that neither
        ``applied_migrations`` nor a ledger partition mentions, routed by the
        same partition rule as a listed record. A migration AT the recorded
        version stays pending, as the retired window still selected it when
        its ``detect()`` held. The bound below ``TARGET_VERSION`` holds because
        no CLI without the ledger shipped a migration at it: an rc8 build
        stamped ``4.0.0rc8`` before the ledger landed must still run the later
        rc8 migrations. An unparseable recorded
        version stamps nothing: with no version there was no window to honour.
        """
        try:
            ceiling = min(Version(recorded_version), Version(TARGET_VERSION))
        except (InvalidVersion, TypeError):
            return []
        stamped_at = now_utc()
        items: list[_PlanItem] = []
        for migration in MigrationRegistry.get_all():
            migration_id = str(migration.migration_id)
            if migration_id == self.migration_id or migration_id in recorded:
                continue
            if Version(migration.target_version) >= ceiling:
                continue
            clone_local = bool(getattr(migration, "clone_local_effect", False))
            if clone_local and not clone_local_effect_in_place(migration, project_path):
                continue
            items.append(_PlanItem(migration_id, migration, _SUCCESS, stamped_at, clone_local))
        return items

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
            # Detect-gated: only backfill when the effect is present here.
            if migration is None or not clone_local_effect_in_place(migration, project_path):
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
