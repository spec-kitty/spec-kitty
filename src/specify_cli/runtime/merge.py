"""Asset merging: populate global runtime from package assets.

Overwrites package-managed directories and files while preserving
user-owned data (config.yaml, missions/custom/, cache/).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import overload

from kernel.tree_removal import remove_tool_owned_tree
from specify_cli.tool_surface.operations import ApplyConsent, OwnerApplyResult, OwnerAssessment

# Directories managed by the package — overwritten on every update.
# NEVER add missions/custom/ here; it is user-owned.
MANAGED_DIRS: list[str] = [
    "missions/software-dev",
    "missions/research",
    "missions/documentation",
    "missions/plan",
    "missions/audit",
    "missions/refactor",
    "scripts",
]

# Individual files managed by the package — overwritten on every update.
MANAGED_FILES: list[str] = [
    "AGENTS.md",
]


@overload
def merge_package_assets(source: Path, dest: Path, *, consent: ApplyConsent = ApplyConsent()) -> None: ...


@overload
def merge_package_assets(source: OwnerAssessment, dest: Path, *, consent: ApplyConsent = ApplyConsent()) -> OwnerApplyResult: ...


def merge_package_assets(source: Path | OwnerAssessment, dest: Path, *, consent: ApplyConsent = ApplyConsent()) -> OwnerApplyResult | None:
    """Overwrite package-managed files only. User files are untouched.

    For each managed directory: if it exists in source, remove the
    corresponding directory in dest (if present) and replace it with the
    source version.  For each managed file: copy from source to dest if
    it exists in source.

    Files/directories NOT listed in MANAGED_DIRS or MANAGED_FILES
    (e.g. config.yaml, missions/custom/) are never touched.

    Args:
        source: Temporary directory with fresh package assets.
        dest: Target ~/.kittify/ directory.
        consent: Explicit authorization when source is a retained assessment.

    A retained assessment uses node-level atomic writes instead of recursive
    replacement, so unchanged files keep their mtimes and custom nodes survive.
    The legacy source-directory signature remains supported unchanged.
    """
    if isinstance(source, OwnerAssessment):
        return _merge_prepared_assets(source, dest, consent)

    for managed_dir in MANAGED_DIRS:
        src = source / managed_dir
        dst = dest / managed_dir
        if src.exists():
            if dst.exists():
                remove_tool_owned_tree(dst, tool_root=dst, reason="package-managed runtime directory replaced on update")
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst)

    for managed_file in MANAGED_FILES:
        src = source / managed_file
        dst = dest / managed_file
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    return None


def _merge_prepared_assets(assessment: OwnerAssessment, destination: Path, consent: ApplyConsent) -> OwnerApplyResult:
    """Keep runtime merge as the writer boundary for retained package bytes."""
    from specify_cli.runtime.asset_preparation import PreparedAssets, _apply_retained_assets, recheck_assets

    prepared = assessment.prepared
    ids = tuple(effect.id for effect in assessment.effects)
    if not isinstance(prepared, PreparedAssets) or assessment.owner_key != "runtime_bootstrap" or prepared.lock_path.parent.parent != destination:
        raise ValueError("Runtime merge requires a retained package assessment for this destination")
    if not assessment.complete or consent.overwrite_paths != assessment.consent.overwrite_paths:
        return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="failed", diagnostics=assessment.diagnostics)
    if not consent.automatic or not ids:
        return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="skipped")
    with recheck_assets(assessment) as diagnostics:
        if diagnostics:
            return OwnerApplyResult(assessment.owner_key, skipped=ids, outcome="precondition_changed", diagnostics=diagnostics)
        return _apply_retained_assets(assessment)
