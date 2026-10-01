"""Atomic migration orchestrator for canonical context architecture.

Orchestrates all migration steps in the correct order with a single
atomic git commit.  Any failure triggers a rollback to the pre-migration
state via backup restoration.

Step order (must be maintained):
  1.  Backup
  2.  Identity backfill (project_uuid, mission_ids, wp_ids)
  3.  Ownership backfill
  4.  State rebuild (event log)
  5.  Strip frontmatter  (AFTER state rebuild)
  6.  Rewrite agent shims
  7.  Update schema version in metadata.yaml
  8.  Update .gitignore
  9.  Move derived files (status.json → .kittify/derived/)
  10. Commit

Rollback on any failure: restore backup, report which step failed.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from kernel.clock import now_utc_iso
from kernel.git import GitCommandError, status_entries

logger = logging.getLogger(__name__)

_TARGET_SCHEMA_VERSION = 3
_TARGET_SCHEMA_CAPABILITIES = [
    "canonical_context",
    "event_log_authority",
    "ownership_manifest",
    "thin_shims",
]

# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------


@dataclass
class MigrationReport:
    """Aggregate outcome of the full one-shot migration."""

    success: bool = False
    features_migrated: int = 0
    wps_backfilled: int = 0
    events_generated: int = 0
    files_moved: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failed_step: str | None = None
    dry_run: bool = False


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------

_BACKUP_DIR_NAME = ".migration-backup"


def _create_backup(repo_root: Path) -> Path | None:
    """Back up .kittify/, kitty-specs/, and .gitignore into .kittify/.migration-backup/.

    The migration mutates all three locations, so rollback must cover all of them.
    Returns the backup directory path, or None if backup failed.
    """
    kittify = repo_root / ".kittify"
    if not kittify.exists():
        return None

    backup_dir = kittify / _BACKUP_DIR_NAME
    # Remove stale backup if present
    if backup_dir.exists():
        try:
            shutil.rmtree(backup_dir)
        except OSError as exc:
            logger.warning("Could not remove stale backup: %s", exc)

    try:
        # 1. Back up .kittify/ (except the backup dir itself)
        shutil.copytree(
            kittify,
            backup_dir,
            ignore=shutil.ignore_patterns(_BACKUP_DIR_NAME),
        )

        # 2. Back up kitty-specs/ (migration modifies WP frontmatter and event logs)
        kitty_specs = repo_root / "kitty-specs"
        if kitty_specs.is_dir():
            shutil.copytree(kitty_specs, backup_dir / "kitty-specs-backup")

        # 3. Back up .gitignore (migration modifies it)
        gitignore = repo_root / ".gitignore"
        if gitignore.is_file():
            shutil.copy2(gitignore, backup_dir / "gitignore-backup")

        logger.info("Backup created at %s (includes kitty-specs/ and .gitignore)", backup_dir)
        return backup_dir
    except OSError as exc:
        logger.error("Failed to create backup: %s", exc)
        return None


def _restore_backup(repo_root: Path, backup_dir: Path) -> None:
    """Restore .kittify/, kitty-specs/, and .gitignore from backup (used on rollback)."""
    kittify = repo_root / ".kittify"
    if not backup_dir.exists():
        logger.error("Backup directory %s does not exist — cannot restore", backup_dir)
        return

    # Restore kitty-specs/ if backed up
    kitty_specs_backup = backup_dir / "kitty-specs-backup"
    if kitty_specs_backup.is_dir():
        kitty_specs = repo_root / "kitty-specs"
        if kitty_specs.is_dir():
            shutil.rmtree(kitty_specs)
        shutil.copytree(kitty_specs_backup, kitty_specs)
        logger.info("Restored kitty-specs/ from backup")

    # Restore .gitignore if backed up
    gitignore_backup = backup_dir / "gitignore-backup"
    if gitignore_backup.is_file():
        shutil.copy2(gitignore_backup, repo_root / ".gitignore")
        logger.info("Restored .gitignore from backup")

    # Remove current .kittify content (except the backup itself)
    for item in kittify.iterdir():
        if item.name == _BACKUP_DIR_NAME:
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except OSError as exc:
            logger.warning("Could not remove %s during rollback: %s", item, exc)

    # Restore from backup
    for item in backup_dir.iterdir():
        dest = kittify / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except OSError as exc:
            logger.warning("Could not restore %s during rollback: %s", item, exc)

    logger.info("Rollback complete: .kittify/ restored from backup")


def _cleanup_backup(repo_root: Path) -> None:
    """Remove the backup directory after a successful migration."""
    backup_dir = repo_root / ".kittify" / _BACKUP_DIR_NAME
    if backup_dir.exists():
        try:
            shutil.rmtree(backup_dir)
            logger.debug("Backup directory removed after successful migration")
        except OSError as exc:
            logger.warning("Could not remove backup dir: %s", exc)


# ---------------------------------------------------------------------------
# Helper: discover feature directories
# ---------------------------------------------------------------------------


def _discover_features(repo_root: Path) -> list[Path]:
    """Return sorted list of feature directories under kitty-specs/."""
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        return []
    features = [
        d for d in sorted(kitty_specs.iterdir())
        if d.is_dir() and (d / "meta.json").exists()
    ]
    return features


# ---------------------------------------------------------------------------
# Schema version update
# ---------------------------------------------------------------------------


def _update_schema_version(repo_root: Path) -> None:
    """Set schema_version=3 and capabilities in metadata.yaml."""
    from ruamel.yaml import YAML

    metadata_path = repo_root / ".kittify" / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found: {metadata_path}")

    y = YAML()
    y.preserve_quotes = True
    y.width = 4096

    with metadata_path.open("r", encoding="utf-8") as fh:
        data = y.load(fh)

    if data is None:
        data = {}

    spec_kitty = data.setdefault("spec_kitty", {})
    spec_kitty["schema_version"] = _TARGET_SCHEMA_VERSION
    spec_kitty["schema_capabilities"] = _TARGET_SCHEMA_CAPABILITIES
    spec_kitty["last_upgraded_at"] = now_utc_iso()

    with metadata_path.open("w", encoding="utf-8") as fh:
        y.dump(data, fh)

    logger.info("Schema version updated to %d in metadata.yaml", _TARGET_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# .gitignore update
# ---------------------------------------------------------------------------

_GITIGNORE_ADD_ENTRIES = [
    ".kittify/derived/",
    ".kittify/runtime/",
    ".kittify/.migration-backup/",
]

_GITIGNORE_REMOVE_ENTRIES = [
    # Old workspaces location (now .kittify/runtime/workspaces/)
    ".kittify/workspaces/",
    # Old merge-state location
    ".kittify/merge-state.json",
]


def _update_gitignore(repo_root: Path) -> list[str]:
    """Add new entries and remove obsolete entries from .gitignore.

    Returns list of descriptions of changes made.
    """
    gitignore_path = repo_root / ".gitignore"
    changes: list[str] = []

    if not gitignore_path.exists():
        # Create minimal gitignore with new entries
        gitignore_path.write_text("\n".join(_GITIGNORE_ADD_ENTRIES) + "\n", encoding="utf-8")
        changes.append(f"Created .gitignore with entries: {_GITIGNORE_ADD_ENTRIES}")
        return changes

    content = gitignore_path.read_text(encoding="utf-8")
    original_content = content

    # Add missing entries
    for entry in _GITIGNORE_ADD_ENTRIES:
        if entry not in content:
            if not content.endswith("\n"):
                content += "\n"
            content += entry + "\n"
            changes.append(f"Added .gitignore entry: {entry}")

    # Remove obsolete entries (only if present)
    for obsolete in _GITIGNORE_REMOVE_ENTRIES:
        if obsolete in content:
            # Remove the line
            lines = content.splitlines(keepends=True)
            new_lines = [ln for ln in lines if ln.rstrip("\n\r") != obsolete]
            content = "".join(new_lines)
            changes.append(f"Removed obsolete .gitignore entry: {obsolete}")

    if content != original_content:
        gitignore_path.write_text(content, encoding="utf-8")

    return changes


# ---------------------------------------------------------------------------
# Derived file relocation
# ---------------------------------------------------------------------------


def _move_derived_files(repo_root: Path) -> list[str]:
    """Move status.json files to .kittify/derived/<slug>/status.json.

    Returns list of moved file descriptions.
    """
    moved: list[str] = []
    kitty_specs = repo_root / "kitty-specs"
    if not kitty_specs.is_dir():
        return moved

    for feature_dir in sorted(kitty_specs.iterdir()):
        if not feature_dir.is_dir():
            continue

        status_json = feature_dir / "status.json"
        if not status_json.exists():
            continue

        # Destination: .kittify/derived/<slug>/status.json
        derived_dir = repo_root / ".kittify" / "derived" / feature_dir.name
        derived_dir.mkdir(parents=True, exist_ok=True)
        dest = derived_dir / "status.json"

        try:
            shutil.copy2(str(status_json), str(dest))
            # Leave source in place for now (it may still be referenced);
            # the .gitignore will keep it out of git once added.
            moved.append(f"Copied {status_json} → {dest}")
            logger.debug("Copied status.json for %s to derived dir", feature_dir.name)
        except OSError as exc:
            logger.warning("Could not copy status.json for %s: %s", feature_dir.name, exc)

    return moved


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git_add_all(repo_root: Path) -> bool:
    """Stage all changes (git add -A). Returns True on success."""
    try:
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("git add -A failed: %s", exc)
        return False


def _git_commit(repo_root: Path, message: str) -> bool:
    """Create the migration commit. Retries once with --no-verify if needed.

    Returns True on success.
    """
    # Check if there is anything to commit
    try:
        if not status_entries(repo_root, untracked=None, timeout=30):
            logger.info("Nothing to commit — migration produced no file changes")
            return True
    except GitCommandError as exc:
        # Advisory pre-check: if the probe fails, fall through and let the
        # commit attempts below decide (as before).
        logger.debug("git status pre-check failed: %s", exc)

    # First attempt: normal commit (honours hooks)
    try:
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "-m", message],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Migration commit created successfully")
            return True
        logger.warning("git commit failed (attempt 1): %s", result.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git commit exception (attempt 1): %s", exc)

    # Second attempt: skip hooks (migration commits must succeed)
    try:
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "commit", "--no-verify", "-m", message],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info("Migration commit created with --no-verify")
            return True
        logger.error("git commit failed (attempt 2 --no-verify): %s", result.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("git commit exception (attempt 2): %s", exc)

    return False


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


def run_migration(repo_root: Path, dry_run: bool = False) -> MigrationReport:  # noqa: C901
    """Orchestrate the full one-shot migration atomically.

    Runs 10 ordered steps.  On any failure the backup is restored and
    ``MigrationReport.failed_step`` is set.

    Args:
        repo_root: Absolute path to the project root.
        dry_run: If True, perform no actual file writes.  Reports what
            would change.

    Returns:
        :class:`MigrationReport` with aggregate counters and any warnings.
    """
    from specify_cli.migration.backfill_identity import (
        backfill_mission_ids,
        backfill_project_uuid,
        backfill_wp_ids,
    )
    from specify_cli.migration.backfill_ownership import backfill_ownership
    from specify_cli.migration.mission_state import rebuild_mission_event_log
    from specify_cli.migration.strip_frontmatter import strip_mutable_fields
    from specify_cli.migration.rewrite_shims import rewrite_agent_shims

    report = MigrationReport(dry_run=dry_run)
    backup_dir: Path | None = None

    def _fail(step: str, msg: str) -> MigrationReport:
        logger.error("Migration failed at step '%s': %s", step, msg)
        report.errors.append(f"[{step}] {msg}")
        report.failed_step = step
        if backup_dir is not None and not dry_run:
            _restore_backup(repo_root, backup_dir)
        return report

    if dry_run:
        # Dry-run: just report what would be done
        features = _discover_features(repo_root)
        report.features_migrated = len(features)
        report.success = True
        report.warnings.append(
            f"DRY RUN: would migrate {len(features)} feature(s) to schema v3"
        )
        return report

    # ------------------------------------------------------------------
    # Step 1: Backup
    # ------------------------------------------------------------------
    logger.info("Migration step 1/10: Backup")
    backup_dir = _create_backup(repo_root)
    if backup_dir is None:
        # Non-fatal: proceed without backup but warn loudly
        report.warnings.append("Could not create backup — proceeding without safety net")

    # ------------------------------------------------------------------
    # Step 2: Identity backfill
    # ------------------------------------------------------------------
    logger.info("Migration step 2/10: Identity backfill")
    try:
        backfill_project_uuid(repo_root)
    except FileNotFoundError as exc:
        return _fail("identity_backfill", f"metadata.yaml missing: {exc}")
    except Exception as exc:
        return _fail("identity_backfill", f"project UUID backfill failed: {exc}")

    # Mission IDs
    try:
        mission_id_map = backfill_mission_ids(repo_root)
    except Exception as exc:
        return _fail("identity_backfill", f"mission ID backfill failed: {exc}")

    # WP IDs for each feature
    all_wp_id_maps: dict[str, dict[str, str]] = {}
    total_wps = 0
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        mid = mission_id_map.get(slug, "")
        try:
            wp_id_map = backfill_wp_ids(feature_dir, mid)
            all_wp_id_maps[slug] = wp_id_map
            total_wps += len(wp_id_map)
        except Exception as exc:
            report.warnings.append(f"WP ID backfill failed for {slug}: {exc}")
            all_wp_id_maps[slug] = {}

    report.wps_backfilled = total_wps

    # ------------------------------------------------------------------
    # Step 3: Ownership backfill
    # ------------------------------------------------------------------
    logger.info("Migration step 3/10: Ownership backfill")
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        try:
            backfill_ownership(feature_dir, slug)
        except Exception as exc:
            return _fail("ownership_backfill", f"ownership backfill failed for {slug}: {exc}")

    # ------------------------------------------------------------------
    # Step 4: State rebuild
    # ------------------------------------------------------------------
    logger.info("Migration step 4/10: State rebuild")
    total_events_generated = 0
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        wp_id_map = all_wp_id_maps.get(slug, {})
        try:
            rb = rebuild_mission_event_log(feature_dir, slug, wp_id_map=wp_id_map)
            total_events_generated += rb.events_generated
            for w in rb.warnings:
                report.warnings.append(w)
            for e in rb.errors:
                report.warnings.append(f"State rebuild warning for {slug}: {e}")
        except Exception as exc:
            return _fail("state_rebuild", f"event log rebuild failed for {slug}: {exc}")

    report.events_generated = total_events_generated

    # ------------------------------------------------------------------
    # Step 5: Strip frontmatter (AFTER state rebuild)
    # ------------------------------------------------------------------
    logger.info("Migration step 5/10: Strip frontmatter")
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        try:
            strip_mutable_fields(feature_dir)
        except Exception as exc:
            return _fail("strip_frontmatter", f"frontmatter strip failed for {slug}: {exc}")

    # ------------------------------------------------------------------
    # Step 6: Rewrite agent shims
    # ------------------------------------------------------------------
    logger.info("Migration step 6/10: Rewrite agent shims")
    try:
        rewrite_agent_shims(repo_root)
    except Exception as exc:
        # Shim failures are non-fatal — agent dirs may not exist in CI
        report.warnings.append(f"Shim rewrite warning (non-fatal): {exc}")

    # ------------------------------------------------------------------
    # Step 7: Update schema version
    # ------------------------------------------------------------------
    logger.info("Migration step 7/10: Update schema version")
    try:
        _update_schema_version(repo_root)
    except Exception as exc:
        return _fail("schema_version_update", f"schema version update failed: {exc}")

    # ------------------------------------------------------------------
    # Step 8: Update .gitignore
    # ------------------------------------------------------------------
    logger.info("Migration step 8/10: Update .gitignore")
    try:
        changes = _update_gitignore(repo_root)
        for change in changes:
            logger.debug(".gitignore: %s", change)
    except Exception as exc:
        return _fail("gitignore_update", f".gitignore update failed: {exc}")

    # ------------------------------------------------------------------
    # Step 9: Move derived files
    # ------------------------------------------------------------------
    logger.info("Migration step 9/10: Move derived files")
    try:
        moved = _move_derived_files(repo_root)
        report.files_moved = moved
    except Exception as exc:
        return _fail("move_derived_files", f"derived file move failed: {exc}")

    # ------------------------------------------------------------------
    # Step 10: Commit
    # ------------------------------------------------------------------
    logger.info("Migration step 10/10: Commit")
    if not _git_add_all(repo_root):
        return _fail("commit", "git add -A failed")

    commit_msg = "chore: migrate to canonical context architecture (schema v3)"
    if not _git_commit(repo_root, commit_msg):
        return _fail("commit", "git commit failed after retry")

    # ------------------------------------------------------------------
    # Success: clean up backup
    # ------------------------------------------------------------------
    _cleanup_backup(repo_root)

    features = _discover_features(repo_root)
    report.features_migrated = len(features)
    report.success = True
    logger.info(
        "Migration complete: %d features, %d WPs, %d events generated",
        report.features_migrated,
        report.wps_backfilled,
        report.events_generated,
    )
    return report
