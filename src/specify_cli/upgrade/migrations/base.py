"""Base migration class for Spec Kitty upgrade system."""

from __future__ import annotations

import functools
import inspect
import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

from kernel.activation_ledger_store import in_legacy_activation_scope, legacy_activation_scope


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


# --------------------------------------------------------------------------- #
# The upgrade-only legacy activation scope (ADR 2026-10-19-1, FR-017, C-001)
# --------------------------------------------------------------------------- #

#: Marks a method this module already wrapped, so a subclass never wraps it twice.
_SCOPE_WRAPPED = "__legacy_activation_scope_wrapped__"


def _canonical_root(project_path: Path) -> Path | None:
    """The main-checkout root of *project_path*, or ``None`` outside a git repository.

    The scope is entered on every wrapped migration call, so the answer is
    cached per process. The cache key includes whether ``<project>/.git``
    exists, so a ``None`` cached for a directory that is not yet a repository
    is not reused after a ``git init`` there.
    """
    return _resolve_canonical_root(project_path, (project_path / ".git").exists())


@functools.lru_cache(maxsize=256)
def _resolve_canonical_root(project_path: Path, has_git: bool) -> Path | None:
    from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError, resolve_canonical_repo_root

    del has_git  # part of the cache key only
    try:
        root: Path = resolve_canonical_repo_root(project_path)
    except (NotInsideRepositoryError, GitCommonDirUnavailableError):
        # No repository: the project itself is the only root the scope needs.
        return None
    return root


@contextmanager
def legacy_upgrade_scope(project_path: Path) -> Iterator[None]:
    """Enter the kernel's legacy activation scope for *project_path* and its canonical root (M3).

    Inside it a project without an activation ledger still reads (and the
    shipped migrations still write) its legacy activation surface, as every
    upgrade before the ledger did. A lane worktree's scope also covers the main
    checkout, because a migration run in the worktree may read the canonical
    root's charter. Re-entrant: inside an open scope for *project_path* it
    resolves nothing and adds nothing.
    """
    path = Path(project_path)
    if in_legacy_activation_scope(path):
        yield
        return
    # The canonical root is resolved lazily: only a query about another path (a lane
    # worktree reading the main checkout) runs the git probe behind it, so a migration
    # that never asks does not reach ``resolve_canonical_repo_root`` (#6539 audit).
    with legacy_activation_scope(path, canonical_root=functools.partial(_canonical_root, path.resolve())):
        yield


def _project_parameter(fn: Callable[..., Any]) -> str | None:
    """The name of *fn*'s first positional parameter after ``self``, or ``None``."""
    try:
        parameters = list(inspect.signature(fn).parameters.values())
    except (TypeError, ValueError):
        return None
    positional = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    if len(parameters) < 2 or parameters[1].kind not in positional:
        return None
    return parameters[1].name


def _wraps_project_method(fn: object) -> bool:
    """Whether :meth:`BaseMigration.__init_subclass__` wraps *fn* in the legacy scope.

    The rule: a plain function (not a ``staticmethod``/``classmethod`` object),
    with a public name, not already wrapped, whose first positional parameter
    after ``self`` exists. That parameter is taken as the project path by its
    POSITION, never by its name, so a renamed parameter is still covered.
    """
    if not inspect.isfunction(fn) or fn.__name__.startswith("_") or getattr(fn, _SCOPE_WRAPPED, False):
        return False
    return _project_parameter(fn) is not None


def _as_path(value: object) -> Path | None:
    return Path(value) if isinstance(value, (str, os.PathLike)) else None


def _in_upgrade_scope(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap *fn* so it runs inside :func:`legacy_upgrade_scope` of its project-path argument."""
    name = _project_parameter(fn)

    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        project = _as_path(args[0] if args else kwargs.get(name or ""))
        if project is None:
            return fn(self, *args, **kwargs)
        with legacy_upgrade_scope(project):
            return fn(self, *args, **kwargs)

    setattr(wrapper, _SCOPE_WRAPPED, True)
    return wrapper


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

    Every public method a subclass defines in its own class body whose first
    positional parameter after ``self`` is the project path (``detect``,
    ``can_apply``, ``apply``, ``structural_detect``, ...) runs inside the
    upgrade-only legacy activation scope (:func:`legacy_upgrade_scope`), so a
    shipped migration keeps reading and writing the pre-ledger activation
    surface without being edited (DIRECTIVE_044). Static and class methods
    and private (``_``-prefixed) names are not wrapped; the project path is
    matched by position, never by parameter name. The wrapper lives here, so
    no migration module's bytes (its ``content_hash``) change.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for name, member in list(vars(cls).items()):
            if _wraps_project_method(member):
                setattr(cls, name, _in_upgrade_scope(member))

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
    #: distinct "ordering-lead" concept: the lead block of the ledger backfill,
    #: the v1 charter-bundle upgrade and the charter-pack cutover). A
    #: ``runs_first`` migration's ``detect()``/``structural_detect`` must be
    #: content-driven, never version-driven
    #: (charter-pack-cutover research/runtime-seams.md §1.2).
    runs_first: ClassVar[bool] = False

    #: The migration resolves the canonical repo root
    #: (``charter.resolution.resolve_canonical_repo_root``), directly or through
    #: ``charter.activation.*``, which raises ``NotInsideRepositoryError`` for a
    #: project outside any git repository (#6539). A migration author who calls
    #: it sets this True; the runner (and the ``upgrade --dry-run --verbose``
    #: preview) then skips the migration BEFORE ``detect()`` when the project is
    #: not inside a repository, records nothing in the ledger, and selects it
    #: again on a run inside one. An executed audit
    #: (``test_requires_git_repository_audit``) fails for a caller that omits it.
    requires_git_repository: ClassVar[bool] = False

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

    #: The migration adopts the ledger: it records other migrations as settled
    #: when it applies (ADR ``2026-10-17-1`` §6, Amendment 2026-10-20). Selection
    #: never caps it at the run's requested target (an upgrade to an older
    #: target must still adopt, or its own records would hide the adoption for
    #: good), and while it is unsettled, selection treats the ids
    #: :meth:`adoption_settled_ids` returns as already settled, so a preview or
    #: dry run lists what the real run will apply (#6431).
    ledger_adoption: ClassVar[bool] = False

    def adoption_settled_ids(self, project_path: Path) -> frozenset[str]:  # noqa: ARG002 -- hook; the default settles nothing
        """The migration ids this ledger-adoption migration will record as ``success`` when it applies."""
        return frozenset()

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
