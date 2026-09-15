"""Reusable utilities for upgrading skill files across all agent skill roots.

Use this module when writing migrations that update skill content. It handles
the complexity of finding skill files across all possible agent skill root
directories (native-root-required, shared-root-capable, and agent-specific).

Example migration using this utility:

    from specify_cli.upgrade.skill_update import (
        find_skill_files,
        apply_text_replacements,
        SkillFileInfo,
    )

    # Find all copies of a skill
    files = find_skill_files(project_path, "spec-kitty-setup-doctor")

    # Apply replacements
    for info in files:
        apply_text_replacements(info.path, [
            ("old text", "new text"),
            ("another old", "another new"),
        ])

See also: agent-path-matrix.md in the setup-doctor skill references.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from specify_cli.core.utils import ensure_within_directory, write_text_within_directory

logger = logging.getLogger(__name__)

# All possible skill root directories from agent-path-matrix.md.
# Covers native-root-required, shared-root-capable, and agent-specific roots.
SKILL_ROOTS: list[str] = [
    ".claude/skills",  # Claude Code (native-root-required)
    ".agents/skills",  # Shared root for shared-root-capable agents
    ".qwen/skills",  # Qwen Code (native-root-required)
    ".kilocode/skills",  # Kilo Code (native-root-required)
    ".github/skills",  # GitHub Copilot (agent-specific)
    ".gemini/skills",  # Gemini CLI (agent-specific)
    ".llxprt/skills",  # LLxprt Code (agent-specific)
    ".cursor/skills",  # Cursor (agent-specific)
    ".opencode/skills",  # opencode (agent-specific)
    ".windsurf/skills",  # Windsurf (agent-specific)
    ".augment/skills",  # Auggie CLI (agent-specific)
    ".roo/skills",  # Roo Code (agent-specific)
    ".agent/skills",  # Google Antigravity (agent-specific)
    ".codex/skills",  # Codex CLI (if agent-specific root exists)
]


@dataclass
class SkillFileInfo:
    """Information about a discovered skill file."""

    path: Path
    """Absolute path to the skill file."""

    skill_root: str
    """The skill root directory (e.g., '.claude/skills')."""

    skill_name: str
    """The skill directory name (e.g., 'spec-kitty-setup-doctor')."""

    relative_path: str
    """Path relative to the skill directory (e.g., 'SKILL.md' or 'references/foo.md')."""


def find_skill_files(
    project_path: Path,
    skill_name: str,
    file_patterns: list[str] | None = None,
) -> list[SkillFileInfo]:
    """Find all installed copies of a skill across all agent skill roots.

    Args:
        project_path: Root of the project directory.
        skill_name: Name of the skill directory (e.g., 'spec-kitty-setup-doctor').
        file_patterns: Optional list of relative file paths within the skill to find.
            If None, finds all files recursively.

    Returns:
        List of SkillFileInfo for each found file.
    """
    found: list[SkillFileInfo] = []

    for root in SKILL_ROOTS:
        skill_dir = project_path / root / skill_name
        if not skill_dir.is_dir():
            continue

        if file_patterns:
            for pattern in file_patterns:
                file_path = skill_dir / pattern
                if file_path.is_file():
                    found.append(
                        SkillFileInfo(
                            path=file_path,
                            skill_root=root,
                            skill_name=skill_name,
                            relative_path=pattern,
                        )
                    )
        else:
            for file_path in sorted(skill_dir.rglob("*")):
                if not file_path.is_file():
                    continue
                rel = str(file_path.relative_to(skill_dir))
                found.append(
                    SkillFileInfo(
                        path=file_path,
                        skill_root=root,
                        skill_name=skill_name,
                        relative_path=rel,
                    )
                )

    return found


def apply_text_replacements(
    file_path: Path,
    replacements: list[tuple[str, str]],
    context_filter: Callable[[Path], bool] | None = None,
    *,
    trusted_root: Path | None = None,
) -> bool:
    """Apply a list of text replacements to a file.

    Args:
        file_path: Path to the file to modify.
        replacements: List of (old_text, new_text) tuples.
        context_filter: Optional callable that receives the file path and returns
            True if the file should be processed, False to skip it. When None
            (the default), all files are processed. This allows callers to
            exclude files by pattern (e.g., skip ``.kittify/`` paths).
        trusted_root: Optional root directory the target file must remain under
            before this helper reads or writes it.

    Returns:
        True if the file was modified, False if no changes were needed
        or the file was skipped by the context_filter.
    """
    if context_filter is not None and not context_filter(file_path):
        return False

    project_root = (
        trusted_root.resolve() if trusted_root is not None else _project_root_for_skill_path(file_path)
    )
    if project_root is None:
        # Fail-closed: the file is not under a recognized skill root, so the
        # HOME-managed-symlink write guard cannot anchor it. Refuse to read or
        # write through an unverified path (PR #2043 review, alphonso).
        return False

    safe_file_path = ensure_within_directory(file_path, trusted_root) if trusted_root else file_path

    try:
        content = safe_file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    original = content
    for old, new in replacements:
        content = content.replace(old, new)

    if content != original:
        wrote, _warning = write_skill_text(safe_file_path, content, project_root)
        return wrote
    return False


def exclude_paths(*patterns: str) -> Callable[[Path], bool]:
    """Create a context filter that excludes files matching any glob pattern.

    Use with ``apply_text_replacements`` to skip files during bulk edits::

        filt = exclude_paths(".kittify/*", "*.lock")
        apply_text_replacements(path, replacements, context_filter=filt)

    Args:
        *patterns: Glob patterns to exclude. Matched against the string
            representation of the file path using :func:`fnmatch.fnmatch`.

    Returns:
        A callable suitable for the ``context_filter`` parameter of
        :func:`apply_text_replacements`.
    """

    def _filter(path: Path) -> bool:
        path_str = str(path)
        return not any(fnmatch(path_str, p) for p in patterns)

    return _filter


def file_contains_any(file_path: Path, markers: list[str]) -> bool:
    """Check if a file contains any of the given marker strings.

    Args:
        file_path: Path to the file to check.
        markers: List of strings to search for.

    Returns:
        True if any marker is found in the file content.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    return any(marker in content for marker in markers)


def _has_symlink_component(dest: Path, project_root: Path) -> bool:
    """Return True when ``dest`` or an ancestor below ``project_root`` is a symlink."""
    try:
        dest_abs = dest.absolute()
        project_root_abs = project_root.absolute()
        rel = dest_abs.relative_to(project_root_abs)
    except ValueError:
        return dest.is_symlink()

    current = project_root_abs
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            return True
    return False


def is_external_symlink(dest: Path, project_root: Path) -> bool:
    """Return True if ``dest`` reaches outside ``project_root`` through a symlink."""
    if not _has_symlink_component(dest, project_root):
        return False
    try:
        target = dest.resolve(strict=False)
        project_root_resolved = project_root.resolve()
        try:
            target.relative_to(project_root_resolved)
        except ValueError:
            return True
        return False
    except OSError:
        return False


def _project_root_for_skill_path(file_path: Path) -> Path | None:
    """Infer the project root for a file living under a known skill root."""
    resolved = file_path.resolve(strict=False)
    for parent in resolved.parents:
        for skill_root in SKILL_ROOTS:
            candidate_root = (parent / skill_root).resolve(strict=False)
            try:
                resolved.relative_to(candidate_root)
            except ValueError:
                continue
            return parent
    return None


def write_skill_text(
    dest: Path,
    content: str,
    project_root: Path,
    *,
    encoding: str = "utf-8",
) -> tuple[bool, str | None]:
    """Write ``content`` to ``dest``, skipping HOME-managed external symlinks.

    Returns ``(wrote, warning)``. When ``dest`` itself or a parent directory
    inside ``project_root`` is a symlink that resolves outside ``project_root``,
    the write is skipped and a warning string is returned; the canonical file
    outside the repo is never modified (see #1184).
    """
    if is_external_symlink(dest, project_root):
        try:
            rel = str(dest.relative_to(project_root))
        except ValueError:
            rel = str(dest)
        warning = f"Skipped {rel}: symlinked path points outside repo (HOME-managed canonical copy)"
        logger.warning(warning)
        return False, warning
    write_text_within_directory(dest, content, root=project_root, encoding=encoding)
    return True, None


def replace_skill_file(
    project_path: Path,
    skill_name: str,
    relative_path: str,
    new_content: str,
) -> list[str]:
    """Replace a skill file across all agent skill roots with new content.

    This is for cases where text replacements aren't sufficient and you need
    to write the entire file content.

    Args:
        project_path: Root of the project directory.
        skill_name: Name of the skill directory.
        relative_path: File path relative to the skill directory.
        new_content: The new file content to write.

    Returns:
        List of paths (relative to project) that were updated.
    """
    updated: list[str] = []

    for root in SKILL_ROOTS:
        file_path = project_path / root / skill_name / relative_path
        if not file_path.is_file():
            continue

        try:
            existing = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if existing != new_content:
            wrote, _warning = write_skill_text(file_path, new_content, project_path)
            if wrote:
                updated.append(str(file_path.relative_to(project_path)))

    return updated
