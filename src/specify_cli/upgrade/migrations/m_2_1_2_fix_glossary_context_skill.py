"""Superseded by the charter-pack cutover; kept as a recorded no-op so upgrade history stays meaningful.

It rewrote the glossary-context skill from a shipped copy the cutover retires.
"""

from ..registry import MigrationRegistry
from .base import SupersededMigration

_SUPERSEDED = "Superseded by the charter-pack cutover"


@MigrationRegistry.register
class FixGlossaryContextSkillMigration(SupersededMigration):
    migration_id = "2.1.2_fix_glossary_context_skill"
    description = _SUPERSEDED
    superseded_by = _SUPERSEDED
    target_version = "2.1.2"
