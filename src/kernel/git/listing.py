"""Intent-named git path queries, NUL-safe (mission git-paths-are-data).

Every query here asks git for ``-z`` output and returns :class:`GitPath` values
or typed entries, so no caller ever reads git's display text. Display text is
lossy: ``git status`` quotes a path containing a space (``!! "src/local
data/"``) while ``ls-tree`` does not, and a file literally named ``p -> q``
reads like a rename. Comparing those spellings silently fails open (#5392).

Paths given to a query are literal by default: they are passed after ``--``
with ``--literal-pathspecs``, so a file named ``*`` or ``:(top)`` is never a
pattern. A caller that means a glob passes ``glob=True``.

Each query raises :class:`~kernel.git.runner.GitCommandError` when git fails;
none returns an empty result on failure. The raw-bytes parsers are separate
pure functions so they can be tested against captured git output.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from kernel.git.paths import GitPath
from kernel.git.runner import GitCommandError, decode_path, run_git

__all__ = [
    "IndexEntry",
    "NameStatusEntry",
    "NumstatEntry",
    "StatusEntry",
    "TreeEntry",
    "changed_entries",
    "changed_paths",
    "commit_paths",
    "index_entries",
    "is_tracked",
    "log_paths",
    "numstat_entries",
    "status_entries",
    "tracked_paths",
    "tree_entries",
    "tree_entry",
    "tree_paths",
]

_NUL: bytes = b"\0"
_UNTRACKED_MODES: frozenset[str] = frozenset({"no", "normal", "all"})
# ``--numstat`` prints ``-`` instead of line counts for a binary file.
_BINARY_COUNT: str = "-"
# Porcelain v1 unmerged codes (git-status(1), "Short Format").
_CONFLICT_CODES: frozenset[str] = frozenset({"DD", "AU", "UD", "UA", "DU", "AA", "UU"})
# Status letters whose record is followed by a second (source) path.
_TWO_PATH_LETTERS: frozenset[str] = frozenset({"R", "C"})
# Keep diff/log/show paths repository-relative even under a user's
# ``diff.relative=true`` (git >= 2.28); ``--no-relative`` is newer than the
# git 2.25 floor, and an unknown ``-c`` key is ignored by older git.
_REPO_RELATIVE_DIFF: tuple[str, ...] = ("-c", "diff.relative=false")
# ``git ls-files --error-unmatch`` exit code for "path is not tracked".
_NOT_TRACKED_EXIT: int = 1

Env = Mapping[str, str] | None


def _printable(path: GitPath) -> str:
    """*path* as safe display text: undecodable bytes as ``\\xNN``, control characters escaped, ``é`` kept."""
    raw = str(path).encode("utf-8", "surrogateescape")
    text = raw.decode("utf-8", "backslashreplace")
    return "".join(char.encode("unicode_escape").decode("ascii") if unicodedata.category(char) == "Cc" else char for char in text)


@dataclass(frozen=True)
class StatusEntry:
    """One ``git status --porcelain=v1 -z`` record."""

    xy: str
    path: GitPath
    orig_path: GitPath | None = None
    is_directory: bool = False

    @property
    def index(self) -> str:
        """Staged status letter (``X``)."""
        return self.xy[0]

    @property
    def worktree(self) -> str:
        """Unstaged status letter (``Y``)."""
        return self.xy[1]

    @property
    def is_untracked(self) -> bool:
        return self.xy == "??"

    @property
    def is_ignored(self) -> bool:
        return self.xy == "!!"

    @property
    def is_conflicted(self) -> bool:
        return self.xy in _CONFLICT_CODES

    def display(self) -> str:
        """Human-readable ``XY path`` (``XY orig -> path`` for a rename), safe to print. Never parse it back."""
        shown = f"{_printable(self.path)}/" if self.is_directory else _printable(self.path)
        if self.orig_path is not None:
            return f"{self.xy} {_printable(self.orig_path)} -> {shown}"
        return f"{self.xy} {shown}"


@dataclass(frozen=True)
class NameStatusEntry:
    """One ``git diff --name-status -z`` record (``status`` like ``M``, ``A``, ``R100``)."""

    status: str
    path: GitPath
    orig_path: GitPath | None = None


@dataclass(frozen=True)
class IndexEntry:
    """One ``git ls-files --stage -z`` record."""

    mode: str
    oid: str
    stage: int
    path: GitPath
    tag: str | None = None
    """``ls-files -v`` tag (``H`` tracked, ``S`` skip-worktree, lowercase = assume-unchanged); ``None`` unless asked for."""


@dataclass(frozen=True)
class NumstatEntry:
    """One ``git diff --numstat -z`` record; counts are ``None`` for a binary file."""

    added: int | None
    deleted: int | None
    path: GitPath


@dataclass(frozen=True)
class TreeEntry:
    """One ``git ls-tree -z`` record (``type`` is ``blob``, ``tree`` or ``commit``)."""

    mode: str
    type: str
    oid: str
    path: GitPath


# ---------------------------------------------------------------------------
# Raw -z parsers (pure)
# ---------------------------------------------------------------------------


def _records(raw: bytes) -> Iterator[bytes]:
    """Yield NUL-terminated records, dropping the empty tail."""
    for record in raw.split(_NUL):
        if record:
            yield record


def _next_record(records: Iterator[bytes], after: bytes) -> bytes:
    """The record that must follow *after* (a rename/copy source); truncated output is an error."""
    try:
        return next(records)
    except StopIteration:
        raise ValueError(f"git output ended after {after!r}; expected a second path record") from None


def _path(record: bytes) -> tuple[GitPath, bool]:
    """Decode a path record; report whether git marked it as a directory."""
    text = decode_path(record)
    return GitPath.parse(text), text.endswith("/")


def parse_status_z(raw: bytes) -> tuple[StatusEntry, ...]:
    """Parse ``status --porcelain=v1 -z``: ``XY path\\0``, renames ``XY new\\0orig\\0``."""
    entries: list[StatusEntry] = []
    records = _records(raw)
    for record in records:
        xy = record[:2].decode("ascii")
        path, is_directory = _path(record[3:])
        orig: GitPath | None = None
        if _TWO_PATH_LETTERS & set(xy):
            orig = _path(_next_record(records, record))[0]
        entries.append(StatusEntry(xy=xy, path=path, orig_path=orig, is_directory=is_directory))
    return tuple(entries)


def parse_name_status_z(raw: bytes) -> tuple[NameStatusEntry, ...]:
    """Parse ``diff --name-status -z``: ``S\\0path\\0``, renames/copies ``R100\\0old\\0new\\0``."""
    entries: list[NameStatusEntry] = []
    records = _records(raw)
    for record in records:
        status = record.decode("ascii")
        first = _path(_next_record(records, record))[0]
        if status[:1] in _TWO_PATH_LETTERS:
            entries.append(NameStatusEntry(status=status, path=_path(_next_record(records, record))[0], orig_path=first))
        else:
            entries.append(NameStatusEntry(status=status, path=first))
    return tuple(entries)


def parse_paths_z(raw: bytes) -> tuple[GitPath, ...]:
    """Parse a plain ``-z`` path list, in git's order."""
    return tuple(_path(record)[0] for record in _records(raw))


def parse_index_z(raw: bytes, *, tags: bool = False) -> tuple[IndexEntry, ...]:
    """Parse ``ls-files [-v] --stage -z``: ``[tag SP] mode SP oid SP stage TAB path\\0``."""
    entries: list[IndexEntry] = []
    for record in _records(raw):
        meta, _, path = record.partition(b"\t")
        fields = meta.decode("ascii").split(" ")
        tag = fields.pop(0) if tags else None
        mode, oid, stage = fields
        entries.append(IndexEntry(mode=mode, oid=oid, stage=int(stage), path=_path(path)[0], tag=tag))
    return tuple(entries)


def _count(text: str) -> int | None:
    return None if text == _BINARY_COUNT else int(text)


def parse_numstat_z(raw: bytes) -> tuple[NumstatEntry, ...]:
    """Parse ``diff --numstat -z --no-renames``: ``added TAB deleted TAB path\\0``."""
    entries: list[NumstatEntry] = []
    for record in _records(raw):
        added, deleted, path = record.split(b"\t", 2)
        entries.append(NumstatEntry(added=_count(added.decode("ascii")), deleted=_count(deleted.decode("ascii")), path=_path(path)[0]))
    return tuple(entries)


def parse_tree_z(raw: bytes) -> tuple[TreeEntry, ...]:
    """Parse ``ls-tree -z``: ``mode SP type SP oid TAB path\\0``."""
    entries: list[TreeEntry] = []
    for record in _records(raw):
        meta, _, path = record.partition(b"\t")
        mode, kind, oid = meta.decode("ascii").split(" ")
        entries.append(TreeEntry(mode=mode, type=kind, oid=oid, path=_path(path)[0]))
    return tuple(entries)


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def _git(
    cwd: Path,
    args: Sequence[str],
    pathspecs: Sequence[str],
    *,
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> bytes:
    """Run a listing; literal pathspecs unless *glob*.

    ``--`` always ends the revisions, so a file named like a branch is never
    read as one (git would otherwise fail with "ambiguous argument").
    """
    prefix = ("--literal-pathspecs",) if pathspecs and not glob else ()
    return run_git(cwd, *prefix, *args, "--", *pathspecs, env=env, timeout=timeout).stdout


def status_entries(
    cwd: Path,
    *,
    pathspecs: Sequence[str] = (),
    untracked: str | None = "normal",
    ignored: bool = False,
    optional_locks: bool = True,
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[StatusEntry, ...]:
    """What is staged, modified, untracked (and optionally ignored) in the checkout at *cwd*.

    Args:
        untracked: ``"no"``, ``"normal"`` (a new directory is one collapsed
            ``?? dir/`` entry), ``"all"`` (every untracked file), or ``None``
            to pass no flag so the repository's ``status.showUntrackedFiles``
            decides.
        ignored: Include ignored entries (``!!``); an ignored directory is
            reported collapsed as ``!! dir/``.
        optional_locks: ``False`` passes ``--no-optional-locks`` so a
            read-only probe never refreshes (writes) the index.
    """
    if untracked is not None and untracked not in _UNTRACKED_MODES:
        raise ValueError(f"untracked must be None or one of {sorted(_UNTRACKED_MODES)}, got {untracked!r}")
    args = [] if optional_locks else ["--no-optional-locks"]
    args += ["status", "--porcelain=v1", "-z"]
    if untracked is not None:
        args.append(f"--untracked-files={untracked}")
    if ignored:
        args.append("--ignored")
    return parse_status_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout))


def tree_paths(
    cwd: Path,
    ref: str,
    *,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> frozenset[GitPath]:
    """Every file path tracked in *ref*'s tree (recursive)."""
    raw = _git(cwd, ["ls-tree", "--full-tree", "-r", "--name-only", "-z", ref], pathspecs, glob=glob, env=env, timeout=timeout)
    return frozenset(parse_paths_z(raw))


def tree_entry(cwd: Path, ref: str, path: str, *, env: Env = None, timeout: float | None = None) -> TreeEntry | None:
    """The entry for exactly *path* in *ref*'s tree, or ``None`` when *ref* has no such path."""
    wanted = GitPath.parse(path)
    entries = parse_tree_z(_git(cwd, ["ls-tree", "--full-tree", "-z", ref], (str(wanted),), env=env, timeout=timeout))
    return next((entry for entry in entries if entry.path == wanted), None)


def tree_entries(
    cwd: Path,
    ref: str,
    *,
    pathspecs: Sequence[str],
    env: Env = None,
    timeout: float | None = None,
) -> tuple[TreeEntry, ...]:
    """The entries of *ref*'s tree matching the literal *pathspecs*, in one ``ls-tree`` call.

    A pathspec *ref* has no entry for is simply absent from the result.
    """
    return parse_tree_z(_git(cwd, ["ls-tree", "--full-tree", "-z", ref], pathspecs, env=env, timeout=timeout))


def _diff_args(flag: str, revs: Sequence[str], *, cached: bool, renames: bool, diff_filter: str | None) -> list[str]:
    args = [*_REPO_RELATIVE_DIFF, "diff", flag, "-z", "-M" if renames else "--no-renames"]
    if cached:
        args.append("--cached")
    if diff_filter is not None:
        args.append(f"--diff-filter={diff_filter}")
    return [*args, *revs]


def changed_paths(
    cwd: Path,
    *revs: str,
    cached: bool = False,
    renames: bool = False,
    diff_filter: str | None = None,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[GitPath, ...]:
    """Paths that differ between *revs* / the index / the worktree (``git diff`` semantics), in git's order.

    With *renames* git detects renames and lists only the new path of each;
    without it a rename is a delete plus an add, so both paths are listed.
    """
    args = _diff_args("--name-only", revs, cached=cached, renames=renames, diff_filter=diff_filter)
    return parse_paths_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout))


def changed_entries(
    cwd: Path,
    *revs: str,
    cached: bool = False,
    renames: bool = False,
    diff_filter: str | None = None,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[NameStatusEntry, ...]:
    """Like :func:`changed_paths`, with each path's status (and source path when *renames*)."""
    args = _diff_args("--name-status", revs, cached=cached, renames=renames, diff_filter=diff_filter)
    return parse_name_status_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout))


def numstat_entries(
    cwd: Path,
    *revs: str,
    cached: bool = False,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[NumstatEntry, ...]:
    """Added/deleted line counts per changed path (renames split into delete + add)."""
    args = _diff_args("--numstat", revs, cached=cached, renames=False, diff_filter=None)
    return parse_numstat_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout))


def commit_paths(
    cwd: Path,
    commit: str,
    *,
    first_parent: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[GitPath, ...]:
    """Paths *commit* changed (renames split into delete + add).

    A merge commit lists nothing by default (git shows a combined diff); pass
    *first_parent* to list what the merge brought in relative to its first parent.
    """
    args = [*_REPO_RELATIVE_DIFF, "show", "--name-only", "--format=", "-z", "--no-renames"]
    if first_parent:
        args += ["--first-parent", "-m"]
    return parse_paths_z(_git(cwd, [*args, commit], (), env=env, timeout=timeout))


def log_paths(
    cwd: Path,
    rev_range: str,
    *,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[GitPath, ...]:
    """Every path touched by a commit in *rev_range* (renames split), first-seen order, no duplicates."""
    args = [*_REPO_RELATIVE_DIFF, "log", "-z", "--name-only", "--format=", "--no-renames", rev_range]
    return tuple(dict.fromkeys(parse_paths_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout))))


def tracked_paths(
    cwd: Path,
    *,
    pathspecs: Sequence[str] = (),
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[GitPath, ...]:
    """Paths tracked in the index (under *cwd* when it is a subdirectory, as ``git ls-files`` scopes)."""
    return parse_paths_z(_git(cwd, ["ls-files", "--full-name", "-z"], pathspecs, glob=glob, env=env, timeout=timeout))


def index_entries(
    cwd: Path,
    *,
    pathspecs: Sequence[str] = (),
    tags: bool = False,
    glob: bool = False,
    env: Env = None,
    timeout: float | None = None,
) -> tuple[IndexEntry, ...]:
    """Index records (mode, object id, stage, path; plus the ``ls-files -v`` tag when *tags*)."""
    args = ["ls-files", "--full-name", "-v", "--stage", "-z"] if tags else ["ls-files", "--full-name", "--stage", "-z"]
    return parse_index_z(_git(cwd, args, pathspecs, glob=glob, env=env, timeout=timeout), tags=tags)


def is_tracked(cwd: Path, path: str, *, env: Env = None, timeout: float | None = None) -> bool:
    """Whether *path* is tracked in the index (a directory counts when a file under it is).

    Raises:
        GitCommandError: git failed for a reason other than "not tracked".
    """
    args = ("--literal-pathspecs", "ls-files", "--error-unmatch", "--", path)
    result = run_git(cwd, *args, env=env, timeout=timeout, check=False)
    if result.returncode not in (0, _NOT_TRACKED_EXIT):
        raise GitCommandError(argv=args, cwd=cwd, returncode=result.returncode, stderr=result.stderr.decode("utf-8", "replace"))
    return result.returncode == 0
