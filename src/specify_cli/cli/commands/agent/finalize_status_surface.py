"""Status-surface guard for a failed ``finalize-tasks`` run (FR-015/NFR-001, #5641).

``finalize-tasks`` seeds every work package as ``planned`` before its final
commit, and the transactional status writer makes one commit per seed on the
status surface: the coordination branch for ``coord`` / ``lanes_with_coord``,
the current branch for ``lanes`` / ``single_branch``, and P's branch for an
owned checkout. When the run then fails before the finalize commit lands,
restoring the Mission directory's bytes is not enough: the branch keeps the
seed commits, and a checkout whose status files were put back is dirty
against its own HEAD.

:class:`StatusSurfaceGuard` captures the surface before the run's first status
write (branch, tip, index tree and, when the status directory lies outside the
Mission directory snapshot, its bytes), records the tip once the run's status
writes are done (:meth:`StatusSurfaceGuard.recording`), and on failure restores
it:

* the branch moves back through :func:`specify_cli.git.ref_advance.restore_branch_ref`
  -- compare-and-swap against the tip this run recorded, never forced, and
  without ``resync_checkouts`` (a checkout hard-reset is reserved to
  ``consolidation/rollback.py``);
* the checkout's index is put back with ``git read-tree`` of the captured tree,
  which never touches the working tree (the ``core/mission_creation.py``
  precedent);
* the working-tree bytes are restored by the caller's byte snapshot, except
  for the files a kept commit changed (:meth:`StatusSurfaceGuard.kept_paths`),
  which stay as that commit left them -- and, when git cannot list them, every
  file under the status directory.

The branch is only ever moved back over commits this run provably made. A
branch that moved after this run's last status write is left alone, and so is a
range ``tip_before..tip_after`` that is not provably the run's own: every
commit in it must be a non-merge commit touching only this Mission's status
files (the event log and its snapshot) and the acceptance-matrix scaffold, the
only paths the run writes on the status surface, resolved from the directory
the guard was captured against. :meth:`StatusSurfaceGuard.restore` then returns
a :class:`StatusSurfaceLeftover` naming the branch and the commits it could not
undo. A commit that touches only those same files for the same Mission would be
indistinguishable from the run's own, so :meth:`StatusSurfaceGuard.recording`
holds the Mission's status lock (the one every status writer takes) for the
whole window: another process's status write waits until the window has closed,
and the compare-and-swap against ``tip_after`` protects every later commit.
Residual: a committer that takes no status lock (a plain ``git commit`` of the
Mission's status files), or one landing between :meth:`StatusSurfaceGuard.capture`
and the opening of the window, is still indistinguishable from the run's own
and is undone with them.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path

from specify_cli.acceptance.matrix import MATRIX_FILENAME
from specify_cli.git.ref_advance import RefRestoreError, restore_branch_ref
from specify_cli.status import (
    BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS,
    EVENTS_FILENAME,
    SNAPSHOT_FILENAME,
    feature_status_lock,
)

__all__ = ["StatusSurfaceGuard", "StatusSurfaceLeftover"]

logger = logging.getLogger(__name__)


def _git(cwd: Path, *args: str) -> str | None:
    """Stripped stdout of ``git <args>`` in ``cwd``, or ``None`` when git fails."""
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _own_status_paths(status_dir: Path, root: Path) -> frozenset[str]:
    """The checkout-relative files a ``finalize-tasks`` run writes on the status surface.

    Derived from ``status_dir`` (already resolved through the placement seam), so
    no Mission path is rebuilt here. Empty -- nothing is provably the run's own --
    when ``status_dir`` does not lie under ``root``.
    """
    try:
        relative = status_dir.resolve().relative_to(root.resolve())
    except ValueError:
        return frozenset()
    return frozenset((relative / name).as_posix() for name in (EVENTS_FILENAME, SNAPSHOT_FILENAME, MATRIX_FILENAME))


def _touches_only(root: Path, commit: str, own_paths: frozenset[str]) -> bool:
    """Whether ``commit`` changes at least one file and every file it changes is in ``own_paths``."""
    names = _git(root, "diff-tree", "--root", "-r", "--no-commit-id", "--name-only", "-z", commit)
    touched = {name for name in (names or "").split("\0") if name}
    return bool(touched) and touched <= own_paths


def _probe_dir(status_dir: Path) -> Path | None:
    """Where to ask git about ``status_dir``: itself, or its parent before the first write creates it.

    Never a further ancestor: above ``kitty-specs/`` a missing coordination
    worktree would resolve to the repository root checkout, the wrong surface.
    """
    for candidate in (status_dir, status_dir.parent):
        if candidate.is_dir():
            return candidate
    return None


@dataclass(frozen=True)
class StatusSurfaceLeftover:
    """What a failed run committed on the status surface and could not undo."""

    branch: str
    reason: str
    commits: tuple[str, ...] = ()

    def lines(self) -> list[str]:
        """Human-readable report lines (branch, reason, then one line per commit)."""
        head = f"status commits on {self.branch!r} were not undone: {self.reason}"
        return [head, *(f"  {commit}" for commit in self.commits)]

    def as_payload(self) -> dict[str, object]:
        """The JSON ``warning`` payload for ``--json`` callers."""
        return {
            "warning": "status_commits_not_undone",
            "branch": self.branch,
            "detail": self.reason,
            "commits": list(self.commits),
        }


@dataclass
class StatusSurfaceGuard:
    """Capture-then-restore of the status surface across one ``finalize-tasks`` run."""

    surface_root: Path | None = None
    branch: str | None = None
    tip_before: str | None = None
    index_tree: str | None = None
    tip_after: str | None = None
    own_paths: frozenset[str] = frozenset()
    status_dir: Path | None = None
    status_bytes: dict[Path, bytes] | None = field(default=None, repr=False)

    def capture(self, status_dir: Path, status_bytes: dict[Path, bytes] | None) -> None:
        """Record the surface before the run's first status write.

        ``status_bytes`` is the caller's byte snapshot of ``status_dir``, or
        ``None`` when the Mission directory snapshot already covers it.
        """
        self.status_dir = status_dir
        self.status_bytes = status_bytes
        cwd = _probe_dir(status_dir)
        probe = _git(cwd, "rev-parse", "--show-toplevel", "HEAD") if cwd is not None else None
        toplevel, _, tip = (probe or "").partition("\n")
        root = Path(toplevel) if toplevel and tip else None
        branch = _git(root, "symbolic-ref", "-q", "--short", "HEAD") if root is not None else None
        tree = _git(root, "write-tree") if root is not None and branch else None
        if not (root and branch and tip and tree):
            # Nothing to compare against later, so nothing to restore or report:
            # the restore stays inert, as the Mission-directory guard does for an
            # unreadable snapshot.
            logger.warning("finalize atomicity: status surface at %s is not a checkout on a branch with a readable HEAD and index", status_dir)
            return
        self.surface_root, self.branch, self.tip_before, self.index_tree = root, branch, tip, tree
        self.own_paths = _own_status_paths(status_dir, root)

    @contextmanager
    def recording(self) -> Iterator[None]:
        """Wrap the run's status writes; the tip is recorded when the window closes, even on an error.

        The Mission's status lock is held for the whole window, and the tip is
        read before it is released, so no other process's status write lands
        inside the window or between its last commit and the recorded tip. A
        lock that cannot be had within the bounded wait fails the run before
        its first status commit. The commits in ``tip_before..tip_after`` are
        still not assumed to be the run's own: :meth:`restore` proves it before
        it moves the branch back.
        """
        root, status_dir = self.surface_root, self.status_dir
        # Keyed on the status directory's name: the key every writer of this surface locks on,
        # under the git common dir all of the Mission's checkouts share.
        lock = (
            feature_status_lock(root, status_dir.name, timeout=BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS)
            if root is not None and status_dir is not None
            else nullcontext()
        )
        with lock:
            try:
                yield
            finally:
                if root is not None and self.branch is not None:
                    self.tip_after = _git(root, "rev-parse", "--verify", f"refs/heads/{self.branch}")

    def restore(self) -> StatusSurfaceLeftover | None:
        """Undo this run's status commits; ``None`` when nothing of this run is left behind.

        When the branch is kept and the files its kept commits changed cannot be
        listed, the leftover says the Mission files under the status directory
        were left as they are (:meth:`kept_paths`).
        """
        leftover = self._restore_branch()
        if leftover is not None and self.kept_paths() is None:
            reason = f"{leftover.reason}; the files the kept commits changed could not be listed, so the files under {self.status_dir} were left as they are"
            return replace(leftover, reason=reason)
        return leftover

    def _restore_branch(self) -> StatusSurfaceLeftover | None:
        """Move the branch and index back when this run's commits are provably its own."""
        root, branch, before, ours = self.surface_root, self.branch, self.tip_before, self.tip_after
        if root is None or branch is None or before is None:
            return None  # never captured: the run failed before its first status write
        current = _git(root, "rev-parse", "--verify", f"refs/heads/{branch}")
        if current == before or ours == before:
            return None  # this run made no status commit (any move is someone else's)
        if ours is None:
            # The branch moved, but the tip this run left it at was never read, so
            # no commit can be told apart as ours: report instead of dropping it.
            logger.warning("finalize atomicity: tip of %s after the status writes is unknown; %s..%s left as is", branch, before[:12], (current or "?")[:12])
            return StatusSurfaceLeftover(
                branch=branch,
                reason=f"the tip of the branch after this run's status writes could not be read, so every commit since {before[:12]} was left as is",
            )
        if current != ours:
            return _leftover(root, branch, before, ours, "the branch moved after this run's last status commit, so it was left as is")
        unproven = self._unproven_ownership(root, before, ours)
        if unproven is not None:
            return _leftover(root, branch, before, ours, f"{unproven}, so the branch was left as is; a commit this run did not make may be among them")
        try:
            restore_branch_ref(root, branch, before, expected_current_sha=ours)
        except RefRestoreError as exc:
            return _leftover(root, branch, before, ours, str(exc))
        still_checked_out = _git(root, "symbolic-ref", "-q", "--short", "HEAD") == branch
        if still_checked_out and self.index_tree is not None and _git(root, "read-tree", self.index_tree) is None:
            repair = f"git -C {root} read-tree {self.index_tree}"
            return StatusSurfaceLeftover(
                branch=branch,
                reason=f"the branch was restored to {before[:12]} but the index of {root} was not; run `{repair}`",
            )
        return None

    def _unproven_ownership(self, root: Path, before: str, ours: str) -> str | None:
        """Why ``before..ours`` cannot be shown to be this run's own commits, or ``None`` when it can.

        Fails closed: a git probe that fails counts as not proven.
        """
        span = f"the commits between {before[:12]} and {ours[:12]}"
        if _git(root, "merge-base", "--is-ancestor", before, ours) is None:
            return f"{span} could not be read back as one line of history"
        listing = _git(root, "rev-list", "--parents", f"{before}..{ours}")
        if listing is None:
            return f"{span} could not be listed"
        for line in listing.splitlines():
            commit, *parents = line.split()
            if len(parents) != 1:
                return f"{span} include a merge commit ({commit[:12]})"
            if not _touches_only(root, commit, self.own_paths):
                return f"{span} include {commit[:12]}, which is not limited to this Mission's status files"
        return None

    def kept_paths(self) -> frozenset[Path] | None:
        """Files changed by the commits left on the branch, which the caller's byte restore must not touch.

        Empty when the branch is back at ``tip_before`` (nothing was kept) or
        when the guard captured nothing; a rewrite of a file that a kept commit
        changed would leave the checkout modified against its own HEAD, or
        delete a file that commit added. ``None`` when the branch was kept but
        git cannot list the change: the caller must then leave every file under
        :attr:`status_dir` as it is, never fall back to the rewrite.
        """
        if self.surface_root is None or self.branch is None or self.tip_before is None or self.is_at_tip_before():
            return frozenset()
        names = _git(self.surface_root, "diff", "--name-only", "-z", self.tip_before, f"refs/heads/{self.branch}")
        if names is None:
            return None
        return frozenset((self.surface_root / name).resolve() for name in names.split("\0") if name)

    def is_at_tip_before(self) -> bool:
        """Whether the captured branch points where it did before the run (status bytes may then be put back)."""
        if self.surface_root is None or self.branch is None:
            return False
        return _git(self.surface_root, "rev-parse", "--verify", f"refs/heads/{self.branch}") == self.tip_before


def _leftover(root: Path, branch: str, before: str, ours: str, reason: str) -> StatusSurfaceLeftover:
    """Name this run's own commits, ``before..ours`` (never a foreign commit on top of them)."""
    log = _git(root, "log", "--format=%h %s", f"{before}..{ours}")
    return StatusSurfaceLeftover(branch=branch, reason=reason, commits=tuple(log.splitlines()) if log else ())
