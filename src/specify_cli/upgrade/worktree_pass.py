"""The worktree pass of ``spec-kitty upgrade``: plan which worktrees it writes, then apply (#7405).

The pass runs after the repository root checkout is migrated. It used to be one
method, ``MigrationRunner._upgrade_worktrees``; it is now two steps:

* :func:`plan_worktree_pass` reads, and writes nothing. It decides which
  worktrees under ``.worktrees/`` the pass touches (through
  :func:`~specify_cli.upgrade.worktree_selection.worktree_dispositions`, the one
  rule the preview also reads), which migrations run there
  (``runs_on_worktrees``), and the result each worktree reports when the pass
  writes nothing to it.
* :class:`WorktreePass` applies the plan, one worktree at a time in name order,
  and collects a :class:`WorktreePassReport`.

The runner keeps what it owns: the ledger and metadata record
(:class:`WorktreePassHooks.record`), the metadata synthesized for a worktree
without one (``synthesize_metadata``), and the save, schema stamp and commit
that settle each worktree (``settle``). It hands them to the pass as hooks.

Like the method it replaces, this pass is NOT sequenced-view aware (#6552,
C-004): each worktree's verdict is its own ``detect()`` there.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from kernel.clock import datetime
from kernel.git import GitCommandError
from specify_cli.context.mission_resolver import residue_notice_path
from specify_cli.core.constants import KITTIFY_DIR, KITTY_SPECS_DIR
from specify_cli.gitignore_manager import GitignorePathError

from .autocommit import capture_upgrade_baseline
from .ledger import MigrationLedger
from .metadata import ProjectMetadata
from .migrations.base import BaseMigration, MigrationResult, MigrationStateUnreadableError
from .registry import migration_settled, migration_settled_in_view
from .worktree_selection import (
    DispositionAction,
    WorktreeOutcome,
    WorktreeRunResult,
    WorktreeSelection,
    initial_results,
    worktree_dispositions,
)

__all__ = [
    "WorktreePass",
    "WorktreePassContext",
    "WorktreePassHooks",
    "WorktreePassPlan",
    "WorktreePassReport",
    "WorktreeRun",
    "append_warnings",
    "has_upgradeable_state",
    "metadata_bytes",
    "plan_worktree_pass",
    "skip_as_applied",
]

#: The errors a migration step raises when the tree cannot be read or written
#: safely. Each fails the step closed instead of being read as "not needed".
_UNSAFE_TREE_ERRORS = (GitignorePathError, MigrationStateUnreadableError)


def append_warnings(target: list[str], new: list[str], *, notice_root: Path, seen: set[Path]) -> None:
    """Append *new* to *target*, naming each residue folder at most once per run (#6669, FR-008).

    A residue notice is keyed on the resolved folder it names under
    *notice_root*, the checkout the notice's path is relative to; the first
    line seen for a folder is kept and later ones are dropped. Every other
    warning is appended unchanged, in order.
    """
    for line in new:
        rel_path = residue_notice_path(line)
        if rel_path is not None:
            key = (notice_root / rel_path).resolve()
            if key in seen:
                continue
            seen.add(key)
        target.append(line)


def metadata_bytes(kittify_dir: Path) -> bytes | None:
    """The raw bytes of ``kittify_dir/metadata.yaml``, or ``None`` when there is no such file."""
    path = kittify_dir / "metadata.yaml"
    return path.read_bytes() if path.is_file() else None


def skip_as_applied(ledger: MigrationLedger, migration: BaseMigration, project_path: Path) -> bool:
    """True when the runner may skip *migration* as already applied.

    The ledger record settles it, the registry's selection-view predicate agrees
    (it adds a residue-safe successor's predecessor outcome, #6688, so selection
    and this apply-time skip cannot disagree), and no structural reselection
    (#6613) overrides. The cheap record check runs first so the selection view is
    only built for a recorded migration.
    """
    return migration_settled(ledger, migration) and migration_settled_in_view(project_path, migration) and not migration.reselect_when_recorded(project_path)


def has_upgradeable_state(worktree: Path, *, worktree_migrations_pending: bool) -> bool:
    """Whether the pass has anything to upgrade in *worktree*.

    A ``.kittify/`` directory always counts. Without one, a ``kitty-specs/`` or
    legacy ``.specify/`` directory counts only when a worktree migration is
    pending, because the version bump alone needs ``.kittify/``.
    """
    if (worktree / KITTIFY_DIR).exists():
        return True
    return worktree_migrations_pending and ((worktree / KITTY_SPECS_DIR).exists() or (worktree / ".specify").exists())


def _notes(items: list[str]) -> str | None:
    """The ledger note for a list of changes or errors: joined, or ``None`` for none."""
    return "; ".join(items) if items else None


@dataclass(frozen=True)
class WorktreePassPlan:
    """What the worktree pass will do, decided before it writes anything.

    ``results`` holds every directory under ``.worktrees/`` with the outcome it
    reports when the pass writes nothing there; the skips are final.
    ``targets`` are the selected worktrees the pass applies migrations to, in
    name order. ``migrations`` are the ones that run on worktrees.
    """

    migrations: tuple[BaseMigration, ...]
    results: Mapping[Path, WorktreeRunResult]
    targets: tuple[Path, ...]


def plan_worktree_pass(worktrees_dir: Path, migrations: Sequence[BaseMigration], selection: WorktreeSelection | None) -> WorktreePassPlan:
    """Plan the worktree pass; reads only.

    * Integrating (Mission) worktrees are skipped (#5457), and a non-Mission
      worktree is a target only when ``selection`` opts it in (#7173, FR-007).
      ``None`` selects none.
    * When migrations are pending but none runs on worktrees, there is no
      target: a selected worktree is left alone rather than only version-bumped.
    * A selected worktree with no upgradeable state
      (:func:`has_upgradeable_state`) is not a target.
    """
    worktree_migrations = tuple(migration for migration in migrations if migration.runs_on_worktrees)
    dispositions = worktree_dispositions(worktrees_dir, selection or WorktreeSelection.none())
    results = initial_results(dispositions)
    if migrations and not worktree_migrations:
        return WorktreePassPlan(migrations=worktree_migrations, results=results, targets=())
    targets = tuple(
        disposition.path
        for disposition in dispositions
        if disposition.action is DispositionAction.UPGRADE and has_upgradeable_state(disposition.path, worktree_migrations_pending=bool(worktree_migrations))
    )
    return WorktreePassPlan(migrations=worktree_migrations, results=results, targets=targets)


@dataclass
class WorktreePassReport:
    """What the worktree pass reports.

    ``worktree_failures`` carries the same failure lines as ``errors``, and it
    is the fatal channel: a non-empty list fails the upgrade (FR-012, #3392).
    ``errors`` and ``warnings`` are observability only.
    """

    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    worktree_failures: list[str] = field(default_factory=list)
    worktree_results: list[WorktreeRunResult] = field(default_factory=list)

    def fail(self, messages: list[str]) -> None:
        """Report *messages* as worktree failures: both the error and the fatal channel."""
        self.errors.extend(messages)
        self.worktree_failures.extend(messages)

    def as_dict(self) -> dict[str, Any]:
        """The dict shape ``MigrationRunner._upgrade_worktrees`` has always returned."""
        return {
            "warnings": self.warnings,
            "errors": self.errors,
            "worktree_failures": self.worktree_failures,
            "worktree_results": self.worktree_results,
        }


@dataclass(frozen=True)
class WorktreePassContext:
    """The run-wide inputs every worktree in one pass shares.

    ``main_metadata`` is the repository root checkout's metadata as this run
    already saved it (``None`` on a dry run), and ``fallback_timestamp`` is
    minted once per pass: a bookkeeping-only worktree bump aligns its
    ``last_upgraded_at`` to main's stamp, or to this one shared value when main
    has none, so sibling worktrees never diverge on it (#4972).
    """

    target_version: str
    dry_run: bool
    auto_commit: bool
    main_metadata: ProjectMetadata | None
    fallback_timestamp: datetime


@dataclass
class WorktreeRun:
    """One target worktree's state while the pass applies migrations to it.

    ``metadata_dirty`` starts True for freshly synthesized metadata, which must be
    saved even when the version already matches (#1873). ``errored`` is set when
    a migration could not be evaluated or raised: nothing is committed, but the
    schema-stamp rules are unchanged. ``failed`` is set when a migration's apply
    failed; it is sticky and suppresses the schema stamp (FR-009, #3376).
    ``held`` are marker-less files a migration preserved for manual review: named
    in the output, never committed, and they do not block the commit (#5443).
    ``migrated`` is whether a migration reported a change (#7173).
    """

    worktree: Path
    metadata: ProjectMetadata
    from_version: str
    baseline: set[str] | None
    metadata_before: bytes | None
    metadata_dirty: bool
    ledger: MigrationLedger
    held: set[str] = field(default_factory=set)
    errored: bool = False
    failed: bool = False
    migrated: bool = False

    @property
    def kittify_dir(self) -> Path:
        return self.worktree.joinpath(KITTIFY_DIR)

    @property
    def prefix(self) -> str:
        """The prefix every line this worktree reports carries."""
        return f"Worktree {self.worktree.name}: "

    def wrote(self) -> bool:
        """Whether the run changed anything here so far: a reported change or a metadata write."""
        return self.migrated or metadata_bytes(self.kittify_dir) != self.metadata_before


class RecordHook(Protocol):
    """Persist one migration result for a checkout; True when a NEW record was written."""

    def __call__(self, metadata: ProjectMetadata, root: Path, migration: BaseMigration, result: str, notes: str | None = None, /) -> bool: ...


class SettleHook(Protocol):
    """Save, stamp and (when enabled) commit one worktree; return its warnings and outcome."""

    def __call__(self, run: WorktreeRun, context: WorktreePassContext, /) -> tuple[list[str], WorktreeOutcome]: ...


@dataclass(frozen=True)
class WorktreePassHooks:
    """What the runner supplies to the pass (see the module docstring)."""

    record: RecordHook
    synthesize_metadata: Callable[[Path], ProjectMetadata]
    settle: SettleHook


class WorktreePass:
    """Apply a :class:`WorktreePassPlan` and collect its :class:`WorktreePassReport`.

    Per target worktree, in name order: capture the commit baseline (before any
    write, so the commit stages only this run's churn, #2385), load or
    synthesize the metadata, run each worktree migration, then settle the
    worktree through the runner's hook. A dry run settles nothing, so each
    target keeps its planned outcome.

    Per migration: a migration the worktree's ledger already settles is skipped
    silently; ``detect()`` False records ``skipped``; a ``can_apply`` refusal is
    a warning and records nothing; ``apply()`` records ``success`` or
    ``failed``. A ``detect()`` or ``apply()`` that cannot run safely is a fatal
    worktree failure (#5746, #6669).
    """

    def __init__(self, context: WorktreePassContext, hooks: WorktreePassHooks, *, seen_residue: set[Path]) -> None:
        self.context = context
        self.hooks = hooks
        # Shared with the main checkout's warnings, so a residue folder is named once per run (#6669).
        self.seen_residue = seen_residue

    def run(self, plan: WorktreePassPlan) -> WorktreePassReport:
        report = WorktreePassReport()
        results = dict(plan.results)
        for worktree in plan.targets:
            outcome = self._upgrade_worktree(worktree, plan.migrations, report)
            if outcome is not None:
                results[worktree] = WorktreeRunResult(disposition=results[worktree].disposition, outcome=outcome)
        report.worktree_results = list(results.values())
        return report

    def _upgrade_worktree(self, worktree: Path, migrations: Sequence[BaseMigration], report: WorktreePassReport) -> WorktreeOutcome | None:
        run = self._open(worktree)
        for migration in migrations:
            self._run_migration(run, migration, report)
        if self.context.dry_run:
            return None
        warnings, outcome = self.hooks.settle(run, self.context)
        report.warnings.extend(warnings)
        return outcome

    def _open(self, worktree: Path) -> WorktreeRun:
        kittify_dir = worktree / KITTIFY_DIR
        baseline = capture_upgrade_baseline(worktree) if self.context.auto_commit and not self.context.dry_run else None
        before = metadata_bytes(kittify_dir)
        metadata = ProjectMetadata.load(kittify_dir)
        synthesized = metadata is None
        if metadata is None:
            metadata = self.hooks.synthesize_metadata(worktree)
        return WorktreeRun(
            worktree=worktree,
            metadata=metadata,
            from_version=metadata.version,
            baseline=baseline,
            metadata_before=before,
            metadata_dirty=synthesized,
            ledger=MigrationLedger(worktree),
        )

    def _run_migration(self, run: WorktreeRun, migration: BaseMigration, report: WorktreePassReport) -> None:
        if skip_as_applied(run.ledger, migration, run.worktree):
            return
        needed = self._detect(run, migration, report)
        if needed is None:
            return
        if not needed:
            # Marks the metadata dirty only when a NEW record was written: an already
            # recorded skip must not bump last_upgraded_at on every re-run (#1872).
            self._record(run, migration, "skipped", "Not applicable")
            return
        can_apply, reason = migration.can_apply(run.worktree)
        if not can_apply:
            report.warnings.append(f"{run.prefix}Cannot apply {migration.migration_id}: {reason}")
            return
        result = self._apply(run, migration, report)
        if result is not None:
            self._absorb(run, migration, result, report)

    def _detect(self, run: WorktreeRun, migration: BaseMigration, report: WorktreePassReport) -> bool | None:
        """``detect()`` on the worktree; ``None`` when it could not run safely (reported and recorded).

        A symlinked ignore file (GitignorePathError), unreadable state or a failed
        git probe is a recorded failure, never a skip: a skip record would read as
        settled when the migration was never evaluated (#5746, #6669).
        """
        try:
            return migration.detect(run.worktree)
        except (GitCommandError, *_UNSAFE_TREE_ERRORS) as exc:
            run.errored = True
            reason = f"git failed ({exc})" if isinstance(exc, GitCommandError) else str(exc)
            report.fail([f"{run.prefix}Cannot safely detect {migration.migration_id}: {reason}"])
            self._record(run, migration, "failed", f"Cannot safely detect: {reason}")
            return None

    def _apply(self, run: WorktreeRun, migration: BaseMigration, report: WorktreePassReport) -> MigrationResult | None:
        """``apply()`` on the worktree; ``None`` when it raised on an unsafe tree (reported, not recorded)."""
        try:
            return migration.apply(run.worktree, dry_run=self.context.dry_run)
        except GitCommandError as exc:
            # As on main (#6669): apply() may already have written, so a recorded failed apply, never a crash.
            return MigrationResult(success=False, errors=[f"Cannot apply {migration.migration_id}: git failed ({exc})"])
        except _UNSAFE_TREE_ERRORS as exc:
            run.errored = True
            report.fail([f"{run.prefix}Cannot apply {migration.migration_id}: {exc}"])
            return None

    def _absorb(self, run: WorktreeRun, migration: BaseMigration, result: MigrationResult, report: WorktreePassReport) -> None:
        if result.manual_review_required:
            run.held.update(result.preserved_paths)
        if result.success:
            run.migrated = run.migrated or bool(result.changes_made)
            self._record(run, migration, "success", _notes(result.changes_made))
            append_warnings(report.warnings, [run.prefix + warning for warning in result.warnings], notice_root=run.worktree, seen=self.seen_residue)
            return
        # A failed migration is not an upgrade: its record does not mark the metadata
        # dirty, so it does not bump last_upgraded_at.
        self._record(run, migration, "failed", _notes(result.errors), marks_dirty=False)
        run.failed = True
        # A failure that gave no error of its own still needs one line, or no failure is recorded (#5746).
        report.fail([run.prefix + error for error in result.errors] or [f"{run.prefix}Migration {migration.migration_id} failed"])

    def _record(self, run: WorktreeRun, migration: BaseMigration, result: str, notes: str | None, *, marks_dirty: bool = True) -> None:
        """Record *result* for *migration* in the worktree (never on a dry run)."""
        if self.context.dry_run:
            return
        recorded = self.hooks.record(run.metadata, run.worktree, migration, result, notes)
        if recorded and marks_dirty:
            run.metadata_dirty = True
