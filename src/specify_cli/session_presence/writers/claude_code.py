"""ClaudeCodeWriter — session presence writer for Claude Code.

Extends ``MarkdownRulesWriter`` targeting ``.claude/CLAUDE.md`` (append mode)
and additionally manages the ``SessionStart`` and ``Stop`` hooks in
``.claude/settings.json`` via ``ClaudeCodeHookRegistrar``.

``has_presence()`` returns ``True`` only when **all** artefacts are present:
1. The orientation section in ``.claude/CLAUDE.md``.
2. The ``spec-kitty session-start`` SessionStart entry in ``.claude/settings.json``.
3. The ``spec-kitty session-stop`` Stop entry in ``.claude/settings.json``.

This means the session-presence migration's ``detect()`` triggers a re-write
when any artefact is missing — existing projects pick up the Stop hook on
``spec-kitty upgrade``.

A ``.claude/settings.json`` that git tracks is the team's file: Spec Kitty
never edits it (#6474). The hook entry is then prepared with the ``preserve``
disposition and :func:`committed_settings_notice` tells the operator how to
add the hooks themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from kernel.git import GitCommandError, tracked_paths

from ..content import SessionPresenceContent
from ..hooks.claude_code_hook import (
    SESSION_START_EVENT,
    STOP_EVENT,
    ClaudeCodeHookRegistrar,
)
from .markdown_rules import MarkdownRulesWriter, PreparedPresenceFile, observe_presence_path

__all__ = ["ClaudeCodeWriter", "SESSION_START_CMD", "SESSION_STOP_CMD", "committed_settings_notice"]

SESSION_START_CMD = "spec-kitty session-start"
SESSION_STOP_CMD = "spec-kitty session-stop"
COMMITTED_SETTINGS_REASON = "Committed team settings are never edited"


def _settings_committed(project_root: Path) -> bool:
    """Whether git tracks ``.claude/settings.json`` (outside a repository: never)."""
    settings = ClaudeCodeHookRegistrar().settings_relative_path
    try:
        return bool(tracked_paths(project_root, pathspecs=(settings,)))
    except (GitCommandError, OSError):
        return False


def _hooks_registered(project_root: Path) -> bool:
    start = ClaudeCodeHookRegistrar(SESSION_START_EVENT).is_registered(project_root, SESSION_START_CMD)
    stop = ClaudeCodeHookRegistrar(STOP_EVENT).is_registered(project_root, SESSION_STOP_CMD)
    return bool(start and stop)


def committed_settings_notice(project_root: Path) -> str | None:
    """What to tell the operator when the hooks were left out of a committed settings file."""
    if not _settings_committed(project_root) or _hooks_registered(project_root):
        return None
    return (
        ".claude/settings.json is committed, so Spec Kitty did not edit it. To enable session orientation, "
        f"add a SessionStart hook running `{SESSION_START_CMD}` and a Stop hook running `{SESSION_STOP_CMD}` "
        "to .claude/settings.json and commit the change."
    )


@dataclass
class ClaudeCodeWriter(MarkdownRulesWriter):
    """Writer for the Claude Code harness.

    Manages two artefacts:
    - ``.claude/CLAUDE.md`` — orientation section (via ``MarkdownRulesWriter``).
    - ``.claude/settings.json`` — ``SessionStart`` and ``Stop`` hooks (via
      ``ClaudeCodeHookRegistrar``).

    Both artefacts are written/removed together so the harness stays consistent.
    """

    harness_key: str = field(default="claude")
    rules_path: str = field(default=".claude/CLAUDE.md")
    append_mode: bool = field(default=True)

    def write(self, project_root: Path, content: SessionPresenceContent) -> None:
        """Write the CLAUDE.md section AND register the SessionStart + Stop hooks."""
        paths = (self.rules_path, ClaudeCodeHookRegistrar().settings_relative_path)
        before = tuple(observe_presence_path(project_root, path) for path in paths)
        prepared = self.prepare_batch(project_root, content)
        if before != tuple(observe_presence_path(project_root, path) for path in paths):
            raise ValueError("Session batch precondition changed")
        for item in prepared:
            self.apply_prepared(project_root, item)

    def prepare_batch(self, project_root: Path, content: SessionPresenceContent) -> tuple[PreparedPresenceFile, ...]:
        """Validate orientation and both hook entries before any sibling write."""
        orientation = super().prepare(project_root, content)
        settings = ClaudeCodeHookRegistrar().prepare_commands(
            project_root,
            ((SESSION_START_EVENT, SESSION_START_CMD), (STOP_EVENT, SESSION_STOP_CMD)),
        )
        if settings.changed and _settings_committed(project_root):
            settings = replace(settings, disposition="preserve", reason=COMMITTED_SETTINGS_REASON)
        return orientation, settings

    def apply_prepared(self, project_root: Path, prepared: PreparedPresenceFile) -> None:
        """Consume one retained member of the already validated writer batch."""
        registrar = ClaudeCodeHookRegistrar()
        if prepared.path == registrar.settings_relative_path:
            registrar.apply_prepared(project_root, prepared)
        else:
            super().apply_prepared(project_root, prepared)

    def remove(self, project_root: Path) -> None:
        """Remove the CLAUDE.md section AND unregister the SessionStart + Stop hooks."""
        super().remove(project_root)
        ClaudeCodeHookRegistrar(SESSION_START_EVENT).unregister(project_root, SESSION_START_CMD)
        ClaudeCodeHookRegistrar(STOP_EVENT).unregister(project_root, SESSION_STOP_CMD)

    def has_presence(self, project_root: Path) -> bool:
        """Return ``True`` only when the CLAUDE.md section AND both hooks exist."""
        return super().has_presence(project_root) and _hooks_registered(project_root)
