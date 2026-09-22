"""Comprehensive charter rename: migrate all constitution-era state.

This migration subsumes the 5 old constitution-related migrations (now stubs)
and handles all 3 legacy layouts, rewrites generated content, updates agent
prompts, and normalizes metadata.

NOTE: This file is one of only 2 permitted to contain "constitution" strings
(as path literals for detecting old state). The other is metadata.py
(_LEGACY_MIGRATION_ID_MAP backward-compatibility lookup keys).
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from specify_cli.asset_preservation import (
    AnyProver,
    CanonicalContentProver,
    ManagedPathProver,
    guard_destructive_removal,
)
from specify_cli.runtime.generated_writer import write_generated_file

from ..metadata import ProjectMetadata, _LEGACY_MIGRATION_ID_MAP
from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from .m_0_9_1_complete_lane_migration import get_agent_dirs_for_project

# File extensions to scan for content rewriting
_TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".txt"}

# Regex for case-preserving replacement of "constitution" -> "charter"
_CONSTITUTION_RE = re.compile(r"constitution", re.IGNORECASE)


def _replace_constitution(match: re.Match[str]) -> str:
    """Case-preserving replacement: constitution->charter, Constitution->Charter."""
    word = match.group(0)
    if word[0].isupper():
        return "Charter"
    return "charter"


@MigrationRegistry.register
class CharterRenameMigration(BaseMigration):
    """Comprehensive charter rename: migrate all constitution-era state."""

    migration_id = "3.1.1_charter_rename"
    description = "Comprehensive charter rename: migrate all constitution-era state"
    target_version = "3.1.1"

    def detect(self, project_path: Path) -> bool:
        """Detect any of the 3 legacy layouts or stale agent artifacts."""
        kittify = project_path / ".kittify"

        # Layout A: modern constitution directory
        if (kittify / "constitution").exists():
            return True

        # Layout B: legacy memory path
        if (kittify / "memory" / "constitution.md").exists():
            return True

        # Layout C: very old mission-specific constitutions
        missions = kittify / "missions"
        if missions.exists():
            for m in missions.iterdir():
                if m.is_dir() and (m / "constitution").exists():
                    return True

        # Agent artifacts: old command files or skill dirs
        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.exists():
                continue
            if (agent_dir / "spec-kitty.constitution.md").exists():
                return True

        # Agent skills: old constitution-doctrine skill dirs
        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            skills_dir = project_path / agent_root / "skills"
            if skills_dir.exists() and (skills_dir / "spec-kitty-constitution-doctrine").exists():
                return True

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        """Check if migration can be applied."""
        if not self.detect(project_path):
            return False, "No constitution-era state found"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply all 4 phases of the charter rename migration."""
        changes: list[str] = []
        errors: list[str] = []
        warnings: list[str] = []
        kittify = project_path / ".kittify"
        charter_dir = kittify / "charter"

        # Phase 1: Layout normalization
        self._normalize_layouts(kittify, charter_dir, dry_run, changes, errors, warnings)

        # Phase 2: Content rewriting
        self._rewrite_content(project_path, charter_dir, dry_run, changes, errors, warnings)

        # Phase 3: Agent artifact rename
        self._rename_agent_artifacts(project_path, dry_run, changes, errors, warnings)

        # Phase 4: Metadata normalization
        self._normalize_metadata(kittify, dry_run, changes, errors, warnings)

        if errors:
            return MigrationResult(
                success=False,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )
        return MigrationResult(success=True, changes_made=changes, warnings=warnings)

    # ------------------------------------------------------------------
    # Phase 1: Layout normalization
    # ------------------------------------------------------------------

    def _normalize_layouts(
        self,
        kittify: Path,
        charter_dir: Path,
        dry_run: bool,
        changes: list[str],
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Normalize all 3 legacy layouts to .kittify/charter/."""
        constitution_dir = kittify / "constitution"
        memory_constitution = kittify / "memory" / "constitution.md"
        missions_dir = kittify / "missions"

        project_path = kittify.parent
        # Archive doomed governance content OUTSIDE the tree being torn down
        # (contract C1.4). ``.kittify/.backup-<ts>/`` is a sibling of every
        # doomed location below, so it survives the removals.
        backup_parent = kittify
        # Governance payloads (constitution/charter files) carry no package
        # version marker and no shipped canonical, so this composite prover
        # returns None for them => preserve-always (NFR-006). A governance file
        # that DID carry the version marker would be proven-owned and removed
        # (the owned-delete anchor).
        governance_prover = AnyProver([CanonicalContentProver(), ManagedPathProver()])

        # Layout C: Remove mission-specific constitution directories
        if missions_dir.exists():
            for mission_dir in sorted(missions_dir.iterdir()):
                if not mission_dir.is_dir():
                    continue
                mission_constitution = mission_dir / "constitution"
                if not mission_constitution.exists():
                    continue
                if dry_run:
                    changes.append(f"Would remove {mission_dir.name}/constitution/")
                else:
                    # Ownership proof (NFR-006): a mission-specific constitution
                    # dir carries no version marker / shipped canonical, so the
                    # governance prover returns None => preserve. The guard
                    # archives its bytes to an external backup and then removes
                    # the legacy dir, so the content stays recoverable (B1).
                    # governance_prover can never prove a markerless governance
                    # target owned -- this is always archive-then-remove, never
                    # prove-then-delete; safe-by-construction (over-preserve).
                    try:
                        verdict = guard_destructive_removal(
                            mission_constitution,
                            project_path,
                            prover=governance_prover,
                            is_tree=True,
                            backup_parent=backup_parent,
                        )
                        if verdict.owned:
                            changes.append(f"Removed mission-specific: {mission_dir.name}/constitution/")
                        else:
                            warnings.append(verdict.diagnostic)
                    except OSError as e:
                        errors.append(f"Failed to remove {mission_dir.name}/constitution/: {e}")

        # Layout B: Move memory/constitution.md -> charter/charter.md
        if memory_constitution.exists():
            if charter_dir.exists() and (charter_dir / "charter.md").exists():
                # Stale Layout B: charter.md already exists, remove stale memory file
                if dry_run:
                    changes.append("Would remove stale .kittify/memory/constitution.md")
                else:
                    # Ownership proof (NFR-006): a stale memory/constitution.md
                    # carries no version marker / shipped canonical => the
                    # governance prover returns None => preserve. The guard
                    # archives it to an external backup before removing the
                    # original (B1).
                    # governance_prover can never prove a markerless governance
                    # target owned -- this is always archive-then-remove, never
                    # prove-then-delete; safe-by-construction (over-preserve).
                    try:
                        verdict = guard_destructive_removal(
                            memory_constitution,
                            project_path,
                            prover=governance_prover,
                            is_tree=False,
                            backup_parent=backup_parent,
                        )
                        if verdict.owned:
                            changes.append("Removed stale .kittify/memory/constitution.md")
                        else:
                            warnings.append(verdict.diagnostic)
                    except OSError as e:
                        errors.append(f"Failed to remove stale memory/constitution.md: {e}")
            else:
                # Move to charter dir
                if dry_run:
                    changes.append("Would move .kittify/memory/constitution.md -> .kittify/charter/charter.md")
                else:
                    try:
                        charter_dir.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(memory_constitution), str(charter_dir / "charter.md"))
                        changes.append("Moved .kittify/memory/constitution.md -> .kittify/charter/charter.md")
                    except OSError as e:
                        errors.append(f"Failed to move memory/constitution.md: {e}")

        # Layout A: Rename constitution/ -> charter/
        if constitution_dir.exists():
            if charter_dir.exists():
                # Partial state: both exist, merge non-conflicting files
                if dry_run:
                    changes.append("Would merge .kittify/constitution/ into .kittify/charter/")
                else:
                    try:
                        for item in sorted(constitution_dir.iterdir()):
                            dest = charter_dir / item.name
                            if not dest.exists():
                                shutil.move(str(item), str(dest))
                                changes.append(f"Merged {item.name} from constitution/ to charter/")
                            else:
                                # #4862: a same-named file already in charter/
                                # used to be destroyed by the residual rmtree
                                # below. Ownership proof (NFR-006): governance
                                # payloads carry no version marker / shipped
                                # canonical, so the governance prover returns
                                # None => preserve. The guard archives the
                                # colliding file to an external backup (outside
                                # constitution_dir) before the residual dir is
                                # removed; a marker-bearing owned file is removed
                                # directly instead.
                                # governance_prover can never prove a markerless
                                # governance target owned -- this is always
                                # archive-then-remove, never prove-then-delete;
                                # safe-by-construction (over-preserve).
                                verdict = guard_destructive_removal(
                                    item,
                                    project_path,
                                    prover=governance_prover,
                                    is_tree=item.is_dir(),
                                    backup_parent=backup_parent,
                                )
                                warnings.append(verdict.diagnostic)
                        # Colliding items were archived-out (or removed when
                        # owned) and merged items moved, so the residual dir is
                        # now empty; remove it with an empty-only rmdir — never a
                        # raw rmtree that could destroy an unproven file.
                        constitution_dir.rmdir()
                        changes.append("Removed residual .kittify/constitution/ after merge")
                    except OSError as e:
                        errors.append(f"Failed to merge constitution/ into charter/: {e}")
            else:
                # Simple rename
                if dry_run:
                    changes.append("Would rename .kittify/constitution/ -> .kittify/charter/")
                else:
                    try:
                        shutil.move(str(constitution_dir), str(charter_dir))
                        changes.append("Renamed .kittify/constitution/ -> .kittify/charter/")
                    except OSError as e:
                        errors.append(f"Failed to rename constitution/ -> charter/: {e}")

        # Rename constitution.md -> charter.md inside charter dir (if it exists)
        if charter_dir.exists():
            old_md = charter_dir / "constitution.md"
            new_md = charter_dir / "charter.md"
            if old_md.exists() and not new_md.exists():
                if dry_run:
                    changes.append("Would rename charter/constitution.md -> charter/charter.md")
                else:
                    try:
                        shutil.move(str(old_md), str(new_md))
                        changes.append("Renamed charter/constitution.md -> charter/charter.md")
                    except OSError as e:
                        errors.append(f"Failed to rename constitution.md -> charter.md: {e}")

    # ------------------------------------------------------------------
    # Phase 2: Content rewriting
    # ------------------------------------------------------------------

    def _rewrite_content(
        self,
        project_path: Path,
        charter_dir: Path,
        dry_run: bool,
        changes: list[str],
        errors: list[str],
        warnings: list[str],  # noqa: ARG002
    ) -> None:
        """Rewrite constitution references in generated files."""
        # Rewrite files under .kittify/charter/
        if charter_dir.exists():
            for file_path in sorted(charter_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                if file_path.suffix not in _TEXT_SUFFIXES:
                    continue
                self._rewrite_file(file_path, project_path, dry_run, changes, errors)

        # Rewrite deployed agent prompt files (generation-layer read-only)
        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            agent_dir = project_path / agent_root / subdir
            if not agent_dir.exists():
                continue
            for file_path in sorted(agent_dir.glob("spec-kitty.*.md")):
                if not file_path.is_file():
                    continue
                self._rewrite_file(file_path, project_path, dry_run, changes, errors, read_only=True)

    def _rewrite_file(
        self,
        file_path: Path,
        project_path: Path,
        dry_run: bool,
        changes: list[str],
        errors: list[str],
        *,
        read_only: bool = False,
    ) -> None:
        """Rewrite a single file, replacing constitution -> charter (case-preserving).

        ``read_only`` must be ``True`` for targets the generation layer marks
        read-only after writing (deployed agent command/skill files) so a
        re-write does not raise ``PermissionError`` on a previously-generated
        file (#3651) and the file is left in the same managed, read-only
        state afterward. ``.kittify/charter/`` content is a plain project
        artifact and stays writable (the default).
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            errors.append(f"Failed to read {file_path.relative_to(project_path)}: {e}")
            return

        updated = _CONSTITUTION_RE.sub(_replace_constitution, content)
        if updated == content:
            return

        rel = str(file_path.relative_to(project_path))
        if dry_run:
            changes.append(f"Would rewrite content in {rel}")
        else:
            try:
                write_generated_file(file_path, updated, read_only=read_only)
                changes.append(f"Rewrote content in {rel}")
            except OSError as e:
                errors.append(f"Failed to write {rel}: {e}")

    # ------------------------------------------------------------------
    # Phase 3: Agent artifact rename
    # ------------------------------------------------------------------

    def _rename_agent_artifacts(
        self,
        project_path: Path,
        dry_run: bool,
        changes: list[str],
        errors: list[str],
        warnings: list[str],  # noqa: ARG002
    ) -> None:
        """Rename agent command files and skill directories."""
        for agent_root, subdir in get_agent_dirs_for_project(project_path):
            # Rename spec-kitty.constitution.md -> spec-kitty.charter.md (if command dir exists)
            agent_dir = project_path / agent_root / subdir
            if agent_dir.exists():
                old_cmd = agent_dir / "spec-kitty.constitution.md"
                new_cmd = agent_dir / "spec-kitty.charter.md"
                if old_cmd.exists() and not new_cmd.exists():
                    if dry_run:
                        changes.append(f"Would rename {agent_root}/{subdir}/spec-kitty.constitution.md")
                    else:
                        try:
                            shutil.move(str(old_cmd), str(new_cmd))
                            changes.append(f"Renamed {agent_root}/{subdir}/spec-kitty.constitution.md -> spec-kitty.charter.md")
                            self._rewrite_file(
                                new_cmd,
                                project_path,
                                dry_run=False,
                                changes=changes,
                                errors=errors,
                                read_only=True,
                            )
                        except OSError as e:
                            errors.append(f"Failed to rename {agent_root}/{subdir}/spec-kitty.constitution.md: {e}")

            # Rename skill directories (independent of command dir existence)
            skills_dir = project_path / agent_root / "skills"
            if not skills_dir.exists():
                continue

            old_skill = skills_dir / "spec-kitty-constitution-doctrine"
            new_skill = skills_dir / "spec-kitty-charter-doctrine"
            if old_skill.exists() and not new_skill.exists():
                if dry_run:
                    changes.append(f"Would rename {agent_root}/skills/spec-kitty-constitution-doctrine/")
                else:
                    try:
                        shutil.move(str(old_skill), str(new_skill))
                        changes.append(f"Renamed {agent_root}/skills/spec-kitty-constitution-doctrine/ -> spec-kitty-charter-doctrine/")
                        # Rewrite content inside skill files
                        for file_path in sorted(new_skill.rglob("*")):
                            if file_path.is_file() and file_path.suffix in _TEXT_SUFFIXES:
                                self._rewrite_file(
                                    file_path,
                                    project_path,
                                    dry_run=False,
                                    changes=changes,
                                    errors=errors,
                                    read_only=True,
                                )
                    except OSError as e:
                        errors.append(f"Failed to rename {agent_root}/skills/spec-kitty-constitution-doctrine/: {e}")

    # ------------------------------------------------------------------
    # Phase 4: Metadata normalization
    # ------------------------------------------------------------------

    def _normalize_metadata(
        self,
        kittify: Path,
        dry_run: bool,
        changes: list[str],
        errors: list[str],
        warnings: list[str],  # noqa: ARG002
    ) -> None:
        """Normalize constitution-era migration IDs in metadata."""
        metadata = ProjectMetadata.load(kittify)
        if metadata is None:
            return

        rewritten = False
        for record in metadata.applied_migrations:
            new_id = _LEGACY_MIGRATION_ID_MAP.get(record.id)
            if new_id:
                if dry_run:
                    changes.append(f"Would rewrite metadata ID {record.id} -> {new_id}")
                else:
                    record.id = new_id
                    rewritten = True

        if rewritten:
            try:
                metadata.save(kittify)
                changes.append("Normalized metadata migration IDs")
            except OSError as e:
                errors.append(f"Failed to save normalized metadata: {e}")
