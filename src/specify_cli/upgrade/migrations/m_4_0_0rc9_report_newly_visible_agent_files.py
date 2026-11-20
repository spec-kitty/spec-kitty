"""Migration: tell every clone which agent-folder files git now shows (#7729).

``4.0.0rc8_narrow_agent_gitignore`` stopped ignoring whole agent folders and
warned about the files that change exposed, but only in the clone that ran it.
A clone that pulled the narrowed ``.gitignore`` was never told, so a later
``git add`` of everything could commit files the old rules had hidden.

This clone-local step runs once in every clone: when git shows untracked files
in the agent folders the old whole-folder rules hid, it lists them as a warning
for review. It writes nothing. It runs after
``4.0.0rc9_exclude_project_local_codex_home``, and a Codex home's own files
are never listed: that step keeps them out of git.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError, status_entries
from specify_cli.agent_utils.codex_home import is_codex_home
from specify_cli.core.git_ops import is_git_repo
from specify_cli.upgrade.migrations.m_4_0_0rc8_narrow_agent_gitignore import LEGACY_AGENT_ENTRIES
from specify_cli.upgrade.migrations.m_4_0_0rc9_exclude_project_local_codex_home import codex_dir_from_root

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc9_report_newly_visible_agent_files"

#: Agent folders the rc8 narrowing stopped ignoring whole (derived from its frozen list).
_AGENT_FOLDERS: tuple[str, ...] = tuple(sorted(entry for entry in LEGACY_AGENT_ENTRIES if entry.endswith("/")))

_MAX_LISTED_PATHS = 20


def _visible_agent_files(project_path: Path) -> list[str]:
    """Untracked, unignored files git shows in the project's agent folders (repository-root paths).

    Runs no git command when no agent folder exists; a failed git read shows nothing.
    A Codex home's files are left out: the sibling exclusion step owns them.
    """
    present = [folder for folder in _AGENT_FOLDERS if (project_path / folder).is_dir()]
    if not present:
        return []
    try:
        entries = status_entries(project_path, pathspecs=present, untracked="all", optional_locks=False)
    except (GitCommandError, OSError, ValueError):
        return []
    paths = sorted(entry.path.as_posix() for entry in entries if entry.xy == "??")
    codex_dir = codex_dir_from_root(project_path) if is_codex_home(project_path) else None
    return [path for path in paths if codex_dir is None or not path.startswith(codex_dir)]


def _visibility_warning(paths: list[str]) -> str | None:
    if not paths:
        return None
    listed = ", ".join(paths[:_MAX_LISTED_PATHS])
    more = f" and {len(paths) - _MAX_LISTED_PATHS} more" if len(paths) > _MAX_LISTED_PATHS else ""
    return (
        f"Spec Kitty no longer ignores whole agent folders (4.0.0rc8), so git shows {len(paths)} untracked file(s) in them: {listed}{more}. "
        "Review them before you stage everything: commit the ones your team shares and add your own ignore rule for the rest."
    )


@MigrationRegistry.register
class ReportNewlyVisibleAgentFilesMigration(BaseMigration):
    """List, once per clone, the untracked files git now shows in agent folders (#7729)."""

    migration_id = MIGRATION_ID
    description = "List the untracked files git now shows in agent folders, once in every clone (#7729)"
    target_version = "4.0.0rc9"
    clone_local_effect = True  # a per-clone notice; nothing committed

    def detect(self, project_path: Path) -> bool:
        """Whether git shows untracked files in an agent folder of this clone."""
        return is_git_repo(project_path) and bool(_visible_agent_files(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not is_git_repo(project_path):
            return False, "Not a git repository"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not is_git_repo(project_path):
            return MigrationResult(success=True, changes_made=["Skipped: not a git repository"])
        warning = _visibility_warning(_visible_agent_files(project_path))
        if warning is None:
            return MigrationResult(success=True, changes_made=["No untracked files in agent folders"])
        verb = "Would list" if dry_run else "Listed"
        return MigrationResult(
            success=True,
            changes_made=[f"{verb} the untracked files git shows in agent folders"],
            warnings=[warning],
            manual_review_required=True,
        )
