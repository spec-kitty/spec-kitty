"""``spec-kitty charter activate`` — in-flight warning on action_sequence change.

FR-008: When a charter override is activated that removes a step from the
current action_sequence, ``spec-kitty charter activate`` emits a structured
warning for each in-flight mission that has a WP currently in the lane
corresponding to the removed step, before completing activation.

The warning is **non-blocking**: activation completes after warning emission.

FR-014: Activation now writes to ``config.yaml`` via ``ActiveCharterManager``
instead of writing ``.kittify/overrides/`` files that nothing reads.

Layer note
----------
This module lives in ``specify_cli`` (not ``charter``); it is permitted to
import both ``charter.*`` and ``specify_cli.status.*``.  The layer rule
(kernel <- doctrine <- charter <- specify_cli) is not violated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from specify_cli.mission_metadata import load_meta_or_empty

__all__ = [
    "AffectedMission",
    "StepRemovalWarning",
    "find_removed_steps",
    "scan_inflight_missions",
    "emit_step_removal_warnings",
]

# ---------------------------------------------------------------------------
# Lanes that correspond to "in-flight" status (non-terminal, active work)
# ---------------------------------------------------------------------------

#: Lanes that count as "in-flight" for the purpose of step-removal warnings.
_INFLIGHT_LANES: frozenset[str] = frozenset(
    {
        "in_progress",
        "for_review",
        "in_review",
        "claimed",
    }
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class AffectedMission:
    """A single WP in a mission that is in-flight for a removed step."""

    mission_slug: str
    wp_id: str
    current_lane: str


@dataclass
class StepRemovalWarning:
    """Warning for a single removed step with the set of affected missions."""

    removed_step_id: str
    affected_missions: list[AffectedMission] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Core logic — T088
# ---------------------------------------------------------------------------


def find_removed_steps(
    current_sequence: list[str],
    incoming_sequence: list[str],
) -> list[str]:
    """Return step IDs that are in current but not in incoming.

    Parameters
    ----------
    current_sequence:
        The active action sequence before the override is applied.
    incoming_sequence:
        The action sequence being activated (the override).

    Returns
    -------
    list[str]
        Ordered list of removed step IDs (preserves order from current_sequence).
    """
    incoming_set = set(incoming_sequence)
    return [step for step in current_sequence if step not in incoming_set]


# ---------------------------------------------------------------------------
# In-flight mission scanner — T089
# ---------------------------------------------------------------------------


def scan_inflight_missions(
    removed_steps: list[str],
    mission_specs_dir: Path,
) -> list[StepRemovalWarning]:
    """Scan all missions for WPs in-flight for the removed steps.

    For each removed step ID, inspect every mission in ``mission_specs_dir``
    for WPs in a non-terminal (in-flight) lane.

    The step→lane mapping uses a simplified heuristic: any WP in an
    in-flight lane (``in_progress``, ``for_review``, ``in_review``,
    ``claimed``) is considered potentially affected by any step removal.
    This is conservative and keeps the implementation free of per-step
    lane-to-step reverse mapping (which would require knowing the mission's
    current position in the action sequence at runtime, a circular
    dependency).

    Parameters
    ----------
    removed_steps:
        Step IDs removed by the incoming override.
    mission_specs_dir:
        The ``kitty-specs/`` directory in the repository root.

    Returns
    -------
    list[StepRemovalWarning]
        One entry per removed step.  ``affected_missions`` is empty when
        no in-flight WPs are found for that step.
    """
    if not removed_steps:
        return []

    # Collect all in-flight WPs across all missions once, then map them to
    # each removed step (conservative: all removed steps get the same set).
    all_inflight = _collect_inflight_missions(mission_specs_dir)

    # Build one StepRemovalWarning per removed step, sharing the inflight list.
    return [
        StepRemovalWarning(
            removed_step_id=step_id,
            affected_missions=list(all_inflight),  # copy per step
        )
        for step_id in removed_steps
    ]


def _collect_inflight_missions(mission_specs_dir: Path) -> list[AffectedMission]:
    """Return in-flight WPs across every mission under ``mission_specs_dir``.

    Extracted from :func:`scan_inflight_missions` (S3776) so the per-mission
    scan is its own testable unit. Silently yields nothing when the directory
    is absent — the caller treats that as "no in-flight WPs found".
    """
    if not mission_specs_dir.is_dir():
        return []

    all_inflight: list[AffectedMission] = []
    for mission_dir in sorted(mission_specs_dir.iterdir()):
        if not mission_dir.is_dir():
            continue
        all_inflight.extend(_inflight_missions_for(mission_dir))
    return all_inflight


def _inflight_missions_for(mission_dir: Path) -> list[AffectedMission]:
    """Return in-flight WPs for a single mission directory.

    Skips missions with no ``status.events.jsonl``, an empty event log, or a
    corrupt one (best-effort scan — a broken mission must not abort the
    whole warning scan).
    """
    from specify_cli.status import read_events  # noqa: PLC0415 — lazy; avoids heavy import
    from specify_cli.status import reduce  # noqa: PLC0415

    events_file = mission_dir / "status.events.jsonl"
    if not events_file.exists():
        return []

    # Determine mission slug from meta.json (prefer) or directory name.
    mission_slug = _read_mission_slug(mission_dir)

    try:
        events = read_events(mission_dir)
    except Exception:  # noqa: BLE001, S112 — best-effort scan; skip corrupt files
        return []

    if not events:
        return []

    snapshot = reduce(events)
    return [
        AffectedMission(mission_slug=mission_slug, wp_id=wp_id, current_lane=lane)
        for wp_id, wp_state in snapshot.work_packages.items()
        if (lane := wp_state.get("lane", "")) in _INFLIGHT_LANES
    ]


def _read_mission_slug(mission_dir: Path) -> str:
    """Extract mission_slug from meta.json, falling back to directory name."""
    # load_meta_or_empty (post-#2091 silent contract) absorbs a missing or
    # malformed meta.json to {}, matching the prior try/except-pass absorption.
    meta = load_meta_or_empty(mission_dir)
    slug = meta.get("mission_slug") or meta.get("feature_slug")
    if slug:
        return str(slug)
    return mission_dir.name


# ---------------------------------------------------------------------------
# Warning emitter — T090
# ---------------------------------------------------------------------------


def emit_step_removal_warnings(
    warnings: list[StepRemovalWarning],
    console: Console,
) -> None:
    """Print structured warnings to *console* for each removed step.

    Produces output matching the format documented in FR-008:

    .. code-block:: text

        ⚠ Step 'review' removed by mission-type override.
          Affected missions:
          - 083-my-feature (WP03, currently in lane 'in_review')

    Only emits output when ``warnings`` contains at least one entry with
    at least one affected mission.  Silent when all steps have no affected
    missions.

    Parameters
    ----------
    warnings:
        Output of :func:`scan_inflight_missions`.
    console:
        Rich console to write warnings to.
    """
    for warning in warnings:
        if not warning.affected_missions:
            continue
        console.print(
            f"[yellow]⚠ Step '{warning.removed_step_id}' removed by mission-type override.[/yellow]"
        )
        console.print("  Affected missions:")
        for mission in warning.affected_missions:
            console.print(
                f"  - {mission.mission_slug} "
                f"({mission.wp_id}, currently in lane '{mission.current_lane}')"
            )
