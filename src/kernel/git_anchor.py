"""Is this ``.git`` a repository? The one classifier (#7262).

A Mission's identity reader (``specify_cli.mission_metadata.read_tracked_meta``) asks git what
it holds for ``meta.json``. When git answers "not a git repository", that answer is only
trustworthy if nothing above the folder could be a repository git failed to open: otherwise a
new identity would be minted over one git still holds (#6673, NFR-002). Before this module that
question was answered three ways (#7093, #7084, #7131); the operator ruling on #7262
(2026-11-06, *refuse on unknown*) fixes one answer, and this module is its only owner.

Each ``.git`` entry is one of three kinds:

* :attr:`AnchorKind.REPOSITORY` -- a ``.git`` pointer *file* (a worktree, submodule or
  separate-git-dir marker), or a ``.git`` *directory* holding a regular ``HEAD`` file. Git may
  hold a copy there; never mint over it.
* :attr:`AnchorKind.RESIDUE` -- absent, an empty directory, or a directory holding only
  ``hooks/`` and ``spec-kitty-locks/`` (the residue Spec Kitty's own fallbacks used to leave,
  #5756). Nothing can be stored there; it is safe to ignore.
* :attr:`AnchorKind.UNKNOWN` -- anything else: a directory with no ``HEAD`` but other contents
  (a repository that lost its ``HEAD``), a ``HEAD`` that is a symlink (dangling or not) or a
  directory, a ``.git`` symlink, an entry that cannot be read or disappears while it is read,
  or an explicit Git repository/index/object redirect in the environment. The caller refuses
  and names the ``.git`` path: repair the repository, or remove the residue.

  This is deliberately stricter than git in two places, both toward refusing: a *live*
  symlinked ``HEAD`` or ``.git`` is a repository to git, but telling live from dangling would
  cost a ``stat`` per entry beyond NFR-002; and a ``head`` entry on a case-insensitive
  filesystem is read as "other contents".

Cost (#6673 NFR-002): one ``lstat`` of the entry and, for a directory, one immediate listing
(``os.scandir``, whose entry types come from the listing itself). No child ``stat``, no
recursion, no git invocation. The upward walk is :func:`kernel.ancestor_walk.iter_ancestors`,
with :func:`kernel.ancestor_walk.git_ceiling_dirs`'s negative-Git-evidence reading: entries
after an empty entry stay unresolved, lossy spellings are dropped, and a start-equal entry
is removed because git ignores it for a search starting there. Stopping before git would
read a repository git found as "nothing here" and mint over it (#6673 NFR-002).

It lives at the ``kernel`` floor beside the ancestor walk so any layer can ask, and it imports
only the standard library and that walk.
"""

from __future__ import annotations

import enum
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from kernel.ancestor_walk import git_ceiling_dirs, iter_ancestors
from kernel.resolution import resolve_rejecting_loops

__all__ = [
    "AnchorKind",
    "GitAnchor",
    "find_git_anchor",
]

#: The directory name git looks for.
_GIT_DIR_NAME: Final[str] = ".git"

#: Entries a non-repository ``.git`` directory may hold and still be harmless residue (#7084).
_RESIDUE_ENTRIES: Final[frozenset[str]] = frozenset({"hooks", "spec-kitty-locks"})

#: The file that makes a ``.git`` directory a repository to git.
_HEAD: Final[str] = "HEAD"

#: Environment variables that point git at a repository, index or object store elsewhere. When
#: one is set and git still refuses, the ``.git`` names on disk cannot rule a repository out.
GIT_REDIRECT_ENV: Final[tuple[str, ...]] = (
    "GIT_DIR",
    "GIT_COMMON_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
)


class AnchorKind(enum.Enum):
    """What a ``.git`` entry is, for the question "may git hold a copy here?"."""

    REPOSITORY = "repository"
    RESIDUE = "residue"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class GitAnchor:
    """The verdict on one ``.git`` entry (or on the walk above a folder).

    ``path`` is the ``.git`` entry the verdict is about (``None`` for a walk that found nothing,
    or for an environment redirect, which names no path). ``reason`` is a short, stable,
    operator-readable phrase saying why: it is printed in refusal notices and never contains
    git's own output.
    """

    kind: AnchorKind
    path: Path | None
    reason: str


def classify_git_entry(git_entry: Path) -> GitAnchor:
    """Classify one ``.git`` entry as a repository, harmless residue, or unknown.

    Args:
        git_entry: The ``.git`` path itself (``<dir>/.git``), not its parent.

    Returns:
        The verdict. Never raises for a filesystem error: an entry that cannot be read is
        :attr:`AnchorKind.UNKNOWN`.
    """
    try:
        mode = git_entry.lstat().st_mode
    except FileNotFoundError:
        return GitAnchor(AnchorKind.RESIDUE, git_entry, "absent")
    except OSError:
        return GitAnchor(AnchorKind.UNKNOWN, git_entry, "cannot be read")
    if stat.S_ISREG(mode):
        return GitAnchor(AnchorKind.REPOSITORY, git_entry, "a pointer file to a repository")
    if stat.S_ISLNK(mode):
        return GitAnchor(AnchorKind.UNKNOWN, git_entry, "a symbolic link")
    if not stat.S_ISDIR(mode):
        return GitAnchor(AnchorKind.UNKNOWN, git_entry, "neither a file nor a directory")
    return _classify_git_directory(git_entry)


def _classify_git_directory(git_dir: Path) -> GitAnchor:
    """Classify a ``.git`` directory from one immediate listing."""
    head_is_file: bool | None = None
    other = False
    try:
        with os.scandir(git_dir) as entries:
            for entry in entries:
                if entry.name == _HEAD:
                    head_is_file = entry.is_file(follow_symlinks=False)
                elif entry.name not in _RESIDUE_ENTRIES:
                    other = True
    except OSError:
        # Unreadable, or removed between the lstat and the listing.
        return GitAnchor(AnchorKind.UNKNOWN, git_dir, "cannot be read")
    if head_is_file:
        return GitAnchor(AnchorKind.REPOSITORY, git_dir, "a repository directory")
    if head_is_file is not None:
        return GitAnchor(AnchorKind.UNKNOWN, git_dir, "a repository whose HEAD is not a regular file")
    if other:
        return GitAnchor(AnchorKind.UNKNOWN, git_dir, "a directory without HEAD that holds more than hooks and locks")
    return GitAnchor(AnchorKind.RESIDUE, git_dir, "empty, or only hooks and locks")


def find_git_anchor(start: Path, *, environ: Mapping[str, str] | None = None) -> GitAnchor | None:
    """The nearest ``.git`` at or above *start* that is not residue, or ``None`` when there is none.

    Walks with :func:`kernel.ancestor_walk.iter_ancestors`, so the walk stops at
    ``GIT_CEILING_DIRECTORIES``. Residue is walked past: git itself walks past a ``.git`` it
    cannot use, so a real repository above it may still own the folder. An explicit
    repository/index/object redirect in *environ* is :attr:`AnchorKind.UNKNOWN` before any
    filesystem read, because the names on disk cannot rule out a store named elsewhere.

    Args:
        start: The folder to ask about.
        environ: The environment to read redirects and ceilings from. Defaults to
            :data:`os.environ`.

    Returns:
        The first repository or unknown verdict, nearest first; ``None`` when every ``.git`` up
        to the ceiling is absent or residue. A start path that cannot be resolved is unknown:
        it cannot prove that no repository holds the Mission's identity.
    """
    source = os.environ if environ is None else environ
    redirect = next((name for name in GIT_REDIRECT_ENV if name in source), None)
    if redirect is not None:
        return GitAnchor(AnchorKind.UNKNOWN, None, f"`{redirect}` points git at a repository elsewhere")
    try:
        resolved_start = resolve_rejecting_loops(start)
    except OSError:
        return GitAnchor(AnchorKind.UNKNOWN, Path(start) / _GIT_DIR_NAME, "cannot be read")
    ceilings = git_ceiling_dirs(source, resolve_after_empty=False) - {resolved_start}
    for candidate in iter_ancestors(resolved_start, ceilings=ceilings):
        verdict = classify_git_entry(candidate / _GIT_DIR_NAME)
        if verdict.kind is not AnchorKind.RESIDUE:
            return verdict
    return None
