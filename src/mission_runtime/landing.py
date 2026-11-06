"""The placement seam's one "has this Mission landed" reader (ADR 2026-11-06-2, ADR 2026-11-06-3).

A Mission has *landed* once ``consolidate`` recorded its landing on the target branch. Two
consumers read that one signal and must never disagree:

* the status read door (``specify_cli.status.read_surface``), whose ``CONSOLIDATED_TARGET``
  source is checked before any coordination probe, so a coordination branch torn down by
  consolidation never reads as ``CoordinationBranchDeleted``;
* the PRIMARY placement of a ``topology_source: default`` Mission (FR-061), which stays on the
  Mission topic branch until this reader answers ``True``.

Today the record is the live merge marker (``merged_at`` in the PRIMARY ``meta.json``,
reopen-aware), the same marker the status surface resolver has used for its merged arm. It is
written by ``consolidation.baseline.record_baseline_merge_commit`` beside
``baseline_merge_commit``. Mission WP14 fixes the record consolidate writes for the landing; it
changes only the body of :func:`mission_has_landed`, never its callers, so no second "landed"
signal can appear.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["mission_has_landed"]


def mission_has_landed(primary_dir: Path) -> bool:
    """True when the Mission whose PRIMARY ``meta.json`` lives in *primary_dir* has landed.

    Non-raising: a missing or corrupt ``meta.json`` (or an unreadable post-merge event log)
    answers ``False``, so the caller falls through to its ordinary source decision and the
    fail-closed meta readers keep the corruption verdict.
    """
    from specify_cli.core.paths import MissionMetaReadError
    from specify_cli.status import StoreError, is_mission_merged

    if not (primary_dir / "meta.json").is_file():
        return False
    try:
        return bool(is_mission_merged(primary_dir))
    except (StoreError, MissionMetaReadError):
        return False
