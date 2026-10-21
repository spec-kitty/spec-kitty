"""Migration registry for Spec Kitty upgrade system."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from .ledger import SETTLED_RESULT, MigrationLedger
from .manifest import load_order_manifest

if TYPE_CHECKING:
    from .migrations.base import BaseMigration


class MigrationRegistry:
    """Registry of all available migrations, ordered by target version."""

    _migrations: dict[str, type[BaseMigration]] = {}

    # Required fields for all migrations
    REQUIRED_FIELDS = ["migration_id", "description", "target_version"]

    @classmethod
    def register(cls, migration_class: type[BaseMigration]) -> type[BaseMigration]:
        """Decorator to register a migration class.

        Args:
            migration_class: The migration class to register

        Returns:
            The same migration class (for decorator use)

        Raises:
            ValueError: If migration_id is not set, required fields are missing,
                        or a migration with this ID is already registered
        """
        # Validate required fields
        for field in cls.REQUIRED_FIELDS:
            value = getattr(migration_class, field, None)
            if not value:
                raise ValueError(f"Migration {migration_class.__name__} is missing required field '{field}'")

        migration_id = migration_class.migration_id

        # Check for duplicate registration
        if migration_id in cls._migrations:
            existing = cls._migrations[migration_id]
            raise ValueError(f"Duplicate migration ID '{migration_id}'. Already registered by {existing.__name__}, cannot register {migration_class.__name__}")

        if getattr(migration_class, "runs_first", False):
            first = next((m for m in cls._migrations.values() if m.runs_first), None)
            if first is not None:
                raise ValueError(f"Migration {migration_class.__name__} sets runs_first, but {first.__name__} already does; at most one migration may run first")

        cls._migrations[migration_id] = migration_class
        return migration_class

    @classmethod
    def get_all(cls) -> list[BaseMigration]:
        """Get all migrations as instances, in declared (order-manifest) order.

        The checked-in ``migrations/order_manifest.txt`` is the single ordering
        authority (ADR ``2026-10-17-1`` §2): a migration's position is its
        manifest index. ``Version(target_version)`` is demoted to a fallback
        cross-check — it orders only migrations that are *not* in the manifest
        (the planted classes test registries register), which sort after every
        manifest entry. Every registered migration IS in the manifest, so the
        real registry is returned in pure manifest order (the annotated
        runs-first backfill leads, ahead of its later version slot).

        Returns:
            List of migration instances in manifest order (version fallback for
            any migration absent from the manifest).
        """
        instances = [m() for m in cls._migrations.values()]
        order = load_order_manifest()
        index = {migration_id: position for position, migration_id in enumerate(order)}
        fallback = len(order)
        return sorted(
            instances,
            key=lambda m: (index.get(m.migration_id, fallback), Version(m.target_version)),
        )

    @classmethod
    def get_applicable(cls, from_version: str, to_version: str, project_path: Path | None = None) -> list[BaseMigration]:
        """Get the migrations a run should apply, by ledger-diff (ADR 2026-10-17-1 §3).

        Selection is **declared minus applied**: a declared migration (in
        :meth:`get_all` manifest order) is selected when the partition that is
        authoritative for it — the per-clone ledger when ``clone_local_effect``
        else the tracked ledger — does not record it as **successfully applied**
        (:func:`migration_settled`), OR when
        :meth:`BaseMigration.reselect_when_recorded` forces it (a ``runs_first``
        migration whose ``structural_detect`` reports the legacy state present).
        A ``skipped`` record (not-needed / Superseded) or a ``failed`` record
        does NOT settle a migration: a not-needed one is re-evaluated each run
        (and re-skipped idempotently), a failed one is retried.
        The version window (``from_v < target <= to_v``) is RETIRED as the
        applied authority; ``detect()``/``can_apply`` stay the runner's
        idempotency guard, not the selection authority (C-003). A drifted source
        never changes selection — a recorded migration stays recorded whatever
        its content now hashes to (C-004).

        ``from_version`` is kept for call-compatibility and the downgrade
        cross-check the caller runs; selection no longer reads it. ``to_version``
        is the run's requested target and stays an UPPER bound (#6431): a
        migration declared for a later version than the run upgrades to is out
        of this run's scope -- neither selected nor settled -- so
        ``upgrade --target X`` never applies work it then stamps as version X.
        An unparseable target caps nothing, and a ``ledger_adoption`` migration
        is never capped. While a ledger-adoption migration is unsettled, the ids
        it will settle on apply count as settled here, so a preview or dry run
        selects exactly what the real run applies.

        Args:
            from_version: Current version (unused by selection; see above).
            to_version: Requested target version; migrations above it are out of scope.
            project_path: Project root whose two-partition ledger is diffed. When
                ``None`` there is no ledger to diff, so every declared migration
                is returned in manifest order (production callers always pass a
                path) and no legacy activation scope is entered.

        Returns:
            List of applicable migrations in manifest order.
        """
        del from_version  # retired as the applied authority (§3)

        all_migrations = [m for m in cls.get_all() if m.ledger_adoption or _within_target(m, to_version)]
        if project_path is None:
            return all_migrations

        # Selection runs inside the upgrade-only legacy activation scope: a
        # ``reselect_when_recorded`` / ``structural_detect`` that reads activation
        # must see the legacy surface exactly as the shipped migration expects
        # (a selection-time exception it turns into ``True`` would silently
        # re-select). Lazy import: ``base`` must not load at registry import.
        from .migrations.base import legacy_upgrade_scope

        path = Path(project_path)
        ledger = MigrationLedger(path)
        selected: list[BaseMigration] = []
        with legacy_upgrade_scope(path):
            adopting = _pending_adoption_ids(ledger, all_migrations, path)
            for migration in all_migrations:
                settled = migration_settled(ledger, migration) or migration.migration_id in adopting
                if not settled or migration.reselect_when_recorded(path):
                    selected.append(migration)
        return selected

    @classmethod
    def get_by_id(cls, migration_id: str) -> BaseMigration | None:
        """Get a specific migration by ID.

        Args:
            migration_id: The migration ID to look up

        Returns:
            Migration instance if found, None otherwise
        """
        migration_class = cls._migrations.get(migration_id)
        return migration_class() if migration_class else None

    @classmethod
    def clear(cls) -> None:
        """Clear all registered migrations (for testing)."""
        cls._migrations.clear()


def _pending_adoption_ids(ledger: MigrationLedger, migrations: list[BaseMigration], project_path: Path) -> frozenset[str]:
    """Ids an unsettled ledger-adoption migration in *migrations* will settle when it applies (#6431)."""
    ids: set[str] = set()
    for migration in migrations:
        if migration.ledger_adoption and not migration_settled(ledger, migration):
            ids |= migration.adoption_settled_ids(project_path) - {migration.migration_id}
    return frozenset(ids)


def _within_target(migration: BaseMigration, to_version: str) -> bool:
    """True when *migration* is declared at or below the run's requested target (#6431).

    An unparseable target (or migration version) caps nothing: the run keeps
    its full declared set rather than silently dropping work.
    """
    try:
        return Version(migration.target_version) <= Version(to_version)
    except (InvalidVersion, TypeError):
        return True


def migration_settled(ledger: MigrationLedger, migration: BaseMigration) -> bool:
    """True when *migration*'s authoritative ledger partition records it applied (``success``).

    The single "already applied" predicate shared by ledger-diff selection and
    the runner's skip gate. Success-only, matching the retired
    ``ProjectMetadata.has_migration``: a ``skipped`` record (a not-needed or
    Superseded migration) leaves it re-evaluable each run — idempotent, it just
    re-skips — and a ``failed`` record leaves it retriable. ``detect()`` is never
    consulted here; the ledger is the applied authority (C-001/C-003).
    """
    migration_id = migration.migration_id
    return any(record.id == migration_id and record.result == SETTLED_RESULT for record in ledger.applicable_records_for(migration))


# Export standalone decorator for convenience
# This allows: from specify_cli.upgrade.registry import register
register = MigrationRegistry.register
