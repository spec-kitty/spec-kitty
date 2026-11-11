"""The board status value: one reduced reading of a Mission's status (#7310, FR-008).

ADR ``docs/adr/4.x/2026-11-06-2-one-status-read-contract.md``. A ``next`` decision or query
reads a Mission's status from the one status read door
(:func:`specify_cli.status.read_surface.resolve_status_read`) and reduces it once into a
:class:`BoardStatus`. Every board and progress helper then reads that one value, so the lane
map, the dependency-readiness states and the weighted progress can no longer come from two
different reads (NFR-002: one read, one reduction per build).

The builder is :func:`board_status_from_surface`: it reads the surface's declared source once
through :func:`~specify_cli.status.read_surface.read_status_stream` (a ref surface reuses the
door's prefetched read) and never re-derives a source (C-001). The reduction itself lives once,
in :func:`_board_from_stream`; the tests' path-read oracle (``tests/runtime/next/_board_path.py``)
reuses it to prove parity with the helpers' ``status_dir=`` Path forms.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any

from specify_cli.status import (
    EventStream,
    Lane,
    StatusReadSurface,
    compute_weighted_progress,
    read_status_stream,
    reduce,
)

__all__ = ["BoardStatus", "board_status_from_surface"]

_logger = logging.getLogger(__name__)

_EVENTS_FILENAME = "status.events.jsonl"


@dataclass(frozen=True)
class BoardStatus:
    """One immutable, reduced reading of a Mission's status (data model § BoardStatus).

    Attributes:
        lanes: WP id -> canonical lane. Genesis WPs are kept (as ``Lane.GENESIS``) so callers
            can skip unseeded WPs.
        wp_states: WP id -> reduced state (lane plus provenance such as ``reason_source``), for
            dependency readiness.
        has_log: whether the declared source holds a status log at all.
        weighted_percentage: weighted progress to one decimal place, or ``None`` when it could
            not be computed (logged).
        source: the door's declared source (a ``StatusReadSource`` value); the tests' path-read
            oracle uses ``"path"``.
    """

    lanes: Mapping[str, Lane]
    wp_states: Mapping[str, Mapping[str, Any]]
    has_log: bool
    weighted_percentage: float | None
    source: str


def board_status_from_surface(surface: StatusReadSurface) -> BoardStatus:
    """Build the board from a door surface: one read, one reduction (NFR-002).

    ``has_log`` for a path source is whether ``status.events.jsonl`` is a file in the surface
    directory. For a ref source it is read off the door's prefetched read when the door made
    one (no second subprocess). A ref surface without a prefetched read (e.g. the Mission
    topic branch) derives it from the stream: a ref whose log is empty reads as no log, which
    is the same empty history the door returns for an absent file.

    Raises:
        StoreError: a log line cannot be parsed. The lanes step raises today
            (``get_all_wp_lanes``), so callers keep their raise; only the weighted figure
            degrades to ``None``.
        StatusSurfaceRefUnreadable: the surface's ref cannot be read (never an empty history).
    """
    stream = read_status_stream(surface)
    return _board_from_stream(stream, has_log=_surface_has_log(surface, stream), source=str(surface.source), where=_describe(surface))


def _board_from_stream(stream: EventStream, *, has_log: bool, source: str, where: str) -> BoardStatus:
    """The one reduction: transitions and annotations -> lanes, states, weighted progress."""
    snapshot = reduce(list(stream.transitions), list(stream.annotations))
    states = {wp_id: MappingProxyType(dict(state)) for wp_id, state in snapshot.work_packages.items()}
    weighted: float | None
    try:
        weighted = round(compute_weighted_progress(snapshot).percentage, 1)
    except Exception as exc:  # noqa: BLE001 -- weighted progress degrades, as decision._compute_wp_progress does today
        _logger.warning("weighted progress unavailable for %s: %s", where, exc)
        weighted = None
    return BoardStatus(
        lanes=MappingProxyType(_lanes_from_states(states)),
        wp_states=MappingProxyType(states),
        has_log=has_log,
        weighted_percentage=weighted,
        source=source,
    )


def _lanes_from_states(states: Mapping[str, Mapping[str, Any]]) -> dict[str, Lane]:
    """WP id -> lane; a state with no lane is kept as GENESIS (mirrors ``discovery._wp_lanes_from_states``)."""
    return {wp_id: Lane(state.get("lane", Lane.GENESIS)) for wp_id, state in states.items()}


def _surface_has_log(surface: StatusReadSurface, stream: EventStream) -> bool:
    # ``specify_cli`` names read as ``Any`` under the narrow mypy check (``follow_imports = skip``),
    # so the path is annotated here rather than trusted from the surface.
    if surface.path is not None:
        mission_dir: Path = surface.path
        return (mission_dir / _EVENTS_FILENAME).is_file()
    if surface.prefetched is not None:
        return surface.prefetched.data is not None
    return bool(stream.transitions or stream.annotations)


def _describe(surface: StatusReadSurface) -> str:
    return str(surface.path) if surface.path is not None else f"{surface.ref} ({surface.mission_dir_name})"
