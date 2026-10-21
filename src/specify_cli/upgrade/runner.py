"""Migration runner for Spec Kitty upgrade system."""

from __future__ import annotations

from specify_cli.core.constants import KITTY_SPECS_DIR
import logging
import platform
import sys
from dataclasses import dataclass, field
from kernel.clock import datetime, now_utc
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version
from rich.console import Console

from charter.resolution import GitCommonDirUnavailableError, NotInsideRepositoryError, resolve_canonical_repo_root
from specify_cli.core.constants import KITTIFY_DIR, WORKTREES_DIR
from specify_cli.core.git_ops import get_current_branch
from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.lanes.branch_naming import parse_mission_slug_from_branch
from specify_cli.migration.schema_version import REQUIRED_SCHEMA_VERSION

from . import autocommit
from .autocommit import capture_upgrade_baseline
from .detector import VersionDetector
from .ledger import MigrationLedger, build_record
from .metadata import _METADATA_HEADER, ProjectMetadata, VersionStamp, canonical_schema_capabilities
from .migrations.base import BaseMigration, MigrationResult, MigrationStateUnreadableError, legacy_upgrade_scope
from .registry import MigrationRegistry, migration_settled

logger = logging.getLogger(__name__)


@dataclass
class UpgradeResult:
    """Result of an upgrade operation."""

    success: bool
    from_version: str
    to_version: str
    migrations_applied: list[str] = field(default_factory=list)
    migrations_skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    dry_run: bool = False
    # Fatal per-worktree migration failures (FR-012, #3376). Distinct from
    # ``errors`` (which already carries the same messages for backward
    # compatibility): this is the structured channel the finalizer/outcome
    # layer (WP04) reads to flip effective success + exit code non-zero.
    # A worktree migration that could not be applied (``can_apply`` refusal)
    # stays warning-only and is intentionally NOT classified fatal here.
    worktree_failures: list[str] = field(default_factory=list)
    # Per-migration ``MigrationResult`` keyed by migration_id. Used by the
    # CLI --json path to surface schema-shaped reports emitted by individual
    # migrations (e.g. 3.2.0rc35_unified_bundle's contract-shaped payload).
    migration_results: dict[str, MigrationResult] = field(default_factory=dict)


def project_is_inside_git_repository(project_path: Path) -> bool:
    """Return True when ``project_path`` is inside a git repository (#6539).

    Uses the same resolver the repository-bound migrations use
    (``charter.resolution.resolve_canonical_repo_root``), so "inside" means exactly
    what that resolver accepts, including a project in a repository subdirectory.
    It is the one probe behind :class:`RepositoryProbe`.
    """
    try:
        resolve_canonical_repo_root(project_path)
    except NotInsideRepositoryError:
        return False
    return True


class RepositoryProbe:
    """Lazy, memoized "is the project inside a git repository" answer (#6539).

    The git probe runs on the first :meth:`inside` call only, so a run whose
    pending migrations never declare ``requires_git_repository`` never invokes git.
    """

    def __init__(self, project_path: Path) -> None:
        self._project_path = project_path
        self._inside: bool | None = None

    def inside(self) -> bool:
        if self._inside is None:
            self._inside = project_is_inside_git_repository(self._project_path)
        return self._inside


def migration_skipped_outside_repository(migration: BaseMigration, probe: RepositoryProbe) -> bool:
    """The one rule for the repository gate (#6539).

    True when ``migration`` declares ``requires_git_repository`` and the project is
    not inside a repository. Both the runner's pre-detect gate and the
    ``--dry-run --verbose`` preview ask this, so they agree on whether the project is
    outside a repository. The probe is consulted only for a flagged migration, and
    may raise ``GitCommonDirUnavailableError``: the runner records that as a failure
    and the preview reports that it would fail.
    """
    return migration.requires_git_repository and not probe.inside()


def _display_version(value: str) -> str:
    """Bound untrusted version text without emitting terminal control characters."""
    escaped = value.encode("unicode_escape").decode("ascii")
    return escaped if len(escaped) <= 256 else escaped[:253] + "..."


def validate_upgrade_target(from_version: str, target_version: str) -> str | None:
    """Validate PEP 440 before selection; equal and future targets remain eligible."""
    try:
        requested = Version(target_version)
    except InvalidVersion:
        return f"Invalid upgrade target version: {_display_version(target_version)}"
    if from_version == "unknown":
        return None
    try:
        current = Version(from_version)
    except InvalidVersion:
        return f"Invalid project metadata version: {_display_version(from_version)}"
    if requested < current:
        return f"Refusing to downgrade project metadata from {_display_version(from_version)} to {_display_version(target_version)}"
    return None


def _is_integrating_worktree(worktree: Path) -> bool:
    """Return True when ``worktree`` integrates back into its mission's target branch (#5457).

    ``spec-kitty upgrade`` writes project-global state (``.kittify/metadata.yaml``,
    ``.gitattributes``, ...) once, in the repository root checkout. An
    *integrating worktree* receives that state through integration and must
    never carry its own upgrade writes or upgrade commit, or every lane and
    coordination branch diverges on bookkeeping that ``consolidate`` and the
    lane auto-rebase then refuse.

    The rule:

    * no ``.git`` entry (a plain directory, not a git worktree): not
      integrating, so today's behaviour is kept;
    * a branch that cannot be read (detached HEAD): integrating (fail safe);
    * otherwise integrating iff the branch is a mission, lane or coordination
      branch, as recognised by the branch-naming authority.
    """
    if not (worktree / ".git").exists():
        return False
    branch = get_current_branch(worktree)
    if branch is None:
        return True
    return parse_mission_slug_from_branch(branch) is not None


def _worktrees_to_upgrade(worktrees_dir: Path) -> list[Path]:
    """Directories under ``.worktrees/`` that upgrade may write, in name order.

    Integrating worktrees are left out (see :func:`_is_integrating_worktree`).
    """
    return [worktree for worktree in sorted(worktrees_dir.iterdir(), key=lambda p: p.name) if worktree.is_dir() and not _is_integrating_worktree(worktree)]


def _commit_worktree_churn(
    worktree: Path,
    *,
    baseline: set[str] | None,
    from_version: str,
    to_version: str,
    failed: bool,
    held_paths: list[str],
) -> list[str]:
    """Commit one upgraded worktree's churn and return its warnings, each prefixed with its name.

    Mirrors the main checkout (FR-019, FR-021, FR-023): a worktree whose migrations failed
    commits nothing and says so (only when the run left changes there); an unavailable
    baseline is reported instead of committed against; files held for manual review are
    named, with the wording that depends on whether a commit landed; and a no-commit case
    prints exactly one reason.
    """
    prefix = f"Worktree {worktree.name}: "
    committed = False
    reason: str | None = None
    if baseline is None:
        reason = autocommit.BASELINE_UNAVAILABLE_WARNING
    elif failed:
        if autocommit.prepare_upgrade_commit_files(worktree, baseline):
            reason = autocommit.FAILED_RUN_LEFT_UNCOMMITTED_WARNING
    else:
        committed, _paths, reason = autocommit.commit_touched_checkout(worktree, baseline, from_version, to_version)
    warnings = [prefix + reason] if reason else []
    if held_paths and not failed:
        joined = ", ".join(held_paths)
        held = (
            autocommit.HELD_FOR_REVIEW_NOT_COMMITTED_WARNING.format(paths=joined)
            if committed
            else autocommit.HELD_FOR_REVIEW_SKIPPED_COMMIT_WARNING.format(count=len(held_paths), paths=joined)
        )
        warnings.append(prefix + held)
    return warnings


class MigrationRunner:
    """Orchestrates the migration process."""

    def __init__(self, project_path: Path, console: Console | None = None):
        """Initialize the runner.

        Args:
            project_path: Root of the project
            console: Optional Rich console for output
        """
        self.project_path = project_path
        self.kittify_dir = project_path / KITTIFY_DIR
        self.console = console or Console()
        self.detector = VersionDetector(project_path)
        self._repository_probe = RepositoryProbe(project_path)

    def upgrade(
        self,
        target_version: str,
        dry_run: bool = False,
        force: bool = False,  # noqa: ARG002
        include_worktrees: bool = True,
        auto_commit: bool = False,
    ) -> UpgradeResult:
        """Run all needed migrations to reach target version.

        Args:
            target_version: Version to upgrade to
            dry_run: If True, simulate but don't apply
            force: If True, skip confirmation prompts
            include_worktrees: If True, also upgrade worktrees
            auto_commit: If True, auto-commit each worktree's upgrade churn on
                its own branch (#2385). The main checkout's commit stays with
                the CLI caller, which owns the main baseline.

        Returns:
            UpgradeResult with details of the upgrade

        The whole run (selection, every migration, the worktree pass) happens
        inside the upgrade-only legacy activation scope of the project
        (:func:`~specify_cli.upgrade.migrations.base.legacy_upgrade_scope`).
        """
        with legacy_upgrade_scope(self.project_path):
            return self._upgrade(target_version, dry_run=dry_run, include_worktrees=include_worktrees, auto_commit=auto_commit)

    def _upgrade(self, target_version: str, *, dry_run: bool, include_worktrees: bool, auto_commit: bool) -> UpgradeResult:
        """The body of :meth:`upgrade`, run inside the legacy activation scope."""
        from_version = self.detector.detect_version()

        result = UpgradeResult(
            success=True,
            from_version=from_version,
            to_version=target_version,
            dry_run=dry_run,
        )

        validation_error = validate_upgrade_target(from_version, target_version)
        if validation_error:
            result.success = False
            result.errors.append(validation_error)
            return result

        # Get applicable migrations
        version_for_migration = "0.0.0" if from_version == "unknown" else from_version
        migrations = MigrationRegistry.get_applicable(
            version_for_migration,
            target_version,
            project_path=self.project_path,
        )

        if not migrations:
            # Still update version stamp even when no migrations needed
            metadata = ProjectMetadata.load(self.kittify_dir)
            if metadata and not dry_run and metadata.version != target_version:
                metadata.version = target_version
                metadata.last_upgraded_at = now_utc()
                metadata.save(self.kittify_dir)
            # Why: even when no schema-changing migrations are needed (e.g. an
            # idempotent 3.2.0a4 -> 3.2.0a4 re-run on a legacy project), the
            # schema_version stamp must still land so the gate does not block
            # the next agent command. Stamp after save(): a legacy in-memory
            # model has schema_version None, and the stamp also settles the
            # canonical capability map (#5229).
            # See FR-002 / #705.
            if not dry_run and REQUIRED_SCHEMA_VERSION is not None:
                self._stamp_schema_version(self.kittify_dir, REQUIRED_SCHEMA_VERSION)

            if include_worktrees and from_version == target_version:
                worktrees_result = self._upgrade_worktrees(target_version, migrations, dry_run, auto_commit=auto_commit)
                result.warnings.extend(worktrees_result.get("warnings", []))
                if worktrees_result.get("errors"):
                    result.errors.extend(worktrees_result["errors"])
                    result.warnings.append("Some worktrees had issues - check errors above")
                result.worktree_failures.extend(worktrees_result.get("worktree_failures", []))

            result.warnings.append(f"No migrations needed from {from_version} to {target_version}")
            return result

        # Load or create metadata
        metadata = ProjectMetadata.load(self.kittify_dir)
        if metadata is None:
            metadata = self._create_initial_metadata(from_version)

        # Normalize legacy migration IDs before the ledger-diff selection reads them
        if not dry_run:
            norm_changes = metadata.normalize_and_save_legacy_ids(self.kittify_dir)
            result.warnings.extend(norm_changes)

        # FR-002 (#3334): capture the on-disk version trio BEFORE the loop.
        # A failed migration's _record_migration_result -> save() rewrites
        # metadata.yaml from a fixed dict and, on the mid-loop break, the
        # success-guarded stamp below never runs -- so without this capture the
        # value is lost and a re-run re-detects the project as legacy and
        # re-hits the same failing migration. We restore this CAPTURED value on
        # failure, never REQUIRED_SCHEMA_VERSION: re-stamping the target onto a
        # half-migrated project would open the gate on a corpus the migration
        # never finished (the exact dishonest-state bug this mission closes).
        # ``VersionStamp`` is the one restore authority (#4275): the CLI reuses
        # it for a failure in the final surface repair.
        pre_run_stamp = VersionStamp.capture(self.kittify_dir)

        # Apply each migration to main project
        for migration in migrations:
            migration_result, status = self._apply_migration(migration, metadata, dry_run)
            result.warnings.extend(migration_result.warnings)
            # Preserve each migration's structured payload so the CLI --json
            # layer can surface schema-shaped reports (Finding 2 / review
            # cycle 1). We record applied and skipped results alike so
            # operators can see both no-op and refresh payloads.
            if status in ("applied", "skipped"):
                result.migration_results[migration.migration_id] = migration_result

            if status == "applied":
                result.migrations_applied.append(migration.migration_id)
            elif status == "skipped":
                result.migrations_skipped.append(migration.migration_id)
            else:
                result.success = False
                result.errors.extend(migration_result.errors)
                # Still record the failed payload for observability.
                result.migration_results[migration.migration_id] = migration_result
                # Stop on first failure
                break

        # Update and save metadata for main project
        if not dry_run:
            self._finalize_main_metadata(metadata, target_version, result, pre_run_stamp)

        # Handle worktrees
        if include_worktrees:
            worktrees_result = self._upgrade_worktrees(target_version, migrations, dry_run, auto_commit=auto_commit)
            result.warnings.extend(worktrees_result.get("warnings", []))
            if worktrees_result.get("errors"):
                result.errors.extend(worktrees_result["errors"])
                # This generic `errors`/`warnings` channel is observability-only
                # and never flips the exit code by itself. The SAME failure
                # messages (populated together at lines ~443-445 above, in
                # `_upgrade_worktrees`) are also recorded below into
                # `worktree_failures` — THAT channel is fatal: FR-012 /
                # `UpgradeOutcome.effective_success` treats a non-empty
                # `worktree_failures` as a real failure and flips the exit
                # code to 1, so a broken worktree is never silently reported
                # as `success: true` (#3392).
                result.warnings.append("Some worktrees had issues - check errors above")
            result.worktree_failures.extend(worktrees_result.get("worktree_failures", []))

        return result

    def upgrade_worktrees_only(
        self,
        target_version: str,
        dry_run: bool = False,
        auto_commit: bool = False,
    ) -> dict[str, Any]:
        """Upgrade worktrees without running any migrations on the main checkout.

        Public entry point for the no-migrations path in the CLI, where the
        main checkout is already at target_version and only the sibling
        worktrees need their metadata stamps refreshed.  Exposes the private
        ``_upgrade_worktrees`` implementation behind a stable, named contract
        so callers are not coupled to an internal method name.

        Args:
            target_version: Version to stamp on each worktree's metadata.
            dry_run: If True, simulate but do not write.
            auto_commit: If True, commit each worktree's upgrade churn on its
                own branch after that worktree's writes (#2385).

        Returns:
            Dict with ``warnings`` and ``errors`` lists.
        """
        with legacy_upgrade_scope(self.project_path):
            return self._upgrade_worktrees(target_version, [], dry_run, auto_commit=auto_commit)

    def _apply_migration(
        self,
        migration: BaseMigration,
        metadata: ProjectMetadata,
        dry_run: bool,
    ) -> tuple[MigrationResult, str]:
        """Apply a single migration.

        Args:
            migration: The migration to apply
            metadata: Project metadata
            dry_run: Whether to simulate only

        Returns:
            Tuple of (MigrationResult, status) where status is one of
            ``applied``, ``skipped``, or ``failed``.
        """
        # Skip if the applicable ledger partition already records this migration
        # (ADR 2026-10-17-1 §3: the ledger, not metadata.yaml, is the applied
        # authority) -- unless a runs_first migration's structural predicate says
        # the project carries its old state again (a pulled metadata.yaml or a
        # merge brought it back), which re-selects it. ``detect()`` below stays
        # the pre-apply() idempotency guard only (C-003), never the skip
        # authority. A drifted source never changes this: a recorded migration
        # stays recorded whatever its content now hashes to (C-004).
        ledger = MigrationLedger(self.project_path)
        if migration_settled(ledger, migration) and not migration.reselect_when_recorded(self.project_path):
            return (
                MigrationResult(
                    success=True,
                    warnings=[f"Migration {migration.migration_id} already applied, skipping"],
                ),
                "skipped",
            )

        # A migration that needs a git repository is not applicable outside one
        # (#6539). Decide before detect() (which may itself resolve the repo
        # root), record nothing, and let a run inside a repository apply it.
        try:
            if migration_skipped_outside_repository(migration, self._repository_probe):
                return self._not_inside_repository_skip(migration)
        except GitCommonDirUnavailableError as exc:
            # The probe could not run (git missing or unusable). That is neither
            # "inside" nor "outside": fail closed with a recorded failure, like a
            # detect() that cannot run safely, so the migration stays retryable.
            return self._probe_unavailable_failure(metadata, migration, exc, dry_run=dry_run)

        # Check if migration is needed via detection. A symlinked
        # `.gitignore`/`.claudeignore` makes detect() fail closed with
        # GitignorePathError (gitignore_manager.py) rather than follow the
        # symlink. Treat that as a migration FAILURE, not a skip: a "skip"
        # here would report the upgrade as successful and let
        # _finalize_main_metadata bump metadata.version/schema_version past
        # this migration, permanently stranding it (it would never be
        # re-considered even after the symlink is replaced with a real file,
        # per MigrationRegistry.get_applicable's from_v/to_v window). Failing
        # closed instead leaves the pre-run schema/version untouched so the
        # next `spec-kitty upgrade` retries once the symlink is gone.
        try:
            migration_needed = migration.detect(self.project_path)
        except NotInsideRepositoryError:
            return self._not_inside_repository_skip(migration)
        except GitCommonDirUnavailableError as exc:
            return self._probe_unavailable_failure(metadata, migration, exc, dry_run=dry_run)
        except (GitignorePathError, MigrationStateUnreadableError) as exc:
            return self._detect_failure(
                metadata,
                migration,
                f"Cannot safely detect: {exc}",
                f"Cannot safely detect {migration.migration_id}: {exc}",
                dry_run=dry_run,
            )

        if not migration_needed:
            # Migration not needed - project doesn't have old state
            if not dry_run:
                self._record_migration_result(
                    metadata,
                    self.project_path,
                    migration,
                    "skipped",
                    "Not applicable",
                )
            return (
                MigrationResult(
                    success=True,
                    warnings=[f"Migration {migration.migration_id} not needed (project already in target state)"],
                ),
                "skipped",
            )

        # Check if safe to apply. Under ledger-diff selection the candidate set is
        # "declared minus applied" -- broader than the retired version window --
        # so a migration that does not fit THIS project (``can_apply`` refuses) is
        # a SKIP, not a failure: it is left for a run where it does fit. This
        # matches the worktree loop, which has always treated a ``can_apply``
        # refusal as a warn-and-continue. Not recorded, so it is re-evaluated when
        # the project state changes. (A genuine inability to complete work is an
        # ``apply()`` failure, which still fails the run.)
        try:
            can_apply, reason = migration.can_apply(self.project_path)
        except NotInsideRepositoryError:
            return self._not_inside_repository_skip(migration)
        except GitCommonDirUnavailableError as exc:
            return self._probe_unavailable_failure(metadata, migration, exc, dry_run=dry_run)
        if not can_apply:
            return (
                MigrationResult(
                    success=True,
                    warnings=[f"Migration {migration.migration_id} not applicable here ({reason}); skipping"],
                ),
                "skipped",
            )

        # Apply the migration. Same TOCTOU-safe handling as detect() above --
        # a symlink swapped in between detect() and apply() fails closed as a
        # migration failure, not an unhandled crash.
        try:
            result = migration.apply(self.project_path, dry_run=dry_run)
        except NotInsideRepositoryError as exc:
            # An ``apply()`` that reaches the repo resolver may already have
            # written state, so this is a failure, never a skip (#6539). It is
            # recorded below like any other failed apply (``runs_first`` records
            # nothing), and the run stops with a non-zero exit.
            result = MigrationResult(
                success=False,
                errors=[f"Cannot apply {migration.migration_id}: it needs a git repository but {exc.path} is not inside one"],
            )
        except GitCommonDirUnavailableError as exc:
            # Same as above: the probe could not run, so the repository state is
            # unknown after a possible write. A recorded failure, never a crash.
            result = MigrationResult(
                success=False,
                errors=[f"Cannot apply {migration.migration_id}: it needs a git repository and the probe could not run ({exc})"],
            )
        except (GitignorePathError, MigrationStateUnreadableError) as exc:
            return (
                MigrationResult(
                    success=False,
                    errors=[f"Cannot apply {migration.migration_id}: {exc}"],
                ),
                "failed",
            )

        # Record in metadata. A failed ``runs_first`` migration is not recorded:
        # its refusal writes nothing (charter-pack cutover contract, collision
        # preflight), only a ``success`` record ever settles it, and its
        # content-driven ``detect()`` re-selects it on the next run anyway.
        if not dry_run and (result.success or not migration.runs_first):
            self._record_migration_result(
                metadata,
                self.project_path,
                migration,
                "success" if result.success else "failed",
                "; ".join(result.changes_made) if result.changes_made else None,
            )

        return result, ("applied" if result.success else "failed")

    def _detect_failure(
        self,
        metadata: ProjectMetadata,
        migration: BaseMigration,
        message: str,
        error: str,
        *,
        dry_run: bool,
    ) -> tuple[MigrationResult, str]:
        """Record (unless dry-run) and return a failed result for a pre-apply check that could not run."""
        if not dry_run:
            self._record_migration_result(metadata, self.project_path, migration, "failed", message)
        return MigrationResult(success=False, errors=[error]), "failed"

    def _probe_unavailable_failure(
        self,
        metadata: ProjectMetadata,
        migration: BaseMigration,
        exc: GitCommonDirUnavailableError,
        *,
        dry_run: bool,
    ) -> tuple[MigrationResult, str]:
        """Fail closed, recorded, when the repository probe itself cannot run (git missing or unusable)."""
        reason = f"Cannot determine whether the project is inside a git repository: {exc}"
        return self._detect_failure(metadata, migration, reason, f"{reason} ({migration.migration_id})", dry_run=dry_run)

    @staticmethod
    def _not_inside_repository_skip(migration: BaseMigration) -> tuple[MigrationResult, str]:
        """Skip a migration that needs a git repository when the project has none (#6437, #6539).

        Reached from the pre-detect gate for a migration that declares
        ``requires_git_repository``, and from the ``detect()`` and ``can_apply()``
        catches of ``NotInsideRepositoryError`` (C-004). All three run before any
        write, so a skip loses nothing: record nothing, and let a run inside a
        repository apply it. The ``apply()`` catch is gone: ``apply()`` may already
        have written state, so an ``apply()``-time repository error is a recorded
        failure (see ``_apply_migration``), never a skip.
        """
        return (
            MigrationResult(
                success=True,
                warnings=[f"Migration {migration.migration_id} not applicable here (not inside a git repository); skipping"],
            ),
            "skipped",
        )

    def _upgrade_worktrees(
        self,
        target_version: str,
        migrations: list[BaseMigration],
        dry_run: bool,
        auto_commit: bool = False,
    ) -> dict[str, Any]:
        """Upgrade the non-integrating worktrees in the .worktrees/ directory.

        Integrating worktrees (a ``kitty/mission-…`` mission, lane or
        coordination branch, or a branch that cannot be read) are skipped by
        :func:`_worktrees_to_upgrade` (#5457): nothing is written, stamped or
        committed in them, and their branches receive project-global state by
        integration instead.

        Args:
            target_version: Target version
            migrations: List of migrations to apply
            dry_run: Whether to simulate only
            auto_commit: If True, commit each worktree's upgrade churn on its
                own branch after that worktree's writes (#2385). The commit-set
                is the porcelain diff against a baseline captured before this
                worktree's writes, so pre-existing uncommitted work in a live
                lane worktree is never swept in.

        Returns:
            Dict with warnings and errors lists
        """
        result: dict[str, Any] = {"warnings": [], "errors": [], "worktree_failures": []}
        worktree_migrations = [migration for migration in migrations if migration.runs_on_worktrees]

        if migrations and not worktree_migrations:
            return result

        worktrees_dir = self.project_path / WORKTREES_DIR
        if not worktrees_dir.exists():
            return result

        # Loaded once, up front: the main checkout's already-settled
        # ``last_upgraded_at`` is the shared stamp a bookkeeping-only
        # worktree version bump must align to (#4972) -- see
        # ``_reconcile_worktree_bookkeeping`` below. Reading it fresh here
        # (rather than threading an already-loaded object through all three
        # callers) picks up whatever this same command run already wrote to
        # main's metadata.yaml (``_finalize_main_metadata`` /
        # ``_stamp_no_migrations_metadata`` both run and save before any
        # caller reaches ``_upgrade_worktrees``).
        main_metadata = ProjectMetadata.load(self.kittify_dir) if not dry_run else None

        # Minted ONCE here, before the worktree loop: the shared fallback a
        # bookkeeping-only worktree bump aligns to when main itself has no
        # already-stamped value to align to (#4972). ``_aligned_worktree_timestamp``
        # is called PER-WORKTREE below; a fresh ``now_utc()`` mint at that call
        # site would give each sibling worktree in this same run a DIFFERENT
        # fallback value, reproducing the exact main/coord/lane divergence
        # this reconciliation path exists to prevent.
        fallback_timestamp = now_utc()

        # Deterministic ordering; integrating worktrees are skipped (#5457).
        for worktree in _worktrees_to_upgrade(worktrees_dir):
            wt_kittify = worktree / KITTIFY_DIR
            has_upgradeable_state = wt_kittify.exists() or (
                bool(worktree_migrations) and ((worktree / KITTY_SPECS_DIR).exists() or (worktree / ".specify").exists())
            )
            if not has_upgradeable_state:
                continue

            # Baseline BEFORE any write to this worktree, so the auto-commit
            # below stages only the churn this upgrade run introduces (#2385).
            wt_baseline = capture_upgrade_baseline(worktree) if auto_commit and not dry_run else None

            # Load or create worktree metadata
            wt_metadata = ProjectMetadata.load(wt_kittify)
            wt_metadata_synthesized = wt_metadata is None
            if wt_metadata is None:
                wt_detector = VersionDetector(worktree)
                wt_version = wt_detector.detect_version()
                wt_metadata = self._create_initial_metadata(wt_version)
            wt_from_version = wt_metadata.version

            # Freshly synthesized metadata must be persisted even when the
            # detected version already equals the target — otherwise the
            # version-bump below never fires, the save is skipped, and the
            # self-healing path silently regresses (#1873, regression of #1857).
            worktree_metadata_dirty = wt_metadata_synthesized
            # Marker-less command files a migration preserved in THIS worktree: named in the
            # output, never committed (they are not written by the run), and they do not
            # suppress the commit of everything else (#5443).
            worktree_held: set[str] = set()
            # A migration that could not be evaluated or raised in this worktree: nothing is
            # committed there, but (unlike ``worktree_failed``) the schema-stamp rules are unchanged.
            worktree_errored = False
            # FR-009 (#3376): a NEW per-worktree flag distinct from
            # ``worktree_metadata_dirty``/``worktree_held`` above --
            # the loop previously tracked no success/failure boolean at all.
            # Sticky for the remainder of this worktree's migrations: once any
            # migration fails here, the schema_version stamp below must stay
            # suppressed even if a later migration in the same worktree
            # succeeds. This is a guard (leave whatever is present on disk),
            # not a restore -- no per-worktree pre-run schema is captured.
            worktree_failed = False

            # Apply migrations to worktree
            wt_ledger = MigrationLedger(worktree)
            for migration in worktree_migrations:
                if migration_settled(wt_ledger, migration) and not migration.reselect_when_recorded(worktree):
                    continue

                # Same fail-closed handling as the main checkout in
                # _apply_migration: a symlinked ignore file makes detect()
                # raise GitignorePathError rather than follow it. Record it
                # as a failure, not a skip -- a "skip" record would be
                # indistinguishable from "not applicable" and could read as
                # settled, when the migration was never actually evaluated.
                try:
                    migration_needed = migration.detect(worktree)
                except (GitignorePathError, MigrationStateUnreadableError) as exc:
                    worktree_errored = True
                    result["errors"].append(f"Worktree {worktree.name}: Cannot safely detect {migration.migration_id}: {exc}")
                    if not dry_run and self._record_migration_result(
                        wt_metadata,
                        worktree,
                        migration,
                        "failed",
                        f"Cannot safely detect: {exc}",
                    ):
                        worktree_metadata_dirty = True
                    continue

                if not migration_needed:
                    # Only mark dirty when a NEW record was written; an
                    # already-recorded "skipped" migration is a no-op and must
                    # not bump last_upgraded_at on every re-run (issue #1872).
                    if not dry_run and self._record_migration_result(
                        wt_metadata,
                        worktree,
                        migration,
                        "skipped",
                        "Not applicable",
                    ):
                        worktree_metadata_dirty = True
                    continue

                can_apply, reason = migration.can_apply(worktree)
                if not can_apply:
                    result["warnings"].append(f"Worktree {worktree.name}: Cannot apply {migration.migration_id}: {reason}")
                    continue

                try:
                    migration_result = migration.apply(worktree, dry_run=dry_run)
                except (GitignorePathError, MigrationStateUnreadableError) as exc:
                    worktree_errored = True
                    result["errors"].append(f"Worktree {worktree.name}: Cannot apply {migration.migration_id}: {exc}")
                    continue
                if migration_result.manual_review_required:
                    worktree_held.update(migration_result.preserved_paths)

                if migration_result.success:
                    if not dry_run and self._record_migration_result(
                        wt_metadata,
                        worktree,
                        migration,
                        "success",
                        "; ".join(migration_result.changes_made) if migration_result.changes_made else None,
                    ):
                        worktree_metadata_dirty = True
                    result["warnings"].extend([f"Worktree {worktree.name}: {w}" for w in migration_result.warnings])
                else:
                    if not dry_run:
                        self._record_migration_result(
                            wt_metadata,
                            worktree,
                            migration,
                            "failed",
                            "; ".join(migration_result.errors) if migration_result.errors else None,
                        )
                        # Intentionally not marking worktree_metadata_dirty: a
                        # failed migration is not an upgrade, so it must not
                        # bump last_upgraded_at. The failure record itself is
                        # already persisted by _record_migration_result.
                    worktree_failed = True
                    failure_messages = [f"Worktree {worktree.name}: {e}" for e in migration_result.errors]
                    result["errors"].extend(failure_messages)
                    result["worktree_failures"].extend(failure_messages)

            # Save worktree metadata only when something material changed
            # (a migration record was written, metadata was synthesized fresh,
            # or the version advanced); a no-op upgrade must not rewrite
            # last_upgraded_at (issue #1838).
            if not dry_run:
                worktree_metadata_dirty = self._reconcile_worktree_bookkeeping(
                    wt_metadata, target_version, worktree_metadata_dirty, main_metadata, fallback_timestamp
                )

                if worktree_metadata_dirty:
                    wt_metadata.save(wt_kittify)
                # Stamp after save() just like the main project path: the
                # model's schema_version may be None, and the stamp settles
                # the canonical capability map (#5229).
                # FR-009 (#3376): guarded by worktree_failed -- a worktree with
                # any failed migration must not have schema_version advanced.
                # Leave whatever value is already present (no pre-run capture
                # exists for worktrees, unlike the main path's restore).
                if REQUIRED_SCHEMA_VERSION is not None and not worktree_failed:
                    self._stamp_schema_version(wt_kittify, REQUIRED_SCHEMA_VERSION)

                # Commit this worktree's upgrade churn on its own branch (#2385) under the
                # same rules as the main checkout: only a successful run commits, held files
                # are named and never block the rest, and one explicit reason per no-commit case.
                if auto_commit:
                    result["warnings"].extend(
                        _commit_worktree_churn(
                            worktree,
                            baseline=wt_baseline,
                            from_version=wt_from_version,
                            to_version=target_version,
                            failed=worktree_failed or worktree_errored,
                            held_paths=sorted(worktree_held),
                        )
                    )

        return result

    @staticmethod
    def _reconcile_worktree_bookkeeping(
        wt_metadata: ProjectMetadata,
        target_version: str,
        worktree_metadata_dirty: bool,
        main_metadata: ProjectMetadata | None,
        fallback_timestamp: datetime,
    ) -> bool:
        """Advance ``wt_metadata.version`` to ``target_version`` and settle
        its ``last_upgraded_at`` stamp; return the resulting dirty flag.

        Extends the #1838 save-gate (a no-op upgrade must not rewrite
        ``last_upgraded_at``): the gate previously only suppressed the mint
        when ``version == target_version`` already, leaving a real hole --
        a worktree that is otherwise fully settled (no migration applied
        content, no metadata synthesized fresh) but merely lagging main's
        ``version`` still got a FRESH ``now_utc()`` mint here, diverging
        main/coord/lane on this one bookkeeping line and wedging in-flight
        coord missions (#4972).

        A version-only bump (``worktree_metadata_dirty`` was False coming
        in) is bookkeeping-only: align ``last_upgraded_at`` to the main
        checkout's already-stamped value instead of minting a new one, or --
        when main has no stamp of its own -- to ``fallback_timestamp``, a
        single value minted once by the caller before the worktree loop and
        shared by every sibling worktree reconciled in this same run (see
        ``_aligned_worktree_timestamp``). A genuine change (migration applied
        real content, or metadata was freshly synthesized --
        ``worktree_metadata_dirty`` was already True coming in) keeps
        stamping a fresh ``now_utc()`` (#2385 preservation).
        """
        bookkeeping_only_bump = not worktree_metadata_dirty and wt_metadata.version != target_version

        if wt_metadata.version != target_version:
            wt_metadata.version = target_version
            worktree_metadata_dirty = True

        if worktree_metadata_dirty:
            wt_metadata.last_upgraded_at = MigrationRunner._aligned_worktree_timestamp(main_metadata, fallback_timestamp) if bookkeeping_only_bump else now_utc()

        return worktree_metadata_dirty

    @staticmethod
    def _aligned_worktree_timestamp(main_metadata: ProjectMetadata | None, fallback_timestamp: datetime) -> datetime:
        """Return the shared stamp a bookkeeping-only worktree bump aligns to.

        Falls back to ``fallback_timestamp`` only when the main checkout has
        no stamped value to align to (missing metadata, or never upgraded).
        ``fallback_timestamp`` is minted ONCE by the caller, before the
        worktree loop, and passed into every call this same run makes --
        never minted fresh here -- so every sibling worktree reconciled in
        one run shares the exact same fallback value instead of each
        diverging on its own ``now_utc()`` (#4972).
        """
        if main_metadata is None:
            return fallback_timestamp
        main_stamp = main_metadata.last_upgraded_at
        if main_stamp is None:
            return fallback_timestamp
        return main_stamp

    def _create_initial_metadata(self, detected_version: str) -> ProjectMetadata:
        """Create initial metadata for a project without it.

        Args:
            detected_version: Version detected from heuristics

        Returns:
            New ProjectMetadata instance
        """
        return ProjectMetadata(
            version=detected_version,
            initialized_at=now_utc(),
            python_version=platform.python_version(),
            platform=sys.platform,
            platform_version=platform.platform(),
        )

    def _record_migration_result(
        self,
        metadata: ProjectMetadata,
        root: Path,
        migration: BaseMigration,
        result: str,
        notes: str | None = None,
    ) -> bool:
        """Persist each migration record immediately for crash/failure recovery.

        Writes the two-partition ledger (ADR 2026-10-17-1) -- the applied
        authority the selection flip reads -- AND makes the legacy
        ``metadata.yaml`` ``record_migration`` call. That metadata write is now
        in-memory only: the WP04 cutover dropped ``migrations.applied`` from
        ``save()``, so this record never reaches disk and is NOT a second
        on-disk authority (C-001). It survives solely so the adoption backfill
        and any in-process legacy reader still see the applied list during a run.

        Returns ``True`` when a NEW ledger record was appended. An idempotent
        no-op (the record already existed) returns ``False`` and skips the
        metadata save, so callers can avoid bumping ``last_upgraded_at`` on a
        re-run that recorded nothing new (issue #1872 / #1838 / #4972). The
        ledger -- not the in-memory metadata list, which a reload leaves empty --
        is the "new record" signal.
        """
        recorded = self._record_ledger_result(root, migration, result)
        metadata.record_migration(migration.migration_id, result, notes)
        if recorded:
            metadata.save(root / KITTIFY_DIR)
        return recorded

    @staticmethod
    def _record_ledger_result(root: Path, migration: BaseMigration, result: str) -> bool:
        """Append a ledger record for *migration* (partition-routed), idempotently.

        Routing, identity and the ``sha256:`` content_hash are filled in by
        :func:`ledger.build_record` (D3). A record with an identical
        ``(id, result)`` already present in the authoritative partition is a
        no-op. Returns ``True`` when a new record was appended.
        """
        ledger = MigrationLedger(root)
        if any(record.id == migration.migration_id and record.result == result for record in ledger.applicable_records_for(migration)):
            return False
        ledger.append(build_record(migration, result))
        return True

    def _finalize_main_metadata(
        self,
        metadata: ProjectMetadata,
        target_version: str,
        result: UpgradeResult,
        pre_run_stamp: VersionStamp,
    ) -> None:
        """Persist metadata and settle ``schema_version`` after the loop.

        On **success**: bump ``version`` + stamp ``REQUIRED_SCHEMA_VERSION`` (the
        target) and the canonical capability map. The stamp runs after
        ``metadata.save()``: ``save()`` keeps keys it does not own but a legacy
        model carries ``schema_version=None``, so the stamp is what settles the
        value (FR-002 / #705, #5229).

        On **failure** (FR-002 / #3334): restore the captured pre-run version
        trio so a failed migration NEVER advances -- or erases -- the schema the
        project actually satisfies. A legacy project (captured value absent) is
        intentionally left unstamped so it is never advanced to the target.
        """
        if result.success:
            metadata.version = target_version
            metadata.last_upgraded_at = now_utc()
            metadata.save(self.kittify_dir)
            if REQUIRED_SCHEMA_VERSION is not None:
                self._stamp_schema_version(self.kittify_dir, REQUIRED_SCHEMA_VERSION)
        else:
            pre_run_stamp.restore(self.kittify_dir)

    @staticmethod
    def _stamp_schema_version(kittify_dir: Path, schema_version: int) -> None:
        """Write ``spec_kitty.schema_version`` and the canonical ``schema_capabilities`` map.

        This is the single step that allows the gate to pass after an upgrade.
        We update the raw YAML rather than going through ProjectMetadata so that
        the stamp survives even if metadata parsing is partial. The capability
        map follows ``init``'s rule (#5229): absent -> the canonical map, a legacy
        list -> a map, an existing map -> left to the operator.

        Args:
            kittify_dir: Path to the ``.kittify/`` directory.
            schema_version: The new schema version integer to stamp.
        """
        import io

        import yaml

        from specify_cli.core.atomic import atomic_write

        metadata_path = kittify_dir / "metadata.yaml"
        if not metadata_path.exists():
            # Why: every spec-kitty project has metadata.yaml after init, so this
            # branch is unreachable in normal operation. Log instead of raising
            # so a corrupted dev environment surfaces a diagnostic. See FU-4 in
            # kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/follow-ups.md.
            logger.warning("schema_version stamp skipped: %s does not exist", metadata_path)
            return

        try:
            with open(metadata_path, encoding="utf-8-sig") as fh:
                data = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            # Why: a parse failure here means the metadata file became corrupt
            # between the upgrade entry point and this stamp call. Surface the
            # cause so operators can repair it. See FU-4 in
            # kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/follow-ups.md.
            logger.warning(
                "schema_version stamp skipped: failed to read %s (%s)",
                metadata_path,
                exc,
            )
            return

        if not isinstance(data, dict):
            return

        spec_kitty = data.get("spec_kitty")
        stamped = dict(spec_kitty) if isinstance(spec_kitty, dict) else {}
        stamped["schema_version"] = schema_version
        stamped["schema_capabilities"] = canonical_schema_capabilities(stamped.get("schema_capabilities"))

        # Compare-before-write (issue #1871): skip the re-dump when the stamp
        # changes no value, so a no-op upgrade does not reformat or mtime-churn
        # metadata.yaml. The comparison is on parsed values, not bytes: init
        # writes the file with a different YAML emitter (an empty
        # ``last_upgraded_at:`` where this dump writes ``null``), and a byte
        # compare re-serialized a just-initialized project's file (#6416).
        if stamped == spec_kitty:
            return
        data["spec_kitty"] = stamped

        buf = io.StringIO()
        buf.write(_METADATA_HEADER)
        yaml.dump(data, buf, default_flow_style=False, sort_keys=False)
        rendered = buf.getvalue()

        atomic_write(metadata_path, rendered, mkdir=True)
