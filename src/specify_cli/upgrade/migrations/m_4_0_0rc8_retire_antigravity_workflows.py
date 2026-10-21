"""Migration: archive Antigravity's dead ``.agent/workflows`` command files (#6470, FR-010).

Google Antigravity stopped reading ``.agent/workflows`` on 2026-10-19 and reads
command skills from the shared ``.agents/skills/`` root, so Antigravity is now a
command-skill agent (``skills._agent_roster``). Projects that ran Spec Kitty
before 3.1.2 (when command files were written into the project) can still hold
Spec Kitty's ``spec-kitty.<cmd>.md`` files there. This migration moves those
files into ``.kittify/backups/antigravity-workflows/`` and installs the command
skills for Antigravity.

**Archive, never delete** (operator ruling 2026-10-20). A file is Spec Kitty's
only when all three proofs hold (plan R-M2):

* it is a regular file (``lstat``; never a symlink),
* its name is ``spec-kitty.<cmd>.md`` with ``<cmd>`` in :data:`HISTORICAL_COMMANDS`,
* one of its first 20 lines is exactly ``<!-- spec-kitty-command-version: X -->``
  (the marker every Spec Kitty command render writes, see
  ``runtime.agent_commands._VERSION_MARKER_LINE``).

A proven file is copied verbatim into a fresh, collision-safe timestamped folder
(``.backup-<stamp>[-n]/.agent/workflows/<name>``, never overwriting an earlier
backup) and only then removed, through the one asset-preservation guard
(``guard_destructive_removal`` with ``backup_parent``). An edited Spec Kitty file
is archived too, so the edit survives in the backup. Anything else in the
directory is kept; a ``spec-kitty.*`` name that fails a proof is kept and named
in a warning. The ``.agent/workflows`` and ``.agent`` directories are never
removed (``.agent/skills/`` still lives there).

**Refusals** (plan R-M4): when ``.agent`` or ``.agent/workflows`` is a symlink
(so it could resolve outside the project) or not a directory, nothing is changed
and a warning is emitted. The same holds for ``.kittify``, ``.kittify/backups`` and
the archive folder, so a backup can never be written outside the project. Each
component is checked from the project root down, so with no link on the path
nothing can resolve outside the project.

**Gate and C-003 deviation.** C-003 asks migrations to iterate
``get_agent_dirs_for_project()``. ``.agent/workflows`` is no longer in
``AGENT_DIRS`` (that is the point of #6470), so this migration gates on
``"antigravity" in get_configured_agents(project_path)`` and the hard-coded
retired path instead. A project without ``.kittify/config.yaml`` (or with an
empty agent list) is a legacy project: it is processed whenever
``.agent/workflows`` exists, mirroring ``get_agent_dirs_for_project``'s own
all-agents fallback. No directory under ``.agent`` is ever created.

**Command skills.** When Antigravity is configured the migration calls
``command_installer.install(project, "antigravity")`` (as the
``4.0.0rc8_command_skill_hyphen_names`` migration does for every command-skill
agent). The upgrade's surface repair (``upgrade.assessment.prepare_upgrade_repairs``)
also installs them, because Antigravity is now in ``SUPPORTED_AGENTS``; the
migration does it itself so the archive and the replacement land in the same
step. An installer refusal is a success with a warning naming
``spec-kitty doctor skills``: a failed record would block every later upgrade,
and the surface repair retries.

**Clone-local** (``clone_local_effect = True``). ``.agent/`` is listed among the
agent folders init suggests ignoring, so in most projects these files are
untracked and each clone holds its own copy: a committed ledger record from one
clone would settle every other clone before it archived its own stale files.
Where a project does track them, the archive is a working-tree change that
travels with the next commit; a teammate's clone then finds nothing to archive,
and ``apply()`` is a no-op. The per-clone record is right in both cases and
``apply()`` is idempotent (a second run finds no proven file).
"""

from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass, field
from pathlib import Path

from specify_cli.asset_preservation import guard_destructive_removal
from specify_cli.core.agent_config import AgentConfigError, get_configured_agents
from specify_cli.skills import command_installer
from specify_cli.skills.command_installer import InstallerError
from specify_cli.tool_surface.operations import OwnershipProof

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

ANTIGRAVITY = "antigravity"
#: The retired project surface (no longer in ``AGENT_DIRS``).
WORKFLOWS_REL = ".agent/workflows"
_AGENT_REL = ".agent"
#: Where proven files are archived (operator ruling 2026-10-20).
ARCHIVE_REL = ".kittify/backups/antigravity-workflows"
_ARCHIVE_PARENTS = (".kittify", ".kittify/backups", ARCHIVE_REL)
_CONFIG_REL = ".kittify/config.yaml"
DOCTOR_SKILLS_COMMAND = "spec-kitty doctor skills"
_FILE_PREFIX = "spec-kitty."
_FILE_SUFFIX = ".md"
_MARKER_HEAD_LINES = 20
#: The exact marker line (whole line, nothing else on it).
_MARKER_LINE = re.compile(r"<!-- spec-kitty-command-version: \S+ -->")

#: Every command Spec Kitty ever wrote as a ``spec-kitty.<cmd>.md`` file, frozen.
#:
#: Sources: the 14 consumer commands of ``shims/registry.CONSUMER_SKILLS``; the
#: retired ``checklist`` (``m_2_1_4_enforce_command_file_state``), ``clarify``
#: (``m_2_0_11_remove_clarify_command``), ``constitution`` (renamed to
#: ``charter`` by ``m_3_1_1_charter_rename``), ``dashboard``
#: (``m_4_0_0rc5_retire_bundled_dashboard``), ``profile-context``
#: (``m_3_2_0rc43_retire_profile_context_command``) and ``merge`` (the command
#: ``consolidate`` replaced). The name is one proof of three, never sufficient.
HISTORICAL_COMMANDS: frozenset[str] = frozenset(
    {
        "accept",
        "analyze",
        "charter",
        "consolidate",
        "implement",
        "plan",
        "research",
        "review",
        "specify",
        "status",
        "tasks",
        "tasks-finalize",
        "tasks-outline",
        "tasks-packages",
        "checklist",
        "clarify",
        "constitution",
        "dashboard",
        "merge",
        "profile-context",
    }
)


def refused_warning(rel: str, why: str) -> str:
    """Warning for a refused archive (nothing was changed)."""
    return f"Antigravity workflow cleanup skipped: {rel} {why}; nothing was changed"


def kept_warning(rel: str) -> str:
    """Warning for a ``spec-kitty.*`` workflow file that is not provably Spec Kitty's."""
    return (
        f"Kept {rel}: not provably generated by Spec Kitty (needs a known command name, a regular file and the exact "
        "version-marker line); Antigravity no longer reads .agent/workflows — review and remove it yourself"
    )


def install_refused_warning(detail: str) -> str:
    """Warning for an installer refusal (the migration still succeeds; the surface repair retries)."""
    return f"Command-skill install for {ANTIGRAVITY} was refused ({detail}) — run `{DOCTOR_SKILLS_COMMAND}`"


def agent_config_warning(detail: str) -> str:
    """Warning for an agent config that cannot be read (the migration still succeeds)."""
    return f"Agent config could not be read ({detail}); Antigravity workflow files were left in place"


def command_of(name: str) -> str | None:
    """Return ``<cmd>`` for a ``spec-kitty.<cmd>.md`` name of a historical command, else ``None``."""
    if not (name.startswith(_FILE_PREFIX) and name.endswith(_FILE_SUFFIX)):
        return None
    command = name[len(_FILE_PREFIX) : -len(_FILE_SUFFIX)]
    return command if command in HISTORICAL_COMMANDS else None


def has_marker_line(path: Path) -> bool:
    """True when one of the first 20 lines of *path* is exactly the version-marker line."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as stream:
            for _ in range(_MARKER_HEAD_LINES):
                line = stream.readline()
                if not line:
                    return False
                if _MARKER_LINE.fullmatch(line.rstrip("\r\n")):
                    return True
    except OSError:
        return False
    return False


def is_spec_kitty_workflow(path: Path) -> bool:
    """All three proofs (R-M2): a regular file, a historical command name, the exact marker line."""
    try:
        mode = path.lstat().st_mode
    except OSError:
        return False
    return stat.S_ISREG(mode) and command_of(path.name) is not None and has_marker_line(path)


class _ArchiveBranch:
    """Prover that never proves, so the guard takes its archive-then-remove branch.

    Ownership was already proven by :func:`is_spec_kitty_workflow`; the guard's
    proven branch *deletes*, and the ruling is archive-never-delete. Returning
    ``None`` routes the file through the guard's verbatim archive (fresh
    timestamped folder, ``O_EXCL`` copy) before the guard's own removal.
    """

    def prove(self, path: Path, project_path: Path) -> OwnershipProof | None:  # noqa: ARG002 -- protocol shape; deliberately proves nothing
        return None


def _refusal(project_path: Path) -> str | None:
    """The first refusal warning for the workflow or archive paths (R-M4), else ``None``.

    Every component from the project root down is checked in order, so a link at
    any level is refused before anything beneath it is read; with no link on the
    path, nothing under the project can resolve outside it.
    """
    for rel in (_AGENT_REL, WORKFLOWS_REL, *_ARCHIVE_PARENTS):
        path = project_path / rel
        if path.is_symlink():
            return refused_warning(rel, "is a symlink")
        if os.path.lexists(path) and not path.is_dir():
            return refused_warning(rel, "is not a directory")
    return None


def _candidates(workflows: Path) -> list[Path]:
    """The ``spec-kitty.*`` entries of the workflows directory, sorted (other files are never looked at)."""
    try:
        return sorted(entry for entry in workflows.iterdir() if entry.name.startswith(_FILE_PREFIX))
    except OSError:
        return []


@dataclass
class _Gate:
    """Whether to process the project, and whether Antigravity is configured."""

    process: bool
    configured: bool
    warnings: list[str] = field(default_factory=list)


def _gate(project_path: Path) -> _Gate:
    """Configured antigravity, or a legacy project (no config / empty list) with the workflows dir."""
    workflows_present = os.path.lexists(project_path / WORKFLOWS_REL)
    try:
        agents = get_configured_agents(project_path)
    except AgentConfigError as exc:
        return _Gate(process=False, configured=False, warnings=[agent_config_warning(str(exc))])
    if ANTIGRAVITY in agents:
        return _Gate(process=workflows_present, configured=True)
    legacy = not (project_path / _CONFIG_REL).exists() or not agents
    return _Gate(process=legacy and workflows_present, configured=False)


@MigrationRegistry.register
class RetireAntigravityWorkflowsMigration(BaseMigration):
    """Archive Spec Kitty's ``.agent/workflows`` files and install Antigravity's command skills."""

    migration_id = "4.0.0rc8_retire_antigravity_workflows"
    description = "Archive Antigravity's dead .agent/workflows command files and install its command skills (#6470)"
    target_version = "4.0.0rc8"
    runs_on_worktrees = True
    clone_local_effect = True

    def detect(self, project_path: Path) -> bool:
        """True when a gated project's ``.agent/workflows`` holds a ``spec-kitty.*`` entry (or is unsafe)."""
        gate = _gate(project_path)
        if gate.warnings:
            return True  # apply() reports the unreadable config once.
        if not gate.process:
            return False
        workflows = project_path / WORKFLOWS_REL
        return _refusal(project_path) is not None or bool(_candidates(workflows))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        gate = _gate(project_path)
        result = MigrationResult(success=True, warnings=list(gate.warnings))
        if gate.process:
            self._archive(project_path, result, dry_run=dry_run)
        if gate.configured and not dry_run:
            _install_skills(project_path, result)
        return result

    @staticmethod
    def _archive(project_path: Path, result: MigrationResult, *, dry_run: bool) -> None:
        refusal = _refusal(project_path)
        if refusal is not None:
            result.warnings.append(refusal)
            return
        workflows = project_path / WORKFLOWS_REL
        for path in _candidates(workflows):
            rel = f"{WORKFLOWS_REL}/{path.name}"
            if not is_spec_kitty_workflow(path):
                result.warnings.append(kept_warning(rel))
                result.preserved_paths.append(rel)
                continue
            if dry_run:
                result.changes_made.append(f"Would archive {rel} to {ARCHIVE_REL}/")
                continue
            verdict = guard_destructive_removal(path, project_path, prover=_ArchiveBranch(), backup_parent=project_path / ARCHIVE_REL)
            archived = verdict.backup_path
            if archived is None:  # pragma: no cover - the guard archives every present unproven path
                result.warnings.append(verdict.diagnostic)
                continue
            result.changes_made.append(f"Archived {rel} to {archived.relative_to(project_path).as_posix()}")


def _install_skills(project_path: Path, result: MigrationResult) -> None:
    """Install Antigravity's command skills; a refusal is a warning (the surface repair retries)."""
    try:
        report = command_installer.install(project_path, ANTIGRAVITY)
    except InstallerError as exc:
        result.warnings.append(install_refused_warning(str(exc)))
        return
    result.changes_made.extend(f"Installed command skill {rel}" for rel in (*report.added, *report.regenerated))
    result.warnings.extend(warning for warning in command_installer.install_warnings(report) if warning not in result.warnings)
    kept = (*report.collisions, *report.legacy_kept, *report.legacy_unrecorded)
    result.preserved_paths.extend(rel for rel in kept if rel not in result.preserved_paths)
