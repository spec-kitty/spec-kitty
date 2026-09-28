"""Migration registry for Spec Kitty upgrade system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from packaging.version import Version

from specify_cli.gitignore_manager import GitignorePathError

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

        applicable = []
        for migration in cls.get_all():
            target = Version(migration.target_version)
            # Include if target is > from_version AND <= to_version
            if from_v < target <= to_v:
                applicable.append(migration)
            # ALSO include migrations at current version if detect() returns True
            elif target == from_v and project_path is not None:  # noqa: SIM102
                detect_path = Path(project_path) if isinstance(project_path, str) else project_path
                try:
                    migration_needed = migration.detect(detect_path)
                except (GitignorePathError, MigrationStateUnreadableError) as exc:
                    # A symlinked `.gitignore`/`.claudeignore` makes detect()
                    # fail closed rather than follow it (gitignore_manager.py)
                    # -- select the migration so the runner can record a
                    # fail-closed failure instead of silently skipping it and
                    # advancing metadata past a migration it could not
                    # safely evaluate.
                    logger.warning(
                        "Selecting migration %s after detect() failed closed: %s",
                        migration.migration_id,
                        exc,
                    )
                    migration_needed = True
                if migration_needed:
                    applicable.append(migration)

        return applicable

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


# Export standalone decorator for convenience
# This allows: from specify_cli.upgrade.registry import register
register = MigrationRegistry.register
