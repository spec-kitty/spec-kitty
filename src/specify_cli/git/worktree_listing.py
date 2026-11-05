"""Typed ``git worktree list --porcelain`` records (#7173).

This lives beside :mod:`specify_cli.git.destructive_guard`, not in
:mod:`kernel.git`: the kernel owns listings of paths and refs and carries no
``worktree`` argv at all (gate C-007,
``tests/kernel/test_git_runner.py::test_kernel_git_contains_no_destructive_literal``).
The subprocess still goes through the kernel's one seam,
:func:`kernel.git.runner.run_git`, and is decoded with its lossless rule.

:func:`_parse_worktree_porcelain` is a pure function so it can be tested against
captured git output; :func:`worktree_entries` asks git and parses the answer.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.git.runner import decode_path, run_git

__all__ = [
    "WorktreeEntry",
    "worktree_entries",
]

# ``git worktree list --porcelain`` attribute keys (git-worktree(1), "Porcelain Format").
_WT_PATH: str = "worktree"
_WT_HEAD: str = "HEAD"
_WT_BRANCH: str = "branch"
_WT_FLAGS: frozenset[str] = frozenset({"detached", "bare", "locked", "prunable"})
_HEADS_PREFIX: str = "refs/heads/"


@dataclass(frozen=True)
class WorktreeEntry:
    """One ``git worktree list --porcelain`` record.

    ``path`` is exactly as git printed it (never resolved: callers decide).
    ``branch`` is the short name (``refs/heads/`` stripped; any other ref is
    kept verbatim) and ``None`` when the worktree is detached or bare; ``head``
    is ``None`` for a bare entry.
    """

    path: Path
    head: str | None
    branch: str | None
    detached: bool
    bare: bool
    locked: bool
    prunable: bool


def _worktree_records(text: str) -> Iterator[list[str]]:
    """Yield the lines of each blank-line-separated porcelain record."""
    record: list[str] = []
    for line in text.splitlines():
        if line:
            record.append(line)
        elif record:
            yield record
            record = []
    if record:
        yield record


def _worktree_entry(record: Sequence[str]) -> WorktreeEntry | None:
    """Build one entry from a record's lines; ``None`` when it names no worktree."""
    values: dict[str, str] = {}
    flags: set[str] = set()
    for line in record:
        key, _, value = line.partition(" ")
        if key in _WT_FLAGS:
            flags.add(key)  # ``locked`` / ``prunable`` may carry a reason; only presence matters.
        elif key in (_WT_PATH, _WT_HEAD, _WT_BRANCH):
            values[key] = value
        # Any other line is an attribute this parser does not know yet: ignored.
    if _WT_PATH not in values:
        return None
    branch = values.get(_WT_BRANCH)
    if branch is not None and branch.startswith(_HEADS_PREFIX):
        branch = branch[len(_HEADS_PREFIX) :]
    return WorktreeEntry(
        path=Path(values[_WT_PATH]),
        head=values.get(_WT_HEAD),
        branch=branch,
        detached="detached" in flags,
        bare="bare" in flags,
        locked="locked" in flags,
        prunable="prunable" in flags,
    )


def _parse_worktree_porcelain(text: str) -> tuple[WorktreeEntry, ...]:
    """Parse ``git worktree list --porcelain`` (without ``-z``), in git's order.

    The first entry git reports is the main worktree. Records are separated by
    blank lines; a path is everything after ``worktree `` (spaces kept). A
    record without a ``worktree`` line is skipped and unknown attribute lines
    are ignored, so a newer git's additions do not break the parse. A path
    containing a newline is not supported (git prints it unquoted).
    """
    entries = (_worktree_entry(record) for record in _worktree_records(text))
    return tuple(entry for entry in entries if entry is not None)


def worktree_entries(cwd: Path, *, env: Mapping[str, str] | None = None, timeout: float | None = None) -> tuple[WorktreeEntry, ...]:
    """Every worktree registered with the repository at *cwd*, main worktree first.

    Raises:
        kernel.git.runner.GitCommandError: ``git worktree list`` failed (also a
            timeout or a git that did not start).
    """
    raw = run_git(cwd, "worktree", "list", "--porcelain", env=env, timeout=timeout).stdout
    return _parse_worktree_porcelain(decode_path(raw))
