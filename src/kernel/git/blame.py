"""Line-level history reads: ``git blame --porcelain`` and zero-context diff hunks (#6309).

Two intent-named queries, each with a pure raw-bytes parser so it can be tested
against captured git output:

* :func:`blame_lines` asks which commit last wrote each line of a file (or, with
  ``reverse``, the last commit in which each line of an older file still existed);
* :func:`diff_hunks` asks which lines one revision removed and added relative to
  another, for one path, with no context lines.

Neither reads paths from git: the path is an input, never parsed back. Line text
is returned as the raw bytes git printed, so a caller decides how to compare it.
Both pin the knobs that would otherwise let a user's configuration change the
answer: the diff algorithm (``myers``), textconv filters (off), external diff
drivers (off) and, for blame, any ``blame.ignoreRevsFile`` (cleared). The
domain meaning of an answer (what counts as "still the canceled commit's
content") stays with the caller.

Each query raises :class:`~kernel.git.runner.GitCommandError` when git fails;
neither returns an empty result on failure.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.git.runner import run_git

__all__ = ["BlameLine", "DiffHunk", "blame_lines", "diff_hunks", "parse_blame_porcelain", "parse_zero_context_diff"]

Env = Mapping[str, str] | None

# ``-c`` pins applied to every read here: a user's ``diff.algorithm`` (patience,
# histogram) can move which lines a diff pairs, and so which commit a line blames to.
_STABLE_DIFF: tuple[str, ...] = ("-c", "diff.algorithm=myers", "-c", "diff.relative=false")
# ``<sha> <line in that commit> <line in the blamed file>[ <lines in group>]``;
# 40 hex for SHA-1, 64 for SHA-256 repositories.
_BLAME_HEADER = re.compile(rb"^([0-9a-f]{40}|[0-9a-f]{64}) (\d+) (\d+)(?: \d+)?$")
_BOUNDARY_KEY = b"boundary"
_HUNK_HEADER = re.compile(rb"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class BlameLine:
    """One line of ``git blame --porcelain`` output.

    ``commit`` is the full object id blame attributed the line to and
    ``commit_line`` the line's number in that commit's version of the file.
    ``blamed_line`` is the line's number in the blamed file: the newest revision
    of a forward blame, the OLDEST (start) revision of a ``--reverse`` blame.
    ``boundary`` is True when blame stopped at the lower bound of the range
    rather than at a commit that wrote the line. ``text`` is the line's bytes,
    without the newline.
    """

    commit: str
    commit_line: int
    blamed_line: int
    boundary: bool
    text: bytes


@dataclass(frozen=True)
class DiffHunk:
    """One ``@@`` hunk of a zero-context diff: the lines removed and the lines added.

    ``old_start``/``old_count`` locate the removed lines in the old revision
    (``old_count == 0`` means a pure insertion after line ``old_start``), and
    ``new_start``/``new_count`` the added lines in the new one.
    """

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    removed: tuple[bytes, ...]
    added: tuple[bytes, ...]


def parse_blame_porcelain(raw: bytes) -> tuple[BlameLine, ...]:
    """Parse ``git blame --porcelain`` output into one :class:`BlameLine` per file line.

    Every line of the file is preceded by a header naming its commit; the
    commit's metadata (including the ``boundary`` key) follows only the first
    header of that commit, so boundary-ness is remembered per commit.

    Raises:
        ValueError: a content line arrived without a header (truncated or
            unrecognised output), so no partial answer is ever returned.
    """
    lines: list[BlameLine] = []
    boundary_commits: set[str] = set()
    current: tuple[str, int, int] | None = None
    for row in raw.split(b"\n"):
        if row.startswith(b"\t"):
            if current is None:
                raise ValueError("git blame --porcelain: a content line has no header")
            commit, commit_line, blamed_line = current
            lines.append(BlameLine(commit, commit_line, blamed_line, commit in boundary_commits, row[1:]))
            current = None
            continue
        header = _BLAME_HEADER.match(row)
        if header is not None:
            current = (header[1].decode("ascii"), int(header[2]), int(header[3]))
        elif row == _BOUNDARY_KEY and current is not None:
            boundary_commits.add(current[0])
    if current is not None:
        raise ValueError("git blame --porcelain: a header has no content line")
    return tuple(lines)


def parse_zero_context_diff(raw: bytes) -> tuple[DiffHunk, ...]:
    """Parse a single-path ``git diff -U0`` into its hunks.

    Lines before the first ``@@`` header are the file header and are skipped.
    Inside a hunk, ``-`` lines are removed, ``+`` lines added, and the
    ``\\ No newline at end of file`` marker is ignored. Every content line
    carries a one-character prefix, so a removed line that itself starts with
    ``--`` is never mistaken for a file header once the first hunk began.
    """
    hunks: list[DiffHunk] = []
    header: tuple[int, int, int, int] | None = None
    removed: list[bytes] = []
    added: list[bytes] = []
    for row in raw.split(b"\n"):
        match = _HUNK_HEADER.match(row)
        if match is not None:
            if header is not None:
                hunks.append(DiffHunk(*header, tuple(removed), tuple(added)))
            header = (int(match[1]), _count(match[2]), int(match[3]), _count(match[4]))
            removed, added = [], []
        elif header is not None and row.startswith(b"-"):
            removed.append(row[1:])
        elif header is not None and row.startswith(b"+"):
            added.append(row[1:])
    if header is not None:
        hunks.append(DiffHunk(*header, tuple(removed), tuple(added)))
    return tuple(hunks)


def _count(raw: bytes | None) -> int:
    """A hunk header omits the count when it is 1."""
    return 1 if raw is None else int(raw)


def blame_lines(
    cwd: Path,
    path: str,
    *,
    revs: Sequence[str],
    reverse: bool = False,
    first_parent: bool = False,
    ignore_whitespace: bool = False,
    detect_moves: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[BlameLine, ...]:
    """Blame *path* over *revs* (``<end>`` or ``<start>..<end>``), one entry per line.

    *ignore_whitespace* (``-w``) keeps a line's author when a later commit only
    re-indented it or changed its line ending; *detect_moves* (``-M``) follows a
    line moved within the file (git's threshold applies: short lines are not
    followed); *first_parent* follows only first parents; *reverse* blames the
    START revision forward. Blame follows a whole-file rename on its own.

    Raises:
        GitCommandError: git failed, including when *path* does not exist in the
            blamed revision (also a timeout or a git that did not start).
        ValueError: git's output could not be parsed.
    """
    flags = [flag for flag, wanted in (("--reverse", reverse), ("--first-parent", first_parent), ("-w", ignore_whitespace), ("-M", detect_moves)) if wanted]
    args = [*_STABLE_DIFF, "blame", "--porcelain", "--no-textconv", "--ignore-revs-file", "", *flags, *revs, "--", path]
    return parse_blame_porcelain(run_git(cwd, *args, env=env, timeout=timeout).stdout)


def diff_hunks(
    cwd: Path,
    old: str,
    new: str,
    path: str,
    *,
    ignore_whitespace: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[DiffHunk, ...]:
    """The zero-context hunks of ``git diff <old> <new> -- <path>`` (renames off, no textconv).

    *ignore_whitespace* (``-w``) drops a hunk that only changed whitespace or
    line endings. A binary path yields no hunks (git prints no text diff for it).

    Raises:
        GitCommandError: git failed (an unreadable revision, a timeout).
    """
    args = [*_STABLE_DIFF, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", "--no-renames"]
    if ignore_whitespace:
        args.append("-w")
    return parse_zero_context_diff(run_git(cwd, *args, old, new, "--", path, env=env, timeout=timeout).stdout)
