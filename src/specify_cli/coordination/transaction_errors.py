"""Error hierarchy for :mod:`specify_cli.coordination.transaction`.

Extracted VERBATIM from ``transaction.py`` (WP08 campsite split, NFR-007):
behaviour-free. Every subclass carries a stable ``error_code`` class attribute
so callers can route on the code without string parsing. ``transaction.py``
re-exports these names, so ``from specify_cli.coordination.transaction import
BookkeepingError`` (and the rest) keeps resolving to the same class objects.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from specify_cli.coordination.types import Refused
from specify_cli.status import SNAPSHOT_FILENAME


class BookkeepingError(Exception):
    """Base for all BookkeepingTransaction failures.

    Subclasses carry a stable ``error_code`` class attribute so callers
    can route on the code without string parsing (NFR-007).
    """

    error_code: ClassVar[str] = "BOOKKEEPING_ERROR"


class BookkeepingPolicyRefused(BookkeepingError):
    """The pre-flight policy gate refused the would-be commit.

    Carries the underlying :class:`Refused` verdict so callers can
    surface the structured diagnostic.
    """

    error_code: ClassVar[str] = "BOOKKEEPING_POLICY_REFUSED"

    def __init__(self, verdict: Refused) -> None:
        self.verdict = verdict
        super().__init__(
            f"Bookkeeping refused: {verdict.error_code}: {verdict.message}"
        )


class BookkeepingStatusSurfaceDiverged(BookkeepingError):
    """The coordination worktree's status log lost events its HEAD has committed (#5572).

    A status write built on such a tree would commit a log without those events,
    silently dropping them. Raised before anything is written.
    """

    error_code: ClassVar[str] = "COORD_STATUS_SURFACE_DIVERGED"

    def __init__(self, *, worktree_root: Path, events_path: Path, missing_event_ids: list[str]) -> None:
        self.missing_event_ids = missing_event_ids
        status_dir = events_path.parent.relative_to(worktree_root).as_posix()
        shown = ", ".join(missing_event_ids[:3]) + (f" (+{len(missing_event_ids) - 3} more)" if len(missing_event_ids) > 3 else "")
        mission = events_path.parent.name  # the mission directory name is the slug `--mission` takes
        super().__init__(
            f"{self.error_code}: the coordination worktree {worktree_root} has {events_path.name} bytes that drop "
            f"{len(missing_event_ids)} event(s) its branch HEAD has committed ({shown}), e.g. after a rolled-back "
            f"consolidation. Writing now would silently lose them; nothing was written. Choose deliberately: "
            f"`spec-kitty doctor coordination --fix --mission {mission}` heals the strand AWAY (it reverts the stranded "
            f"`done`, so the mission is no longer recorded as done), and `spec-kitty consolidate --resume --mission "
            f"{mission}` does the same heal and then completes the consolidation, whereas "
            f"`git -C {worktree_root} checkout HEAD -- {status_dir}/{events_path.name} {status_dir}/{SNAPSHOT_FILENAME}` "
            f"KEEPS the committed events (the stranded `done` stays recorded) and only discards the stale "
            f"working-tree bytes. Once a later status write lands on top of the kept events, `consolidate --resume` "
            f"and `doctor coordination --fix` decline the automatic heal (the status log holds a commit the marker "
            f"did not record) and ask you to reconcile manually. Do not run `doctor coordination --fix` without "
            f"`--mission`: it then acts on every mission and flattens those with a stale coordination branch. Then retry "
            f"the status write."
        )


class BookkeepingStatusSurfaceUnreadable(BookkeepingError):
    """The status log committed at the coordination worktree's HEAD could not be read (#5613).

    The guard cannot tell whether a status write would drop committed events, so it
    refuses rather than report "nothing missing". Raised before anything is written.
    """

    error_code: ClassVar[str] = "COORD_STATUS_SURFACE_UNREADABLE"

    def __init__(self, *, worktree_root: Path, events_path: Path, reason: str) -> None:
        self.reason = reason
        super().__init__(
            f"{self.error_code}: cannot verify that the coordination worktree {worktree_root} still holds every event "
            f"its branch HEAD has committed in {events_path.name}: {reason}. Writing now could silently lose committed "
            f"events; nothing was written. Repair the committed log or the checkout, then retry."
        )


class BookkeepingLockTimeout(BookkeepingError):
    """The feature status lock could not be acquired within the timeout."""

    error_code: ClassVar[str] = "BOOKKEEPING_LOCK_TIMEOUT"


class BookkeepingWorktreeMissing(BookkeepingError):
    """Worktree resolution found neither a coord nor a valid lane worktree."""

    error_code: ClassVar[str] = "BOOKKEEPING_WORKTREE_MISSING"


class BookkeepingCommitFailed(BookkeepingError):
    """``safe_commit()`` raised; rollback ran; the original error is chained."""

    error_code: ClassVar[str] = "BOOKKEEPING_COMMIT_FAILED"


class BookkeepingDoubleEventId(BookkeepingError):
    """The same event_id was appended twice in one transaction."""

    error_code: ClassVar[str] = "BOOKKEEPING_DOUBLE_EVENT_ID"


class BookkeepingLegacyResolutionFailed(BookkeepingError):
    """Legacy mission detected but the lane worktree could not be resolved.

    Stable error code ``BOOKKEEPING_LEGACY_RESOLUTION_FAILED``.  Raised
    when ``meta.json`` lacks ``coordination_branch`` (legacy mission)
    but the operator's current working directory does not sit inside a
    recognisable lane worktree, so we cannot determine which branch is
    the legitimate write target for this mission's bookkeeping.
    """

    error_code: ClassVar[str] = "BOOKKEEPING_LEGACY_RESOLUTION_FAILED"
