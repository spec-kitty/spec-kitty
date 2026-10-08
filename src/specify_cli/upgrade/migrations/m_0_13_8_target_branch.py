"""Migration: Add target_branch field to feature metadata.

This migration adds a target_branch field to all feature meta.json files.
The target_branch determines where status commits and implementation work
should be routed:
- "main" for 1.x features (CLI-only features)
- "2.x" for SaaS features (requires 2.x architecture)

This fixes the race condition where Feature 025 (targeting 2.x) was having
its status commits routed to main, causing branch divergence.

Version: 0.13.7 → 0.13.8
Breaking: No
Required: Yes
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Any

from specify_cli.core.paths import MissionMetaReadError, load_meta_fail_closed
from specify_cli.mission_metadata import load_meta, locked_update_meta
from specify_cli.upgrade.feature_meta import infer_target_branch

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


def _add_target_branch(meta: dict[str, Any], target_branch: str) -> bool:
    """Add ``target_branch`` to a fresh *meta* unless it already carries one; report whether it changed."""
    if "target_branch" in meta:
        return False
    meta["target_branch"] = target_branch
    return True


def _is_io_failure(exc: BaseException) -> bool:
    """True when a meta.json read error was caused by an I/O failure, not bad content.

    Keeps the pre-#2479 split: an unreadable file was reported as "Failed to
    update", a malformed one as "Malformed JSON".
    """
    cause = exc.__cause__
    while cause is not None:
        if isinstance(cause, OSError):
            return True
        cause = cause.__cause__
    return False


@MigrationRegistry.register
class TargetBranchMigration(BaseMigration):
    """Add target_branch to all features."""

    migration_id = "0.13.8_target_branch"
    description = "Add target_branch field to feature metadata"
    target_version = "0.13.8"

    def detect(self, project_path: Path) -> bool:
        """Check if any feature is missing target_branch field."""
        kitty_specs = project_path / "kitty-specs"
        if not kitty_specs.exists():
            return False

        for feature_dir in kitty_specs.glob("[0-9][0-9][0-9]-*/"):
            meta_file = feature_dir / "meta.json"
            if not meta_file.exists():
                continue

            # Canonical reader (#2479): a malformed meta.json (syntax error,
            # undecodable bytes, non-object top level) reads as None and is skipped.
            meta = load_meta(feature_dir, on_malformed="none")
            if meta is not None and "target_branch" not in meta:
                # At least one feature missing target_branch
                return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if migration can be applied."""
        kitty_specs = project_path / "kitty-specs"
        if not kitty_specs.exists():
            return True, ""  # No features, nothing to do

        # Migration can always be applied (just adds missing fields)
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Add target_branch to all feature meta.json files."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        kitty_specs = project_path / "kitty-specs"
        if not kitty_specs.exists():
            return MigrationResult(
                success=True,
                changes_made=["No features found, skipping target_branch addition"],
            )

        for feature_dir in kitty_specs.glob("[0-9][0-9][0-9]-*/"):
            meta_file = feature_dir / "meta.json"
            if not meta_file.exists():
                continue

            try:
                # Canonical fail-closed reader (#2479): a malformed meta.json raises
                # MissionMetaReadError, reported per mission below.
                meta = load_meta_fail_closed(feature_dir)
                if meta is None:  # vanished between the exists() check and the read
                    continue

                # Skip if already has target_branch
                if "target_branch" in meta:
                    continue

                target_branch = infer_target_branch(feature_dir, project_path)
                if target_branch != "main":
                    warnings.append(f"{feature_dir.name} auto-detected target_branch={target_branch}")

                if dry_run:
                    changes.append(f"Would add target_branch={target_branch} to {feature_dir.name}")
                else:
                    # Add the field on a fresh read under the Mission write lock; a target_branch a
                    # concurrent writer recorded meanwhile is kept.
                    locked_update_meta(
                        feature_dir,
                        partial(_add_target_branch, target_branch=target_branch),
                        validate=False,
                        fallback_to_dir_name=True,
                    )
                    changes.append(f"Added target_branch={target_branch} to {feature_dir.name}")

            except MissionMetaReadError as e:
                label = "Failed to update" if _is_io_failure(e) else "Malformed JSON in"
                errors.append(f"{label} {feature_dir.name}/meta.json: {e}")
            except OSError as e:
                errors.append(f"Failed to update {feature_dir.name}/meta.json: {e}")

        success = len(errors) == 0
        return MigrationResult(
            success=success,
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
