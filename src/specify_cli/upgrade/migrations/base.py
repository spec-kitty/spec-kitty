"""Base migration class for Spec Kitty upgrade system."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar


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

    #: Marks a migration for RESELECTION even once its ledger record exists:
    #: :meth:`reselect_when_recorded` re-selects a ``runs_first`` migration whose
    #: :meth:`structural_detect` reports the old state present (a pulled
    #: ``metadata.yaml`` or a merge can revive the legacy state after the first
    #: application); at most one registered migration may set it. It does NOT
    #: govern execution ORDER -- ordering is owned solely by
    #: ``order_manifest.txt`` (the manifest's ``# runs-first:`` annotation is the
    #: distinct "ordering-lead" concept, e.g. the backfill at index 0). A
    #: ``runs_first`` migration's ``detect()``/``structural_detect`` must be
    #: content-driven, never version-driven
    #: (charter-pack-cutover research/runtime-seams.md §1.2).
    runs_first: ClassVar[bool] = False

    #: The migration's effect lives OUTSIDE version control -- clone-local state
    #: such as ``.git/info/exclude``, ``git config --local`` or ``.git/hooks``.
    #: The tracked, pushed ``metadata.yaml`` ledger records one clone's local
    #: state yet propagates to every clone, so a recorded ledger is NOT
    #: authoritative for these: a pulled clone that lacks the effect would
    #: otherwise skip the migration forever (#6233). When True,
    #: :meth:`reselect_when_recorded` routes the skip decision to this
    #: checkout's own ``detect()`` instead of trusting the ledger. The default
    #: is False, so a TRACKED-effect migration stays recorded-once-and-skipped.
    #: Requires an idempotent ``apply()`` (reselection re-applies it): see
    #: ADR ``2026-07-07-1`` and the ``test_clone_local_migration_idempotent``
    #: gate.
    clone_local_effect: ClassVar[bool] = False

    #: The stable drift key (ADR ``2026-10-17-1`` §4). Empty by default, in which
    #: case the ledger falls back to :attr:`migration_id`. Declare an explicit
    #: ``identity`` only when a migration's drift should be tracked under a name
    #: that outlives a rename of its ``migration_id``. The WP01 ledger reaches it
    #: by defensive ``getattr``, so it works whether or not a subclass sets it.
    identity: ClassVar[str] = ""

    #: The source files whose bytes define this migration's ``content_hash``
    #: (ADR ``2026-10-17-1`` §4). Empty (the default) means "the migration's own
    #: defining module file"; a non-empty tuple names module-relative or absolute
    #: files whose sorted-concatenated bytes are hashed (deterministic regardless
    #: of declaration order). Audit-only: a hash mismatch is surfaced read-only
    #: and never re-selects or re-applies the migration.
    content_hash_sources: ClassVar[tuple[str, ...]] = ()

    def structural_detect(self, project_path: Path) -> bool:  # noqa: ARG002 -- hook; the default ignores the project
        """Return True when the project still carries state this migration owns.

        Consulted only for a ``runs_first`` migration: when it returns True the
        migration is selected and applied again even though ``metadata.yaml``
        records it as applied (a pulled ``metadata.yaml`` or a merge can bring
        the old state back after the first application). The default is False,
        so a recorded migration stays settled.
        """
        return False

    def reselect_when_recorded(self, project_path: Path) -> bool:
        """True when a recorded application must not settle this migration.

        Only a ``runs_first`` migration whose :meth:`structural_detect` reports
        the old state present qualifies (a pulled ``metadata.yaml`` or a merge
        can bring the legacy state back after the first application). Every other
        recorded migration is skipped as applied.

        Clone-local reselection is no longer a per-migration hook: under the
        two-partition ledger (ADR ``2026-10-17-1``) a clone-local migration's
        applicable authority IS its per-clone ledger, so a pulled clone whose
        per-clone ledger lacks the record re-selects it by ledger-diff and the
        runner's ``detect()`` idempotency guard no-ops when the effect is
        already present. The ``clone_local_effect`` flag survives only as the
        ledger's routing key.
        """
        return self.runs_first and self.structural_detect(project_path)

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


class SupersededMigration(BaseMigration):
    """A migration kept only as a recorded no-op so upgrade history stays meaningful.

    Its module, class and ``migration_id`` stay registered, but ``detect()``
    is always False, so the runner records it as ``skipped / "Not
    applicable"`` and never applies it. ``superseded_by`` names what replaced it.
    """

    superseded_by: ClassVar[str] = ""

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 -- superseded: never needed, whatever the project holds
        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002 -- superseded: refused for every project
        return False, self.superseded_by

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002 -- superseded: a no-op for every project
        return MigrationResult(success=True, warnings=[self.superseded_by])
