"""
GitignoreManager module for protecting runtime state and generated agent files.

This module provides a centralized system for managing .gitignore entries:
runtime state under ``.kittify/`` (from the state contract), ``.worktrees/``,
and the files Spec Kitty generates inside agent folders. The agent files live
in one delimited block that :meth:`GitignoreManager.sync_agent_block` rewrites
from the configured agents (#6474); whole agent folders are no longer ignored,
so a team can commit its own ``.claude/settings.json`` or ``.kiro/steering/``.
"""

import os
import subprocess
import stat
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kernel.git import GitCommandError, tracked_paths
from specify_cli.core.constants import WORKTREES_DIR
from specify_cli.core.no_follow import (
    NoFollowPathError,
    open_no_follow,
    read_text_no_follow,
)
from specify_cli.agent_utils.ignore_entries import agent_ignore_entries, ignored_agent_keys
from specify_cli.state.contract import get_runtime_gitignore_entries


SPEC_KITTY_GITIGNORE_MARKER = "# Added by Spec Kitty CLI (auto-managed)"

#: Delimiters of the agent-files block. Everything between them is rewritten
#: by :meth:`GitignoreManager.sync_agent_block`; lines outside are never touched.
AGENT_BLOCK_BEGIN = "# >>> Spec Kitty agent files (auto-managed; lines in this block are replaced) >>>"
AGENT_BLOCK_END = "# <<< Spec Kitty agent files <<<"


class GitignoreBlockError(ValueError):
    """Raised when the agent-files block delimiters are missing a partner or repeated."""


def replace_agent_block(content: str | None, entries: Sequence[str], *, create: bool = True) -> str | None:
    """Return *content* with the agent-files block set to *entries*.

    The block is replaced where it stands; with no block, it is appended when
    *create* is true. Returns ``None`` when nothing would change (including no
    block and ``create=False``). The file's newline style is kept.

    Raises:
        GitignoreBlockError: a begin line without its end line (or the
            reverse), or more than one block. The file is left for the
            operator to repair rather than guessed at.
    """
    text = content or ""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    begins = [index for index, line in enumerate(lines) if line.strip() == AGENT_BLOCK_BEGIN]
    ends = [index for index, line in enumerate(lines) if line.strip() == AGENT_BLOCK_END]
    block = [AGENT_BLOCK_BEGIN, *entries, AGENT_BLOCK_END]
    if not begins and not ends:
        if not create:
            return None
        updated_lines = list(lines)
        if updated_lines and updated_lines[-1].strip():
            updated_lines.append("")
        updated_lines.extend(block)
    elif len(begins) == 1 and len(ends) == 1 and begins[0] < ends[0]:
        updated_lines = [*lines[: begins[0]], *block, *lines[ends[0] + 1 :]]
    else:
        raise GitignoreBlockError(
            f".gitignore has a damaged Spec Kitty agent-files block ({len(begins)} begin and {len(ends)} end line(s)); "
            f"keep exactly one '{AGENT_BLOCK_BEGIN}' ... '{AGENT_BLOCK_END}' pair, or delete both lines, then re-run"
        )
    updated = newline.join(updated_lines) + newline
    return None if updated == text else updated


class GitignorePathError(Exception):
    """Raised when an ignore file (`.gitignore`, `.claudeignore`) is a symlink.

    `Path.read_text()` / `Path.write_text()` / `Path.exists()` all follow
    symlinks, so an ignore file swapped for a symlink (e.g. by a malicious
    repo checkout) would let a caller's presence/content check, or a write,
    follow it to an arbitrary path. Fail closed instead of following it.
    """


_WORKTREES_ENTRY = f"{WORKTREES_DIR}/"
_WORKTREES_PROBE = f"{WORKTREES_DIR}/.spec-kitty-ignore-probe"


# Kept as a compatibility alias for migrations that predate the manager-wide
# name consolidation; both names signal the same fail-closed condition.
IgnoreFilePathError = GitignorePathError


def _get_umask() -> int:
    """Return the process umask without permanently changing it.

    `os.umask()` is the only way to read the current umask, and it's a
    process-global set-and-return-previous call, so restore it immediately.
    """
    current = os.umask(0)
    os.umask(current)
    return current


def read_ignore_file_text(path: Path, encoding: str = "utf-8-sig", errors: str | None = None) -> str:
    """Read an ignore file's text content, refusing to follow a symlink.

    Used for presence/content checks against `.gitignore`/`.claudeignore`
    (e.g. migration `detect()` logic) that must not be redirected by a
    symlink the way a bare `Path.read_text()`/`.exists()` pair would be.
    Opens through `read_text_no_follow()` rather than an `is_symlink()`
    check-then-read, so a symlink swapped in between the check and the read
    cannot be followed either.

    Args:
        path: Path to the ignore file (e.g. `.gitignore` or `.claudeignore`).
        encoding: Text encoding to decode with.
        errors: Decode error handler passed through to `Path.read_text()`
            (e.g. `"ignore"` to tolerate undecodable bytes). `None` uses
            strict decoding.

    Returns:
        The file's text content, or `""` if it does not exist.

    Raises:
        GitignorePathError: If `path` is a symlink.
    """
    try:
        return read_text_no_follow(path, encoding=encoding, errors=errors)
    except FileNotFoundError:
        return ""
    except NoFollowPathError as exc:
        raise GitignorePathError(f"{path} is a symlink; refusing to read through it") from exc


def read_gitignore_text(gitignore_path: Path) -> str | None:
    """Read a regular UTF-8 ``.gitignore`` without following a final symlink."""
    if gitignore_path.is_symlink():
        raise GitignorePathError(f"Refusing to read symlinked .gitignore: {gitignore_path}")
    try:
        fd = open_no_follow(gitignore_path, os.O_RDONLY)
    except FileNotFoundError:
        return None
    except NoFollowPathError as exc:
        raise GitignorePathError(f"Refusing to read symlinked .gitignore: {gitignore_path}") from exc
    except OSError as exc:
        raise GitignorePathError(f"Could not safely open .gitignore: {exc}") from exc
    try:
        with os.fdopen(fd, "r", encoding="utf-8-sig", newline="") as handle:
            return handle.read()
    except UnicodeDecodeError as exc:
        raise GitignorePathError(f".gitignore is not valid UTF-8: {exc}") from exc


def write_gitignore_text(gitignore_path: Path, content: str) -> None:
    """Atomically replace a regular ``.gitignore`` without following symlinks."""
    if gitignore_path.is_symlink():
        raise GitignorePathError(f"Refusing to write symlinked .gitignore: {gitignore_path}")

    existing_mode: int | None = None
    if gitignore_path.exists():
        existing_mode = stat.S_IMODE(gitignore_path.stat(follow_symlinks=False).st_mode)
        if not existing_mode & stat.S_IWUSR:
            raise PermissionError(f"Permission denied: {gitignore_path}")

    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=gitignore_path.parent,
            prefix=".gitignore.spec-kitty-",
            delete=False,
        ) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        if existing_mode is not None:
            temporary_path.chmod(existing_mode)
        else:
            # No existing file to replicate the mode of (the common
            # `spec-kitty init` first-write path): `NamedTemporaryFile`
            # always creates its tempfile at 0600 regardless of the process
            # umask, so a brand-new .gitignore would otherwise land there
            # instead of the umask-respecting mode `write_text()` used to
            # produce. Match that historical behaviour explicitly.
            temporary_path.chmod(0o666 & ~_get_umask())
        if gitignore_path.is_symlink():
            raise GitignorePathError(f"Refusing to replace symlinked .gitignore: {gitignore_path}")
        os.replace(temporary_path, gitignore_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def is_gitignore_path_ignored(project_path: Path, relative_path: str) -> bool | None:
    """Return Git's effective ignore verdict for an untracked path.

    ``--no-index`` keeps the check meaningful even if a path is tracked, while
    also allowing a non-existent probe path. ``None`` means the project is not
    a Git repository or Git could not provide a trustworthy verdict.
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", "--", relative_path],
            cwd=project_path,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def _has_git_control_path(project_path: Path) -> bool:
    """Return whether this path or an ancestor has Git control metadata."""
    return any(
        candidate.joinpath(".git").is_file() or (candidate.joinpath(".git").is_dir() and candidate.joinpath(".git", "HEAD").is_file())
        for candidate in (project_path, *project_path.parents)
    )


def _git_work_tree_state(project_path: Path) -> bool | None:
    """Return true/false for worktree/non-repo, or ``None`` on Git failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=project_path,
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None if _has_git_control_path(project_path) else False
    if result.returncode == 0 and result.stdout.strip() == b"true":
        return True
    return None if _has_git_control_path(project_path) else False


def _tracked_git_paths(project_path: Path, root_path: str) -> tuple[str, ...]:
    """Return tracked paths under a managed root, failing closed on Git errors."""
    try:
        return tuple(str(path) for path in tracked_paths(project_path, pathspecs=[root_path], timeout=5))
    except GitCommandError as exc:
        # Guard: a failed probe must refuse, never read as "nothing tracked".
        detail = exc.stderr.strip()
        raise GitignorePathError(f"Could not inspect tracked paths under {root_path}" + (f": {detail}" if detail else "")) from exc


def is_gitignore_root_effectively_ignored(
    project_path: Path,
    *,
    root_path: str,
    equivalent_entries: frozenset[str],
    probe_path: str,
) -> bool:
    """Return whether a managed root is safely ignored as a whole.

    Git can adjudicate one concrete probe, but a later, narrower negation may
    re-include another descendant while leaving that probe ignored. Require an
    equivalent whole-root rule and reject every later negation conservatively;
    then use Git's verdict when one is available. Reasserting the managed rule
    at EOF is harmless and restores a whole-root guarantee.
    """
    root = project_path / root_path
    if root.is_symlink():
        raise GitignorePathError(f"Refusing symlinked managed root: {root}")
    if root.exists() and not root.is_dir():
        raise GitignorePathError(f"Managed root is not a directory: {root}")

    work_tree_state = _git_work_tree_state(project_path)
    if work_tree_state is None:
        raise GitignorePathError("Git could not verify the managed root ignore state")
    if work_tree_state:
        tracked = _tracked_git_paths(project_path, root_path)
        if tracked:
            raise GitignorePathError(
                f"Tracked paths exist under {root_path}; .gitignore cannot protect tracked files. "
                f"Review them, then untrack with `git rm -r --cached -- {root_path}` and rerun "
                "`spec-kitty upgrade` (or `spec-kitty init` during initialization)."
            )

    try:
        content = read_ignore_file_text(project_path / ".gitignore")
    except UnicodeError as exc:
        raise GitignorePathError(f"{project_path / '.gitignore'} is not valid UTF-8; refusing to decode it") from exc
    if not content:
        return False

    entries = tuple(entry for line in content.splitlines() if (entry := line.rstrip()) and not entry.startswith("#"))
    positive_positions = [index for index, entry in enumerate(entries) if entry in equivalent_entries]
    if not positive_positions:
        return False
    if any(entry.startswith("!") for entry in entries[positive_positions[-1] + 1 :]):
        return False

    if not work_tree_state:
        return True

    verdict = is_gitignore_path_ignored(project_path, probe_path)
    if verdict is None:
        raise GitignorePathError("Git could not verify the managed root ignore state")
    return verdict


@dataclass
class AgentDirectory:
    """Represents a single agent's directory that needs protection."""

    name: str
    """Agent name identifier (e.g., 'claude', 'codex')"""

    directory: str
    """Directory path with trailing slash (e.g., '.claude/')"""

    is_special: bool
    """Indicates if special handling is needed (e.g., .github/)"""

    description: str
    """Human-readable description for documentation"""


@dataclass
class ProtectionResult:
    """Result of a gitignore protection operation."""

    success: bool
    """Whether the operation succeeded"""

    modified: bool
    """Whether .gitignore was modified"""

    entries_added: list[str] = field(default_factory=list)
    """New entries added to .gitignore"""

    entries_skipped: list[str] = field(default_factory=list)
    """Entries already present in .gitignore"""

    errors: list[str] = field(default_factory=list)
    """Error messages if any occurred"""

    warnings: list[str] = field(default_factory=list)
    """Warning messages if any were generated"""


# Legacy registry of the whole-folder entries Spec Kitty used to write (#6474).
# Nothing writes these any more; shipped migrations still read it to recognise
# Spec Kitty-authored lines (m_3_2_6rc3_narrow_cursor_gitignore), so it stays
# frozen. The live ignore set is agent_utils.ignore_entries.
AGENT_DIRECTORIES = [
    AgentDirectory("claude", ".claude/", False, "Claude Code CLI"),
    AgentDirectory("codex", ".codex/", False, "Codex (contains auth.json)"),
    AgentDirectory("vibe", ".vibe/", False, "Mistral Vibe (runtime state, config, session logs)"),
    AgentDirectory("pi", ".pi/", False, "Pi (runtime state, auth, session logs)"),
    AgentDirectory("letta", ".letta/", False, "Letta Code (runtime state, auth, memory)"),
    AgentDirectory("opencode", ".opencode/", False, "opencode CLI"),
    AgentDirectory("windsurf", ".windsurf/", False, "Windsurf"),
    AgentDirectory("gemini", ".gemini/", False, "Google Gemini"),
    AgentDirectory("llxprt", ".llxprt/", False, "LLxprt Code"),
    # Narrow, not blanket .cursor/ (#2498): many teams version-control their
    # own rules under .cursor/rules/, so only Spec Kitty-owned paths under
    # .cursor/ are ignored — mirrors the copilot precedent below. The rules
    # file and the commands dir are written by Spec Kitty today; .cursor/skills/
    # is a *declared* secondary skill root (AGENT_SKILL_CONFIG["cursor"]
    # ["skill_roots"] in core/config.py) that the skill installer does not yet
    # populate (it writes only the primary .agents/skills/ root) — it is ignored
    # for consistency with the canonical config. .cursor/hooks.json is
    # deliberately NOT ignored: it is team-owned and Spec Kitty only writes it
    # on an explicit `agent config set lint_on_edit`.
    AgentDirectory("cursor", ".cursor/rules/spec-kitty.mdc", False, "Cursor (Spec Kitty orientation rule)"),
    AgentDirectory("cursor", ".cursor/commands/", False, "Cursor (Spec Kitty slash commands)"),
    AgentDirectory(
        "cursor",
        ".cursor/skills/",
        False,
        "Cursor (declared Spec Kitty skill root; AGENT_SKILL_CONFIG)",
    ),
    AgentDirectory("qwen", ".qwen/", False, "Qwen"),
    AgentDirectory("kilocode", ".kilocode/", False, "Kilocode"),
    AgentDirectory("auggie", ".augment/", False, "Auggie"),
    # "roo" removed — Roo Code shut down on 2026-05-15 (C-007)
    AgentDirectory("amazonq", ".amazonq/", False, "Amazon Q"),
    AgentDirectory("kiro", ".kiro/", False, "Kiro CLI (rebrand of Amazon Q — registered in PR #626)"),
    AgentDirectory("antigravity", ".agent/", False, "Google Antigravity"),
    AgentDirectory("copilot", ".github/copilot/", True, "GitHub Copilot (user settings)"),
]

# Runtime/generated artifacts that should never be tracked.
# Derived from the state contract -- not hardcoded.
RUNTIME_PROTECTED_ENTRIES = get_runtime_gitignore_entries()


class GitignoreManager:
    """Manages gitignore entries for AI agent directories."""

    def __init__(self, project_path: Path):
        """
        Initialize GitignoreManager with project root path.

        Args:
            project_path: Root directory of the project

        Raises:
            ValueError: If project_path doesn't exist or isn't a directory
        """
        if not isinstance(project_path, Path):
            project_path = Path(project_path)

        if not project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        if not project_path.is_dir():
            raise ValueError(f"Project path is not a directory: {project_path}")

        self.project_path = project_path
        self.gitignore_path = project_path / ".gitignore"
        self.marker = SPEC_KITTY_GITIGNORE_MARKER
        self._line_ending: str = os.linesep

    def ensure_entries(self, entries: list[str], *, force_append: bool = False) -> bool:
        """
        Core method to add entries to .gitignore.

        This method migrates the logic from the original ensure_gitignore_entries
        function, maintaining the same behavior for compatibility.

        Args:
            entries: List of gitignore patterns to add
            force_append: Append every requested entry even when the same text
                already occurs earlier. This reasserts a managed rule after a
                later negation without deleting or reordering user-authored
                patterns.

        Returns:
            True if .gitignore was modified, False otherwise
        """
        if not entries:
            return False

        self._reject_symlink()
        content = read_gitignore_text(self.gitignore_path)
        if content is not None:
            # Detect and store line ending style
            self._line_ending = self._detect_line_ending(content)
            lines = content.splitlines()
        else:
            lines = []
            # Use system default for new files
            self._line_ending = os.linesep

        existing = set(lines)
        changed = False

        # Check if any entry needs to be added
        if force_append or any(entry not in existing for entry in entries):
            # Add marker if not present
            if self.marker not in existing:
                if lines and lines[-1].strip():
                    lines.append("")  # Add blank line before marker
                lines.append(self.marker)
                existing.add(self.marker)
                changed = True

            # Add missing entries
            for entry in entries:
                if force_append or entry not in existing:
                    lines.append(entry)
                    existing.add(entry)
                    changed = True

        # Write back if changed
        if changed:
            # Ensure file ends with newline
            if lines and lines[-1] != "":
                lines.append("")

            # Join with detected line ending
            content = self._line_ending.join(lines)
            write_gitignore_text(self.gitignore_path, content)

        return changed

    def _reject_symlink(self) -> None:
        """Raise GitignorePathError if `.gitignore` is a symlink."""
        if self.gitignore_path.is_symlink():
            target = os.readlink(self.gitignore_path)
            raise GitignorePathError(f".gitignore is a symlink to {target!r}; refusing to read or write through it: {self.gitignore_path}")

    def _detect_line_ending(self, content: str) -> str:
        """
        Detect and return the line ending style used in content.

        Args:
            content: File content to analyze

        Returns:
            Line ending string ('\r\n' for Windows, '\n' for Unix/Mac)
        """
        if "\r\n" in content:
            return "\r\n"
        else:
            return "\n"

    def _protect_entries(self, directories: list[str], error_context: str) -> ProtectionResult:
        """
        Shared implementation for adding entries to .gitignore with tracking.

        Args:
            directories: List of gitignore patterns to add
            error_context: Description for error messages (e.g., "agent directories")

        Returns:
            ProtectionResult containing details of the operation
        """
        result = ProtectionResult(success=True, modified=False)

        try:
            # Snapshot existing entries before modification
            self._reject_symlink()
            existing_before: set[str] = set()
            content = read_gitignore_text(self.gitignore_path)
            if content is not None:
                existing_before = set(content.splitlines())

            # Attempt to add entries
            modified = self.ensure_entries(directories)
            result.modified = modified

            # Classify entries as added vs skipped without re-reading the file:
            # ensure_entries() guarantees that after it runs, all requested entries
            # are present. So we just check against the before-snapshot.
            for directory in directories:
                if directory in existing_before:
                    result.entries_skipped.append(directory)
                else:
                    result.entries_added.append(directory)

        except PermissionError:
            result.success = False
            result.errors.append(f"Cannot update .gitignore: Permission denied. Run: chmod u+w {self.gitignore_path}")
        except Exception as exc:
            result.success = False
            result.errors.append(f"Error protecting {error_context}: {exc}")

        return result

    def sync_agent_block(self, agent_keys: Sequence[str] | None = None, *, create: bool = True) -> bool:
        """Rewrite the agent-files block from the configured agents (#6474).

        Args:
            agent_keys: Agents whose generated files to ignore. ``None`` reads
                them from ``.kittify/config.yaml`` (``ignored_agent_keys``).
            create: Append the block when the file has none. Callers that only
                keep an existing block current (skill installs, ``agent
                config``) pass ``False``.

        Returns:
            True if .gitignore was modified.

        Raises:
            GitignoreBlockError: the existing block is damaged.
            AgentConfigError: *agent_keys* is ``None`` and the config is unreadable.
        """
        keys = ignored_agent_keys(self.project_path) if agent_keys is None else agent_keys
        entries = agent_ignore_entries(self.project_path, keys)
        self._reject_symlink()
        content = read_gitignore_text(self.gitignore_path)
        updated = replace_agent_block(content, entries, create=create)
        if updated is None:
            return False
        write_gitignore_text(self.gitignore_path, updated)
        return True

    def protect_all_agents(self, agent_keys: Sequence[str] | None = None) -> ProtectionResult:
        """Protect runtime state and the generated files of the configured agents.

        This is the primary method used during spec-kitty init. It adds the
        runtime entries from the state contract, makes sure ``.worktrees/`` is
        ignored, and writes the agent-files block (:meth:`sync_agent_block`).
        Whole agent folders are no longer ignored (#6474).

        Args:
            agent_keys: Agents to protect; ``None`` reads them from config.
                ``init`` passes its selection, because it saves the config
                only after this step.

        Returns:
            ProtectionResult containing details of the operation
        """
        result = self._protect_entries(list(RUNTIME_PROTECTED_ENTRIES), "runtime files")
        if not result.success:
            return result

        try:
            self._protect_worktrees(result)
            self._protect_agent_block(result, agent_keys)
        except PermissionError:
            result.success = False
            result.errors.append(f"Cannot update .gitignore: Permission denied. Run: chmod u+w {self.gitignore_path}")
        except Exception as exc:
            result.success = False
            result.errors.append(f"Error protecting agent files: {exc}")

        return result

    def _protect_worktrees(self, result: ProtectionResult) -> None:
        if is_gitignore_root_effectively_ignored(
            self.project_path,
            root_path=WORKTREES_DIR,
            equivalent_entries=frozenset({_WORKTREES_ENTRY}),
            probe_path=_WORKTREES_PROBE,
        ):
            return
        self.ensure_entries([_WORKTREES_ENTRY], force_append=True)
        result.modified = True
        if _WORKTREES_ENTRY in result.entries_skipped:
            result.entries_skipped.remove(_WORKTREES_ENTRY)
        if _WORKTREES_ENTRY not in result.entries_added:
            result.entries_added.append(_WORKTREES_ENTRY)

    def _protect_agent_block(self, result: ProtectionResult, agent_keys: Sequence[str] | None) -> None:
        before = set((read_gitignore_text(self.gitignore_path) or "").splitlines())
        if self.sync_agent_block(agent_keys):
            result.modified = True
        after = [line.strip() for line in (read_gitignore_text(self.gitignore_path) or "").splitlines()]
        # Safe: ``sync_agent_block`` just wrote (or kept) a well-formed block, so both markers exist.
        begin = after.index(AGENT_BLOCK_BEGIN)
        end = after.index(AGENT_BLOCK_END)
        for entry in after[begin + 1 : end]:
            (result.entries_skipped if entry in before else result.entries_added).append(entry)


def refresh_agent_block(project_path: Path) -> str | None:
    """Best-effort: bring an existing agent-files block up to date (#6474).

    For callers whose own work already succeeded (skill installs, surface
    repair): the block follows the configured agents and the skills manifest,
    and a project without a block is left for ``init``/``upgrade`` to create.
    Returns a warning to show the operator when the refresh could not run,
    else ``None``; it never raises for a damaged block, an unsafe or
    unwritable ``.gitignore`` or an unreadable config.
    """
    from specify_cli.core.agent_config import AgentConfigError

    if not project_path.is_dir():
        return None  # no project, so no .gitignore to keep current
    try:
        GitignoreManager(project_path).sync_agent_block(create=False)
    except (AgentConfigError, GitignoreBlockError, GitignorePathError, OSError) as exc:
        return f".gitignore agent-files block not refreshed: {exc}"
    return None
