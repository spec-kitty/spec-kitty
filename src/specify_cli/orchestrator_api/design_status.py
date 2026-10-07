"""orchestrator-api ``design-status`` verb (#5628).

Registered on the app by ``commands.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from specify_cli.core.contract_gate import validate_outbound_payload
from specify_cli.status import (
    check_no_snapshot_drift as _check_no_snapshot_drift,
    tasks_are_finalized as _tasks_are_finalized,
)

from .envelope import (
    make_envelope,
)


from . import _common
from ._common import (
    _HELP_MISSION_SLUG,
    _emit,
    _fail,
    _planning_read_dir,
)

__all__ = ["design_status", "_tasks_are_finalized", "_check_no_snapshot_drift"]


# ---------------------------------------------------------------------------
# Command: design-status (WP06, FR-010)
#
# A narrow, design-phase-only reduction over on-disk artifact presence
# (spec.md/plan.md/tasks/-finalized/analysis-report.md, all PRIMARY-partition)
# and the decisions/index.json ledger (COORD-partition) -- spec Clarification
# 6. Mirrors list-ready's own "no state transition, no event emission"
# read-only contract: no --policy required, reduces state rather than
# invoking the full DAG engines.
#
# HARD CONSTRAINT (Clarification 6): never import or call
# resolve_next_workflow_action (_internal_runtime/planner.py) or
# decide_next/_resolve_next_unified_step/runtime_bridge.query_current_state --
# both return a WP-loop/run-state-shaped payload (action/wp_id/prompt_file),
# not FR-010's four design-phase fields, and decide_next's query path
# materializes/reads a runtime run (get_or_start_run) as a side effect this
# read-only verb must not depend on. A reviewer should reject any import of
# either.
# ---------------------------------------------------------------------------


def _open_decisions(mission_dir: Path) -> list[dict[str, str]]:
    """Return ``{decision_id, origin}`` for every OPEN entry in the
    decisions ledger, regardless of which design phase opened it (spec
    Acceptance Scenario 2: an open decision from an earlier phase still
    blocks phase advancement).

    ``decisions/index.json`` is written via ``tmp-then-rename`` atomic
    replace (``decisions/store.py::_atomic_write``), so -- unlike
    ``status.events.jsonl`` -- there is no torn-read hazard here: a reader
    always sees either the fully-old or fully-new file, never a partial one.
    """
    from specify_cli.decisions.store import load_index

    index = load_index(mission_dir)
    return [{"decision_id": entry.decision_id, "origin": entry.origin_flow.value} for entry in index.entries if entry.status.value == "open"]


def _reduce_design_status(planning_dir: Path, mission_dir: Path) -> dict[str, Any]:
    """The core FR-010 reduction: ``current_phase``/``next_action`` from
    on-disk artifact presence, ``open_decisions`` from the ledger.

    ``planning_dir`` is the PRIMARY-surface mission dir (``spec.md``/
    ``plan.md``/``tasks/``/``analysis-report.md`` -- all PRIMARY-partition
    kinds per ``mission_runtime.artifacts._PRIMARY_ARTIFACT_KINDS``).
    ``mission_dir`` is the COORD-aware status dir (``status.events.jsonl``/
    ``decisions/index.json`` -- both STATUS_STATE-kind), the SAME
    resolution ``list-ready`` already uses for its own event-log reduction.

    Phase naming: ``current_phase`` names the phase whose artifact is
    present but not yet superseded by the next phase's artifact (matching
    spec Acceptance Scenario 1's literal "spec.md scaffolded ->
    current_phase: specify" example); ``next_action`` always names the VERB
    the host should call next. An open decision overrides ``next_action``
    to ``resolve-decision`` regardless of phase (Acceptance Scenario 2).
    """
    spec_exists = (planning_dir / "spec.md").exists()
    plan_exists = (planning_dir / "plan.md").exists()
    tasks_finalized = _tasks_are_finalized(mission_dir)
    analysis_exists = (planning_dir / "analysis-report.md").exists()

    current_phase: str
    next_action: str | None
    if not spec_exists:
        current_phase, next_action = "specify", "specify"
    elif not plan_exists:
        current_phase, next_action = "specify", "plan"
    elif not tasks_finalized:
        current_phase, next_action = "plan", "tasks"
    elif not analysis_exists:
        current_phase, next_action = "tasks", "check-prerequisites"
    else:
        current_phase, next_action = "analyze", None

    open_decisions = _open_decisions(mission_dir)
    if open_decisions:
        next_action = "resolve-decision"

    return {
        "current_phase": current_phase,
        "next_action": next_action,
        "open_decisions": open_decisions,
    }


def design_status(
    mission: str = typer.Option(..., "--mission", help=_HELP_MISSION_SLUG),
) -> None:
    """Read-only design-phase status query (FR-010) -- mirrors ``list-ready``'s
    no-state-transition, no-event-emission, no-``--policy`` contract for the
    design pipeline instead of the WP loop.

    Never delegates to ``resolve_next_workflow_action`` or
    ``decide_next``/``query_current_state`` -- see the Clarification-6
    module comment above ``_tasks_are_finalized``.
    """
    cmd = "design-status"

    main_repo_root = _common._get_main_repo_root()
    mission_dir = _common._resolve_mission_dir_or_fail(cmd, main_repo_root, mission)
    planning_dir = _planning_read_dir(main_repo_root, mission)

    from pydantic import ValidationError

    from specify_cli.decisions.store import DecisionIndexReadError
    from specify_cli.status import StoreError

    try:
        reduction = _reduce_design_status(planning_dir, mission_dir)
    except StoreError as exc:
        _fail(
            cmd,
            "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
            f"status.events.jsonl could not be read cleanly for mission {mission!r}: {exc}",
            {"mission_slug": mission, "error": str(exc)},
        )
        return
    except (json.JSONDecodeError, ValidationError, DecisionIndexReadError) as exc:
        # ``_open_decisions`` -> ``decisions.store.load_index`` reads
        # ``decisions/index.json`` inside the SAME reduction this ``try``
        # guards -- a hand-corrupted index (malformed JSON, non-UTF-8, or
        # schema-invalid) now fails closed as the wrapping
        # ``DecisionIndexReadError`` (#4642); the raw ``json.JSONDecodeError`` /
        # pydantic ``ValidationError`` are retained defensively. None is a
        # ``StoreError``. Reuse the SAME typed STORE error envelope the
        # torn-``status.events.jsonl`` shapes above already produce, rather
        # than letting either exception escape un-enveloped.
        _fail(
            cmd,
            "DESIGN_STATUS_EVENT_LOG_UNREADABLE",
            f"decisions/index.json could not be read cleanly for mission {mission!r}: {exc}",
            {"mission_slug": mission, "error": str(exc)},
        )
        return

    data = {
        **_common._mission_identity_payload(mission_dir),
        **reduction,
    }
    validate_outbound_payload(data, "orchestrator_api")
    envelope = make_envelope(command=cmd, success=True, data=data)
    _emit(envelope)
