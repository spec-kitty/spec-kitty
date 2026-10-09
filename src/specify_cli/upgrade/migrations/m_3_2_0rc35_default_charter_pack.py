"""Superseded by the charter-pack cutover; kept as a recorded no-op so upgrade history stays meaningful.

It wrote snapshot activation lists from the retired ``default.yaml``; the cutover resets those lists instead.
"""

from ..registry import MigrationRegistry
from .base import SupersededMigration

_SUPERSEDED = "Superseded by the charter-pack cutover"


@MigrationRegistry.register
class DefaultCharterPackMigration(SupersededMigration):
    migration_id = "3.2.0rc35_default_charter_pack"
    description = _SUPERSEDED
    superseded_by = _SUPERSEDED
    target_version = "3.2.0rc35"
