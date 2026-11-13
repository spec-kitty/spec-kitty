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

from kernel.ancestor_walk import find_ancestor, git_ceiling_dirs, iter_ancestors
from kernel.resolution import resolve_rejecting_loops

__all__ = [
    "AnchorKind",
    "GitAnchor",
    "UNRESOLVABLE_START_REASON",
    "checkout_root_containing",
    "checkout_root_in_spelling",
    "find_git_anchor",
]

#: The reason on the verdict for a start folder whose path cannot be resolved. Its ``path`` is
#: that folder, not a ``.git``: the cause is the folder's own path (for example a symbolic-link
#: loop), so the repair is to fix that path, not to repair or remove a ``.git``.
UNRESOLVABLE_START_REASON: Final[str] = "a folder whose path cannot be resolved"

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
        return GitAnchor(AnchorKind.UNKNOWN, git_entry, "unreadable")
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
        return GitAnchor(AnchorKind.UNKNOWN, git_dir, "unreadable")
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
        return GitAnchor(AnchorKind.UNKNOWN, Path(start), UNRESOLVABLE_START_REASON)
    ceilings = git_ceiling_dirs(source, resolve_after_empty=False) - {resolved_start}
    for candidate in iter_ancestors(resolved_start, ceilings=ceilings):
        verdict = classify_git_entry(candidate / _GIT_DIR_NAME)
        if verdict.kind is not AnchorKind.RESIDUE:
            return verdict
    return None


def checkout_root_containing(path: Path) -> Path | None:
    """The git checkout (repository root checkout or linked worktree) that contains *path*.

    The nearest ancestor of *path* (inclusive) holding a ``.git`` entry of any kind: the
    repository root checkout has a ``.git`` *directory*, a linked worktree a ``.git`` *file*;
    both count. This is a containment question, not the identity classifier above: it never
    reads the entry, so residue is not walked past. It runs on the one ancestor walk
    (:func:`kernel.ancestor_walk.find_ancestor`, #7056), so it honours
    ``GIT_CEILING_DIRECTORIES`` and returns the **resolved** checkout (symbolic links
    followed, e.g. macOS ``/var`` -> ``/private/var``): compare it with resolved forms. The
    one exception is a *path* that cannot be resolved (e.g. a symbolic-link loop): the walk
    then runs over its lexical form and the answer is an unresolved ancestor. No
    subprocess. *path* need not exist; the walk starts at it either way.

    Returns:
        The checkout root (resolved, unless *path* could not be resolved), or ``None`` when
        no ancestor up to the ceiling holds a ``.git`` entry.
    """
    return find_ancestor(path, lambda candidate: (candidate / _GIT_DIR_NAME).exists())


def checkout_root_in_spelling(path: Path) -> Path | None:
    """The checkout that contains *path*, spelled as an ancestor of *path* itself (#7546, FR-001).

    :func:`checkout_root_containing` answers in resolved form. When *path* is spelled through
    a symbolic link, the answer is re-expressed as *path*'s own ancestor, so
    ``path.is_relative_to(answer)`` holds without mixing spellings. The answer stays the
    resolved checkout in three cases, all of them still a checkout that contains *path*'s
    resolved form: *path* cannot be resolved (a symbolic-link loop: the walk already ran over
    its lexical form), *path* is shallower than the checkout depth (a relative path), and the
    lexical ancestor does not resolve to the checkout.

    Returns:
        The checkout root, or ``None`` when no ancestor of *path* is a checkout.
    """
    holder = checkout_root_containing(path)
    if holder is None or path.is_relative_to(holder):
        return holder
    try:
        depth = len(resolve_rejecting_loops(path).relative_to(holder).parts)
    except (OSError, ValueError):
        return holder
    if depth >= len(path.parts):
        return holder
    lexical = path.parents[depth - 1] if depth else path
    return lexical if lexical.resolve() == holder else holder
