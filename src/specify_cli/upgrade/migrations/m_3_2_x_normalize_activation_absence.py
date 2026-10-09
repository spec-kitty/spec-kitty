"""Superseded by the charter-pack cutover; kept as a recorded no-op so upgrade history stays meaningful.

It wrote an explicit ``[]`` (nothing activated) for every absent per-artifact
``activated_<kind>`` key. That contradicts the live absent-means-all contract
(``ArtifactKind.effective_when_absent``, ``PackContext.from_config``), and on a
pre-3.2.6 project it would rewrite the keys the cutover had just reset to
absent. Its ``charter:`` pointer half was unreachable: the store it resolved
existed only when the pointer was already present.
"""

from ..registry import MigrationRegistry
from .base import SupersededMigration

MIGRATION_ID = "normalize_activation_absence"
TARGET_VERSION = "3.2.6rc1"
_SUPERSEDED = "Superseded by the charter-pack cutover"


@MigrationRegistry.register
class NormalizeActivationAbsenceMigration(SupersededMigration):
    migration_id = MIGRATION_ID
    description = _SUPERSEDED
    superseded_by = _SUPERSEDED
    target_version = TARGET_VERSION
    runs_on_worktrees = False
