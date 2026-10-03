"""Migration 4.0.0rc5: install the decisions/index.json union merge driver.

Sibling of ``m_3_1_1_event_log_merge_driver.py`` (status.events.jsonl),
``m_3_2_6_decisions_event_log_merge_driver.py`` (decisions.events.jsonl) and
``m_3_2_7_review_cycle_merge_driver.py`` (review-cycle-*.md):
coord-artifact-single-home-01M3V4BE WP11 (FR-009b / D13 / #5023) registers
``spec-kitty-decision-index`` for already-initialized (upgraded) consumer
clones, the same way those migrations registered their own drivers.

**``target_version`` is pinned at or below the installed package version.**
Unlike ``m_3_2_7``'s documented mismatch (filename vs. ``target_version``,
chosen because the installed package was a release candidate below the
module's own number), ``target_version`` here is ``4.0.0rc5`` -- at or below
the installed ``pyproject.toml`` version (currently ``4.0.0rc6``), so it never
exceeds it. ``spec-kitty upgrade`` /
``test_discovered_migration_targets_do_not_exceed_package_version`` skip/flag
any migration whose ``target_version`` exceeds the installed package
version -- a project already AT ``4.0.0rc5`` therefore only gains this
driver via its own ``detect()`` returning ``True`` (the ``.gitattributes``
line or the local git config is missing), never via a version bump alone
(``upgrade/registry.py``'s eligibility check).

The driver this migration seeds unions ``decisions/index.json`` ``entries``
keyed by ``decision_id`` with terminal-beats-open fold precedence (see
``run_decision_index_driver``'s docstring in ``consolidation/drivers.py``)
so two lanes that each add a decision never lose either entry under the
mission->target squash. This migration only wires the *registration*
surfaces (``.gitattributes`` entry + local git config); the reconciliation
semantics live entirely in the driver command it points at.

**Command form:** this migration writes the bare ``spec-kitty
merge-driver-decision-index %O %A %B`` command, byte-identical in shape to
every existing driver's ``command=`` string in
``specify_cli.lanes.consolidation._MERGE_DRIVERS`` -- see ``m_3_2_7``'s own
docstring for why a migration never hardcodes an environment-specific
interpreter path.
"""

from __future__ import annotations

from ..registry import MigrationRegistry
from ._merge_driver_seeding import DriverSpec, MergeDriverSeedingMigration

_DRIVERS: tuple[DriverSpec, ...] = (
    DriverSpec(
        config_key="spec-kitty-decision-index",
        name="Spec Kitty decision-index entry union merge",
        command="spec-kitty merge-driver-decision-index %O %A %B",
        pattern="kitty-specs/**/decisions/index.json",
    ),
)


@MigrationRegistry.register
class DecisionIndexMergeDriverMigration(MergeDriverSeedingMigration):
    """Install the git merge driver for decisions/index.json (FR-009b/#5023)."""

    migration_id = "4.0.0rc5_decision_index_merge_driver"
    description = "Install a union git merge driver for decisions/index.json"
    target_version = "4.0.0rc5"
    drivers = _DRIVERS
    dry_run_summary = "Would install the decisions/index.json merge driver and .gitattributes entry"
