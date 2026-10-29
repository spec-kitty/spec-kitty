"""Duplicated decision openings fold; the reopen rule comes from spec-kitty-events.

#4848: two concurrent identical ``decision open`` calls (or a concurrent retry
after an interrupted open) could each append a ``DecisionPointOpened`` row for
the same decision. Both writers build the opening from the same saved index
entry, so the payloads are equal except ``recorded_at`` (the envelope
``event_id`` and ``at`` differ too). Logs that already hold such rows must read
again: the fold accepts them and folds the earliest, in any row order. Any
other payload difference is still a malformed group.

#6412 (reader half): the deferred -> resolved reopen rule is read from
``spec_kitty_events.decisionpoint.DECISION_POINT_TERMINAL_REOPEN``; the CLI keeps
no local copy of the table.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import pytest
from spec_kitty_events.decision_moment import TerminalOutcome
from spec_kitty_events.decisionpoint import DECISION_POINT_OPENED, DECISION_POINT_TERMINAL_REOPEN

from specify_cli.decisions import index_fold
from specify_cli.decisions.index_fold import FoldError, fold_events, is_allowed_terminal_reopen
from specify_cli.decisions.models import DecisionStatus, OriginFlow
from specify_cli.decisions.service import open_decision, resolve_decision

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KTEST_DUPOPEN_MISSION_000"
MISSION_SLUG = "duplicate-open-mission"

Envelope = dict[str, Any]


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup_meta(repo_root: Path) -> None:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _events_for_decision(repo_root: Path, decision_id: str) -> list[Envelope]:
    events_path = _mission_dir(repo_root) / "status.events.jsonl"
    rows = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [row for row in rows if row.get("payload", {}).get("decision_point_id") == decision_id]


def _open(repo_root: Path) -> str:
    _setup_meta(repo_root)
    resp = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="dup-open-step",
        input_key="dup-open-key",
        question="How large is the team?",
        options=("1-5", "6-20"),
        actor="alice",
    )
    return resp.decision_id


def _opened_row(events: list[Envelope]) -> Envelope:
    (opened,) = [e for e in events if e["event_type"] == DECISION_POINT_OPENED]
    return opened


def _later_copy(opened: Envelope, n: int, **payload_changes: Any) -> Envelope:
    """A second opening row as a concurrent writer appends it: new ``event_id``,
    later ``at`` and later ``payload.recorded_at``; the rest of the payload equal
    unless *payload_changes* say otherwise."""
    payload = {**opened["payload"], "recorded_at": f"2099-01-0{n}T00:00:00+00:00", **payload_changes}
    return {**opened, "event_id": f"{opened['event_id']}-dup{n}", "at": f"2099-01-0{n}T00:00:00+00:00", "payload": payload}


@pytest.mark.parametrize("original_first", [True, False], ids=["original-first", "duplicate-first"])
def test_identical_duplicate_openings_fold_like_one(tmp_path: Path, original_first: bool) -> None:
    decision_id = _open(tmp_path)
    original = _opened_row(_events_for_decision(tmp_path, decision_id))
    duplicate = _later_copy(original, 1)
    rows = [original, duplicate] if original_first else [duplicate, original]

    assert fold_events(rows) == fold_events([original])


def test_identical_duplicate_openings_with_terminal_row_fold(tmp_path: Path) -> None:
    decision_id = _open(tmp_path)
    resolve_decision(
        tmp_path,
        MISSION_SLUG,
        decision_id,
        final_answer="6-20",
        other_answer=False,
        rationale="measured headcount",
        resolved_by="bob",
        actor="bob",
    )
    events = _events_for_decision(tmp_path, decision_id)
    duplicate = _later_copy(_opened_row(events), 1)

    folded = fold_events([*events, duplicate])

    assert folded == fold_events(events)
    assert folded.status == DecisionStatus.RESOLVED
    assert folded.final_answer == "6-20"


def test_three_identical_openings_fold(tmp_path: Path) -> None:
    decision_id = _open(tmp_path)
    original = _opened_row(_events_for_decision(tmp_path, decision_id))
    rows = [_later_copy(original, 2), original, _later_copy(original, 1)]

    for permutation in itertools.permutations(rows):
        assert fold_events(list(permutation)) == fold_events([original])


@pytest.mark.parametrize("original_first", [True, False], ids=["original-first", "duplicate-first"])
def test_duplicate_openings_differing_payload_refuse(tmp_path: Path, original_first: bool) -> None:
    """Positive control on the same fixture: only ``recorded_at`` may differ."""
    decision_id = _open(tmp_path)
    original = _opened_row(_events_for_decision(tmp_path, decision_id))
    differing = _later_copy(original, 1, question="A different question?")
    rows = [original, differing] if original_first else [differing, original]

    with pytest.raises(FoldError, match="more than one DecisionPointOpened"):
        fold_events(rows)


_OUTCOME_STATUS = {
    TerminalOutcome.RESOLVED: DecisionStatus.RESOLVED,
    TerminalOutcome.DEFERRED: DecisionStatus.DEFERRED,
    TerminalOutcome.CANCELED: DecisionStatus.CANCELED,
}


def test_reopen_rule_comes_from_events_package() -> None:
    assert not hasattr(index_fold, "ALLOWED_TERMINAL_REOPEN"), "the CLI must keep no local copy of the reopen table"

    allowed = {(_OUTCOME_STATUS[a], _OUTCOME_STATUS[b]) for a, b in DECISION_POINT_TERMINAL_REOPEN}
    assert allowed, "the events package must declare at least one legal reopen"
    terminal = list(_OUTCOME_STATUS.values())
    for current, target in itertools.product(terminal, terminal):
        assert is_allowed_terminal_reopen(current, target) is ((current, target) in allowed), (current, target)
    # Verdicts unchanged: defer -> resolve is the only reopen.
    assert allowed == {(DecisionStatus.DEFERRED, DecisionStatus.RESOLVED)}
