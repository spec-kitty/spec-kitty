"""Migration: remove stale standalone governance skill packages."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from specify_cli.asset_preservation import ManifestProver, guard_destructive_removal
from specify_cli.core.config import AGENT_SKILL_CONFIG, SKILL_CLASS_WRAPPER
from specify_cli.skills.retired import RETIRED_STANDALONE_SKILL_NAMES

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


def _project_skill_roots(project_path: Path) -> list[Path]:
    roots: set[Path] = set()
    for config in AGENT_SKILL_CONFIG.values():
        if config["class"] == SKILL_CLASS_WRAPPER:
            continue
        skill_roots = config["skill_roots"]
        if not isinstance(skill_roots, list):
            continue
        for root in skill_roots:
            roots.add(project_path / root.strip("/"))
    return sorted(roots)


def _path_contains_retired_skill(path: str) -> bool:
    return any(part in RETIRED_STANDALONE_SKILL_NAMES for part in Path(path).parts)


def _iter_existing_retired_skill_paths(project_path: Path) -> Iterator[Path]:
    for root in _project_skill_roots(project_path):
        for skill_name in sorted(RETIRED_STANDALONE_SKILL_NAMES):
            dest = root / skill_name
            if dest.exists() or dest.is_symlink():
                yield dest


def _managed_manifest_has_retired_entries(project_path: Path) -> bool:
    from specify_cli.skills.manifest import load_manifest

    manifest = load_manifest(project_path)
    if manifest is None:
        return False
    return any(entry.skill_name in RETIRED_STANDALONE_SKILL_NAMES or _path_contains_retired_skill(entry.installed_path) for entry in manifest.entries)


def _command_manifest_has_retired_entries(project_path: Path) -> bool:
    from specify_cli.skills import manifest_store
    from specify_cli.skills.manifest_errors import ManifestError

    manifest_path = project_path / ".kittify" / "command-skills-manifest.json"
    if not manifest_path.exists():
        return False
    try:
        manifest = manifest_store.load(project_path)
    except ManifestError:
        return False
    return any(_path_contains_retired_skill(entry.path) for entry in manifest.entries)


def _prune_managed_manifest(project_path: Path, *, dry_run: bool) -> tuple[list[str], list[str]]:
    from specify_cli.skills.manifest import load_manifest, save_manifest

    changes: list[str] = []
    errors: list[str] = []
    manifest = load_manifest(project_path)
    if manifest is None:
        return changes, errors

    def _prunable(skill_name: str, installed_path: str) -> bool:
        matches = skill_name in RETIRED_STANDALONE_SKILL_NAMES or _path_contains_retired_skill(installed_path)
        # Preserve-aware pruning (#4859 / T010): keep the entry whenever its file
        # still lives on disk — that is a not-package-owned collision the guard
        # preserved in place; the manifest must not orphan a surviving user file.
        # Prune only when the file is gone: the guard removed a proven-owned skill,
        # or the entry is stale/dangling with no backing file.
        return matches and not (project_path / installed_path).exists()

    removed = [entry.installed_path for entry in manifest.entries if _prunable(entry.skill_name, entry.installed_path)]
    if not removed:
        return changes, errors

    if dry_run:
        changes.extend(f"Would prune retired skill manifest entry {path}" for path in sorted(removed))
        return changes, errors

    manifest.entries = [entry for entry in manifest.entries if not _prunable(entry.skill_name, entry.installed_path)]
    try:
        save_manifest(manifest, project_path)
        changes.extend(f"Pruned retired skill manifest entry {path}" for path in sorted(removed))
    except OSError as exc:
        errors.append(f"Failed to update .kittify/skills-manifest.json: {exc}")
    return changes, errors


def _prune_command_manifest(project_path: Path, *, dry_run: bool) -> tuple[list[str], list[str], list[str]]:
    from specify_cli.skills import manifest_store
    from specify_cli.skills.manifest_errors import ManifestError

    changes: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    manifest_path = project_path / ".kittify" / "command-skills-manifest.json"
    if not manifest_path.exists():
        return changes, warnings, errors

    try:
        manifest = manifest_store.load(project_path)
    except ManifestError as exc:
        warnings.append(f"Could not prune command skills manifest: {exc}")
        return changes, warnings, errors

    def _prunable(entry_path: str) -> bool:
        # Preserve-aware pruning (#4859 / T010): keep the entry when its file
        # survived on disk (a preserved, not-package-owned collision); prune only
        # a gone file (guard removed a proven-owned skill) or a stale entry.
        return _path_contains_retired_skill(entry_path) and not (project_path / entry_path).exists()

    removed = [entry.path for entry in manifest.entries if _prunable(entry.path)]
    if not removed:
        return changes, warnings, errors

    if dry_run:
        changes.extend(f"Would prune retired command skills manifest entry {path}" for path in sorted(removed))
        return changes, warnings, errors

    manifest.entries = [entry for entry in manifest.entries if not _prunable(entry.path)]
    try:
        manifest_store.save(project_path, manifest)
        changes.extend(f"Pruned retired command skills manifest entry {path}" for path in sorted(removed))
    except OSError as exc:
        errors.append(f"Failed to update .kittify/command-skills-manifest.json: {exc}")
    return changes, warnings, errors


@MigrationRegistry.register
class RetireStandaloneSkillSurfaceMigration(BaseMigration):
    """Remove stale standalone governance skill packages from project surfaces."""

    migration_id = "3.2.0rc45_retire_standalone_skill_surface"
    description = "Remove stale standalone governance skill packages"
    target_version = "3.2.0rc45"

    def detect(self, project_path: Path) -> bool:
        return (
            any(_iter_existing_retired_skill_paths(project_path))
            or _managed_manifest_has_retired_entries(project_path)
            or _command_manifest_has_retired_entries(project_path)
        )

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Ownership proof (NFR-006 / charter L479): a retired-basename path is a
        # candidate by NAME only, which is never proof of package ownership. It is
        # removed ONLY when the ManifestProver produces a proof — a managed- or
        # command-skills manifest entry maps to the path AND its recorded
        # content_hash matches the current bytes under copy delivery — i.e. the
        # package demonstrably installed exactly these bytes. Otherwise (unmanifested,
        # or byte-drifted from the recorded hash) ownership is unprovable, so the
        # guard preserves the path in place (its parent skill root survives) and the
        # verdict's diagnostic is surfaced as a warning; nothing is deleted.
        prover = ManifestProver()
        for dest in _iter_existing_retired_skill_paths(project_path):
            rel = str(dest.relative_to(project_path))
            if dry_run:
                changes.append(f"Would remove retired skill surface {rel}")
                continue

            is_tree = dest.is_dir() and not dest.is_symlink()
            try:
                verdict = guard_destructive_removal(dest, project_path, prover=prover, is_tree=is_tree)
            except OSError as exc:
                errors.append(f"Failed to remove {rel}: {exc}")
                continue

            if verdict.owned:
                changes.append(f"Removed retired skill surface {rel}")
            else:
                warnings.append(verdict.diagnostic)

        manifest_changes, manifest_errors = _prune_managed_manifest(project_path, dry_run=dry_run)
        changes.extend(manifest_changes)
        errors.extend(manifest_errors)

        command_changes, command_warnings, command_errors = _prune_command_manifest(
            project_path,
            dry_run=dry_run,
        )
        changes.extend(command_changes)
        warnings.extend(command_warnings)
        errors.extend(command_errors)

        if not changes and not warnings and not errors:
            changes.append("Retired standalone governance skill surfaces absent")

        return MigrationResult(
            success=len(errors) == 0,
            changes_made=changes,
            warnings=warnings,
            errors=errors,
        )
