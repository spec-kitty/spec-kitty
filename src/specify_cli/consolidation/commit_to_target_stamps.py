"""Consolidation reads no window stamp of a commit-to-target ``single_branch`` Mission (#7578, ruling Q8).

A commit-to-target ``single_branch`` Mission (STORED topology ``single_branch``, write branch == target)
records ``policy_metadata.lane_head`` and ``policy_metadata.wp_window`` at the target head since #7578, so
the review range has a recorded window on every topology. Consolidation verdicts must stay what they were
before those stamps existed (operator ruling Q8, ADR ``2026-11-08-2`` Amendment 2026-11-12): the claim's
canceled-work attribution, the ``--dependency-ref`` "names Mission work" guard and the
``--attest-approved-reviewed`` validation read the Mission's status events through
:func:`consolidation_events`, the one consolidation event-loading door: it reads the log and drops both
keys for such a Mission, and passes every other Mission's events through unchanged. Any other
``read_events*`` call in ``consolidation/`` is allowlisted, with a reason, in
``tests/consolidation/test_single_consolidation_event_door.py``.

The one predicate is :func:`~specify_cli.lanes.single_branch_landing.is_commit_to_target_meta`, over
``meta.json`` and the ``single_branch_landing`` rules (the same
:func:`~specify_cli.lanes.single_branch_landing.single_branch_branches` reading the lane-head stamp uses). A status directory with no readable
``meta.json`` is not a commit-to-target Mission, so its events pass through unchanged.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Final

from specify_cli.status import LANE_HEAD_KEY, WP_WINDOW_KEY, StatusEvent

#: The ``policy_metadata`` keys consolidation ignores on a commit-to-target Mission's events.
WINDOW_STAMP_KEYS: Final = frozenset({LANE_HEAD_KEY, WP_WINDOW_KEY})


def is_commit_to_target_mission(feature_dir: Path) -> bool:
    """:func:`~specify_cli.lanes.single_branch_landing.is_commit_to_target_meta` over the ``meta.json`` in *feature_dir* (``False`` when absent or malformed)."""
    from specify_cli.lanes.single_branch_landing import is_commit_to_target_meta
    from specify_cli.mission_metadata import load_meta_or_empty

    return bool(is_commit_to_target_meta(load_meta_or_empty(feature_dir)))


def without_window_stamps(event: StatusEvent) -> StatusEvent:
    """*event* with ``lane_head`` and ``wp_window`` removed from its ``policy_metadata`` (``None`` when nothing is left)."""
    metadata = event.policy_metadata
    if not metadata or WINDOW_STAMP_KEYS.isdisjoint(metadata):
        return event
    kept = {key: value for key, value in metadata.items() if key not in WINDOW_STAMP_KEYS}
    return dataclasses.replace(event, policy_metadata=kept or None)


def consolidation_events(feature_dir: Path) -> list[StatusEvent]:
    """The status events consolidation reads for the Mission in *feature_dir* (``StoreError`` when the log is unreadable).

    Window stamps are dropped for a commit-to-target Mission; every other Mission's events are returned unchanged.
    """
    from specify_cli.status import read_events  # looked up per call, so a test patching ``specify_cli.status.read_events`` reaches the door

    events = read_events(feature_dir)
    if not is_commit_to_target_mission(feature_dir):
        return list(events)
    return [without_window_stamps(event) for event in events]


__all__ = ["consolidation_events"]
