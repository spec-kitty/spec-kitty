"""The ONE shared, tested authority for charter-write checkout safety (#4785 Finding 3).

Before this module, root resolution for charter write commands
(``generate``/``synthesize``/``resynthesize``/``activate``) was a **3-way
parallel authority** (``find_repo_root``, ``get_main_repo_root``, a local
``_is_inside_git_worktree`` in ``generate.py``), none of them the kernel
canonical :mod:`kernel.git_topology`. Because ``find_repo_root`` /
``get_main_repo_root`` follow a linked worktree's ``.git`` pointer back to the
PRIMARY checkout (by contract -- and that contract is depended on elsewhere,
so it is NOT changed here, C-002), a charter write issued from inside a
linked worktree silently landed in the PRIMARY checkout instead of the
worktree the maintainer was standing in.

:func:`resolve_charter_write_root` is the single, tested replacement: it
**fails closed** (raises :class:`LinkedWorktreeCharterWriteError`) when
invoked from a linked git worktree, so no charter write command wired to it
can produce that split-brain. It reuses the kernel :mod:`kernel.git_topology`
probe (git-dir vs git-common-dir) -- the canonical primitive already
consumed by ~20 other call sites (C-003) -- rather than adding a fourth root
resolution authority or a ``.worktrees/`` path-substring match (NFR-003).

Callers: WP03 (``activate``/``deactivate``) and WP04 (``synthesize``) wire
their write paths through this helper and map
:class:`LinkedWorktreeCharterWriteError` to a non-zero CLI exit.
"""

from __future__ import annotations

from pathlib import Path

from kernel.git_topology import (
    GitTopologyError,
    git_common_dir,
    git_toplevel,
)

_REMEDY = "use a repository-root checkout or dedicated clone for charter authoring"


class CharterWriteRootError(RuntimeError):
    """Base class for charter-write-root resolution failures."""


class LinkedWorktreeCharterWriteError(CharterWriteRootError):
    """Raised when a charter write is attempted from inside a linked git worktree.

    Carries the actionable remedy message (verbatim, per Contract C3 /
    FR-006): "use a repository-root checkout or dedicated clone for charter
    authoring". Callers should map this to a non-zero CLI exit without
    falling back to any other resolved root -- the whole point of failing
    closed is that no charter write lands anywhere on this path.
    """

    def __init__(self, start: Path) -> None:
        self.start = start
        super().__init__(f"Refusing charter write from linked git worktree {start}: {_REMEDY}.")


def resolve_charter_write_root(start: Path) -> Path:
    """Resolve the safe checkout root for a charter write command.

    Detection (Contract C3 / data-model.md checkout-topology table) compares
    the kernel :mod:`kernel.git_topology` probes for ``start``:

    * **Repository-root checkout / dedicated clone** -- ``git_common_dir(start)
      .parent == git_toplevel(start)``. Returns the toplevel (the checkout
      root charter writes should target).
    * **Linked git worktree** -- the two differ (a linked worktree's
      common-dir points at the PRIMARY checkout's shared ``.git``, while its
      own toplevel is the worktree itself). Raises
      :class:`LinkedWorktreeCharterWriteError`.
    * **git-absent / not-a-repo** -- either probe raising
      :class:`~kernel.git_topology.GitTopologyError` (its
      :class:`~kernel.git_topology.GitTopologyUnavailableError` or
      :class:`~kernel.git_topology.NotAGitRepositoryError` subclasses)
      degrades safely: treated as not-a-linked-worktree, returning the
      resolved ``start`` with no raise.

    Never uses a ``.worktrees/`` path-substring match (NFR-003): a primary
    checkout whose own path happens to contain ``.worktrees`` is not flagged.
    """
    try:
        toplevel = git_toplevel(start)
        common_dir = git_common_dir(start)
    except GitTopologyError:
        return start.resolve()

    if common_dir.parent != toplevel:
        raise LinkedWorktreeCharterWriteError(start)

    return toplevel


# ``LinkedWorktreeCharterWriteError`` is deliberately NOT re-exported: the five
# charter-write command handlers (activate/deactivate/generate/synthesize/
# resynthesize) catch the BASE ``CharterWriteRootError`` (more robust -- any
# future subclass fails closed the same way), so the subclass has no
# cross-module importer. It stays a public, tested class used within this
# module (raised by :func:`resolve_charter_write_root`); dropping it from
# ``__all__`` keeps the dead-symbol gate honest without hiding the type.
__all__ = [
    "CharterWriteRootError",
    "resolve_charter_write_root",
]
