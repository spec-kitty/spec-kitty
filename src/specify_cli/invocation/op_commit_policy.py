"""Commit-or-skip policy for the Op-record auto-commit (#6410).

``ProfileInvocationExecutor._commit_op_record`` force-adds the record it
commits, so on its own it lands an ``op(...)`` commit on whatever branch is
checked out, even in a repository that never tracks Op records or that
gitignores ``kitty-ops/``. This module answers the two questions that decide
whether the commit should happen at all:

* Is the exact path about to be committed gitignored? (``is_path_ignored``)
* Does the primary branch track any Op-record-shaped file?
  (``resolve_primary_refs`` + ``primary_tracks_op_records``)

The primary branch is resolved WITHOUT current-branch bias: when nothing
resolves, the answer is "unresolved", never the checked-out branch. Falling
back to the current branch would let the first ``op(...)`` commit on an issue
branch satisfy the predicate for the next close on that same branch. That is
why ``core.git_ops.resolve_primary_branch`` is not reused: even with
``bias=False`` its last resort is the biased cascade, which returns the
checked-out branch.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePath

from kernel.git.listing import tree_paths
from kernel.git.runner import GitCommandError
from specify_cli.core.git_ops import COMMON_PRIMARY_BRANCHES

__all__ = [
    "LIFECYCLE_RECORDS",
    "OP_RECORDS",
    "OpCommitProbeError",
    "PrimaryTracking",
    "ROOT_KITTY_OPS_RECORD_RE",
    "RecordKind",
    "op_commit_skip_reason",
    "probe_primary_tracking",
]

_ULID = r"[0-9A-HJKMNP-TV-Z]{26}"
#: Op-record path ``kitty-ops/<26-char ULID>.jsonl``, unanchored: the one definition every matcher derives from.
OP_RECORD_PATH = rf"kitty-ops/{_ULID}\.jsonl"
#: WP lifecycle-record path ``kitty-ops/lifecycle/<26-char ULID>.json`` (#7346), unanchored.
LIFECYCLE_RECORD_PATH = rf"kitty-ops/lifecycle/{_ULID}\.json"
#: Op-record shape at any depth. Same pattern as the one ``coordination/coherence.py`` uses; a test pins that the two agree.
OP_RECORD_PATH_RE = re.compile(rf"(?:^|/){OP_RECORD_PATH}$")
LIFECYCLE_RECORD_PATH_RE = re.compile(rf"(?:^|/){LIFECYCLE_RECORD_PATH}$")
#: A repository-root Op or lifecycle record; match with ``fullmatch`` (``$`` would accept a trailing newline).
ROOT_KITTY_OPS_RECORD_RE = re.compile(rf"{OP_RECORD_PATH}|{LIFECYCLE_RECORD_PATH}")

_GIT_TIMEOUT_SECONDS = 30
_EVENTS_PATHSPEC = "kitty-ops/"
_ORIGIN_PREFIX = "origin/"
_UNRESOLVED_PRIMARY = "primary branch unresolved"


class OpCommitProbeError(RuntimeError):
    """A git probe needed for the commit-or-skip decision failed."""


@dataclass(frozen=True)
class RecordKind:
    """A kind of ``kitty-ops/`` record the auto-commit decides about (#6410, #7346)."""

    label: str
    pathspec: str
    pattern: re.Pattern[str]


#: Op records, ``kitty-ops/<ULID>.jsonl`` (#6410).
OP_RECORDS = RecordKind(label="Op records", pathspec=_EVENTS_PATHSPEC, pattern=OP_RECORD_PATH_RE)
#: WP lifecycle records, ``kitty-ops/lifecycle/<ULID>.json``, closed by the doctor sweep (#7346).
LIFECYCLE_RECORDS = RecordKind(label="lifecycle records", pathspec="kitty-ops/lifecycle/", pattern=LIFECYCLE_RECORD_PATH_RE)


@dataclass(frozen=True)
class PrimaryTracking:
    """Whether the primary branch tracks records of ``kind``, and which ref was asked."""

    tracked: bool
    primary: str | None  # short branch name, ``None`` when unresolved
    kind: RecordKind = OP_RECORDS


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise OpCommitProbeError(f"git {args[0]} could not run: {exc!r}") from exc


def _ref_exists(repo_root: Path, ref: str) -> bool:
    return _git(repo_root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}").returncode == 0


def _existing_refs(repo_root: Path, name: str) -> tuple[str, ...]:
    candidates = (f"refs/heads/{name}", f"refs/remotes/origin/{name}")
    return tuple(ref for ref in candidates if _ref_exists(repo_root, ref))


def resolve_primary_refs(repo_root: Path) -> tuple[str, ...]:
    """Return the existing refs of the primary branch (local, then ``origin``).

    Resolution: ``origin/HEAD`` (when it names a branch that exists), then the
    first of ``main``/``master``/``develop`` existing locally or on ``origin``.
    Returns ``()`` when nothing resolves; it never falls back to the checked-out
    branch (FR-006). Each ref is probed at most once, so this costs at most 9
    git calls: 1 ``symbolic-ref``, 2 for a dangling ``origin/HEAD`` name, 6 for
    the ladder (NFR-001).
    """
    head = _git(repo_root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    probed: str | None = None
    if head.returncode == 0:
        probed = head.stdout.strip().removeprefix(_ORIGIN_PREFIX) or None
        refs = _existing_refs(repo_root, probed) if probed else ()
        if refs:
            return refs
    for candidate in COMMON_PRIMARY_BRANCHES:
        if candidate == probed:
            continue
        refs = _existing_refs(repo_root, candidate)
        if refs:
            return refs
    return ()


def primary_tracks_op_records(repo_root: Path, refs: tuple[str, ...], kind: RecordKind = OP_RECORDS) -> bool:
    """True when any of ``refs`` tracks a record of ``kind`` (default: ``kitty-ops/<ULID>.jsonl``)."""
    for ref in refs:
        try:
            paths = tree_paths(repo_root, ref, pathspecs=(kind.pathspec,), timeout=_GIT_TIMEOUT_SECONDS)
        except GitCommandError as exc:
            raise OpCommitProbeError(f"listing {kind.pathspec} on {ref} failed: {exc}") from exc
        if any(kind.pattern.search(path.as_posix()) for path in paths):
            return True
    return False


def probe_primary_tracking(repo_root: Path, kind: RecordKind = OP_RECORDS) -> PrimaryTracking:
    """Resolve the primary branch and ask whether it tracks records of ``kind``."""
    refs = resolve_primary_refs(repo_root)
    if not refs:
        return PrimaryTracking(tracked=False, primary=None, kind=kind)
    primary = refs[0].removeprefix("refs/heads/").removeprefix("refs/remotes/origin/")
    return PrimaryTracking(tracked=primary_tracks_op_records(repo_root, refs, kind), primary=primary, kind=kind)


def is_path_ignored(repo_root: Path, rel_path: PurePath | str) -> bool:
    """True when ``rel_path`` is gitignored, even if it is already tracked.

    ``--no-index`` is what makes a tracked-but-ignored path report as ignored;
    plain ``git check-ignore`` answers "not ignored" for any tracked path.
    """
    posix = PurePath(rel_path).as_posix()
    result = _git(repo_root, "check-ignore", "-q", "--no-index", "--", posix)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise OpCommitProbeError(f"git check-ignore {posix} failed: {result.stderr.strip()}")


def op_commit_skip_reason(repo_root: Path, rel_path: PurePath | str, *, tracking: PrimaryTracking) -> str | None:
    """Reason to skip the Op-record auto-commit, or ``None`` to commit it."""
    posix = PurePath(rel_path).as_posix()
    if is_path_ignored(repo_root, posix):
        return f"{posix} matches an ignore rule in this repository"
    if not tracking.tracked:
        kind = tracking.kind
        if tracking.primary is None:
            return f"{_UNRESOLVED_PRIMARY}, so it cannot be shown to track {kind.label}"
        return f"the primary branch ({tracking.primary}) tracks no {kind.label} under {kind.pathspec}"
    return None
