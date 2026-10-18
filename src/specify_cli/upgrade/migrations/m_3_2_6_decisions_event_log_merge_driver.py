"""Migration 3.2.6: install the decisions.events.jsonl git merge driver.

Sibling of ``m_3_1_1_event_log_merge_driver.py`` (status.events.jsonl) and
``m_3_2_6_meta_traces_merge_drivers.py`` (meta.json + traces/*.md). #2709 /
FR-003: ``decisions.events.jsonl`` is a both-sides-divergent append-only event
log, so the squash mission->target integration (``git merge --squash -X theirs``)
must reconcile it with the union driver instead of clobbering it. It reuses the
pre-existing ``spec-kitty-event-log`` driver (same config/command as
``status.events.jsonl`` -- the union algorithm is filename-agnostic).

This driver ships as its OWN migration id rather than folded into
``m_3_2_6_meta_traces_merge_drivers``. The runner short-circuits at
``migration_settled(migration)`` -- the two-partition ledger's success-only
applied check (ADR 2026-10-17-1) -- BEFORE it ever calls ``detect()``
(``runner._apply_migration``), so a consumer who already recorded the
meta+traces migration as ``success`` on a prior 3.2.6 upgrade would have it
skipped forever and never gain this line -- re-inheriting #2709 on
``decisions.events.jsonl``. A distinct id leaves the ledger with no ``success``
record for it, so the runner reaches ``detect()`` and seeds the driver
on their next upgrade. This mirrors how ``status.events.jsonl`` and the gate
artifacts each carry their own migration id.
"""

from __future__ import annotations

from ..registry import MigrationRegistry
from ._merge_driver_seeding import DriverSpec, MergeDriverSeedingMigration

_DRIVERS: tuple[DriverSpec, ...] = (
    DriverSpec(
        config_key="spec-kitty-event-log",
        name="Spec Kitty event log union merge",
        command="spec-kitty merge-driver-event-log %O %A %B",
        pattern="kitty-specs/**/decisions.events.jsonl",
    ),
)


@MigrationRegistry.register
class DecisionsEventLogMergeDriverMigration(MergeDriverSeedingMigration):
    """Install the git merge driver for decisions.events.jsonl (#2709)."""

    migration_id = "3.2.6_decisions_event_log_merge_driver"
    description = "Install a semantic git merge driver for decisions.events.jsonl"
    target_version = "3.2.6rc1"
    drivers = _DRIVERS
    dry_run_summary = "Would install the decisions.events.jsonl merge driver and .gitattributes entry"
