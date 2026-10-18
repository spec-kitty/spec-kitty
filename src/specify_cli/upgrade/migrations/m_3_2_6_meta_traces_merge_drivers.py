"""Migration 3.2.6: install the meta.json + traces/*.md git merge drivers.

Sibling of ``m_3_1_1_event_log_merge_driver.py``. #2709 / FR-003 / FR-004 / C-006:
the squash mission→target integration (``git merge --squash -X theirs``) must
reconcile target-newer ``meta.json`` acceptance/VCS provenance and ``traces/*.md``
sections instead of clobbering them. Custom merge drivers override ``-X theirs``
on their registered paths, so this migration seeds the ``.gitattributes`` mapping
plus the local ``merge.<driver>.*`` config for both drivers.

The seeding body itself lives in ``_merge_driver_seeding.py`` and is shared with
the other driver-seeding migrations (DIRECTIVE_044 — parametrized, not cloned).

The ``decisions.events.jsonl`` driver (added by
coord-write-placement-closure-01KYCF83 WP06) does NOT live here — it ships as
its own migration id in ``m_3_2_6_decisions_event_log_merge_driver.py``. Folding
it into this migration's ``drivers`` tuple would have stranded it on every repo
that already recorded ``3.2.6_meta_traces_merge_drivers`` as ``success``, since
``runner._apply_migration`` short-circuits at ``migration_settled()`` (the
two-partition ledger's success-only applied check, ADR 2026-10-17-1) before ever
calling ``detect()`` (a per-driver ``.gitattributes`` check never gets a chance
to run). A distinct id is the only way already-upgraded repos gain it.
"""

from __future__ import annotations

from ..registry import MigrationRegistry
from ._merge_driver_seeding import DriverSpec, MergeDriverSeedingMigration

_DRIVERS: tuple[DriverSpec, ...] = (
    DriverSpec(
        config_key="spec-kitty-meta",
        name="Spec Kitty mission meta field merge",
        command="spec-kitty merge-driver-meta %O %A %B",
        pattern="kitty-specs/**/meta.json",
    ),
    DriverSpec(
        config_key="spec-kitty-traces",
        name="Spec Kitty mission traces union merge",
        command="spec-kitty merge-driver-traces %O %A %B",
        pattern="kitty-specs/**/traces/*.md",
    ),
)


@MigrationRegistry.register
class MetaTracesMergeDriverMigration(MergeDriverSeedingMigration):
    """Install git merge drivers for meta.json and traces/*.md (#2709).

    decisions.events.jsonl ships as its own migration id — see the module
    docstring."""

    migration_id = "3.2.6_meta_traces_merge_drivers"
    description = "Install semantic git merge drivers for meta.json and traces/*.md"
    target_version = "3.2.6rc1"
    drivers = _DRIVERS
    dry_run_summary = "Would install meta.json + traces/*.md merge drivers and .gitattributes entries"
