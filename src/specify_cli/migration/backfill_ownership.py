"""Infer and backfill ownership fields for legacy work packages.

Calls the inference functions from :mod:`specify_cli.ownership.inference`
to derive ``execution_mode``, ``owned_files``, and ``authoritative_surface``
for each WP that does not already have these fields.

Additionally attempts a best-effort git-diff to discover actually-changed
files when the WP has a lane branch in lanes.json.
"""

from __future__ import annotations

import functools
import logging
import re
from pathlib import Path
from typing import Any

from specify_cli.core.vcs.git import git_diff_names
from specify_cli.ownership.inference import (
    infer_authoritative_surface,
    infer_execution_mode,
    infer_owned_files,
)
from specify_cli.ownership.validation import validate_all

logger = logging.getLogger(__name__)


def _git_diff_files(repo_root: Path, base_branch: str, wp_branch: str) -> list[str]:
    """Return file paths changed between *base_branch* and *wp_branch*.

    Returns an empty list on any error (branch not found, git not available).

    Args:
        repo_root: Root directory of the git repository.
        base_branch: The base/target branch (e.g. ``"main"``).
        wp_branch: The WP's lane branch.

    Returns:
        Sorted list of relative file paths touched by the lane branch.
    """
    try:
        files = sorted(git_diff_names(repo_root, base_branch, wp_branch, timeout=10))
        logger.debug("git diff %s..%s: %d files", base_branch, wp_branch, len(files))
        return files
    except Exception as exc:
        logger.debug("git diff failed for branch %s: %s", wp_branch, exc)
    return []


def _apply_absent_fields(frontmatter: dict[str, Any], *, updates: dict[str, Any]) -> bool:
    """Set each of *updates* on *frontmatter* when absent (``scope`` is always set: it is the canonical value); say whether anything changed."""
    changed = False
    for key, value in updates.items():
        if key == "scope" or key not in frontmatter:
            frontmatter[key] = value
            changed = True
    return changed


def backfill_ownership(feature_dir: Path, feature_slug: str) -> None:
    """Infer and write ownership fields for all WPs in *feature_dir*.

    For each ``tasks/WP*.md`` file:

    1. Reads the WP body content.
    2. Optionally gathers actually-changed files via ``git diff`` if the WP
       has a ``base_branch`` and ``wp_branch`` in its frontmatter.
    3. Calls inference functions to derive ``execution_mode``, ``owned_files``,
       and ``authoritative_surface``.
    4. Writes inferred values only when the field is **absent** from frontmatter
       (never overwrites existing values).

    After processing all WPs, runs :func:`~specify_cli.ownership.validation.validate_all`
    and logs any warnings — validation failures do NOT abort the migration.

    Args:
        feature_dir: Path to the feature directory (e.g. ``kitty-specs/057-…``).
        feature_slug: Slug of the feature (e.g. ``"057-canonical-context-architecture-cleanup"``).
    """
    from specify_cli.frontmatter import FrontmatterManager, locked_update_frontmatter

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        logger.debug("No tasks/ directory in %s — skipping ownership backfill", feature_dir.name)
        return

    manager = FrontmatterManager()
    manifests: dict[str, Any] = {}  # wp_code → OwnershipManifest

    # Locate repo root: walk up until we find a .git directory
    repo_root: Path | None = None
    candidate = feature_dir
    for _ in range(10):
        if (candidate / ".git").exists():
            repo_root = candidate
            break
        candidate = candidate.parent

    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            frontmatter, body = manager.read(wp_file)
        except Exception as exc:
            logger.warning("Cannot read %s: %s — skipping ownership backfill", wp_file.name, exc)
            continue

        # Derive wp_code for manifests key
        _m_code = re.match(r"^(WP\d+)", wp_file.stem)
        _wp_code_key = _m_code.group(1) if _m_code else wp_file.stem

        # Skip if all ownership fields already present.
        #
        # ``scope`` is human-authored only (no inference path — see
        # specify_cli.ownership.inference.infer_ownership). It is *scope-aware*
        # here only so the guard does not treat a WP as fully resolved while
        # silently ignoring a human-authored ``scope`` (FR-028): when scope is
        # present it must round-trip through the canonical owner
        # (OwnershipManifest.from_frontmatter) on every write below, never via
        # incidental dict passthrough.
        has_mode = "execution_mode" in frontmatter
        has_files = "owned_files" in frontmatter
        has_surface = "authoritative_surface" in frontmatter
        has_scope = "scope" in frontmatter
        if has_mode and has_files and has_surface:
            logger.debug("Ownership already present for %s — skipping", wp_file.name)
            # Still gather for validation
            try:
                from specify_cli.ownership.models import OwnershipManifest as _OM

                manifests[_wp_code_key] = _OM.from_frontmatter(frontmatter)
            except Exception:
                pass
            continue

        # Full WP content for inference
        full_content = body

        # Best-effort: try to get actually-changed files from the lane branch diff
        git_files: list[str] = []
        if repo_root is not None:
            base_branch = frontmatter.get("base_branch") or frontmatter.get("planning_base_branch") or ""  # MIGRATION-ONLY: raw dict read-mutate-write
            wp_code = frontmatter.get("wp_code", "")  # MIGRATION-ONLY: raw dict read-mutate-write
            if not wp_code:
                m_code = re.match(r"^(WP\d+)", wp_file.stem)
                wp_code = m_code.group(1) if m_code else ""

            if base_branch and wp_code:
                try:
                    from specify_cli.lanes.branch_naming import lane_branch_name
                    from specify_cli.lanes.persistence import read_lanes_json

                    manifest = read_lanes_json(feature_dir)
                    lane = manifest.lane_for_wp(wp_code) if manifest is not None else None
                    if lane is not None and manifest is not None:
                        git_files = _git_diff_files(
                            repo_root,
                            base_branch,
                            lane_branch_name(feature_slug, lane.lane_id, target_branch=manifest.target_branch),
                        )
                except Exception as exc:
                    logger.debug("lane diff inference failed for %s: %s", wp_file.name, exc)

        updates: dict[str, Any] = {}

        if not has_mode:
            mode = infer_execution_mode(full_content, git_files)
            updates["execution_mode"] = str(mode)

        if not has_files:
            owned, _infer_warnings = infer_owned_files(full_content, feature_slug)
            # Prefer git-diff files if available and execution_mode is code_change
            if git_files and updates.get("execution_mode") == "code_change":
                owned = git_files
            updates["owned_files"] = owned

        if not has_surface:
            current_files: list[str] = updates.get("owned_files") or frontmatter.get("owned_files") or []  # MIGRATION-ONLY: raw dict read-mutate-write
            surface = infer_authoritative_surface(current_files)
            updates["authoritative_surface"] = surface

        # FR-028: ``scope`` is human-authored only (never inferred). When the WP
        # already declares a scope, persist it through the canonical owner so the
        # written value is the normalized one (``codebase-wide`` or None) rather
        # than relying on incidental dict passthrough.
        if has_scope:
            from specify_cli.ownership.models import OwnershipManifest as _OMScope

            merged = {**frontmatter, **updates}
            canonical_scope = _OMScope.from_frontmatter(merged).scope
            if canonical_scope is not None:
                updates["scope"] = canonical_scope

        if updates:
            # Re-applied to the frontmatter read under the Mission lock: a field another writer set since
            # the read above is never overwritten ("never overwrites existing values"), ``scope`` aside.
            frontmatter = locked_update_frontmatter(wp_file, functools.partial(_apply_absent_fields, updates=updates), feature_dir=feature_dir)
            logger.info(
                "Backfilled ownership for %s: execution_mode=%s",
                wp_file.name,
                frontmatter.get("execution_mode"),  # MIGRATION-ONLY: raw dict read-mutate-write
            )

        # Gather manifest for cross-WP validation
        try:
            from specify_cli.ownership.models import OwnershipManifest

            manifests[_wp_code_key] = OwnershipManifest.from_frontmatter(frontmatter)
        except Exception as exc:
            logger.debug("Could not build OwnershipManifest for %s: %s", wp_file.name, exc)

    # Cross-WP validation — warnings only, never fail
    if manifests:
        result = validate_all(manifests)
        for warning in result.warnings:
            logger.warning("Ownership validation warning: %s", warning)
        for error in result.errors:
            logger.warning("Ownership validation error (non-fatal): %s", error)
