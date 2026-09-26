"""RED-FIRST regression test for #4897.

``spec-kitty doctor mission-state --fix`` quarantined the authoritative
``DecisionPoint*`` rows out of a **healthy** mission's ``status.events.jsonl``
-- exit 0, ``errors=0`` -- because ``_is_preserved_non_lane_row``
(:mod:`specify_cli.migration.mission_state`) preserved only
``LIFECYCLE_EVENT_TYPES``, on the INVERTED belief that a DecisionPoint row's
"canonical store is elsewhere" (``decisions/index.json``). In truth
``decisions/index_fold.py`` rebuilds ``index.json`` FROM this event log, so
the log is the decision's only durable, authoritative copy; the durable
reader (:func:`specify_cli.status.store.is_non_lane_event`) already treats
every ``DecisionPoint*`` row as non-lane precisely because it is
authoritative, not disposable. The advertised follow-up
``doctor decisions --repair`` then rebuilt ``index.json`` from the emptied
log to zero entries, and ``agent decision list`` lost the record.

This test drives the repro through the REAL production surfaces
``doctor mission-state --fix`` / ``doctor decisions`` use under the hood --
:func:`specify_cli.decisions.service.open_decision` /
:func:`~specify_cli.decisions.service.resolve_decision` (the same service
layer ``agent decision open`` / ``resolve`` call),
:func:`specify_cli.migration.mission_state.repair_repo` (the same function
``doctor mission-state --fix`` calls), and
:func:`specify_cli.cli.commands._decisions_doctor._diagnose` (the same
reconciler ``doctor decisions`` calls) -- per the QA repro script in issue
#4897.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.cli.commands._decisions_doctor import _diagnose
from specify_cli.decisions import store as decisions_store
from specify_cli.decisions.models import OriginFlow
from specify_cli.decisions.service import open_decision, resolve_decision
from specify_cli.migration.mission_state import (
    _is_preserved_non_lane_row,
    _registry_authoritative_quarantine_violations,
    _row_level_repair_errors,
    repair_repo,
)
from specify_cli.status.lifecycle_events import (
    AUTHORITATIVE_NON_LANE_EVENT_TYPES,
    is_authoritative_non_lane_event_type,
)
from specify_cli.status.store import is_non_lane_event


pytestmark = [pytest.mark.integration, pytest.mark.regression]

_MISSION_SLUG = "regression-4897"
_MISSION_ID = "01KREGR4897MISSIONHEALTHY0"


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / _MISSION_SLUG


def _setup_mission(repo_root: Path) -> None:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00+00:00",
        "friendly_name": "Regression 4897",
    }
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _decision_point_rows(mission_dir: Path) -> list[dict[str, Any]]:
    events_path = mission_dir / "status.events.jsonl"
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if isinstance(row.get("event_type"), str) and row["event_type"].startswith("DecisionPoint")]


def _seed_wp01_lane_transition(mission_dir: Path) -> None:
    """Append a real WP01 ``planned -> claimed`` lane row.

    Without a co-located lane-transition row the mixed mission log would be
    dropped to zero rows by a buggy repair, which the pre-existing #2376
    all-dropped backstop (``_repair_mission``) already catches as a loud
    ``status="error"`` -- masking the #4897 defect, which is specifically
    that a MIXED log (lane rows + DecisionPoint rows, the realistic healthy-
    mission shape from the issue's QA repro script) survives the backstop
    and reports a silent ``status="updated"`` / ``errors=0`` success while
    quarantining the DecisionPoint rows.
    """
    lane_row = {
        "actor": "claude",
        "at": "2026-01-01T00:00:00+00:00",
        "event_id": "01KREGR4897LANEROWWP01AAA",
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "planned",
        "mission_id": _MISSION_ID,
        "mission_slug": _MISSION_SLUG,
        "to_lane": "claimed",
        "wp_id": "WP01",
    }
    events_path = mission_dir / "status.events.jsonl"
    with events_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(lane_row, sort_keys=True) + "\n")


def test_mission_state_fix_preserves_decision_point_rows_4897(tmp_path: Path) -> None:
    """``doctor mission-state --fix`` on a healthy mission with one resolved
    Decision Moment must not remove its ``DecisionPoint*`` rows; ``doctor
    decisions`` and ``agent decision list`` must stay unchanged (#4897).
    """
    repo_root = tmp_path
    _setup_mission(repo_root)
    mission_dir = _mission_dir(repo_root)
    _seed_wp01_lane_transition(mission_dir)

    open_response = open_decision(
        repo_root,
        _MISSION_SLUG,
        origin_flow=OriginFlow.PLAN,
        step_id="S1",
        input_key="db.engine",
        question="Which database engine?",
        options=("postgres", "sqlite"),
        actor="qa",
    )
    resolve_decision(
        repo_root,
        _MISSION_SLUG,
        open_response.decision_id,
        final_answer="postgres",
        rationale="team expertise",
        resolved_by="qa",
        actor="qa",
    )

    before_rows = _decision_point_rows(mission_dir)
    assert len(before_rows) == 2, "sanity: DecisionPointOpened + DecisionPointResolved must exist before repair"
    index_before = decisions_store.load_index(mission_dir)
    assert len(index_before.entries) == 1

    report = repair_repo(repo_root)

    result = report.missions[0]
    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0, "the DecisionPoint* rows must not be quarantined by a healthy repair (#4897)"

    after_rows = _decision_point_rows(mission_dir)
    assert len(after_rows) == 2, "doctor mission-state --fix must preserve both DecisionPoint rows (#4897)"
    assert after_rows == before_rows

    # #4966: ``_diagnose`` now takes (events_dir, ledger_dir, mission_slug) since
    # the ledger moved to the PRIMARY_METADATA partition. This is a FLAT/non-coord
    # mission, so the COORD events dir and the PRIMARY ledger dir coincide at
    # ``mission_dir`` — pass it for both, matching the flat-fixture caller in
    # tests/decisions/test_decisions_reconciler.py.
    diagnosis, _grouped = _diagnose(mission_dir, mission_dir, _MISSION_SLUG)
    assert diagnosis.clean, diagnosis
    assert diagnosis.orphaned_in_index == []

    index_after = decisions_store.load_index(mission_dir)
    assert len(index_after.entries) == 1
    assert index_after.entries[0].decision_id == open_response.decision_id


# ---------------------------------------------------------------------------
# T011 — single-authority guard: both consumers derive from ONE registry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", sorted(AUTHORITATIVE_NON_LANE_EVENT_TYPES))
def test_registry_members_agree_between_reader_and_repair(event_type: str) -> None:
    """Every registry member must be treated as non-lane-and-preserved by
    BOTH consumers -- a non-vacuous guard against the whack-a-field class
    (#2376 retrospective, #3066 ``WPStatusChanged``, #3541 ``review_result``,
    #4897 ``DecisionPoint*``) reopening a THIRD hand-maintained list that
    silently drifts from the other two.
    """
    row = {"event_id": "01REGISTRYAGREEMENTTEST00", "event_type": event_type, "payload": {}}

    assert is_authoritative_non_lane_event_type(event_type) is True
    assert is_non_lane_event(row) is True, f"{event_type!r} must be treated as non-lane by the durable reader"
    assert _is_preserved_non_lane_row(row) is True, f"{event_type!r} must be preserved by mission-state repair"


def test_non_registry_event_type_now_preserved_by_default() -> None:
    """#4993 (FR-001 inversion): an unregistered ``event_type`` is now
    preserved by repair, not quarantined.

    Before the inversion, this pinned the OPPOSITE behavior (repair
    quarantined any type outside the registry) as an intentional divergence
    from the reader. That divergence was the unregistered-future gap #4993
    closes: ``_is_preserved_non_lane_row`` now DELEGATES to the reader
    (:func:`is_non_lane_event`) with an EMPTY denylist, so any row the
    reader treats as non-lane -- including a type it has never seen before
    -- is preserved by construction, no registry update required.
    """
    row = {"event_id": "01UNKNOWNEVENTTYPETEST000", "event_type": "SomeFutureUnregisteredEvent", "payload": {}}

    assert is_authoritative_non_lane_event_type(row["event_type"]) is False
    assert is_non_lane_event(row) is True, "the reader's presence-based fallback skips it"
    assert _is_preserved_non_lane_row(row) is True, "repair now preserves a type outside the registry (#4993)"


def test_registry_contains_all_five_documented_decision_point_types() -> None:
    """Pins the WP02 floor: the registry contains at least the five
    ``DecisionPoint*`` types named in #4897 and in
    ``status/store.py``'s historical comment.
    """
    expected = {
        "DecisionPointOpened",
        "DecisionPointResolved",
        "DecisionPointDeferred",
        "DecisionPointCanceled",
        "DecisionPointWidened",
    }
    assert expected <= AUTHORITATIVE_NON_LANE_EVENT_TYPES


# --- T010 fail-closed guard: exercise the firing branch directly (review fold) ---
# The happy path can never reach these violations (the preservation predicate and
# the reader now share one registry), so the guard's error-emission is only
# reachable by feeding it a synthetic quarantine line -- a non-vacuous test that a
# FUTURE divergence (a registry-authoritative row reaching quarantine) is reported
# as an error rather than a silent errors=0 success (the exact #4897 defect shape).


def test_guard_flags_registry_authoritative_quarantined_row() -> None:
    line = json.dumps({"event_id": "01GUARDFIRE0000000000000000", "event_type": "DecisionPointResolved", "payload": {}})

    violations = _registry_authoritative_quarantine_violations([line])

    assert len(violations) == 1
    assert violations[0].startswith("registry_authoritative_row_quarantined:")
    assert "DecisionPointResolved" in violations[0]


def test_guard_now_flags_unregistered_reader_non_lane_line_ignores_unparseable() -> None:
    """#4993 (FR-002 strengthening): the guard now flags an unregistered but
    reader-non-lane quarantined line too (it should never have been
    quarantined at all under preserve-by-default) -- only a genuinely
    unparseable line is still ignored (nothing diagnosable to report).
    """
    unregistered = json.dumps({"event_id": "01X", "event_type": "SomeFutureUnregisteredEvent"})
    not_json = "{not valid json"

    violations = _registry_authoritative_quarantine_violations([unregistered, not_json])

    assert len(violations) == 1
    assert "01X" in violations[0]
    assert "SomeFutureUnregisteredEvent" in violations[0]


def test_row_level_repair_errors_unions_row_errors_with_guard_violations() -> None:
    authoritative = json.dumps({"event_id": "01Y", "event_type": "DecisionPointOpened"})

    combined = _row_level_repair_errors([authoritative], ["pre-existing canonicalization error"])

    assert combined[0] == "pre-existing canonicalization error"
    assert any(v.startswith("registry_authoritative_row_quarantined:") for v in combined)
