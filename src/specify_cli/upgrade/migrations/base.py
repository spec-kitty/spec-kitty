"""Base migration class for Spec Kitty upgrade system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ClaudeignorePathError(Exception):
    """Raised when ``.claudeignore`` is a symlink instead of a regular file.

    ``Path.read_text()`` / ``Path.write_text()`` both follow symlinks, so a
    ``.claudeignore`` replaced with a symlink would let a migration read or
    clobber whatever path it points to (issue #627, sibling of
    ``GitignorePathError``'s fix for the same class of bug in ``.gitignore``,
    #582/#618). Defined here rather than in the migration module itself so
    its identity survives ``auto_discover_migrations()``'s
    ``importlib.reload()`` of ``m_*.py`` modules -- ``base.py`` is the one
    migration-package module that reload deliberately skips (see the
    docstring in ``auto_discover_migrations()``), which is exactly why
    :class:`MigrationResult` and :class:`PartialWrite` live here too.
    """


class MigrationStateUnreadableError(Exception):
    """Raised when a migration cannot read the project state it must evaluate.

    ``detect()`` returning ``False`` means "project already in target state";
    the runner records that as a skip and may then stamp the project version
    past the migration, after which it is never re-considered. A migration
    whose input (e.g. a malformed ``charter.yaml``) cannot be parsed has not
    proven that, so it raises this instead and the runner records a FAILURE
    and leaves the version untouched -- the same fail-closed contract as
    ``GitignorePathError``. Lives in ``base.py`` so its identity survives the
    ``importlib.reload()`` in ``auto_discover_migrations()``.
    """


@dataclass(frozen=True)
class PartialWrite:
    """A single file a migration persisted before a non-atomic abort (FR-005).

    A migration that walks a corpus mission-by-mission (e.g. the runtime-state
    backfill) is intentionally *not* transactional across missions — there is no
    cross-mission rollback primitive — so an abort mid-walk leaves the missions
    already processed on disk. This record is the machine-readable account of
    one such write: the mission it belongs to and the absolute path written, so
    an operator (or a caller) can enumerate the on-disk residue instead of
    guessing at it. See :attr:`MigrationResult.partial_writes`.
    """

    mission: str
    path: str


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    changes_made: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manual_review_required: bool = False
    preserved_paths: list[str] = field(default_factory=list)
    #: Files already persisted when a non-atomic migration aborted mid-walk
    #: (FR-005). Empty on a clean run; populated on abort so the partial write is
    #: never silent. Each entry names one mission and one absolute file path.
    partial_writes: list[PartialWrite] = field(default_factory=list)


class BaseMigration(ABC):
    """Base class for all migrations.

    Migrations should:
    1. Be idempotent (safe to run multiple times)
    2. Check preconditions before applying
    3. Report what changes were made
    4. Handle dry-run mode
    """

    # Migration identifier (e.g., "0.6.5_commands_rename")
    # Format: {version}_{short_description}
    migration_id: str = ""

    # Human-readable description
    description: str = ""

    # Target version this migration brings project to
    target_version: str = ""

    # Minimum version this migration can be applied from (optional)
    # If None, detection is used
    min_version: str | None = None

    # Whether the migration should also run inside `.worktrees/*` checkouts
    # when the upgrade runner is invoked with include_worktrees=True.
    runs_on_worktrees: bool = True

    @abstractmethod
    def detect(self, project_path: Path) -> bool:
        """Detect if this migration is needed based on project state.

        Returns True if the project has the OLD state that needs migration.
        This is used for heuristic detection when metadata is missing.

        Args:
            project_path: Root of the project (.kittify parent)

        Returns:
            True if migration is needed
        """

    @abstractmethod
    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if migration can be safely applied.

        Args:
            project_path: Root of the project

        Returns:
            (can_apply, reason) - True if safe, False with explanation if not
        """

    @abstractmethod
    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply the migration.

        Args:
            project_path: Root of the project (.kittify parent)
            dry_run: If True, only simulate changes

        Returns:
            MigrationResult with details of what was changed
        """
