"""Shipped migrations superseded by a later one, declared without editing them (#6589).

A shipped migration module is never edited (DIRECTIVE_044): its bytes are its
``content_hash``. When a later migration replaces what an older one wrote, the
older one is listed here instead. :meth:`MigrationRegistry.register` then
registers a :class:`SupersededMigration` substitute under the same id, so
every registry consumer (selection, the runner, ``upgrade --dry-run``,
``migrate ledger``, the adoption backfill) sees a recorded no-op: ``detect()``
is always False and the runner records it ``skipped``. The decorator still
returns the shipped class, so a direct import keeps the original behaviour.

The substitute keeps the original's identity, routing key and defining module,
so its ``content_hash`` stays the shipped module's hash and recorded history
never reads as drift. Because a ``skipped`` record does not settle a
migration, a superseded one is selected and re-skipped on every run; that is
idempotent. The runner marks the substitute's record with its
``superseded_by`` note, so a successor can tell that no-op apart from a
``skipped`` the shipped migration recorded itself (#6629). ADR ``2026-10-17-1``, Amendment 2026-10-25.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .migrations.base import BaseMigration

#: Superseded migration id -> the id of the migration that replaced it.
SUPERSEDED_MIGRATIONS: dict[str, str] = {
    # Both wrote rows that 4.0.0rc8_narrow_agent_gitignore removes; re-selected
    # after a ``skipped`` record, they wrote ``.agents/skills/`` and the
    # ``.cursor/`` rows back on the next upgrade.
    "3.2.5_agents_skills_gitignore_backfill": "4.0.0rc8_narrow_agent_gitignore",
    "3.2.6rc3_narrow_cursor_gitignore": "4.0.0rc8_narrow_agent_gitignore",
    # It seeded an absent activated_<kind> key with the whole in-force set, which
    # synthesis then read as an operator's activation (#6629); the successor
    # never writes an absent key and promotes through the activation ledger.
    "unify_charter_activation_promote_answers": "4.0.0rc8_promote_interview_selections",
    # These four rewrote a ``kitty-specs/`` residue folder (a child with no
    # ``spec.md`` / ``meta.json`` that git does not recognise as a Mission);
    # each successor repairs the same Missions and leaves residue untouched.
    "0.9.0_frontmatter_only_lanes": "0.9.0_residue_safe_frontmatter_only_lanes",  # #6669: residue-aware successor
    "0.9.1_complete_migration": "0.9.1_residue_safe_complete_migration",  # #6669: residue-aware successor
    "2.0.6_consistency_sweep": "2.0.6_residue_safe_consistency_sweep",  # #6669: residue-aware successor
    "3.1.1_normalize_status_json": "3.1.1_residue_safe_normalize_status_json",  # #6669: residue-aware successor
}

#: Class attributes the substitute carries over from the shipped class.
_CARRIED_ATTRIBUTES = (
    "migration_id",
    "description",
    "target_version",
    "min_version",
    "runs_on_worktrees",
    "runs_first",
    "requires_git_repository",
    "clone_local_effect",
    "identity",
    "content_hash_sources",
)


def superseded_note(successor_id: str) -> str:
    """The ``superseded_by`` text for a migration replaced by *successor_id*."""
    return f"Superseded by {successor_id}"


def substitute_if_superseded(migration_class: type[BaseMigration]) -> type[BaseMigration]:
    """The class to register for *migration_class*: a superseded substitute, or the class itself."""
    successor = SUPERSEDED_MIGRATIONS.get(migration_class.migration_id)
    if successor is None:
        return migration_class
    # Lazy import: ``base`` must not load at registry import.
    from .migrations.base import SupersededMigration

    namespace: dict[str, object] = {name: getattr(migration_class, name) for name in _CARRIED_ATTRIBUTES}
    namespace.update(
        {
            # The defining module stays the shipped one, so ``content_hash`` hashes its bytes.
            "__module__": migration_class.__module__,
            "__qualname__": migration_class.__qualname__,
            "__doc__": f"{migration_class.__name__}, registered as a recorded no-op. {superseded_note(successor)}.",
            "superseded_by": superseded_note(successor),
        }
    )
    return type(migration_class.__name__, (SupersededMigration,), namespace)
