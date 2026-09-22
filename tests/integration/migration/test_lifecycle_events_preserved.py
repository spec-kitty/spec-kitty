"""Regression: mission-state repair preserves canonical lifecycle events (#2376)
and Decision-Moment events (#4897).

A completed mission's ``status.events.jsonl`` legitimately holds canonical
lifecycle events (``MissionCreated``, ``SpecifyStarted``, ``WPCreated``) whose
*only* per-mission home is this file (see
:mod:`specify_cli.status.lifecycle_events`). The repair previously quarantined
all ``event_type`` rows and emptied such a log. This test pins the corrected
contract: canonical lifecycle events are preserved in place; the log is never
emptied.

Decision-Moment rows (``DecisionPoint*``) are ALSO preserved (#4897): the
event log is these events' canonical store -- ``decisions/index_fold.py``
rebuilds ``decisions/index.json`` FROM this log, so the copy here is not a
disposable mirror. (Before #4897 this module's own docstring asserted the
opposite -- that the mirror was safely prunable -- and the repair quarantined
it out of every healthy mission with a ``DecisionPoint*`` row.)

The fixtures are built through the canonical event producers (C-007 / #1248) —
``emit_mission_created_local`` / ``emit_artifact_phase`` / ``emit_wp_created_local``
for the lifecycle rows and ``emit_decision_opened`` for the Decision-Moment
mirror — rather than hand-assembled ``{event_type, payload}`` dicts. The producers
generate realistic Crockford ULID ``event_id`` values, which the assertions read
back from the on-disk log.
"""

from __future__ import annotations

import json
from kernel.clock import UTC, datetime
from pathlib import Path

import pytest
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED

from specify_cli.decisions.emit import emit_decision_opened
from specify_cli.decisions.models import DecisionStatus, IndexEntry, OriginFlow
from specify_cli.migration.mission_state import _repair_mission
from specify_cli.retrospective.events import CompletedPayload, emit_retrospective_event
from specify_cli.retrospective.schema import ActorRef
from specify_cli.status.models import InnerStateChanged, WPInnerStateDelta
from specify_cli.status.store import append_annotations_atomic_verified
from specify_cli.status.lifecycle_events import (
    SPECIFY_STARTED,
    emit_artifact_phase,
    emit_mission_created_local,
    emit_wp_created_local,
    mission_event_log_path,
)

pytestmark = pytest.mark.integration

_MISSION_ID = "01KWN9D0MJ79NK1T90RWYY2Y7R"
_DECISION_ID = "01KWN9YWCZBHNWQCKSY7EXMQDS"


def _seed_meta(mission_dir: Path) -> None:
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": "m",
                "mission_id": _MISSION_ID,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-07-04T00:45:00+00:00",
            }
        ),
        encoding="utf-8",
    )


def _emit_lifecycle_events(mission_dir: Path) -> set[str]:
    """Emit the three canonical lifecycle events; return their ``event_id`` set.

    Uses the durable local-first producers (their *only* per-mission home is
    ``status.events.jsonl``), so the repair MUST preserve every emitted row.
    """
    created = emit_mission_created_local(
        mission_dir,
        mission_slug="m",
        mission_id=_MISSION_ID,
        mission_number=None,
        mission_type="software-dev",
        target_branch="main",
        created_at="2026-07-04T00:45:35+00:00",
    )
    specify = emit_artifact_phase(
        mission_dir,
        event_type=SPECIFY_STARTED,
        mission_slug="m",
        at="2026-07-04T00:46:00+00:00",
    )
    wp = emit_wp_created_local(
        mission_dir,
        mission_slug="m",
        wp_id="WP01",
        wp_title="Decompose the god-module",
        created_at="2026-07-04T00:47:00+00:00",
    )
    assert created is not None
    assert specify is not None
    assert wp is not None
    return {created["event_id"], specify["event_id"], wp["event_id"]}


def _emit_decision_mirror(tmp_path: Path, mission_dir: Path) -> str:
    """Emit a canonical ``DecisionPointOpened`` mirror; return its ``event_id``.

    ``status.events.jsonl`` is this event's canonical store (#4897):
    ``decisions/index.json`` is REBUILT FROM this log, so the repair must
    preserve this row in place, not quarantine it.
    """
    entry = IndexEntry(
        decision_id=_DECISION_ID,
        origin_flow=OriginFlow.PLAN,
        input_key="merge-strategy",
        question="Which merge strategy for the god-module split?",
        options=("consolidate", "defer"),
        status=DecisionStatus.OPEN,
        created_at=datetime(2026, 7, 4, 0, 55, 20, tzinfo=UTC),
        mission_id=_MISSION_ID,
        mission_slug="m",
        step_id="plan.q1",
    )
    emit_decision_opened(tmp_path, "m", decision_id=_DECISION_ID, entry=entry, actor="claude")
    return _find_event_id(mission_event_log_path(mission_dir), DECISION_POINT_OPENED)


def _write_mission(tmp_path: Path, *, with_decision: bool) -> tuple[Path, Path, set[str], str | None]:
    """Seed a mission whose event log is built via canonical producers.

    Returns ``(mission_dir, log, lifecycle_event_ids, decision_event_id)``.
    ``decision_event_id`` is ``None`` when ``with_decision`` is false.
    """
    mission_dir = tmp_path / "kitty-specs" / "m"
    mission_dir.mkdir(parents=True)
    _seed_meta(mission_dir)

    lifecycle_ids = _emit_lifecycle_events(mission_dir)
    decision_id = _emit_decision_mirror(tmp_path, mission_dir) if with_decision else None

    return mission_dir, mission_event_log_path(mission_dir), lifecycle_ids, decision_id


def _find_event_id(log: Path, event_type: str) -> str:
    for line in log.read_text(encoding="utf-8").splitlines():
        obj = json.loads(line)
        if obj.get("event_type") == event_type:
            return str(obj["event_id"])
    raise AssertionError(f"no {event_type} row was written to {log}")


def _event_ids(text: str) -> set[str]:
    return {json.loads(line)["event_id"] for line in text.splitlines() if line.strip()}


def test_lifecycle_only_log_is_fully_preserved(tmp_path: Path) -> None:
    """The moov-shaped failure: a log of only canonical lifecycle events must
    survive intact with zero quarantines (it was being emptied to 0 bytes)."""
    mission_dir, log, _lifecycle_ids, _ = _write_mission(tmp_path, with_decision=False)
    before_ids = _event_ids(log.read_text(encoding="utf-8"))

    result = _repair_mission(tmp_path, mission_dir, run_id="lifecycle-only")

    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0
    after_text = log.read_text(encoding="utf-8")
    assert after_text.strip(), "repair must not empty a lifecycle-only log"
    assert _event_ids(after_text) == before_ids


def test_lifecycle_and_decision_mirror_both_preserved(tmp_path: Path) -> None:
    """Mixed log: lifecycle events AND the DecisionPoint mirror are both
    preserved (#4897); zero rows are quarantined and the log is not emptied.
    """
    mission_dir, log, lifecycle_ids, decision_id = _write_mission(tmp_path, with_decision=True)
    assert decision_id is not None

    result = _repair_mission(tmp_path, mission_dir, run_id="mixed")

    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0
    surviving = _event_ids(log.read_text(encoding="utf-8"))
    for event_id in lifecycle_ids:
        assert event_id in surviving
    assert decision_id in surviving


def _emit_retrospective_completed(mission_dir: Path) -> str:
    """Emit a canonical ``retrospective.completed`` row; return its ``event_id``.

    Retrospective rows use the ``event_name`` envelope (``retrospective.*``) —
    a THIRD reader-preserved non-lane class (see
    :func:`specify_cli.status.store.is_non_lane_event`). Their only per-mission
    home is ``status.events.jsonl``; the reducer / retrospective gate + summary
    read them back as load-bearing state.
    """
    event_id = emit_retrospective_event(
        feature_dir=mission_dir,
        mission_slug="m",
        mission_id=_MISSION_ID,
        mid8=_MISSION_ID[:8],
        actor=ActorRef(kind="agent", id="claude", profile_id="reviewer-renata"),
        event_name="retrospective.completed",
        payload=CompletedPayload(
            record_path="kitty-specs/m/retrospective/record.md",
            record_hash="sha256:" + "0" * 64,
            findings_summary={"helped": 3, "not_helpful": 0, "gaps": 1},
            proposals_count=2,
        ),
    )
    return event_id


def test_retrospective_event_name_row_is_preserved(tmp_path: Path) -> None:
    """#2376 residual: a ``retrospective.*`` (``event_name`` envelope) row shares
    the log with lifecycle rows and MUST survive repair with zero quarantines.

    This is the same #2376 data-loss class in a different event format: the
    repair's ``_is_preserved_non_lane_row`` predicate must match the durable
    reader ``is_non_lane_event``, which preserves rows whose ``event_name``
    starts with ``"retrospective."``. Before the predicate was aligned the
    retrospective row was silently stripped (``quarantined_rows == 1``).
    """
    mission_dir, log, lifecycle_ids, _ = _write_mission(tmp_path, with_decision=False)
    retro_id = _emit_retrospective_completed(mission_dir)
    before_ids = _event_ids(log.read_text(encoding="utf-8"))
    assert retro_id in before_ids

    result = _repair_mission(tmp_path, mission_dir, run_id="retro")

    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0
    surviving = _event_ids(log.read_text(encoding="utf-8"))
    assert retro_id in surviving, "the retrospective.* row must survive repair"
    for event_id in lifecycle_ids:
        assert event_id in surviving


def test_retrospective_and_decision_mirror_both_preserved(tmp_path: Path) -> None:
    """Mixed log with all preserved classes: lifecycle + retrospective +
    DecisionPoint mirror ALL survive (#4897); zero rows are quarantined."""
    mission_dir, log, lifecycle_ids, decision_id = _write_mission(tmp_path, with_decision=True)
    assert decision_id is not None
    retro_id = _emit_retrospective_completed(mission_dir)

    result = _repair_mission(tmp_path, mission_dir, run_id="mixed-retro")

    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0
    surviving = _event_ids(log.read_text(encoding="utf-8"))
    assert retro_id in surviving
    for event_id in lifecycle_ids:
        assert event_id in surviving
    assert decision_id in surviving


def _emit_inner_state_annotation(mission_dir: Path) -> str:
    """Emit a canonical ``InnerStateChanged`` annotation; return its ``event_id``.

    Annotations use the ``kind: "annotation"`` envelope — a FOURTH
    reader-preserved non-lane class (see
    :func:`specify_cli.status.store.is_non_lane_event`, whose explicit
    ``kind == ANNOTATION_KIND`` branch is deliberately placed FIRST). They carry
    no ``from_lane``/``to_lane`` by construction and their only per-mission home
    is ``status.events.jsonl``; the reducer folds their typed
    :class:`WPInnerStateDelta` into the per-WP runtime slots.

    Written through the durability-verified producer
    :func:`append_annotations_atomic_verified` (C-007 / #1248) rather than a
    hand-assembled dict, matching the rows ``migration:backfill_runtime_state``
    put in the dogfood corpus.
    """
    annotation = InnerStateChanged(
        event_id="01KWNA4XQF7T3M0GZC1B8VD2WR",
        wp_id="WP01",
        at="2026-07-04T00:48:00+00:00",
        actor="migration:backfill_runtime_state",
        delta=WPInnerStateDelta(subtasks={"T001": "done", "T002": "done"}),
    )
    append_annotations_atomic_verified(mission_dir, [annotation])
    return annotation.event_id


def test_annotation_row_is_preserved(tmp_path: Path) -> None:
    """#2376 residual: a ``kind: "annotation"`` row shares the log with lifecycle
    rows and MUST survive repair with zero quarantines.

    This is the same #2376 data-loss class in a FOURTH event format. The repair's
    ``_is_preserved_non_lane_row`` predicate routes only on ``event_name`` /
    ``event_type`` / retrospective, so an annotation row matches none of them,
    falls through ``_rule_reject_non_status_event``'s passthrough, and reaches
    ``_rule_require_to_lane`` — which hard-errors with "missing required to_lane"
    on a row that carries no lane fields by construction. The whole mission
    repair then aborts, so the TeamSpace gate can never clear.

    Preserve is the only correct disposition: annotations are load-bearing
    (the reducer folds them into runtime slots), so quarantining them would
    reopen #2376 rather than fix it.
    """
    mission_dir, log, lifecycle_ids, _ = _write_mission(tmp_path, with_decision=False)
    annotation_id = _emit_inner_state_annotation(mission_dir)
    before_ids = _event_ids(log.read_text(encoding="utf-8"))
    assert annotation_id in before_ids

    result = _repair_mission(tmp_path, mission_dir, run_id="annotation")

    assert result.status != "error", result.validation_errors
    assert not any("missing required to_lane" in err for err in result.validation_errors), "an annotation row must never be asked for a to_lane it cannot have"
    assert result.quarantined_rows == 0
    surviving = _event_ids(log.read_text(encoding="utf-8"))
    assert annotation_id in surviving, "the annotation row must survive repair"
    for event_id in lifecycle_ids:
        assert event_id in surviving


def test_annotation_and_decision_mirror_both_preserved(tmp_path: Path) -> None:
    """Mixed log with all five preserved classes: lifecycle + retrospective +
    annotation + DecisionPoint mirror ALL survive (#4897); zero quarantines."""
    mission_dir, log, lifecycle_ids, decision_id = _write_mission(tmp_path, with_decision=True)
    assert decision_id is not None
    retro_id = _emit_retrospective_completed(mission_dir)
    annotation_id = _emit_inner_state_annotation(mission_dir)

    result = _repair_mission(tmp_path, mission_dir, run_id="mixed-annotation")

    assert result.status != "error", result.validation_errors
    assert result.quarantined_rows == 0
    surviving = _event_ids(log.read_text(encoding="utf-8"))
    assert retro_id in surviving
    assert annotation_id in surviving
    for event_id in lifecycle_ids:
        assert event_id in surviving
    assert decision_id in surviving


def test_backstop_never_empties_when_all_rows_preserved(tmp_path: Path) -> None:
    """Idempotence + backstop: re-running on a lifecycle-only log is a no-op and
    never empties it."""
    mission_dir, log, lifecycle_ids, _ = _write_mission(tmp_path, with_decision=False)

    _repair_mission(tmp_path, mission_dir, run_id="first")
    first = log.read_text(encoding="utf-8")
    _repair_mission(tmp_path, mission_dir, run_id="second")
    second = log.read_text(encoding="utf-8")

    assert first.strip()
    assert second.strip()
    assert _event_ids(second) == lifecycle_ids
