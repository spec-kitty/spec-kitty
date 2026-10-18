"""Seed the migration ledger at fresh-project creation (finding-1 remediation).

A fresh ``spec-kitty init`` already embodies the outcome of every migration
declared up to the current CLI version: the scaffold it writes is in the shape
those migrations produce. Yet without a ledger, the first ``spec-kitty upgrade``
on that project diffs an EMPTY ledger against the full declared set and selects
ALL historical migrations (ledger-diff selection, ADR 2026-10-17-1 §3). Replaying
~114 migrations against an already-current project is not idempotent: two of them
disagree over ``mission_type_activations`` -- the rc35 activation migration adds
it to ``config.yaml`` while the charter-bundle fold moves it into
``charter.yaml`` -- so the first upgrade mutates config and auto-commits,
breaking NFR-002.

This module records, at init time, every migration the fresh project has
effectively already satisfied, so the first ``upgrade`` SELECTS NOTHING -- the
Liquibase "changelog-sync for a new project" baseline, a one-time init stamp,
NOT a revived version-selection window.

Partitioning (ADR 2026-10-17-1 §1) is preserved exactly, routed by each
migration's ``clone_local_effect`` through the shipped ledger API:

* a **tracked-effect** migration (``clone_local_effect`` False) is seeded
  unconditionally into the tracked ``.kittify/migration-ledger.jsonl`` -- its
  effect travels with the commit, so suppressing its re-selection on every
  clone is correct;
* a **clone-local** migration (``clone_local_effect`` True) is seeded into the
  per-clone (gitignored) ``.kittify/migrations/clone-local.jsonl``, and only
  when its effect is actually present on THIS checkout (``detect()`` False).
  Because that ledger never travels, a pulled clone still re-applies the
  clone-local effect (#6233); seeding it on the origin never leaks a tracked
  record that would suppress that re-apply.

Idempotent: a migration already recorded as applied (``success``) in its
authoritative partition is never seeded twice (:func:`migration_settled`).
"""

from __future__ import annotations

from pathlib import Path

from .ledger import MigrationLedger, build_record
from .registry import MigrationRegistry, migration_settled

#: The honest init-seed result stamped on every seeded record.
_SEED_RESULT = "success"


def _effect_absent(migration: object, project_root: Path) -> bool:
    """True when a clone-local migration's own ``detect()`` says the effect is absent here.

    ``detect()`` True means the OLD state is present -- i.e. the effect is not
    yet applied on this checkout -- so the migration is left pending and the
    first ``upgrade`` applies it. Any ``detect()`` error is treated as "absent"
    so the seed leaves the migration pending rather than wrongly suppressing it;
    the seed never crashes init on one migration's probe.
    """
    detect = getattr(migration, "detect", None)
    if detect is None:
        return True
    try:
        return bool(detect(project_root))
    except Exception:  # noqa: BLE001 - a flaky detect() must leave the migration pending, never fail the seed
        return True


def seed_migration_ledger_for_init(project_root: Path) -> list[str]:
    """Seed the two-partition ledger for a freshly-created project.

    Records every declared migration the fresh project has already satisfied
    into its authoritative partition, so the first ``spec-kitty upgrade`` is a
    no-op. Tracked-effect migrations are seeded unconditionally; clone-local
    migrations only when their effect is present here (``detect()`` False).

    Args:
        project_root: The project root (the ``.kittify`` parent).

    Returns:
        The migration ids recorded this call, for optional reporting. An empty
        list when every declared migration is already recorded (idempotent
        re-entry) or left pending.
    """
    from .migrations import auto_discover_migrations

    auto_discover_migrations()
    ledger = MigrationLedger(project_root)
    seeded: list[str] = []
    for migration in MigrationRegistry.get_all():
        if migration_settled(ledger, migration):
            continue
        clone_local = bool(getattr(migration, "clone_local_effect", False))
        if clone_local and _effect_absent(migration, project_root):
            # Effect not yet present on this checkout: leave it pending so the
            # first upgrade applies it (and so a pulled clone re-applies it, #6233).
            continue
        ledger.append(build_record(migration, _SEED_RESULT))
        seeded.append(str(migration.migration_id))
    return seeded
