"""Migration registry for Spec Kitty upgrade system."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import InvalidVersion, Version

from .ledger import SETTLED_RESULT, MigrationLedger
from .manifest import load_order_manifest
from .supersession import substitute_if_superseded

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

        # A superseded migration is registered as a recorded no-op; the decorator
        # still returns the shipped class (supersession.py, #6589).
        cls._migrations[migration_id] = substitute_if_superseded(migration_class)
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
        runs-first lead block, the backfill, the bundle v2 upgrade and the
        cutover, leads ahead of its later version slots).

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
        A migration that declares a ``predecessor_id`` (a residue-safe successor,
        #6688) is further settled only while that predecessor's recorded outcome
        proves the repair ran (inside :func:`_settled_in_view`), because first
        adoption settles an id from the version stamp rather than from a run.
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
            adopting = pending_adoption_ids(ledger, all_migrations, path)
            for migration in all_migrations:
                if not _settled_in_view(ledger, migration, adopting):
                    selected.append(migration)
                elif migration.reselect_when_recorded(path):
                    # Only a settled migration needs the reselection hook, and it may need
                    # the adoption projection `_settled_in_view` already holds; asking it
                    # twice would read the ledger twice for the same answer (#6688).
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


def pending_adoption_ids(ledger: MigrationLedger, migrations: list[BaseMigration], project_path: Path) -> frozenset[str]:
    """Ids an unsettled ledger-adoption migration in *migrations* will settle when it applies (#6431)."""
    ids: set[str] = set()
    for migration in migrations:
        if migration.ledger_adoption and not migration_settled(ledger, migration):
            ids |= migration.adoption_settled_ids(project_path) - {migration.migration_id}
    return frozenset(ids)


def _settled_in_view(ledger: MigrationLedger, migration: BaseMigration, adopting: frozenset[str]) -> bool:
    """The one selection-view predicate: applied, or settled by a pending adoption (#6669).

    A migration's own record is not the whole answer for a *successor*: first
    adoption settles an id from the recorded version rather than from a run, so
    a ``success`` stamped that way must not hide an unsettled predecessor
    (#6688). :func:`_predecessor_outcome_settled_in_view` is that second half.
    """
    recorded = migration_settled(ledger, migration) or migration.migration_id in adopting
    if not recorded:
        return False
    return _predecessor_outcome_settled_in_view(ledger, migration, adopting)


def _predecessor_outcome_settled_in_view(ledger: MigrationLedger, migration: BaseMigration, adopting: frozenset[str]) -> bool:
    """True unless *migration*'s declared predecessor leaves its repair unproven (#6688).

    A migration that declares no :attr:`~specify_cli.upgrade.migrations.base.BaseMigration.predecessor_id`
    is answered True, so every ordinary migration keeps its success-only settlement.
    A declared predecessor settles it when its own authoritative partition records
    ``success``, or when a pending adoption will record that — exactly the evidence the
    predecessor itself would be settled by, which is why the retry matches what the
    predecessor did on ``main`` before #6669. A predecessor id the registry no longer
    carries cannot be evaluated, so the migration's own record keeps its word rather
    than replaying forever.
    """
    predecessor_id = migration.predecessor_id
    if not predecessor_id:
        return True
    predecessor = MigrationRegistry.get_by_id(predecessor_id)
    if predecessor is None:
        return True
    return migration_settled(ledger, predecessor) or predecessor_id in adopting


def settled_in_selection_view(project_path: Path, migration_id: str) -> bool:
    """True when ``get_applicable`` would treat *migration_id* as settled for *project_path* (#6669).

    Uses the same predicate as :meth:`MigrationRegistry.get_applicable`
    (:func:`_settled_in_view`): the id is a ``success`` record in its
    authoritative ledger partition, or an unsettled ledger-adoption migration
    will settle it on apply — and, for a migration that declares a
    ``predecessor_id``, that predecessor's own outcome settles it too (#6688).
    ``ledger_adoption`` migrations are never target capped, so every declared
    migration feeds the adoption probe. An unknown id was never recorded and
    returns False.
    """
    migration = MigrationRegistry.get_by_id(migration_id)
    if migration is None:
        return False
    ledger, adopting = _selection_view(project_path)
    return _settled_in_view(ledger, migration, adopting)


def _selection_view(project_path: Path | str) -> tuple[MigrationLedger, frozenset[str]]:
    """The ledger and pending-adoption projection a selection-view answer is computed from.

    Runs inside the upgrade-only legacy activation scope for the same
    reason :meth:`MigrationRegistry.get_applicable` does.
    """
    # Lazy import: ``base`` must not load at registry import.
    from .migrations.base import legacy_upgrade_scope

    path = Path(project_path)
    ledger = MigrationLedger(path)
    with legacy_upgrade_scope(path):
        adopting = pending_adoption_ids(ledger, MigrationRegistry.get_all(), path)
    return ledger, adopting


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

    The success-only "recorded applied" predicate. Success-only, matching the
    retired ``ProjectMetadata.has_migration``: a ``skipped`` record (a
    not-needed or Superseded migration) leaves it re-evaluable each run —
    idempotent, it just re-skips — and a ``failed`` record leaves it retriable.
    ``detect()`` is never consulted here; the ledger is the applied authority
    (C-001/C-003).

    This is one half of settlement, not all of it. :func:`_settled_in_view` is
    the selection authority, and for a migration that declares a
    ``predecessor_id`` it also requires the predecessor's outcome to prove the
    repair ran (#6688); the runner's skip gate reaches the same second half
    through :func:`settled_in_selection_view`. Read this as "the
    record says applied", never as "the run may skip it".
    """
    migration_id = migration.migration_id
    return any(record.id == migration_id and record.result == SETTLED_RESULT for record in ledger.applicable_records_for(migration))


# Export standalone decorator for convenience
# This allows: from specify_cli.upgrade.registry import register
register = MigrationRegistry.register
