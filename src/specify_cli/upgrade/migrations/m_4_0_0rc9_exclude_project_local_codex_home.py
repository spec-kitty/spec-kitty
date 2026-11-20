"""Migration: keep a project-local Codex home out of git in every clone (#7729).

``4.0.0rc8_narrow_agent_gitignore`` replaced the whole-folder agent lines with
Spec Kitty's own files. A project whose ``.codex/`` is also a Codex home
(``CODEX_HOME=<project>/.codex``, advice Spec Kitty once gave) then had its
personal Codex state shown as untracked, and only the clone that ran the
upgrade was told.

The committed agent-files block now ignores the Codex home state that is never
team config (``agent_utils.codex_home.CODEX_HOME_STATE_ENTRIES``). What the
block cannot decide is ``.codex/config.toml``: shared config in a plain project
folder, personal config in a Codex home. That is decided here, per clone:

1. When this clone's ``.codex/`` is a Codex home and git shows files from it,
   add ``.codex/`` to the clone's common-dir ``.git/info/exclude`` (never
   committed). Files already committed there stay tracked.
2. Warn about the untracked files git still shows in the agent folders the old
   whole-folder rules hid, so every clone, including one that pulled the
   narrowed ``.gitignore``, reviews them before staging everything.

The effect lives outside version control, so the migration is clone-local: it is
pending in every clone until it runs there. It never deletes, moves or untracks
a file. With nothing to show, ``detect()`` is False and the next upgrade checks
again.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError, status_entries
from specify_cli.agent_utils.codex_home import CODEX_DIR, is_codex_home
from specify_cli.core.git_ops import exclude_from_git_index, is_git_repo
from specify_cli.upgrade.migrations.m_4_0_0rc8_narrow_agent_gitignore import LEGACY_AGENT_ENTRIES

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc9_exclude_project_local_codex_home"

#: Agent folders the rc8 narrowing stopped ignoring whole (derived from its frozen list).
_AGENT_FOLDERS: tuple[str, ...] = tuple(sorted(entry for entry in LEGACY_AGENT_ENTRIES if entry.endswith("/")))

_MAX_LISTED_PATHS = 20


def _visible_agent_files(project_path: Path) -> list[str]:
    """Untracked files git shows (not ignored) inside the project's agent folders.

    Runs no git command when no agent folder exists. A failed git read shows nothing.
    """
    present = [folder for folder in _AGENT_FOLDERS if (project_path / folder).is_dir()]
    if not present:
        return []
    try:
        entries = status_entries(project_path, pathspecs=present, untracked="all", optional_locks=False)
    except (GitCommandError, OSError, ValueError):
        return []
    return sorted(entry.path.as_posix() for entry in entries if entry.xy == "??")


def _needs_codex_exclusion(project_path: Path, visible: list[str]) -> bool:
    return any(path.startswith(CODEX_DIR) for path in visible) and is_codex_home(project_path)


def _visibility_warning(paths: list[str]) -> str | None:
    if not paths:
        return None
    listed = ", ".join(paths[:_MAX_LISTED_PATHS])
    more = f" and {len(paths) - _MAX_LISTED_PATHS} more" if len(paths) > _MAX_LISTED_PATHS else ""
    return (
        f"Spec Kitty no longer ignores whole agent folders (4.0.0rc8), so git shows {len(paths)} untracked file(s) in them: {listed}{more}. "
        "Review them before you stage everything: commit the ones your team shares and add your own ignore rule for the rest."
    )


_EXCLUSION_NOTE = (
    "This clone's .codex/ folder is a Codex home (CODEX_HOME state found), so .codex/ was added to .git/info/exclude "
    "to keep its personal files out of git in this clone only. Files already committed under .codex/ stay tracked; "
    "use 'git add -f' to add a new team file there."
)


@MigrationRegistry.register
class ExcludeProjectLocalCodexHomeMigration(BaseMigration):
    """Exclude a Codex-home ``.codex/`` per clone and list newly visible agent-folder files (#7729)."""

    migration_id = MIGRATION_ID
    description = "Keep a project-local Codex home out of git in every clone and list newly visible agent-folder files (#7729)"
    target_version = "4.0.0rc9"
    clone_local_effect = True  # effect is .git/info/exclude and a per-clone warning, never a committed file

    def detect(self, project_path: Path) -> bool:
        """Whether git shows untracked files inside an agent folder of this clone."""
        return is_git_repo(project_path) and bool(_visible_agent_files(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not is_git_repo(project_path):
            return False, "Not a git repository"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not is_git_repo(project_path):
            return MigrationResult(success=True, changes_made=["Skipped: not a git repository"])

        visible = _visible_agent_files(project_path)
        changes: list[str] = []
        warnings: list[str] = []
        if _needs_codex_exclusion(project_path, visible):
            if dry_run:
                changes.append(f"Would add {CODEX_DIR} to .git/info/exclude (this clone's .codex/ is a Codex home)")
                visible = [path for path in visible if not path.startswith(CODEX_DIR)]
            else:
                exclude_from_git_index(project_path, [CODEX_DIR])
                changes.append(f"Added {CODEX_DIR} to .git/info/exclude (this clone's .codex/ is a Codex home)")
                visible = _visible_agent_files(project_path)
            warnings.append(_EXCLUSION_NOTE)

        visibility = _visibility_warning(visible)
        if visibility:
            warnings.append(visibility)
        if not changes:
            changes.append("No Codex home to exclude in this clone")

        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=warnings,
            manual_review_required=bool(visibility),
        )
