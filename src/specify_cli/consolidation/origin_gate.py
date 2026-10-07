"""Origin freshness gate for ``consolidate`` (#5780, FR-001/002/008/009/010).

The executor-side wrapper over :mod:`specify_cli.git.origin_freshness`: it
selects the lane branches, runs ONE read-only freshness check (one remote
contact per remote, NFR-001) BEFORE ``_resolve_run_status_dir`` can seed or
commit a coordination surface, and renders the outcome. A refusal prints the
operator text and exits 1 with nothing moved and nothing pushed; ``warn`` mode
prints the same verdicts as warnings and lets the run continue.

A coordination mission whose coordination branch exists only on the remote
(evidence ``local_missing``) is not refused here: the existing
``COORDINATION_WORKTREE_UNMATERIALIZED`` path owns that case (ADR 2026-09-24-2)
and the fetch the check performed makes its remedy work.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import typer

from mission_runtime import MissionArtifactKind, PlacementSeam
from specify_cli.cli.console import console
from specify_cli.consolidation.entry_preflight import _merge_record_may_exist
from specify_cli.consolidation.state import ConsolidationStateReadError, MergeAmbiguousStateError, load_state
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.git.origin_freshness import (
    OriginCheckSetting,
    OriginFreshnessRefused,
    approved_lane_branches,
    resolve_origin_check_mode,
)
from specify_cli.git.origin_gate import run_origin_gate
from specify_cli.lanes.persistence import CorruptLanesError, read_lanes_json
from specify_cli.mission_metadata import resolve_mission_identity

__all__ = ["check_origin_before_status_dir"]


def _completed_wps(seam: PlacementSeam) -> frozenset[str]:
    """WP ids a persisted consolidation record already consolidated (a resume); empty when none or unreadable.

    Unreadable means over-selecting lanes, never under-selecting them.
    """
    try:
        identity = resolve_mission_identity(seam.read_dir(MissionArtifactKind.PRIMARY_METADATA))
        state = load_state(seam.repo_root, identity.mission_id if identity.mission_id is not None else seam.mission_slug)
    except (MissionMetaReadError, ConsolidationStateReadError, MergeAmbiguousStateError):
        return frozenset()
    return frozenset(state.completed_wps) if state is not None else frozenset()


def _lane_branches(seam: PlacementSeam) -> list[str]:
    """Code-lane branches the check covers; none when ``lanes.json`` is absent or unreadable (the entry reports that itself)."""
    try:
        manifest = read_lanes_json(seam.read_dir(MissionArtifactKind.LANE_STATE))
    except CorruptLanesError:
        return []
    if manifest is None:
        return []
    branches: list[str] = approved_lane_branches(seam.repo_root, seam.mission_slug, manifest, completed_wps=_completed_wps(seam))
    return branches


def _render_warnings(warnings: Sequence[str]) -> None:
    for warning in warnings:
        console.print(warning, markup=False)


def check_origin_before_status_dir(main_repo: Path, seam: PlacementSeam, origin_check: str | None) -> OriginCheckSetting:
    """Run the origin freshness check once; refuse (exit 1) or warn per the resolved setting.

    Reads nothing that mutates, and must run before the status directory is
    resolved. Returns the resolved setting so the caller can reuse it. The
    check itself is the shared :func:`specify_cli.git.origin_gate.run_origin_gate`;
    this wrapper only selects lanes, reads the resume record and renders.
    """
    setting = resolve_origin_check_mode(origin_check)
    try:
        warnings = run_origin_gate(
            main_repo,
            seam.mission_slug,
            setting=setting,
            lane_branches=_lane_branches(seam),
            merge_record_exists=_merge_record_may_exist(seam),
        )
    except OriginFreshnessRefused as exc:
        console.print(str(exc), markup=False)
        raise typer.Exit(1) from exc
    _render_warnings(warnings)
    return setting
