"""Mission-scoped dirt: whose uncommitted path is this? (#7545, #7556).

A gate that guards a write for one Mission lists the checkout's uncommitted
paths and must decide which of them it is allowed to refuse on. This module is
the single structural answer: a path belongs to this Mission (``OWN``), to
another Mission (``OTHER_MISSION``), or to no Mission at all (``OUTSIDE``).

The rule reads only the path string and the Mission's own directory names: no
git call, no file-system read and no filename list. Which scope a gate refuses on
and which it reports as a warning is the gate's own decision (research D2 of
Mission ``cli-owns-its-commits-01M75NTA``).

Shapes it understands:

* ``kitty-specs/<name>/...`` and the collapsed directory entry
  ``kitty-specs/<name>/`` that ``git status`` reports for a wholly untracked
  Mission directory in its default untracked mode;
* the derived status views ``.kittify/derived/<name>/<view>``;
* a ``kitty-specs`` segment anywhere in the path (a path listed from a parent
  checkout), and Windows separators.

A bare ``kitty-specs/`` entry or a file directly under ``kitty-specs/`` names no
Mission, so it is ``OUTSIDE``: a collapsed parent may hide this Mission's own
files and must never be dropped silently.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath

from kernel.paths import to_posix
from specify_cli.core.constants import KITTY_SPECS_DIR

__all__ = [
    "DirtScope",
    "MissionDirt",
    "classify_dirt",
    "derived_view_mission_dir",
    "mission_dir_segments",
    "partition_mission_dirt",
]


class DirtScope(StrEnum):
    """Whose uncommitted path a gate is looking at."""

    OWN = "own"
    OTHER_MISSION = "other_mission"
    OUTSIDE = "outside"


@dataclass(frozen=True)
class MissionDirt:
    """Uncommitted paths split by :class:`DirtScope`, each in input order."""

    own: tuple[str, ...] = ()
    other_mission: tuple[str, ...] = ()
    outside: tuple[str, ...] = ()

    @property
    def foreign(self) -> tuple[str, ...]:
        """Every path that is not this Mission's: another Mission's, then outside every Mission."""
        return self.other_mission + self.outside


def derived_view_mission_dir(path: str | Path) -> str | None:
    """The Mission directory of a ``.kittify/derived/<mission>/<view>`` status view, else ``None``.

    The status views (``status/views.py``) are regenerated from the event log.
    Depth-exact: a file directly under ``.kittify/derived/`` or nested deeper is
    not a view. The pattern is function-local so no module-level filename
    pattern exists here (the R-014 exemption-registry scan).
    """
    match = re.search(r"(?:^|/)\.kittify/derived/([^/]+)/[^/]+$", to_posix(path).rstrip("/"))
    return match.group(1) if match else None


def mission_dir_segments(path: str | Path) -> tuple[str, ...] | None:
    """The path segments after the first ``kitty-specs`` segment, or ``None`` when there is none.

    A trailing ``/`` (git's collapsed directory entry) is dropped, so
    ``kitty-specs/m/`` and ``kitty-specs/m`` both give ``("m",)``; callers that
    must tell them apart look at the trailing ``/`` themselves.
    """
    parts = PurePosixPath(to_posix(path)).parts
    if KITTY_SPECS_DIR not in parts:
        return None
    return parts[parts.index(KITTY_SPECS_DIR) + 1 :]


def classify_dirt(path: str | Path, *, own_dir_names: Collection[str]) -> DirtScope:
    """Classify one uncommitted ``path`` against the Mission whose directories are ``own_dir_names``.

    Args:
        path: A path as ``git status`` reports it, relative to the checkout.
        own_dir_names: The Mission's own directory names under ``kitty-specs/``
            (its slug plus any alias such as the composed ``<slug>-<mid8>``).
    """
    derived = derived_view_mission_dir(path)
    if derived is not None:
        return DirtScope.OWN if derived in own_dir_names else DirtScope.OTHER_MISSION
    after = mission_dir_segments(path)
    if not after:
        return DirtScope.OUTSIDE
    if len(after) == 1 and not to_posix(path).endswith("/"):
        # A file directly under ``kitty-specs/`` (``kitty-specs/README.md``) names no Mission.
        return DirtScope.OUTSIDE
    return DirtScope.OWN if after[0] in own_dir_names else DirtScope.OTHER_MISSION


def partition_mission_dirt(paths: Iterable[str], *, own_dir_names: Collection[str]) -> MissionDirt:
    """Split ``paths`` by :func:`classify_dirt`, keeping each scope in input order."""
    buckets: dict[DirtScope, list[str]] = {scope: [] for scope in DirtScope}
    for path in paths:
        buckets[classify_dirt(path, own_dir_names=own_dir_names)].append(path)
    return MissionDirt(
        own=tuple(buckets[DirtScope.OWN]),
        other_mission=tuple(buckets[DirtScope.OTHER_MISSION]),
        outside=tuple(buckets[DirtScope.OUTSIDE]),
    )
