"""Side-effect-free claim discovery for ``spec-kitty next --json``.

Issue #988 — Prior to this module, ``spec-kitty next --json`` reported
``mission_state: implement`` while emitting ``wp_id: null``, even though the
explicit ``spec-kitty agent action implement`` would have auto-claimed a
concrete WP. Operators and AI agents driving the readiness loop could not
trust ``next --json`` as the canonical "what should I do next?" signal.

This module exposes :func:`preview_claimable_wp`, the **single
implementation path** for "which WP would the next implement action claim?".
``_preview_claimable_wp_for_mission`` in
``specify_cli.cli.commands.agent.workflow`` delegates to this helper, so
spec FR-003 ("claimability discovery MUST share a single implementation
path with the explicit ``agent action implement`` claim logic, with no
divergent forking") is satisfied by construction rather than by
documented parallel forks.

Design constraints (spec FR-001..FR-003, C-001):

* The helper never mutates state. It must not be confused with the actual
  claim path; only :func:`start_implementation_status` mutates the event log.
* When ``mission_state != "implement"`` the ``next --json`` payload's wire
  shape is preserved (no new keys are added) — see ``runtime_bridge``.
* When ``wp_id`` is non-``None`` then ``selection_reason`` is ``None`` and
  vice versa (invariant I-001 from ``data-model.md``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specify_cli.core.dependency_graph import build_dependency_graph, dependency_readiness_for_wp
from specify_cli.status import Lane
from specify_cli.status import reduce as _reduce_events
from specify_cli.status import read_events as _read_events
from specify_cli.task_utils.support import extract_scalar, split_frontmatter

if TYPE_CHECKING:
    from runtime.next.board_status import BoardStatus

__all__ = ["ClaimablePreview", "preview_claimable_wp"]


# Lanes whose WPs are still moving through the implement → review → approve
# pipeline. Used to distinguish "all candidates are active but not claimable"
# from "all candidates are terminal/blocked" when computing selection_reason.
_ACTIVE_NON_PLANNED_LANES: frozenset[Lane] = frozenset(
    {Lane.CLAIMED, Lane.IN_PROGRESS, Lane.FOR_REVIEW, Lane.IN_REVIEW}
)


@dataclass(frozen=True)
class ClaimablePreview:
    """Side-effect-free preview of which WP ``agent action implement`` would claim.

    Attributes:
        wp_id: The concrete WP that the explicit action would auto-claim, or
            ``None`` when no WP is selectable.
        selection_reason: A stable token explaining why selection is suppressed
            when ``wp_id`` is ``None``. Always ``None`` when ``wp_id`` is set.
            Tokens:

            * ``"no_tasks_dir"`` — ``<feature_dir>/tasks/`` does not exist.
            * ``"no_wp_files"`` — the tasks directory has no parseable WP files.
            * ``"no_planned_wps"`` — WP files exist but all candidates are in
              terminal or blocked lanes (``done``, ``approved``, ``canceled``,
              ``blocked``).
            * ``"all_wps_in_progress"`` — at least one candidate is in an
              active non-planned lane (``claimed``, ``in_progress``,
              ``for_review``, ``in_review``).
            * ``"dependencies_not_satisfied"`` — planned WPs exist, but every
              planned candidate is waiting on at least one dependency that is
              not yet ``approved`` or ``done``.
        candidates: Ordered tuple of WP IDs the claim algorithm would have
            considered, in alphabetical ``WP*.md`` order.
    """

    wp_id: str | None
    selection_reason: str | None
    candidates: tuple[str, ...]


def _read_candidate_wp_ids(tasks_dir: Path) -> list[str]:
    candidates: list[str] = []
    for wp_file in sorted(tasks_dir.glob("WP*.md")):
        try:
            content = wp_file.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        frontmatter, _, _ = split_frontmatter(content)
        wp_id = extract_scalar(frontmatter, "work_package_id")
        if wp_id:
            candidates.append(wp_id)
    return candidates


def _load_wp_states(feature_dir: Path) -> dict[str, Mapping[str, Any]]:
    """Reduced per-WP snapshot states (lane **and** provenance), best-effort.

    Returns the raw reduced ``work_packages`` state dicts so callers can derive
    the lane map *and* thread per-dependency provenance (``reason_source``) into
    :func:`dependency_readiness_for_wp` (FR-009). On any read/reduce failure the
    map is empty — discovery is best-effort and must never raise.
    """
    try:
        events = _read_events(feature_dir)
        if not events:
            return {}
        snapshot = _reduce_events(events)
    except Exception:  # noqa: BLE001 — discovery is best-effort; on read failure return empty
        return {}
    return dict(snapshot.work_packages)


def _wp_lanes_from_states(states: Mapping[str, Mapping[str, Any]]) -> dict[str, Lane]:
    """Derive the lane map from reduced snapshot states.

    Genesis WPs are non-display but kept in the map (as GENESIS) so callers can
    detect and skip them (Contract 2, FR-008). reduce() always writes a string
    "lane"; the GENESIS default covers a (never-observed) missing key. Lane(...)
    coerces both a lane string and the GENESIS enum default (#1775 Randy-Reducer).
    """
    return {wp_id: Lane(state.get("lane", Lane.GENESIS)) for wp_id, state in states.items()}


def _preview_from_candidates(
    candidates: list[str],
    wp_lanes: dict[str, Lane],
    dependency_graph: dict[str, list[str]],
    provenance: Mapping[str, Mapping[str, Any] | None] | None = None,
) -> ClaimablePreview:
    has_active_candidate = False
    has_dependency_blocked_candidate = False
    has_genesis_candidate = False
    for wp_id in candidates:
        # Default to GENESIS for unseeded WPs: a genesis WP is not claimable
        # and must not be reported as planned (Contract 3, FR-008).
        lane = wp_lanes.get(wp_id, Lane.GENESIS)
        # GENESIS-specific (intentionally NOT NON_DISPLAY_LANES): this branch sets
        # the distinct has_genesis_candidate signal for genesis WPs specifically,
        # so it must match GENESIS alone, not the non-display set.
        if lane == Lane.GENESIS:
            has_genesis_candidate = True
            continue
        if lane == Lane.PLANNED:
            # Thread per-dependency provenance so a dependent of a
            # canceled-with-operator-provenance WP is surfaced as claimable
            # rather than reported blocked (FR-009). The default (None) keeps
            # the legacy lane-only behaviour for callers that pass no map.
            # Pre-flight UX only (FR-014, fsm-write-path-integrity WP04). The authoritative
            # dependency gate is `GuardContext.dependency_ready`, resolved in-lock by the emit shells.
            readiness = dependency_readiness_for_wp(
                wp_id,
                dependency_graph.get(wp_id, []),
                wp_lanes,
                provenance=provenance,
            )
            if not readiness.satisfied:
                has_dependency_blocked_candidate = True
                continue
            return ClaimablePreview(
                wp_id=wp_id,
                selection_reason=None,
                candidates=tuple(candidates),
            )
        if lane in _ACTIVE_NON_PLANNED_LANES:
            has_active_candidate = True
    return ClaimablePreview(
        wp_id=None,
        selection_reason=_claimable_selection_reason(
            has_dependency_blocked_candidate,
            has_active_candidate,
            has_genesis_candidate,
        ),
        candidates=tuple(candidates),
    )


def _claimable_selection_reason(
    has_dependency_blocked_candidate: bool,
    has_active_candidate: bool,
    has_genesis_candidate: bool,
) -> str:
    if has_dependency_blocked_candidate:
        return "dependencies_not_satisfied"
    if has_active_candidate:
        return "all_wps_in_progress"
    # Genesis WPs are not finalized: the actionable next step is finalize-tasks,
    # not "no planned WPs" (which implies WPs exist but have all advanced). Only
    # report not_finalized when nothing else is actionable (review m3).
    if has_genesis_candidate:
        return "not_finalized"
    return "no_planned_wps"


def preview_claimable_wp(
    feature_dir: Path,
    *,
    status_dir: Path | None = None,
    board: BoardStatus | None = None,
) -> ClaimablePreview:
    """Return the WP that ``agent action implement`` would auto-claim, if any.

    Walks ``<feature_dir>/tasks/WP*.md`` in alphabetical order, reads each
    file's YAML frontmatter ``work_package_id``, then consults the canonical
    status event log for current lane and the canonical dependency graph for
    dependency readiness. The first candidate whose lane is
    :class:`Lane.PLANNED` and whose dependencies are all ``approved`` or
    ``done`` is the WP the explicit action would claim.

    Args:
        feature_dir: Absolute path to ``kitty-specs/<mission_slug>/`` for
            **planning artifacts** (``tasks/``, dependency graph).  Under
            coord topology this is the PRIMARY checkout dir (not the coord
            husk, which carries STATUS-only files).
        status_dir: Absolute path to the directory that holds the canonical
            ``status.events.jsonl`` for lane state.  When ``None`` (default),
            ``feature_dir`` is used for both planning and status reads — the
            existing single-arg callers (``runtime_bridge``, existing tests)
            keep working unchanged.  Pass a distinct coord-aware path here
            when the caller operates under coord topology so events come from
            the authoritative coord husk rather than a primary decoy.
            Kept for outside callers (``workflow.py``) and tests; ``board=``
            is the preferred form. Ignored when ``board`` is given.
        board: The preferred form (#7310, FR-008): a :class:`BoardStatus`
            already read through the status read door. When given, lanes and
            dependency provenance come from ``board.wp_states``, the same
            derivation as the Path form, and no status file is read here.

    Returns:
        :class:`ClaimablePreview` whose ``wp_id`` matches what ``agent action
        implement`` would claim, or ``None`` with a structured
        ``selection_reason``.
    """
    # WP04 / T015: tasks/ and dependency-graph reads use the planning arg;
    # status events use status_dir (or fall back to feature_dir for single-arg
    # callers — backward-compatible).
    _status_dir = status_dir if status_dir is not None else feature_dir

    tasks_dir = feature_dir / "tasks"
    if not tasks_dir.is_dir():
        return ClaimablePreview(
            wp_id=None,
            selection_reason="no_tasks_dir",
            candidates=(),
        )

    candidates = _read_candidate_wp_ids(tasks_dir)
    if not candidates:
        return ClaimablePreview(
            wp_id=None,
            selection_reason="no_wp_files",
            candidates=(),
        )

    # Read lanes from the canonical status event log (lane is event-log-only).
    # Dependency graph is a planning artifact → feature_dir (primary partition).
    # Load the reduced states once and reuse them for both the lane map and the
    # provenance map (FR-009) so a dependent of a canceled-with-operator-provenance
    # WP is surfaced as claimable, mirroring the primary claim gates.
    # The Path form keeps its own best-effort read (``_load_wp_states`` swallows
    # every failure); it is deliberately not routed through
    # ``board_status_from_dir``, which raises on a corrupt log.
    wp_states: Mapping[str, Mapping[str, Any]] = board.wp_states if board is not None else _load_wp_states(_status_dir)
    return _preview_from_candidates(
        candidates,
        _wp_lanes_from_states(wp_states),
        build_dependency_graph(feature_dir),
        provenance=wp_states,
    )
