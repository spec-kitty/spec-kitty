"""Migration registry for Spec Kitty upgrade system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import Version

from specify_cli.gitignore_manager import GitignorePathError

from .metadata import ProjectMetadata
from .migrations.base import MigrationStateUnreadableError

if TYPE_CHECKING:
    from .migrations.base import BaseMigration

logger = logging.getLogger(__name__)


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
            raise ValueError(
                f"Duplicate migration ID '{migration_id}'. "
                f"Already registered by {existing.__name__}, "
                f"cannot register {migration_class.__name__}"
            )

        if getattr(migration_class, "runs_first", False):
            first = next((m for m in cls._migrations.values() if m.runs_first), None)
            if first is not None:
                raise ValueError(
                    f"Migration {migration_class.__name__} sets runs_first, but "
                    f"{first.__name__} already does; at most one migration may run first"
                )

        cls._migrations[migration_id] = migration_class
        return migration_class

    @classmethod
    def get_all(cls) -> list[BaseMigration]:
        """Get all migrations as instances, ordered by target version.

        Returns:
            List of migration instances sorted by target version
        """
        instances = [m() for m in cls._migrations.values()]
        return sorted(instances, key=lambda m: Version(m.target_version))

    @classmethod
    def get_applicable(
        cls, from_version: str, to_version: str, project_path: Path | None = None
    ) -> list[BaseMigration]:
        """Get migrations needed to go from one version to another.

        Returns applicable migrations in version order, except that a
        ``runs_first`` migration is placed first and is selected on
        ``detect()`` alone, independent of the version window (see
        :func:`_order_runs_first`). Residual: a same-version migration
        (``target == from``) has ``detect()`` evaluated once here, before the
        ``runs_first`` migration has run, so a project stamped exactly at that
        version can have it deselected in this run; the next upgrade picks it
        up.

        Args:
            from_version: Current version
            to_version: Target version
            project_path: Optional project path for detect() check

        Returns:
            List of applicable migrations in order
        """
        from pathlib import Path

        from_v = Version(from_version)
        to_v = Version(to_version)

        all_migrations = cls.get_all()
        applicable = []
        for migration in all_migrations:
            target = Version(migration.target_version)
            # Include if target is > from_version AND <= to_version
            if from_v < target <= to_v:
                applicable.append(migration)
            # ALSO include migrations at current version if detect() returns True
            elif target == from_v and project_path is not None:  # noqa: SIM102
                detect_path = Path(project_path) if isinstance(project_path, str) else project_path
                if _detect_fail_closed(migration, detect_path):
                    applicable.append(migration)

        return _order_runs_first(applicable, all_migrations, project_path)

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


def _detect_fail_closed(migration: BaseMigration, project_path: Path) -> bool:
    """Run ``detect()``, treating a fail-closed detection error as "needed".

    A symlinked ``.gitignore``/``.claudeignore`` makes detect() fail closed
    rather than follow it (gitignore_manager.py) -- select the migration so
    the runner can record a fail-closed failure instead of silently skipping
    it and advancing metadata past a migration it could not safely evaluate.
    """
    try:
        return migration.detect(project_path)
    except (GitignorePathError, MigrationStateUnreadableError) as exc:
        logger.warning(
            "Selecting migration %s after detect() failed closed: %s",
            migration.migration_id,
            exc,
        )
        return True


def _runs_first_selected_outside_window(migration: BaseMigration, project_path: Path) -> bool:
    """Whether a ``runs_first`` migration the version window excluded is still needed.

    It is selected when it is not recorded as applied and its ``detect()`` is
    true, or -- recorded or not -- when its ``structural_detect()`` is true.
    """
    if migration.reselect_when_recorded(project_path):
        return True
    metadata = ProjectMetadata.load(project_path / ".kittify")
    if metadata is not None and metadata.has_migration(migration.migration_id):
        return False
    return _detect_fail_closed(migration, project_path)


def _order_runs_first(
    applicable: list[BaseMigration],
    all_migrations: list[BaseMigration],
    project_path: Path | str | None,
) -> list[BaseMigration]:
    """Stable-partition *applicable* so the ``runs_first`` migration leads.

    A ``runs_first`` migration the version window excluded is added when
    :func:`_runs_first_selected_outside_window` says the project needs it
    (a project stamped at or above its version can still carry the state it
    migrates). Without a ``runs_first`` migration the order is unchanged.
    """
    selected_ids = {m.migration_id for m in applicable}
    first = [m for m in applicable if m.runs_first]
    if project_path is not None:
        path = Path(project_path)
        first.extend(
            m
            for m in all_migrations
            if m.runs_first and m.migration_id not in selected_ids and _runs_first_selected_outside_window(m, path)
        )
    return first + [m for m in applicable if not m.runs_first]


# Export standalone decorator for convenience
# This allows: from specify_cli.upgrade.registry import register
register = MigrationRegistry.register
