"""The write-checkout switch core (#5676; S7 #7282).

One authority for moving the write checkout onto another branch: create's Mission
topic-branch mint (:mod:`specify_cli.core.mission_creation_protected_mint`) and
settlement's move back to ``create_return_branch`` both go through
:func:`switch_write_checkout`, which refuses ``WRITE_CHECKOUT_OCCUPIED`` and
``WRITE_CHECKOUT_DIRTY`` before any git write.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

from kernel.git import GitPath, status_entries
from specify_cli.core.mission_creation_errors import (
    MissionCreationError,
    WriteCheckoutSwitchDirtyError,
    WriteCheckoutSwitchOccupiedError,
)

__all__ = ["switch_write_checkout"]


def _refuse_occupied_write_checkout(write_root: Path, repository_root: Path) -> None:
    """Raise :class:`WriteCheckoutSwitchOccupiedError` when a WP is ``in_progress`` in *write_root*."""
    from specify_cli.lanes.checkout_occupancy import in_progress_wps_in_write_checkout

    occupants = in_progress_wps_in_write_checkout(repository_root, write_root)
    if occupants:
        named = ", ".join(f"{slug}/{wp_id}" for slug, wp_id in occupants)
        raise WriteCheckoutSwitchOccupiedError(
            f"{WriteCheckoutSwitchOccupiedError.error_code}: cannot switch the write checkout at {write_root}: "
            f"{named} is in_progress there. Finish or move that work package first, then retry."
        )


def _dirty_paths_outside(write_root: Path, owned_paths: tuple[str, ...]) -> tuple[str, ...]:
    """The write checkout's uncommitted paths that overlap none of *owned_paths*."""
    owned = tuple(GitPath.parse(path) for path in owned_paths)
    return tuple(str(entry.path) for entry in status_entries(write_root, untracked=None) if not any(item.overlaps(entry.path) for item in owned))


def _git_switch(write_root: Path, branch_name: str, *, start_point: str | None) -> None:
    """Check *branch_name* out in *write_root*, creating it at *start_point* when one is given."""
    args = ["checkout", "-b", branch_name, start_point] if start_point is not None else ["checkout", branch_name]
    result = subprocess.run(["git", "-C", str(write_root), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        if start_point is not None:
            raise MissionCreationError(f"Failed to create and check out mission branch {branch_name!r} from {start_point!r}: {detail}")
        raise MissionCreationError(f"Failed to check out branch {branch_name!r} in {write_root}: {detail}")


def switch_write_checkout(
    write_root: Path,
    branch_name: str,
    *,
    start_point: str | None,
    repository_root: Path,
    owned_paths: tuple[str, ...],
    decide: Callable[[tuple[str, ...]], None] | None = None,
) -> None:
    """Switch the write checkout onto *branch_name*, refusing an occupied or dirty checkout.

    The one switch core: create's topic-branch mint and settlement's move back to
    ``create_return_branch`` (S7 #7282) both go through it. In order, before any git write:

    1. ``WRITE_CHECKOUT_OCCUPIED`` when a ``single_branch`` WP is ``in_progress`` in
       *write_root* (:func:`~specify_cli.lanes.checkout_occupancy.in_progress_wps_in_write_checkout`,
       the rule ``implement`` applies, #5550 included);
    2. *decide*, when given, with the uncommitted paths outside *owned_paths*: the
       caller's own refusals in its probe order (create's protected-mint decision
       words the dirty refusal and then refuses an existing mission branch);
    3. ``WRITE_CHECKOUT_DIRTY`` when *write_root* has uncommitted changes outside
       *owned_paths* (spec-kitty's own paths the caller names), whatever *decide* did.

    With *start_point* the branch is created there; without it, an existing branch is
    checked out.
    """
    _refuse_occupied_write_checkout(write_root, repository_root)
    dirty = _dirty_paths_outside(write_root, owned_paths)
    if decide is not None:
        decide(dirty)
    if dirty:
        raise WriteCheckoutSwitchDirtyError(
            f"{WriteCheckoutSwitchDirtyError.error_code}: cannot switch the write checkout at {write_root}: "
            f"it has uncommitted changes: {', '.join(dirty)}. Commit or discard them, then retry."
        )
    _git_switch(write_root, branch_name, start_point=start_point)
