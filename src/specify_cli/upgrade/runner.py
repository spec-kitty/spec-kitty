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

from specify_cli.core.constants import KITTIFY_DIR, WORKTREES_DIR
from specify_cli.gitignore_manager import GitignorePathError
from specify_cli.migration.schema_version import (
    REQUIRED_SCHEMA_VERSION,
    get_project_schema_version,
)

from . import autocommit
from .autocommit import capture_upgrade_baseline
from .detector import VersionDetector
from .metadata import ProjectMetadata
from .migrations.base import BaseMigration, MigrationResult
from .registry import MigrationRegistry

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
        """
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
            # the next agent command. Stamping after any save() is required
            # because ProjectMetadata.save() does not preserve unknown keys.
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

        # Normalize legacy migration IDs before checking has_migration()
        if not dry_run:
            norm_changes = metadata.normalize_and_save_legacy_ids(self.kittify_dir)
            result.warnings.extend(norm_changes)

        # FR-002 (#3334): capture the on-disk schema_version BEFORE the loop.
        # A failed migration's _record_migration_result -> save() rewrites
        # metadata.yaml from a fixed dict and, on the mid-loop break, the
        # success-guarded stamp below never runs -- so without this capture the
        # value is lost and a re-run re-detects the project as legacy and
        # re-hits the same failing migration. We restore this CAPTURED value on
        # failure, never REQUIRED_SCHEMA_VERSION: re-stamping the target onto a
        # half-migrated project would open the gate on a corpus the migration
        # never finished (the exact dishonest-state bug this mission closes).
        pre_run_schema_version = get_project_schema_version(self.project_path)

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
            self._finalize_main_metadata(metadata, target_version, result, pre_run_schema_version)

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
        # Skip if already applied
        if metadata.has_migration(migration.migration_id):
            return (
                MigrationResult(
                    success=True,
                    warnings=[f"Migration {migration.migration_id} already applied, skipping"],
                ),
                "skipped",
            )

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
        except GitignorePathError as exc:
            if not dry_run:
                self._record_migration_result(
                    metadata,
                    self.kittify_dir,
                    migration.migration_id,
                    "failed",
                    f"Cannot safely detect: {exc}",
                )
            return (
                MigrationResult(
                    success=False,
                    errors=[f"Cannot safely detect {migration.migration_id}: {exc}"],
                ),
                "failed",
            )

        if not migration_needed:
            # Migration not needed - project doesn't have old state
            if not dry_run:
                self._record_migration_result(
                    metadata,
                    self.kittify_dir,
                    migration.migration_id,
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

        # Check if safe to apply
        can_apply, reason = migration.can_apply(self.project_path)
        if not can_apply:
            return (
                MigrationResult(
                    success=False,
                    errors=[f"Cannot apply {migration.migration_id}: {reason}"],
                ),
                "failed",
            )

        # Apply the migration. Same TOCTOU-safe handling as detect() above --
        # a symlink swapped in between detect() and apply() fails closed as a
        # migration failure, not an unhandled crash.
        try:
            result = migration.apply(self.project_path, dry_run=dry_run)
        except GitignorePathError as exc:
            return (
                MigrationResult(
                    success=False,
                    errors=[f"Cannot apply {migration.migration_id}: {exc}"],
                ),
                "failed",
            )

        # Record in metadata
        if not dry_run:
            self._record_migration_result(
                metadata,
                self.kittify_dir,
                migration.migration_id,
                "success" if result.success else "failed",
                "; ".join(result.changes_made) if result.changes_made else None,
            )

        return result, ("applied" if result.success else "failed")

    def _upgrade_worktrees(
        self,
        target_version: str,
        migrations: list[BaseMigration],
        dry_run: bool,
        auto_commit: bool = False,
    ) -> dict[str, Any]:
        """Upgrade all worktrees in .worktrees/ directory.

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

        # Use deterministic ordering so migrations and logs are reproducible.
        for worktree in sorted(worktrees_dir.iterdir(), key=lambda p: p.name):
            if not worktree.is_dir():
                continue

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
            worktree_manual_review = False
            # FR-009 (#3376): a NEW per-worktree flag distinct from
            # ``worktree_metadata_dirty``/``worktree_manual_review`` above --
            # the loop previously tracked no success/failure boolean at all.
            # Sticky for the remainder of this worktree's migrations: once any
            # migration fails here, the schema_version stamp below must stay
            # suppressed even if a later migration in the same worktree
            # succeeds. This is a guard (leave whatever is present on disk),
            # not a restore -- no per-worktree pre-run schema is captured.
            worktree_failed = False

            # Apply migrations to worktree
            for migration in worktree_migrations:
                if wt_metadata.has_migration(migration.migration_id):
                    continue

                # Same fail-closed handling as the main checkout in
                # _apply_migration: a symlinked ignore file makes detect()
                # raise GitignorePathError rather than follow it. Record it
                # as a failure, not a skip -- a "skip" record would be
                # indistinguishable from "not applicable" and could read as
                # settled, when the migration was never actually evaluated.
                try:
                    migration_needed = migration.detect(worktree)
                except GitignorePathError as exc:
                    result["errors"].append(f"Worktree {worktree.name}: Cannot safely detect {migration.migration_id}: {exc}")
                    if not dry_run and self._record_migration_result(
                        wt_metadata,
                        wt_kittify,
                        migration.migration_id,
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
                        wt_kittify,
                        migration.migration_id,
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
                except GitignorePathError as exc:
                    result["errors"].append(f"Worktree {worktree.name}: Cannot apply {migration.migration_id}: {exc}")
                    continue
                if migration_result.manual_review_required:
                    worktree_manual_review = True

                if migration_result.success:
                    if not dry_run and self._record_migration_result(
                        wt_metadata,
                        wt_kittify,
                        migration.migration_id,
                        "success",
                        "; ".join(migration_result.changes_made) if migration_result.changes_made else None,
                    ):
                        worktree_metadata_dirty = True
                    result["warnings"].extend([f"Worktree {worktree.name}: {w}" for w in migration_result.warnings])
                else:
                    if not dry_run:
                        self._record_migration_result(
                            wt_metadata,
                            wt_kittify,
                            migration.migration_id,
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
                # ProjectMetadata.save() rewrites metadata.yaml from its fixed
                # model, so stamp after save just like the main project path.
                # FR-009 (#3376): guarded by worktree_failed -- a worktree with
                # any failed migration must not have schema_version advanced.
                # Leave whatever value is already present (no pre-run capture
                # exists for worktrees, unlike the main path's restore).
                if REQUIRED_SCHEMA_VERSION is not None and not worktree_failed:
                    self._stamp_schema_version(wt_kittify, REQUIRED_SCHEMA_VERSION)

                # Commit this worktree's upgrade churn on its own branch
                # (#2385); the baseline diff keeps pre-existing uncommitted
                # work (e.g. in-flight WP edits) out of the commit.
                if auto_commit:
                    if worktree_manual_review:
                        result["warnings"].append(
                            f"Worktree {worktree.name}: Skipped auto-commit because the upgrade preserved customized files that require manual review."
                        )
                    else:
                        _committed, _paths, wt_commit_warning = autocommit.commit_touched_checkout(
                            worktree,
                            wt_baseline,
                            wt_from_version,
                            target_version,
                        )
                        if wt_commit_warning:
                            result["warnings"].append(f"Worktree {worktree.name}: {wt_commit_warning}")

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
        metadata_dir: Path,
        migration_id: str,
        result: str,
        notes: str | None = None,
    ) -> bool:
        """Persist each migration record immediately for crash/failure recovery.

        Returns ``True`` when a new record was written. An idempotent no-op
        (the record already existed) returns ``False`` and skips the save, so
        callers can avoid bumping ``last_upgraded_at`` on a re-run that recorded
        nothing new (issue #1872 / #1838).
        """
        recorded = metadata.record_migration(migration_id, result, notes)
        if recorded:
            metadata.save(metadata_dir)
        return recorded

    def _finalize_main_metadata(
        self,
        metadata: ProjectMetadata,
        target_version: str,
        result: UpgradeResult,
        pre_run_schema_version: int | None,
    ) -> None:
        """Persist metadata and settle ``schema_version`` after the loop.

        On **success**: bump ``version`` + stamp ``REQUIRED_SCHEMA_VERSION`` (the
        target). The stamp MUST run after ``metadata.save()`` because
        ``ProjectMetadata.save()`` reconstructs the YAML from a fixed dict, so a
        stamp written first would be clobbered (FR-002 / #705).

        On **failure** (FR-002 / #3334): restore the captured pre-run
        ``schema_version`` so a failed migration NEVER advances -- or erases --
        the schema the project actually satisfies. A legacy project (captured
        value ``None``) is intentionally left unstamped so it is never advanced
        to the target.
        """
        if result.success:
            metadata.version = target_version
            metadata.last_upgraded_at = now_utc()
            metadata.save(self.kittify_dir)
            if REQUIRED_SCHEMA_VERSION is not None:
                self._stamp_schema_version(self.kittify_dir, REQUIRED_SCHEMA_VERSION)
        elif pre_run_schema_version is not None:
            self._stamp_schema_version(self.kittify_dir, pre_run_schema_version)

    @staticmethod
    def _stamp_schema_version(kittify_dir: Path, schema_version: int) -> None:
        """Write ``spec_kitty.schema_version`` into ``.kittify/metadata.yaml``.

        This is the single step that allows the gate to pass after an upgrade.
        We update the raw YAML rather than going through ProjectMetadata so that
        the stamp survives even if metadata parsing is partial.

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

        if "spec_kitty" not in data or not isinstance(data["spec_kitty"], dict):
            data["spec_kitty"] = {}

        data["spec_kitty"]["schema_version"] = schema_version

        header = "# Spec Kitty Project Metadata\n# Auto-generated by spec-kitty init/upgrade\n# DO NOT EDIT MANUALLY\n\n"
        buf = io.StringIO()
        buf.write(header)
        yaml.dump(data, buf, default_flow_style=False, sort_keys=False)
        rendered = buf.getvalue()

        # Compare-before-write (issue #1871): skip the re-dump when the rendered
        # bytes already match the file on disk, so a no-op upgrade does not
        # reformat or mtime-churn an already-stamped metadata.yaml.
        try:
            current = metadata_path.read_text(encoding="utf-8-sig")
        except OSError:
            current = None
        if current == rendered:
            return

        atomic_write(metadata_path, rendered, mkdir=True)
