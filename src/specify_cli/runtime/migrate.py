"""Migration from per-project .kittify/ to centralized runtime model.

Classifies per-project files as identical/customized/project-specific
and migrates them accordingly:
- IDENTICAL: removed (byte-identical to the shipped package counterpart)
- SUPERSEDED: differs from the shipped counterpart (a customisation OR an
  outdated default) — routed through the ownership guard, which cannot prove
  ownership of differing bytes and therefore PRESERVES it in place (#4961).
  Removal only ever happens for a byte-identical (proven) counterpart.
- CUSTOMIZED: moved to .kittify/overrides/ (no shipped counterpart at all)
- PROJECT_SPECIFIC: kept in place
- UNKNOWN: kept in place with warning

Every destructive removal routes through
``asset_preservation.guard_destructive_removal`` (charter L463-479): a file is
removed only when a content-hash proof (byte-match to the shipped counterpart)
is produced; any differing or unprovable file is preserved, never deleted.
"""

from __future__ import annotations

import filecmp
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from specify_cli.asset_preservation import (
    CanonicalContentProver,
    guard_destructive_removal,
)
from specify_cli.runtime.home import get_kittify_home, get_package_asset_root


class AssetDisposition(Enum):
    """Classification of a per-project .kittify/ file."""

    IDENTICAL = "identical"  # Remove (byte-identical to shipped counterpart)
    SUPERSEDED = "superseded"  # Differs from shipped counterpart -> preserved in place (#4961)
    CUSTOMIZED = "customized"  # Move to overrides
    PROJECT_SPECIFIC = "project_specific"  # Keep
    UNKNOWN = "unknown"  # Keep + warn


# Paths within .kittify/ that are always project-specific (never shared assets)
PROJECT_SPECIFIC_PATHS = {
    "config.yaml",
    "metadata.yaml",
    "memory",
    "workspaces",
    "logs",
    "overrides",
    "merge-state.json",
}

# Directories within .kittify/ that contain shared assets (may exist in global)
SHARED_ASSET_DIRS = {"templates", "missions", "scripts", "command-templates"}

# Individual files at .kittify/ root that are shared assets
SHARED_ASSET_FILES = {"AGENTS.md"}


def _find_package_counterpart(rel: Path, package_root: Path, mission: str) -> Path | None:
    """Locate the package-bundled counterpart for a project .kittify/ relative path.

    Tries mission-specific path first, then direct path under package root.
    Returns None if no counterpart exists in the package.
    """
    # Try mission-specific path: package_root/{mission}/{rel}
    pkg_path = package_root / mission / str(rel)
    if pkg_path.exists() and pkg_path.is_file():
        return pkg_path

    # Fall back to direct path under package root
    pkg_path = package_root / str(rel)
    if pkg_path.exists() and pkg_path.is_file():
        return pkg_path

    return None


def _resolve_shared_counterpart(
    rel: Path,
    global_home: Path,
    mission: str,
    package_root: Path | None,
) -> Path | None:
    """Locate the shipped counterpart a shared asset is classified against.

    Immutable package-bundled defaults take precedence (``package_root``); when
    no ``package_root`` is supplied this falls back to the mutable global home
    (``~/.kittify/``) for legacy callers. Returns the counterpart path, or
    ``None`` when none exists. This is the single lookup shared by
    :func:`classify_asset` (to decide the disposition) and
    :func:`execute_migration` (to feed the ownership guard's canonical prover),
    so the bytes compared for classification are exactly the bytes proved
    against at the removal site.
    """
    if package_root is not None:
        return _find_package_counterpart(rel, package_root, mission)

    global_path = global_home / "missions" / mission / str(rel)
    if not global_path.exists():
        global_path = global_home / str(rel)
    if global_path.exists() and global_path.is_file():
        return global_path
    return None


def _counterpart_bytes(counterpart: Path | None) -> bytes | None:
    """Read the shipped counterpart bytes for the canonical prover.

    Returns ``None`` (fail-closed toward preservation) when there is no
    counterpart or its bytes cannot be read — a ``None`` canonical means the
    prover cannot match, so the guard preserves the file rather than deleting it.
    """
    if counterpart is None:
        return None
    try:
        return counterpart.read_bytes()
    except OSError:
        return None


def classify_asset(
    local_path: Path,
    global_home: Path,
    project_kittify: Path,
    mission: str = "software-dev",
    package_root: Path | None = None,
) -> AssetDisposition:
    """Classify a per-project .kittify/ file.

    Args:
        local_path: Absolute path to the file inside per-project .kittify/
        global_home: Path to the global ~/.kittify/ directory
        project_kittify: Path to the per-project .kittify/ directory
        mission: Mission name for locating global counterparts
        package_root: Path to package-bundled assets (immutable). When provided,
            shared assets are compared against the package defaults to distinguish
            outdated defaults (SUPERSEDED) from genuine user customizations (CUSTOMIZED).

    Returns:
        AssetDisposition indicating how the file should be handled.
    """
    rel = local_path.relative_to(project_kittify)
    top_level = rel.parts[0] if rel.parts else ""

    # Project-specific paths: always keep
    if top_level in PROJECT_SPECIFIC_PATHS:
        return AssetDisposition.PROJECT_SPECIFIC

    # Shared asset: compare to package defaults (immutable) when available,
    # falling back to global home (mutable) for backwards compatibility.
    if top_level in SHARED_ASSET_DIRS or rel.name in SHARED_ASSET_FILES:
        if not local_path.is_file():
            return AssetDisposition.UNKNOWN

        # When package_root is provided, compare against immutable package defaults
        # to correctly distinguish old defaults from user customizations.
        if package_root is not None:
            pkg_counterpart = _resolve_shared_counterpart(rel, global_home, mission, package_root)
            if pkg_counterpart is not None:
                if filecmp.cmp(str(local_path), str(pkg_counterpart), shallow=False):
                    return AssetDisposition.IDENTICAL
                # File has a package counterpart but differs. It may be an
                # outdated default OR a team customisation — the two are
                # content-indistinguishable, so this SUPERSEDED classification
                # is honest only about "differs"; execute_migration routes it
                # through the ownership guard, which preserves it (#4961).
                return AssetDisposition.SUPERSEDED
            # No package counterpart = genuinely user-created
            return AssetDisposition.CUSTOMIZED

        # Legacy path: compare against global home (mutable ~/.kittify/).
        # This preserves backwards compatibility for callers that don't pass package_root.
        global_path = _resolve_shared_counterpart(rel, global_home, mission, None)
        if global_path is not None:
            if filecmp.cmp(str(local_path), str(global_path), shallow=False):
                return AssetDisposition.IDENTICAL
            return AssetDisposition.CUSTOMIZED

        # No global counterpart found = treat as customized (user-created)
        return AssetDisposition.CUSTOMIZED

    return AssetDisposition.UNKNOWN


@dataclass
class MigrationReport:
    """Report of migration actions taken (or planned in dry-run mode)."""

    removed: list[Path] = field(default_factory=list)  # byte-identical to counterpart -> removed
    superseded: list[Path] = field(default_factory=list)  # differs from counterpart -> PRESERVED in place (#4961)
    moved: list[tuple[Path, Path]] = field(default_factory=list)  # (from, to)
    kept: list[Path] = field(default_factory=list)
    unknown: list[Path] = field(default_factory=list)
    dry_run: bool = False


def _route_shared_removal(
    path: Path,
    project_dir: Path,
    rel: Path,
    *,
    global_home: Path,
    mission: str,
    package_root: Path | None,
    dry_run: bool,
) -> bool:
    """Route an IDENTICAL/SUPERSEDED shared asset through the ownership guard.

    The guard removes the file ONLY when the canonical prover proves ownership —
    i.e. the file byte-matches the shipped counterpart (NFR-004, genuine
    duplicates). A file that differs (a team customisation OR an outdated
    default; the two are content-indistinguishable) is unprovable and is
    PRESERVED in place (``backup_parent=None``), never deleted (#4961).

    The default version-marker branch of ``CanonicalContentProver`` is inert
    here: no ``.kittify/`` shared asset ships that command marker, so ownership
    is decided solely by the byte-match to the counterpart.

    Returns ``True`` when the guard proved ownership (identical -> removed),
    ``False`` when the file was preserved (differs).
    """
    counterpart = _resolve_shared_counterpart(rel, global_home, mission, package_root)
    verdict = guard_destructive_removal(
        path,
        project_dir,
        prover=CanonicalContentProver(canonical=_counterpart_bytes(counterpart)),
        backup_parent=None,
        dry_run=dry_run,
    )
    return bool(verdict.owned)


def execute_migration(
    project_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,  # noqa: ARG001
    mission: str = "software-dev",
) -> MigrationReport:
    """Scan and migrate per-project .kittify/ shared assets.

    Files byte-identical to their shipped counterpart are removed (proven
    package-owned); files that differ (customisations or outdated defaults) are
    PRESERVED in place via the ownership guard (#4961); genuinely user-created
    files (no counterpart) are moved to .kittify/overrides/; project-specific
    files are kept in place.

    Compares shared assets against immutable package-bundled defaults (not the
    mutable ~/.kittify/) to correctly distinguish outdated defaults from genuine
    user customizations during version-skew upgrades.

    Args:
        project_dir: Root of the project containing .kittify/
        dry_run: If True, report what would happen without modifying the filesystem
        verbose: If True, enable verbose output (reserved for CLI layer)
        mission: Mission name for global asset lookup

    Returns:
        MigrationReport with lists of affected files.
    """
    kittify_dir = project_dir / ".kittify"
    global_home = get_kittify_home()
    report = MigrationReport(dry_run=dry_run)

    # Use immutable package-bundled assets as comparison target.
    # This prevents version-skew: ensure_runtime() may have already updated
    # ~/.kittify/ to the new version, making old defaults look "customized".
    try:
        package_root = get_package_asset_root()
    except FileNotFoundError:
        package_root = None

    for path in sorted(kittify_dir.rglob("*")):
        if path.is_dir():
            continue
        disposition = classify_asset(
            path, global_home, kittify_dir,
            mission=mission, package_root=package_root,
        )

        if disposition in (AssetDisposition.IDENTICAL, AssetDisposition.SUPERSEDED):
            rel = path.relative_to(kittify_dir)
            removed = _route_shared_removal(
                path,
                project_dir,
                rel,
                global_home=global_home,
                mission=mission,
                package_root=package_root,
                dry_run=dry_run,
            )
            # The guard is the sole removal authority: a proven byte-identical
            # file is removed; a differing file is preserved in place. Report
            # honestly on the guard's verdict, not the classification.
            if removed:
                report.removed.append(path)
            else:
                report.superseded.append(path)
        elif disposition == AssetDisposition.CUSTOMIZED:
            rel = path.relative_to(kittify_dir)
            dest = kittify_dir / "overrides" / rel
            report.moved.append((path, dest))
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                path.rename(dest)
        elif disposition == AssetDisposition.PROJECT_SPECIFIC:
            report.kept.append(path)
        else:
            report.unknown.append(path)

    # Clean up empty directories after removal/move
    if not dry_run:
        _cleanup_empty_dirs(kittify_dir)

    return report


def _cleanup_empty_dirs(kittify_dir: Path) -> None:
    """Remove empty directories within shared asset paths.

    Only removes directories that are children of SHARED_ASSET_DIRS
    or the root-level shared asset dirs themselves if empty.
    Does NOT touch project-specific directories.
    """
    # Walk bottom-up so child dirs are removed before parents
    for dirpath in sorted(kittify_dir.rglob("*"), reverse=True):
        if not dirpath.is_dir():
            continue

        # Only clean up shared asset directories, not project-specific ones
        try:
            rel = dirpath.relative_to(kittify_dir)
        except ValueError:
            continue

        top_level = rel.parts[0] if rel.parts else ""
        if top_level not in SHARED_ASSET_DIRS:
            continue

        # Remove if empty (no files, no subdirs)
        if not any(dirpath.iterdir()):
            dirpath.rmdir()
