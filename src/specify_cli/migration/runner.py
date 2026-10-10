"""Atomic migration orchestrator for canonical context architecture.

Orchestrates all migration steps in the correct order.  Any failure triggers a
rollback to the pre-migration state via backup restoration.

The runner writes files, rolls back on failure, and never touches git: it does
not stage, commit, or move HEAD or the index.  ``spec-kitty upgrade`` owns the
commit decision (its pre-run baseline, hooks honoured, only on success).

Step order (must be maintained):
  1.  Backup
  2.  Identity backfill (project_uuid, mission_ids, wp_ids)
  3.  Ownership backfill
  4.  State rebuild (event log)
  5.  Strip frontmatter  (AFTER state rebuild)
  6.  Update schema version in metadata.yaml
  7.  Update .gitignore
  8.  Move derived files (status.json → .kittify/derived/)
  9.  Rewrite agent shims (non-fatal; last, so a failure in steps 6-8 never
      leaves rewritten shims outside ``.kittify/``, which the backup does not cover)

Rollback on any failure: restore backup, report which step failed.
"""

from __future__ import annotations

import io
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from kernel.clock import now_utc_iso
from kernel.tree_removal import ToolOwnedPathUnproven, remove_tool_owned_tree
from specify_cli.core.atomic import atomic_write
from specify_cli.migration.schema_version import CURRENT_SCHEMA_VERSION

logger = logging.getLogger(__name__)

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
_KITTY_SPECS_BACKUP = "kitty-specs-backup"
_GITIGNORE_BACKUP = "gitignore-backup"
_GITIGNORE_ABSENT_SENTINEL = "gitignore-absent"
# Entries of the backup directory that are NOT copies of ``.kittify/`` content: they are
# restored to their real homes (``kitty-specs/``, ``.gitignore``) and must never be copied
# back into ``.kittify/`` (#4763).
_BACKUP_SIBLING_ENTRIES = frozenset({_KITTY_SPECS_BACKUP, _GITIGNORE_BACKUP, _GITIGNORE_ABSENT_SENTINEL})


def _create_backup(repo_root: Path) -> Path | None:
    """Back up .kittify/, kitty-specs/, and .gitignore into .kittify/.migration-backup/.

    The migration mutates all three locations, so rollback must cover all of them.
    A missing ``.gitignore`` is recorded with an empty sentinel so rollback removes
    the one the migration creates.  Returns the backup directory path, or None if
    backup failed.
    """
    kittify = repo_root / ".kittify"
    if not kittify.exists():
        return None

    backup_dir = kittify / _BACKUP_DIR_NAME
    # Remove stale backup if present
    if backup_dir.exists():
        try:
            remove_tool_owned_tree(backup_dir, tool_root=backup_dir, reason="stale migration backup")
        except (OSError, ToolOwnedPathUnproven) as exc:
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
            shutil.copytree(kitty_specs, backup_dir / _KITTY_SPECS_BACKUP)

        # 3. Back up .gitignore (migration modifies or creates it)
        gitignore = repo_root / ".gitignore"
        if gitignore.is_file():
            shutil.copy2(gitignore, backup_dir / _GITIGNORE_BACKUP)
        else:
            (backup_dir / _GITIGNORE_ABSENT_SENTINEL).touch()

        logger.info("Backup created at %s (includes kitty-specs/ and .gitignore)", backup_dir)
        return backup_dir
    except OSError as exc:
        logger.error("Failed to create backup: %s", exc)
        return None


def _restore_siblings(repo_root: Path, backup_dir: Path) -> bool:
    """Restore ``kitty-specs/`` and ``.gitignore`` from their backup siblings."""
    ok = True
    kitty_specs_backup = backup_dir / _KITTY_SPECS_BACKUP
    if kitty_specs_backup.is_dir():
        kitty_specs = repo_root / "kitty-specs"
        try:
            if kitty_specs.is_dir():
                # Proof of ownership: kitty-specs/ is replaced by the snapshot taken at the start of this very
                # run (kitty_specs_backup.is_dir() above); a failed copy keeps the backup (ok=False).
                remove_tool_owned_tree(kitty_specs, tool_root=kitty_specs, reason="rollback restore of kitty-specs from this run's backup")
            shutil.copytree(kitty_specs_backup, kitty_specs)
            logger.info("Restored kitty-specs/ from backup")
        except (OSError, ToolOwnedPathUnproven) as exc:
            logger.warning("Could not restore kitty-specs/ during rollback: %s", exc)
            ok = False

    gitignore_backup = backup_dir / _GITIGNORE_BACKUP
    try:
        if gitignore_backup.is_file():
            shutil.copy2(gitignore_backup, repo_root / ".gitignore")
            logger.info("Restored .gitignore from backup")
        elif (backup_dir / _GITIGNORE_ABSENT_SENTINEL).exists():
            # There was no .gitignore before the run: the one present now is ours.
            (repo_root / ".gitignore").unlink(missing_ok=True)
            logger.info("Removed .gitignore created by the migration")
    except OSError as exc:
        logger.warning("Could not restore .gitignore during rollback: %s", exc)
        ok = False
    return ok


def _restore_backup(repo_root: Path, backup_dir: Path) -> bool:
    """Restore .kittify/, kitty-specs/, and .gitignore from backup (used on rollback).

    Returns ``True`` only when every restore operation succeeded; after a partial
    restore the backup is the only copy of what failed to come back, so the caller
    must keep it.
    """
    kittify = repo_root / ".kittify"
    if not backup_dir.exists():
        logger.error("Backup directory %s does not exist — cannot restore", backup_dir)
        return False

    ok = _restore_siblings(repo_root, backup_dir)

    # Remove current .kittify content (except the backup itself)
    for item in kittify.iterdir():
        if item.name == _BACKUP_DIR_NAME:
            continue
        try:
            if item.is_dir():
                remove_tool_owned_tree(item, tool_root=item, reason="rollback restore of .kittify from this run's backup")
            else:
                item.unlink()
        except (OSError, ToolOwnedPathUnproven) as exc:
            logger.warning("Could not remove %s during rollback: %s", item, exc)
            ok = False

    # Restore from backup (the siblings above are not .kittify content)
    for item in backup_dir.iterdir():
        if item.name in _BACKUP_SIBLING_ENTRIES:
            continue
        dest = kittify / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dest)
            else:
                shutil.copy2(item, dest)
        except OSError as exc:
            logger.warning("Could not restore %s during rollback: %s", item, exc)
            ok = False

    if ok:
        logger.info("Rollback complete: .kittify/ restored from backup")
    return ok


def _cleanup_backup(repo_root: Path) -> bool:
    """Remove the backup directory; return ``False`` when it could not be removed."""
    backup_dir = repo_root / ".kittify" / _BACKUP_DIR_NAME
    if backup_dir.exists():
        try:
            remove_tool_owned_tree(backup_dir, tool_root=backup_dir, reason="migration backup cleanup")
            logger.debug("Backup directory removed")
        except (OSError, ToolOwnedPathUnproven) as exc:
            logger.warning("Could not remove backup dir: %s", exc)
            return False
    return True


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
    """Stamp the current schema version and the canonical capability map (#5229).

    Same shape ``init`` stamps: ``CURRENT_SCHEMA_VERSION`` and a
    ``schema_capabilities`` map (absent -> canonical map, legacy list -> map, an
    existing map is the operator's). Every other key survives and the write is
    atomic.

    Raises:
        FileNotFoundError: ``.kittify/metadata.yaml`` does not exist.
        ValueError: the file is not parseable YAML, or ``spec_kitty`` is not a mapping.
    """
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    # Function-local: ``specify_cli.upgrade`` imports the migrations, which import this module.
    from specify_cli.upgrade.metadata import canonical_schema_capabilities

    metadata_path = repo_root / ".kittify" / "metadata.yaml"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata.yaml not found: {metadata_path}")

    y = YAML()
    y.preserve_quotes = True
    y.width = 4096

    try:
        with metadata_path.open("r", encoding="utf-8") as fh:
            data = y.load(fh)
    except YAMLError as exc:
        raise ValueError(f"metadata.yaml is not valid YAML, refusing to rewrite it: {metadata_path}") from exc

    if data is None:
        data = {}

    spec_kitty = data.setdefault("spec_kitty", {})
    if not isinstance(spec_kitty, dict):
        raise ValueError(f"metadata.yaml spec_kitty must be a mapping, refusing to rewrite it: {metadata_path}")
    spec_kitty["schema_version"] = CURRENT_SCHEMA_VERSION
    spec_kitty["schema_capabilities"] = canonical_schema_capabilities(spec_kitty.get("schema_capabilities"))
    spec_kitty["last_upgraded_at"] = now_utc_iso()

    buf = io.StringIO()
    y.dump(data, buf)
    atomic_write(metadata_path, buf.getvalue())

    logger.info("Schema version updated to %d in metadata.yaml", CURRENT_SCHEMA_VERSION)


# ---------------------------------------------------------------------------
# .gitignore update
# ---------------------------------------------------------------------------

_GITIGNORE_ADD_ENTRIES = [
    ".kittify/derived/",
    ".kittify/runtime/",
    ".kittify/.migration-backup/",
]

# Obsolete ignore lines (``.kittify/workspaces/``, ``.kittify/merge-state.json``) are
# deliberately KEPT: removing them un-ignores operator runtime files that a later commit
# would then pick up (same class as m_3_2_6rc3_narrow_cursor_gitignore).


def _update_gitignore(repo_root: Path) -> list[str]:
    """Add new entries to .gitignore (obsolete entries are kept, never removed).

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
# Main orchestrator
# ---------------------------------------------------------------------------


def _settle_failed_backup(repo_root: Path, backup_dir: Path, report: MigrationReport) -> None:
    """Roll back after a failure and remove the backup, but only after a full restore.

    The backup holds copies of everything under ``.kittify/`` (ignored operator files
    included), so it must not outlive a successful rollback.  After a partial restore it
    is the only copy of what failed to come back: keep it and say where it is.
    """
    if _restore_backup(repo_root, backup_dir):
        if not _cleanup_backup(repo_root):
            report.warnings.append(f"Rollback succeeded but the backup at {backup_dir} could not be removed; delete it by hand.")
        return
    report.warnings.append(
        f"Rollback was incomplete: the backup at {backup_dir} holds the pre-migration state; restore from it by hand and then delete it."
    )


def run_migration(repo_root: Path, dry_run: bool = False) -> MigrationReport:  # noqa: C901
    """Orchestrate the full one-shot migration atomically.

    Runs 9 ordered steps.  On any failure the backup is restored and
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
            _settle_failed_backup(repo_root, backup_dir, report)
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
    logger.info("Migration step 1/9: Backup")
    backup_dir = _create_backup(repo_root)
    if backup_dir is None:
        # Non-fatal: proceed without backup but warn loudly
        report.warnings.append("Could not create backup — proceeding without safety net")

    # ------------------------------------------------------------------
    # Step 2: Identity backfill
    # ------------------------------------------------------------------
    logger.info("Migration step 2/9: Identity backfill")
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
    logger.info("Migration step 3/9: Ownership backfill")
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        try:
            backfill_ownership(feature_dir, slug)
        except Exception as exc:
            return _fail("ownership_backfill", f"ownership backfill failed for {slug}: {exc}")

    # ------------------------------------------------------------------
    # Step 4: State rebuild
    # ------------------------------------------------------------------
    logger.info("Migration step 4/9: State rebuild")
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
    logger.info("Migration step 5/9: Strip frontmatter")
    for feature_dir in _discover_features(repo_root):
        slug = feature_dir.name
        try:
            strip_mutable_fields(feature_dir)
        except Exception as exc:
            return _fail("strip_frontmatter", f"frontmatter strip failed for {slug}: {exc}")

    # ------------------------------------------------------------------
    # Step 6: Update schema version
    # ------------------------------------------------------------------
    logger.info("Migration step 6/9: Update schema version")
    try:
        _update_schema_version(repo_root)
    except Exception as exc:
        return _fail("schema_version_update", f"schema version update failed: {exc}")

    # ------------------------------------------------------------------
    # Step 7: Update .gitignore
    # ------------------------------------------------------------------
    logger.info("Migration step 7/9: Update .gitignore")
    try:
        changes = _update_gitignore(repo_root)
        for change in changes:
            logger.debug(".gitignore: %s", change)
    except Exception as exc:
        return _fail("gitignore_update", f".gitignore update failed: {exc}")

    # ------------------------------------------------------------------
    # Step 8: Move derived files
    # ------------------------------------------------------------------
    logger.info("Migration step 8/9: Move derived files")
    try:
        moved = _move_derived_files(repo_root)
        report.files_moved = moved
    except Exception as exc:
        return _fail("move_derived_files", f"derived file move failed: {exc}")

    # ------------------------------------------------------------------
    # Step 9: Rewrite agent shims -- last, so a failure above never leaves rewritten
    # shims behind (the backup covers .kittify/, kitty-specs/ and .gitignore only).
    # ------------------------------------------------------------------
    logger.info("Migration step 9/9: Rewrite agent shims")
    try:
        rewrite_agent_shims(repo_root)
    except Exception as exc:
        # Shim failures are non-fatal — agent dirs may not exist in CI
        report.warnings.append(f"Shim rewrite warning (non-fatal): {exc}")

    # ------------------------------------------------------------------
    # Success: clean up backup
    # ------------------------------------------------------------------
    if not _cleanup_backup(repo_root):
        report.warnings.append(f"Could not remove the migration backup at {repo_root / '.kittify' / _BACKUP_DIR_NAME}; delete it by hand.")

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
