"""orchestrator-api ``design-status`` verb (#5628).

Registered on the app by ``commands.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specify_cli.status import StatusSnapshot

import typer

from specify_cli.core.contract_gate import validate_outbound_payload

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


def _tasks_are_finalized(mission_dir: Path) -> bool:
    """True once ``finalize-tasks`` has bootstrapped canonical status for at
    least one WP -- the SAME signal ``bootstrap_canonical_state``
    (``status/bootstrap.py``) writes, and the SAME reduction ``list-ready``
    already performs via ``reduce(read_events(mission_dir))`` (T029: reuse
    finalize-tasks's own signal, not a new heuristic). A ``tasks/`` directory
    merely populated by an earlier tasks-outline/tasks-packages pass does
    NOT set this -- only finalize-tasks's own bootstrap write does (verified
    against ``status/bootstrap.py``: ``bootstrap_canonical_state`` is called
    exclusively from the finalize-tasks command family, never from the
    outline/packages phases).

    Torn/truncated read handling (ledger SK-131, WP06-001 review finding):
    two DISTINCT corruption shapes, two distinct defenses --

    1. A genuinely torn line (an unlocked-writer race landing mid-read;
       historically -- as of 2026-08 -- only 2 of 6 ``status.events.jsonl``
       writers took the mission status lock; WP01 of
       fsm-write-path-integrity-01M1TZV6 serialized all seven writer
       families, see that mission's ``design-notes/WP01-lock-rules.md``)
       breaks JSON parsing itself: ``read_events`` raises
       ``StoreError`` on a malformed JSON line or invalid event structure.
       This function does NOT catch that exception -- it propagates to
       ``design_status``, which turns it into a structured
       ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` failure envelope instead of
       guessing.
    2. A rollback-truncated log (``coordination/transaction.py``'s
       ``_rollback``: ``fh.truncate(self._pre_emit_size)``, a byte offset
       captured BEFORE the append began) does NOT break JSON parsing --
       the file is append-only, so truncating to a pre-append offset
       always lands on a line boundary and every remaining line is still
       valid JSON. ``StoreError`` never fires for this shape, so (1)'s
       defense does not catch it: silently reducing the truncated log
       would return a plausible-but-wrong ``current_phase``/
       ``next_action`` snapshot, exactly the silent-success failure class
       this repo names as dominant (live-reproduced: dropping a real
       tasks-finalized mission's trailing bootstrap event line whole
       returned ``current_phase: "plan"`` with no error).

       Defense: a structural drift check against ``status.json`` --
       finalize-tasks's own ``bootstrap_canonical_state`` already
       materializes it (``status/bootstrap.py``) as a persisted,
       INDEPENDENT record of "these WP ids are known", written via
       atomic tmp-then-rename (``status/reducer.py::materialize``), so it
       cannot itself be torn. If the persisted ``work_packages`` set
       names a WP id the FRESH event-log reduction no longer contains,
       the event log lost information relative to the last durable
       materialization -- the SAME ``SNAPSHOT_DRIFT`` concept
       ``audit/classifiers/status_json.py`` already names for
       ``doctor mission-state --fix`` (issue #1782), reused here for this
       read path rather than inventing a parallel one. That drift is
       surfaced as ``StoreError`` so it flows through the SAME
       ``DESIGN_STATUS_EVENT_LOG_UNREADABLE`` handling as (1) -- one
       failure code for "the log cannot be trusted", regardless of which
       of the two shapes broke it.

       This does not require modeling ``_rollback`` exactly: its own
       truncate-then-restore-status.json sequence is two independently
       ``try/except OSError``-guarded steps (transaction.py:922-971), not
       one atomic operation, so a crash or I/O failure between them
       leaves precisely this asymmetric state on disk -- truncated events,
       stale-but-larger status.json -- on the real rollback path itself,
       not only via the live reproduction's direct file edit.

    Inode replacement (adjacent hazard, examined): CANNOT occur for
    ``status.events.jsonl`` specifically, because every writer mutates the
    file'S CONTENT in place through the SAME inode -- ``append_event``
    opens in ``"a"`` mode, ``_rollback`` opens in ``"ab"`` mode and
    truncates -- neither ever ``os.replace()``s a new inode over this
    path (unlike ``status.json``/``decisions/index.json``, which DO use
    tmp-then-rename, and are safe for the opposite reason: a reader who
    already holds an fd open before a rename keeps reading the old
    inode's complete content; a reader who opens after gets the fully-new
    inode's complete content -- either way, no torn/mixed read is
    possible via rename). No reader here can observe a page composed of
    two different inodes' bytes, because only one inode ever exists for
    this file.
    """
    from specify_cli.status import read_events, reduce

    snapshot = reduce(read_events(mission_dir))
    _check_no_snapshot_drift(mission_dir, snapshot)
    return bool(snapshot.work_packages)


def _check_no_snapshot_drift(mission_dir: Path, snapshot: StatusSnapshot) -> None:
    """Raise ``StoreError`` if persisted ``status.json`` knows about a WP the
    freshly-reduced event log no longer contains (WP06-001 remediation).

    ``status.json`` is written by ``status/reducer.py::materialize`` via
    tmp-then-rename atomic replace, so a reader always sees either the
    fully-old or fully-new file, never a partial one -- there is no
    torn-read hazard on THIS side of the comparison. Its absence (no
    finalize-tasks bootstrap has ever run for this mission) is not drift;
    there is simply no persisted record yet to compare against.
    """
    from specify_cli.status import SNAPSHOT_FILENAME, StoreError

    status_json_path = mission_dir / SNAPSHOT_FILENAME
    if not status_json_path.exists():
        return

    try:
        persisted = json.loads(status_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StoreError(f"status.json could not be read for snapshot-drift comparison: {exc}") from exc

    persisted_wp_ids = set(persisted.get("work_packages") or {})
    fresh_wp_ids = set(snapshot.work_packages)
    missing = persisted_wp_ids - fresh_wp_ids
    if missing:
        raise StoreError(
            "snapshot drift: status.json's persisted work_packages set "
            f"names {sorted(missing)!r}, which the freshly-reduced "
            "status.events.jsonl no longer contains -- treating this as a "
            "torn/truncated event-log read (SNAPSHOT_DRIFT, cf. "
            "audit/classifiers/status_json.py, issue #1782) rather than "
            "trusting a silently-shrunk reduction"
        )


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
