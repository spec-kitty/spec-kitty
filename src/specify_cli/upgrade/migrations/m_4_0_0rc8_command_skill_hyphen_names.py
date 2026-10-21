"""Migration: move command skills from ``spec-kitty.<cmd>`` to ``spec-kitty-<cmd>`` (#6475, FR-005).

Releases before #6475 installed the shared-root command skills as
``.agents/skills/spec-kitty.<cmd>/SKILL.md`` and recorded them in
``.kittify/command-skills-manifest.json``. This migration moves an upgraded
checkout onto the ``spec-kitty-<cmd>`` names by calling the command-skill
installer once per configured command-skill agent. The installer owns the one
legacy rule (FR-020, :meth:`command_installer._CommandBatch.migrate_legacy_entry`
and :meth:`~command_installer._CommandBatch.retire_unrecorded_legacy`): an
unmodified dotted skill is deleted (recorded: its recorded or legacy-rendered
bytes; not recorded: exactly the legacy rendering, operator ruling 2026-10-21),
anything else is kept and no longer managed, and a canonical path occupied by the
user's own content is skipped as a collision. This module only translates the
installer's report into a :class:`MigrationResult`; it deletes nothing itself.
Every dotted path still on disk afterwards is named in a warning and in
``preserved_paths``.

Clone-local (``clone_local_effect = True``, plan A-B2/R-M1): ``.agents/skills/``
is git-ignored, so the dotted files a clone holds are its own and never travel
with a commit. The command-skill manifest *is* committed: a teammate who pulls an
already-migrated manifest no longer has their dotted folders recorded, which is
why the installer recognises an unrecorded exact legacy rendering as Spec Kitty's
(User Story 2, scenario 9). A committed ledger record would settle that teammate's
clone before it migrated; the per-clone record (``.kittify/migrations/``, also
git-ignored) makes every clone migrate itself. ``apply()`` is idempotent: the
second run finds nothing to retire and changes nothing.

An unreadable manifest, an unreadable agent config and any installer refusal are a
success with a warning naming ``spec-kitty doctor skills`` (R-m3): a failed record
would retry and fail every later upgrade, and the upgrade's surface repair re-runs
the same legacy rule. When no command-skill agent is configured nothing is
installed and no directory is created (scenario 5); only entries whose files are
gone are dropped, and the rest are named in a warning.
"""

from __future__ import annotations

import os
from pathlib import Path

from specify_cli.core.agent_config import AgentConfigError, get_configured_agents
from specify_cli.skills import command_installer, manifest_store
from specify_cli.skills.command_installer import (
    CANONICAL_COMMANDS,
    InstallReport,
    InstallerError,
    is_legacy_rel_path,
    unrecorded_legacy_warning as unrecorded_legacy_warning,
)
from specify_cli.skills.command_skill_names import legacy_command_skill_rel_path
from specify_cli.skills.manifest_errors import ManifestError
from specify_cli.skills.manifest_store import SkillsManifest

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

#: Repair command named by every warning this migration emits.
DOCTOR_SKILLS_COMMAND = "spec-kitty doctor skills"
_MANIFEST_REL = ".kittify/command-skills-manifest.json"
_KITTIFY_DIR = ".kittify"


def manifest_unreadable_warning(detail: str) -> str:
    """Warning for a command-skill manifest that cannot be read (the migration still succeeds)."""
    return f"Command-skill manifest {_MANIFEST_REL} could not be read ({detail}); legacy dotted command skills were left in place — run `{DOCTOR_SKILLS_COMMAND}`"


def unconfigured_legacy_warning(path: str) -> str:
    """Warning for a recorded legacy dotted skill when no command-skill agent is configured."""
    return f"Legacy dotted command skill {path} is still recorded but no command-skill agent is configured; it was left in place — run `{DOCTOR_SKILLS_COMMAND}`"


def install_refused_warning(agent: str, detail: str) -> str:
    """Warning for an installer refusal (the migration still succeeds; the surface repair retries)."""
    return f"Command-skill install for {agent} was refused ({detail}); legacy dotted command skills were left in place — run `{DOCTOR_SKILLS_COMMAND}`"


def agent_config_warning(detail: str) -> str:
    """Warning for an agent config that cannot be read (the migration still succeeds)."""
    return f"Agent config could not be read ({detail}); legacy dotted command skills were left in place — run `{DOCTOR_SKILLS_COMMAND}`"


def _legacy_entries(manifest: SkillsManifest) -> list[str]:
    return [entry.path for entry in manifest.entries if is_legacy_rel_path(entry.path)]


def _legacy_folders_on_disk(project_path: Path) -> list[str]:
    """Dotted folders of the canonical commands present on disk (explicit set only, never a prefix)."""
    folders: list[str] = []
    for command in CANONICAL_COMMANDS:
        rel = legacy_command_skill_rel_path(command)
        if os.path.lexists((project_path / rel).parent):
            folders.append(rel)
    return folders


def _leftover_path(project_path: Path, rel: str) -> str:
    """The ``SKILL.md`` when it exists, otherwise the folder with a trailing ``/`` (what verify reports)."""
    return rel if os.path.lexists(project_path / rel) else f"{Path(rel).parent.as_posix()}/"


def _warn_leftovers(project_path: Path, result: MigrationResult, *, retiring: tuple[str, ...] = ()) -> MigrationResult:
    """Name every dotted path still on disk (and not being retired) in warnings and ``preserved_paths``."""
    covered = {*result.preserved_paths, *(Path(p).parent.as_posix() + "/" for p in result.preserved_paths)}
    for rel in _legacy_folders_on_disk(project_path):
        if rel in retiring:
            continue
        leftover = _leftover_path(project_path, rel)
        if leftover in covered or rel in covered:
            continue
        result.warnings.append(unrecorded_legacy_warning(leftover))
        result.preserved_paths.append(leftover)
    return result


def _configured_skill_agents(project_path: Path) -> tuple[str, ...]:
    configured = set(get_configured_agents(project_path))
    return tuple(agent for agent in command_installer.SUPPORTED_AGENTS if agent in configured)


@MigrationRegistry.register
class CommandSkillHyphenNamesMigration(BaseMigration):
    """Rename this checkout's command skills to ``spec-kitty-<cmd>`` through the installer's legacy rule."""

    migration_id = "4.0.0rc8_command_skill_hyphen_names"
    description = "Move command skills to their hyphenated spec-kitty-<command> names (#6475)"
    target_version = "4.0.0rc8"
    runs_on_worktrees = True
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:
        """True when this checkout has a legacy manifest entry, a dotted folder, or an unreadable manifest."""
        if not (project_path / _KITTIFY_DIR).is_dir():
            return False
        try:
            manifest = manifest_store.load(project_path)
        except (ManifestError, OSError, UnicodeDecodeError):
            return True  # apply() reports it once with the doctor remedy (R-m3).
        return bool(_legacy_entries(manifest) or _legacy_folders_on_disk(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        try:
            manifest = manifest_store.load(project_path)
        except (ManifestError, OSError, UnicodeDecodeError) as exc:
            return _warn_leftovers(project_path, MigrationResult(success=True, warnings=[manifest_unreadable_warning(str(exc))]))
        try:
            agents = _configured_skill_agents(project_path)
        except AgentConfigError as exc:
            return _warn_leftovers(project_path, MigrationResult(success=True, warnings=[agent_config_warning(str(exc))]))
        if not agents:
            return _warn_leftovers(project_path, self._without_skill_agents(project_path, manifest, _legacy_entries(manifest), dry_run=dry_run))
        if dry_run:
            return self._preview(project_path, agents[0])
        return _warn_leftovers(project_path, self._install(project_path, agents))

    @staticmethod
    def _install(project_path: Path, agents: tuple[str, ...]) -> MigrationResult:
        """Install the canonical batch per agent; the first install retires every legacy skill."""
        result = MigrationResult(success=True)
        for agent in agents:
            try:
                report = command_installer.install(project_path, agent)
            except InstallerError as exc:
                result.warnings.append(install_refused_warning(agent, str(exc)))
                return result
            _merge_report(result, report)
        return result

    @staticmethod
    def _preview(project_path: Path, agent: str) -> MigrationResult:
        """Dry run: prepare the first agent's batch (it carries the whole legacy rule) and write nothing."""
        try:
            report = command_installer.install(project_path, agent, dry_run=True)
        except InstallerError as exc:
            return _warn_leftovers(project_path, MigrationResult(success=True, warnings=[install_refused_warning(agent, str(exc))]))
        result = MigrationResult(success=True, changes_made=[f"Would remove legacy dotted command skill {rel}" for rel in report.legacy_removed])
        result.warnings.extend(command_installer.install_warnings(report))
        result.preserved_paths.extend((*report.collisions, *report.legacy_kept, *report.legacy_unrecorded))
        return _warn_leftovers(project_path, result, retiring=tuple(report.legacy_removed))

    @staticmethod
    def _without_skill_agents(project_path: Path, manifest: SkillsManifest, legacy: list[str], *, dry_run: bool) -> MigrationResult:
        """No command-skill agent: drop entries whose files are gone, name the rest, create nothing."""
        gone = [rel for rel in legacy if not (project_path / rel).exists() and not (project_path / rel).is_symlink()]
        kept = [rel for rel in legacy if rel not in gone]
        prefix = "Would drop" if dry_run else "Dropped"
        result = MigrationResult(
            success=True,
            changes_made=[f"{prefix} manifest entry of absent legacy command skill {rel}" for rel in gone],
            warnings=[unconfigured_legacy_warning(rel) for rel in kept],
            preserved_paths=kept,
        )
        if gone and not dry_run:
            for rel in gone:
                manifest.remove_path(rel)
            manifest_store.save(project_path, manifest)
        return result


def _merge_report(result: MigrationResult, report: InstallReport) -> None:
    """Translate one installer report into migration changes, warnings and preserved paths."""
    result.changes_made.extend(f"Removed legacy dotted command skill {rel}" for rel in report.legacy_removed)
    result.changes_made.extend(f"Installed command skill {rel}" for rel in (*report.added, *report.regenerated))
    result.warnings.extend(warning for warning in command_installer.install_warnings(report) if warning not in result.warnings)
    kept = (*report.collisions, *report.legacy_kept, *report.legacy_unrecorded)
    result.preserved_paths.extend(rel for rel in kept if rel not in result.preserved_paths)
