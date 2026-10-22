"""Migration: replace whole-folder agent ignores with Spec Kitty's own files (#6474).

Spec Kitty used to add every agent folder to ``.gitignore`` (``.claude/``,
``.gemini/``, ``.kiro/`` ... for all agents, whatever ``--ai`` chose, plus
``.agents/skills/``). That silently hid files a team commits on purpose, such
as ``.claude/settings.json``, ``.claude/rules/`` and ``.kiro/steering/``.

This migration:

1. Removes those whole-folder lines, but only where Spec Kitty wrote them: in
   the run of entries after its ``# Added by Spec Kitty CLI (auto-managed)``
   marker, or after the header the 0.4.8 migration wrote. A matching line
   anywhere else is the operator's own and is kept, with a warning.
2. Writes the agent-files block (``GitignoreManager.sync_agent_block``) for the
   configured agents: secrets and runtime-state folders, generated command
   files and skill folders, generated session files.
3. Warns about untracked files that the removed lines used to hide and that
   git now shows. It does not add them anywhere; the operator decides.

The legacy entry list is frozen here, so what counts as "written by Spec Kitty"
never moves with the live registry. The block's content is live on purpose: it
follows the project's configured agents and skills manifest.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git import GitCommandError, status_entries
from specify_cli.core.agent_config import AgentConfigError
from specify_cli.gitignore_manager import (
    SPEC_KITTY_GITIGNORE_MARKER,
    GitignoreBlockError,
    GitignorePathError,
    read_gitignore_text,
    replace_agent_block,
    write_gitignore_text,
)

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult

MIGRATION_ID = "4.0.0rc8_narrow_agent_gitignore"

#: Every whole-folder or narrow agent entry an earlier Spec Kitty wrote (frozen).
LEGACY_AGENT_ENTRIES: frozenset[str] = frozenset(
    {
        ".claude/",
        ".codex/",
        ".vibe/",
        ".pi/",
        ".letta/",
        ".opencode/",
        ".windsurf/",
        ".gemini/",
        ".llxprt/",
        ".cursor/",
        ".cursor/rules/spec-kitty.mdc",
        ".cursor/commands/",
        ".cursor/skills/",
        ".qwen/",
        ".kilocode/",
        ".augment/",
        ".roo/",
        ".amazonq/",
        ".kiro/",
        ".agent/",
        ".github/copilot/",
        ".agents/skills/",
    }
)

#: Folders those entries hid; a team's own files there may now show up.
_LEGACY_FOLDERS: tuple[str, ...] = tuple(sorted(entry for entry in LEGACY_AGENT_ENTRIES if entry.endswith("/")))

#: The header ``0.4.8_gitignore_agents`` wrote above its entries (frozen).
_LEGACY_HEADER = "# AI Agent directories (added by Spec Kitty CLI)"
_LEGACY_HEADER_NOTE = "# These contain auth tokens and should NEVER be committed"

#: Other lines Spec Kitty writes in the same run (runtime state); they keep a run open.
_RUNTIME_PREFIXES: tuple[str, ...] = (".kittify/", "kitty-specs/", "kitty-ops/", ".worktrees/")

#: Entries later backfills appended at the end of the file once the marker existed,
#: so they can follow the operator's own lines (frozen): 3.2.5 (``.agents/skills/``),
#: 3.2.6rc3 (the narrow cursor rows) and the 3.2.0rc35 Pi/Letta backfill.
_BACKFILL_APPENDED: frozenset[str] = frozenset({".agents/skills/", ".cursor/rules/spec-kitty.mdc", ".cursor/commands/", ".cursor/skills/", ".pi/", ".letta/"})

#: The blanket cursor row is Spec Kitty's only where 3.2.6rc3 proved it: between
#: ``.gemini/`` and ``.qwen/`` in a managed run. Anywhere else it is the operator's.
_CURSOR_ENTRY = ".cursor/"
_CURSOR_NEIGHBOURS = (".gemini/", ".qwen/")

#: Folders the agent-files block ignores whole anyway; an operator's rule for them needs no warning.
_STILL_IGNORED_FOLDERS: frozenset[str] = frozenset({".vibe/", ".pi/", ".letta/", ".github/copilot/"})

_MAX_LISTED_PATHS = 20


def _folder_forms(folder: str) -> frozenset[str]:
    """Spellings git treats as ignoring the whole *folder* (``.claude``, ``/.claude/``, ``.claude/**`` ...)."""
    bare = folder.rstrip("/")
    return frozenset(f"{prefix}{bare}{suffix}" for prefix in ("", "/", "**/") for suffix in ("", "/", "/*", "/**"))


_OPERATOR_FOLDER_FORMS: dict[str, str] = {form: folder for folder in _LEGACY_FOLDERS for form in _folder_forms(folder)}


def _is_run_entry(stripped: str) -> bool:
    return stripped in LEGACY_AGENT_ENTRIES or stripped.startswith(_RUNTIME_PREFIXES)


def _is_cursor_row_proven(lines: list[str], index: int) -> bool:
    return 0 < index < len(lines) - 1 and (lines[index - 1].strip(), lines[index + 1].strip()) == _CURSOR_NEIGHBOURS


def _is_owned(lines: list[str], index: int, *, in_run: bool, after_marker: bool) -> bool:
    """Whether Spec Kitty provably wrote the agent line at *index*."""
    stripped = lines[index].strip()
    if stripped == _CURSOR_ENTRY:
        return in_run and _is_cursor_row_proven(lines, index)
    if in_run and stripped in LEGACY_AGENT_ENTRIES:
        return True
    return after_marker and stripped in _BACKFILL_APPENDED


def _classify(lines: list[str]) -> tuple[set[int], list[str]]:
    """Return the indexes of Spec Kitty-written agent lines, and the operator's own whole-folder rules."""
    owned: set[int] = set()
    operator_rules: list[str] = []
    in_run = after_marker = False
    header_indexes: list[int] = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped in (SPEC_KITTY_GITIGNORE_MARKER, _LEGACY_HEADER, _LEGACY_HEADER_NOTE):
            in_run = True
            after_marker = after_marker or stripped == SPEC_KITTY_GITIGNORE_MARKER
            if stripped != SPEC_KITTY_GITIGNORE_MARKER:
                header_indexes.append(index)
            continue
        if not stripped:
            continue
        if stripped.startswith("#") or not _is_run_entry(stripped):
            in_run = False
        if _is_owned(lines, index, in_run=in_run, after_marker=after_marker):
            owned.add(index)
        elif stripped in _OPERATOR_FOLDER_FORMS and _OPERATOR_FOLDER_FORMS[stripped] not in _STILL_IGNORED_FOLDERS:
            operator_rules.append(stripped)
    owned.update(_orphaned_headers(lines, header_indexes, owned))
    owned.update(_emptied_markers(lines, owned))
    return owned, operator_rules


def _orphaned_headers(lines: list[str], header_indexes: list[int], owned: set[int]) -> set[int]:
    """The 0.4.8 header lines whose entries are all being removed."""
    orphaned: set[int] = set()
    for index in header_indexes:
        following = (i for i in range(index + 1, len(lines)) if lines[i].strip() and lines[i].strip() not in (_LEGACY_HEADER, _LEGACY_HEADER_NOTE))
        first_entry = next(following, None)
        if first_entry is None or first_entry in owned:
            orphaned.add(index)
    return orphaned


def _emptied_markers(lines: list[str], owned: set[int]) -> set[int]:
    """Marker lines with nothing left under them once *owned* lines go."""
    emptied: set[int] = set()
    for index, line in enumerate(lines):
        if line.strip() != SPEC_KITTY_GITIGNORE_MARKER:
            continue
        following = (i for i in range(index + 1, len(lines)) if i not in owned and lines[i].strip())
        next_kept = next(following, None)
        if next_kept is None or lines[next_kept].strip().startswith("#"):
            emptied.add(index)
    return emptied


def _without(lines: list[str], removed: set[int]) -> list[str]:
    """Drop *removed* lines, closing only the double blank line a removal leaves."""
    kept: list[str] = []
    just_removed = False
    for index, line in enumerate(lines):
        if index in removed:
            just_removed = True
            continue
        if just_removed and not line.strip() and kept and not kept[-1].strip():
            continue
        just_removed = False
        kept.append(line)
    return kept


def _plan(project_path: Path) -> tuple[str | None, str, list[str], list[str]]:
    """Return (current text, updated text, removed lines, operator rules).

    Raises:
        GitignorePathError / OSError: ``.gitignore`` is unsafe or unreadable.
        GitignoreBlockError: the agent-files block is damaged.
        AgentConfigError: ``.kittify/config.yaml`` is unreadable.
    """
    from specify_cli.agent_utils.ignore_entries import agent_ignore_entries, ignored_agent_keys

    content = read_gitignore_text(project_path / ".gitignore")
    text = content or ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    owned, operator_rules = _classify(lines)
    kept = _without(lines, owned)
    narrowed = newline.join(kept) + newline if kept else ""
    entries = agent_ignore_entries(project_path, ignored_agent_keys(project_path))
    updated = replace_agent_block(narrowed, entries, create=True)
    removed = [lines[index].strip() for index in sorted(owned) if lines[index].strip().startswith(".")]
    return content, narrowed if updated is None else updated, removed, operator_rules


def _newly_visible(project_path: Path, removed: list[str]) -> list[str]:
    """Untracked, unignored files under the paths whose ignore lines were removed."""
    if not removed:
        return []
    try:
        entries = status_entries(project_path, pathspecs=sorted(set(removed)), untracked="all", optional_locks=False)
    except (GitCommandError, OSError, ValueError):
        return []
    return sorted(entry.path.as_posix() for entry in entries if entry.xy == "??")


def _visibility_warning(paths: list[str]) -> str | None:
    if not paths:
        return None
    listed = ", ".join(paths[:_MAX_LISTED_PATHS])
    more = f" and {len(paths) - _MAX_LISTED_PATHS} more" if len(paths) > _MAX_LISTED_PATHS else ""
    return (
        f"Git now shows {len(paths)} file(s) that the old agent ignore rules hid: {listed}{more}. "
        "Review them, then commit the ones your team shares or add your own ignore rule for the rest."
    )


def _operator_rule_warnings(rules: list[str]) -> list[str]:
    return [
        f"Kept your own ignore rule '{rule}' (Spec Kitty did not write it); remove it if your team commits files under {_OPERATOR_FOLDER_FORMS[rule]}"
        for rule in sorted(set(rules))
    ]


@MigrationRegistry.register
class NarrowAgentGitignoreMigration(BaseMigration):
    """Ignore only Spec Kitty's own files in agent folders, for configured agents."""

    migration_id = MIGRATION_ID
    description = "Replace whole-folder agent ignores with Spec Kitty's generated files for configured agents (#6474)"
    target_version = "4.0.0rc8"

    def detect(self, project_path: Path) -> bool:
        try:
            content, updated, _removed, _rules = _plan(project_path)
        except (GitignorePathError, GitignoreBlockError, AgentConfigError, OSError):
            return True  # apply() reports the cause once.
        return updated != (content or "")

    def can_apply(self, project_path: Path) -> tuple[bool, str]:
        if not project_path.exists():
            return False, f"Project path does not exist: {project_path}"
        try:
            _plan(project_path)
        except (GitignorePathError, GitignoreBlockError, AgentConfigError, OSError) as exc:
            return False, f".gitignore cannot be narrowed: {exc}"
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        try:
            content, updated, removed, rules = _plan(project_path)
        except (GitignorePathError, GitignoreBlockError, AgentConfigError, OSError) as exc:
            return MigrationResult(success=False, errors=[str(exc)])

        warnings = _operator_rule_warnings(rules)
        verb = "Would remove" if dry_run else "Removed"
        changes = [f"{verb} agent ignore line: '{line}'" for line in removed]
        if updated != (content or ""):
            changes.append(f"{'Would write' if dry_run else 'Wrote'} the Spec Kitty agent-files block in .gitignore")
            if not dry_run:
                try:
                    write_gitignore_text(project_path / ".gitignore", updated)
                except (GitignorePathError, OSError) as exc:
                    return MigrationResult(success=False, errors=[str(exc)])
                visibility = _visibility_warning(_newly_visible(project_path, removed))
                if visibility:
                    warnings.append(visibility)
        if not changes:
            changes.append("Agent ignore rules already narrow")

        return MigrationResult(
            success=True,
            changes_made=changes,
            warnings=warnings,
            manual_review_required=bool(warnings),
            preserved_paths=[str(project_path / ".gitignore")] if warnings else [],
        )
