"""Migration: tell every clone which agent-folder files git now shows, minus Spec Kitty's own (#7878).

Supersedes ``4.0.0rc9_report_newly_visible_agent_files`` (#7729), which is kept
frozen and listed in ``SUPERSEDED_MIGRATIONS``. That step listed every
untracked, unignored file in the agent folders the rc8 narrowing stopped
ignoring whole, and settled only when it found one. Its ``detect()`` runs before
upgrade's finalizer writes the session-presence files (``.claude/CLAUDE.md``,
``.claude/settings.json`` and the other harnesses' orientation files). With
auto-commit off the first upgrade found nothing and recorded ``skipped``; the
second found the files the first had written, listed them and recorded
``success``, so a second upgrade changed ``.kittify/migrations/clone-local.jsonl``
(NFR-004).

This step lists the same files except those the session-presence writers own
(``session_presence.writers.registry.presence_file_paths``). Those are Spec
Kitty's own output, which the upgrade itself names among the paths it changed;
they are not files the old whole-folder rules hid from the operator. Like its
predecessor it writes nothing, runs after
``4.0.0rc9_exclude_project_local_codex_home`` and leaves a Codex home's own
files out.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git_topology import GitTopologyError, git_toplevel_uncached
from specify_cli.core.git_ops import is_git_repo
from specify_cli.session_presence.writers.registry import presence_file_paths

# The two helpers are private to the superseded module, which is frozen (DIRECTIVE_044), so their behaviour
# cannot drift; reusing them keeps the listing identical to the shipped step's apart from the presence filter.
from specify_cli.upgrade.migrations.m_4_0_0rc9_report_newly_visible_agent_files import (
    _visibility_warning,
    _visible_agent_files,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc9_report_exposed_agent_files"


def _presence_paths_from_root(project_path: Path) -> frozenset[str]:
    """The session-presence files as repository-root paths (project-relative when the root is unknown)."""
    try:
        prefix = project_path.resolve().relative_to(git_toplevel_uncached(project_path)).as_posix()
    except (GitTopologyError, OSError, ValueError):
        prefix = "."
    paths = presence_file_paths()
    return frozenset(paths if prefix == "." else (f"{prefix}/{path}" for path in paths))


def exposed_agent_files(project_path: Path) -> list[str]:
    """Untracked, unignored agent-folder files git shows, less a Codex home's and Spec Kitty's session-presence files."""
    visible = _visible_agent_files(project_path)
    if not visible:
        return []
    own = _presence_paths_from_root(project_path)
    return [path for path in visible if path not in own]


@MigrationRegistry.register
class ReportExposedAgentFilesMigration(BaseMigration):
    """List, once per clone, the operator's untracked files git now shows in agent folders (#7729, #7878)."""

    migration_id = MIGRATION_ID
    description = "List the untracked files git now shows in agent folders, leaving Spec Kitty's own out, once in every clone (#7878)"
    target_version = "4.0.0rc9"
    clone_local_effect = True  # a per-clone notice; nothing committed
    #: Its behaviour is this module, the frozen helpers it reuses, and the session-presence modules that say
    #: which files the writers own (the registry, each writer class's module and the Claude Code hook path),
    #: so a change to any of them shows as drift (audit-only).
    content_hash_sources = (
        "m_4_0_0rc9_report_exposed_agent_files.py",
        "m_4_0_0rc9_report_newly_visible_agent_files.py",
        "../../session_presence/writers/registry.py",
        "../../session_presence/writers/markdown_rules.py",
        "../../session_presence/writers/agents_md.py",
        "../../session_presence/writers/skills_preamble.py",
        "../../session_presence/writers/claude_code.py",
        "../../session_presence/writers/null_writer.py",
        "../../session_presence/hooks/claude_code_hook.py",
    )

    def detect(self, project_path: Path) -> bool:
        """Whether git shows untracked files of the operator's own in an agent folder of this clone."""
        return is_git_repo(project_path) and bool(exposed_agent_files(project_path))

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not is_git_repo(project_path):
            return False, "Not a git repository"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        if not is_git_repo(project_path):
            return MigrationResult(success=True, changes_made=["Skipped: not a git repository"])
        warning = _visibility_warning(exposed_agent_files(project_path))
        if warning is None:
            return MigrationResult(success=True, changes_made=["No untracked files in agent folders"])
        verb = "Would list" if dry_run else "Listed"
        return MigrationResult(
            success=True,
            changes_made=[f"{verb} the untracked files git shows in agent folders"],
            warnings=[warning],
            manual_review_required=True,
        )
