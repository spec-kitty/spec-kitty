"""T018 — Unit tests for service resolve/defer/cancel terminal command semantics.

Tests verify idempotency on exact re-call, conflict rejection on contradictory
re-call, and that each terminal outcome updates the index and artifact correctly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.decisions.models import DecisionErrorCode, DecisionStatus, OriginFlow
from specify_cli.decisions.service import (
    DecisionError,
    cancel_decision,
    defer_decision,
    open_decision,
    resolve_decision,
)
from specify_cli.decisions import store as _store

pytestmark = [pytest.mark.unit, pytest.mark.fast]

MISSION_ID = "01KTEST_MISSION_ID_000001"
MISSION_SLUG = "test-mission"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup_meta(repo_root: Path) -> None:
    """Create meta.json so open_decision can resolve mission_id."""
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _open_decision(repo_root: Path) -> str:
    """Open a fresh decision and return its decision_id."""
    _setup_meta(repo_root)
    with patch("specify_cli.decisions.emit.emit_decision_opened", return_value=1):
        resp = open_decision(
            repo_root,
            MISSION_SLUG,
            origin_flow=OriginFlow.CHARTER,
            step_id="step-1",
            input_key="team_size",
            question="How large is the team?",
            options=("1-5", "6-20", "20+"),
            actor="alice",
        )
    return resp.decision_id


def _resolve(
    repo_root: Path,
    decision_id: str,
    *,
    final_answer: str = "1-5",
    other_answer: bool = False,
    rationale: str | None = None,
    resolved_by: str | None = None,
    dry_run: bool = False,
):
    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        return resolve_decision(
            repo_root,
            MISSION_SLUG,
            decision_id,
            final_answer=final_answer,
            other_answer=other_answer,
            rationale=rationale,
            resolved_by=resolved_by,
            actor="alice",
            dry_run=dry_run,
        )


def _defer(
    repo_root: Path,
    decision_id: str,
    *,
    rationale: str = "not sure yet",
    dry_run: bool = False,
):
    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        return defer_decision(
            repo_root,
            MISSION_SLUG,
            decision_id,
            rationale=rationale,
            actor="alice",
            dry_run=dry_run,
        )


def _cancel(
    repo_root: Path,
    decision_id: str,
    *,
    rationale: str = "no longer needed",
    dry_run: bool = False,
):
    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        return cancel_decision(
            repo_root,
            MISSION_SLUG,
            decision_id,
            rationale=rationale,
            actor="alice",
            dry_run=dry_run,
        )


# ---------------------------------------------------------------------------
# T018a — resolve transitions status to RESOLVED with final_answer
# ---------------------------------------------------------------------------


def test_resolve_transitions_to_resolved(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    resp = _resolve(tmp_path, did)

    assert resp.status == DecisionStatus.RESOLVED
    assert resp.terminal_outcome == "resolved"
    assert not resp.idempotent

    # Check index
    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.RESOLVED
    assert entry.final_answer == "1-5"


def test_resolve_writes_artifact(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    _resolve(tmp_path, did)
    artifact = _store.artifact_path(_mission_dir(tmp_path), did)
    assert artifact.exists()
    content = artifact.read_text()
    assert "resolved" in content


# ---------------------------------------------------------------------------
# T018b — resolve twice with identical payload is idempotent
# ---------------------------------------------------------------------------


def test_resolve_twice_same_answer_is_idempotent(tmp_path: Path) -> None:
    # Re-pinned (#5681, NFR-004): real emit, so the second call is a true no-op
    # rather than silently taking the missing-event repair branch under a mock.
    did = _open_real(tmp_path)
    _call("resolve", tmp_path, did)
    resp2 = _call("resolve", tmp_path, did)

    assert resp2.idempotent is True
    assert resp2.event_lamport is None
    assert len(_rows(tmp_path, did, "resolved")) == 1


def test_resolve_idempotent_emits_no_second_event(tmp_path: Path) -> None:
    # Re-pinned (#5681, NFR-004): the old version mocked the emit, so no row ever
    # landed and a correct retry must now treat that as interrupted. With a real
    # emit: the retry neither calls the emit nor adds a second row.
    did = _open_real(tmp_path)
    _call("resolve", tmp_path, did)
    with patch("specify_cli.decisions.emit.emit_decision_resolved") as mock_emit:
        resp = _call("resolve", tmp_path, did)

    mock_emit.assert_not_called()
    assert resp.idempotent is True
    assert len(_rows(tmp_path, did, "resolved")) == 1


# ---------------------------------------------------------------------------
# T018c — resolve after defer closes the decision
# ---------------------------------------------------------------------------


def test_resolve_after_defer_transitions_to_resolved(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    _defer(tmp_path, did)

    resp = _resolve(tmp_path, did, final_answer="accept plan default")

    assert resp.status == DecisionStatus.RESOLVED
    assert resp.terminal_outcome == "resolved"
    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.RESOLVED
    assert entry.final_answer == "accept plan default"


# ---------------------------------------------------------------------------
# T018d — resolve twice with different final_answer raises TERMINAL_CONFLICT
# ---------------------------------------------------------------------------


def test_resolve_twice_different_answer_raises_conflict(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    _resolve(tmp_path, did, final_answer="1-5")

    with pytest.raises(DecisionError) as exc_info:
        _resolve(tmp_path, did, final_answer="6-20")

    assert exc_info.value.code == DecisionErrorCode.TERMINAL_CONFLICT


# ---------------------------------------------------------------------------
# T018e — defer transitions status to DEFERRED with rationale
# ---------------------------------------------------------------------------


def test_defer_transitions_to_deferred(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    resp = _defer(tmp_path, did, rationale="need more info")

    assert resp.status == DecisionStatus.DEFERRED
    assert resp.terminal_outcome == "deferred"
    assert not resp.idempotent

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.DEFERRED
    assert entry.rationale == "need more info"


# ---------------------------------------------------------------------------
# T018f — cancel transitions status to CANCELED with rationale
# ---------------------------------------------------------------------------


def test_cancel_transitions_to_canceled(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    resp = _cancel(tmp_path, did, rationale="no longer applicable")

    assert resp.status == DecisionStatus.CANCELED
    assert resp.terminal_outcome == "canceled"
    assert not resp.idempotent

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.CANCELED
    assert entry.rationale == "no longer applicable"


# ---------------------------------------------------------------------------
# T018g — resolve with nonexistent decision_id raises NOT_FOUND
# ---------------------------------------------------------------------------


def test_resolve_nonexistent_raises_not_found(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    with pytest.raises(DecisionError) as exc_info:
        _resolve(tmp_path, "NONEXISTENT_DECISION_ID_XXXX")

    assert exc_info.value.code == DecisionErrorCode.NOT_FOUND


def test_defer_nonexistent_raises_not_found(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    with pytest.raises(DecisionError) as exc_info:
        _defer(tmp_path, "NONEXISTENT_DECISION_ID_XXXX")

    assert exc_info.value.code == DecisionErrorCode.NOT_FOUND


def test_cancel_nonexistent_raises_not_found(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    with pytest.raises(DecisionError) as exc_info:
        _cancel(tmp_path, "NONEXISTENT_DECISION_ID_XXXX")

    assert exc_info.value.code == DecisionErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# Fold-in review finding -- resolve_decision rejects an empty/whitespace-only
# final_answer BEFORE the ledger is ever mutated, mirroring the emptiness
# check defer_decision/cancel_decision already get for --rationale at each
# CLI-layer caller (decision.py's cmd_defer/cmd_cancel,
# orchestrator_api/commands.py's ``_validate_rationale_or_fail``). Fixed
# HERE, in the shared ``resolve_decision`` service function both the host
# CLI's ``cmd_resolve`` and the orchestrator-api's ``resolve-decision`` verb
# call directly, so neither caller can drift from the other (unlike the
# rationale check, which is duplicated per-caller).
# ---------------------------------------------------------------------------


def test_resolve_empty_final_answer_raises_missing_step_or_slot(tmp_path: Path) -> None:
    _setup_meta(tmp_path)
    did = _open_decision(tmp_path)

    with pytest.raises(DecisionError) as exc_info:
        _resolve(tmp_path, did, final_answer="")

    assert exc_info.value.code == DecisionErrorCode.MISSING_STEP_OR_SLOT
    assert exc_info.value.details == {"field": "final_answer"}

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.OPEN
    assert entry.final_answer is None


def test_resolve_whitespace_only_final_answer_raises_missing_step_or_slot(
    tmp_path: Path,
) -> None:
    _setup_meta(tmp_path)
    did = _open_decision(tmp_path)

    with pytest.raises(DecisionError) as exc_info:
        _resolve(tmp_path, did, final_answer="   \t\n")

    assert exc_info.value.code == DecisionErrorCode.MISSING_STEP_OR_SLOT

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.OPEN
    assert entry.final_answer is None


# ---------------------------------------------------------------------------
# T018h — dry_run returns mock response with no filesystem side effects
# ---------------------------------------------------------------------------


def test_resolve_dry_run_returns_response(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    resp = _resolve(tmp_path, did, dry_run=True)

    assert resp.terminal_outcome == "resolved"
    assert resp.status == DecisionStatus.RESOLVED
    assert not resp.idempotent

    # Index entry should still be OPEN
    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.OPEN


def test_defer_dry_run_no_side_effects(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    _defer(tmp_path, did, dry_run=True)

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.OPEN


def test_cancel_dry_run_no_side_effects(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    _cancel(tmp_path, did, dry_run=True)

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.status == DecisionStatus.OPEN


# ---------------------------------------------------------------------------
# T018i — resolve with other_answer=True records other_answer in index
# ---------------------------------------------------------------------------


def test_resolve_other_answer_recorded(tmp_path: Path) -> None:
    did = _open_decision(tmp_path)
    with patch("specify_cli.decisions.emit.emit_decision_resolved", return_value=2):
        resolve_decision(
            tmp_path,
            MISSION_SLUG,
            did,
            final_answer="something custom",
            other_answer=True,
            actor="alice",
        )

    entry = next(
        e for e in _store.load_index(_mission_dir(tmp_path)).entries if e.decision_id == did
    )
    assert entry.other_answer is True
    assert entry.final_answer == "something custom"


# ---------------------------------------------------------------------------
# defer + re-defer with same rationale is idempotent
# ---------------------------------------------------------------------------


def test_defer_twice_same_rationale_is_idempotent(tmp_path: Path) -> None:
    # Re-pinned (#5681, NFR-004): real emit; the retry writes nothing.
    did = _open_real(tmp_path)
    _call("defer", tmp_path, did)
    resp2 = _call("defer", tmp_path, did)

    assert resp2.idempotent is True
    assert resp2.event_lamport is None
    assert len(_rows(tmp_path, did, "deferred")) == 1


# ---------------------------------------------------------------------------
# cancel + re-cancel with same rationale is idempotent
# ---------------------------------------------------------------------------


def test_cancel_twice_same_rationale_is_idempotent(tmp_path: Path) -> None:
    # Re-pinned (#5681, NFR-004): real emit; the retry writes nothing.
    did = _open_real(tmp_path)
    _call("cancel", tmp_path, did)
    resp2 = _call("cancel", tmp_path, did)

    assert resp2.idempotent is True
    assert resp2.event_lamport is None
    assert len(_rows(tmp_path, did, "canceled")) == 1


# ---------------------------------------------------------------------------
# Interrupted terminal call: the index is saved but the terminal event (or the
# artifact) never landed. An identical retry must finish the job (#5681).
# These use a REAL emit; only the append is made to fail.
# ---------------------------------------------------------------------------

_TERMINAL_VERBS = ("resolve", "defer", "cancel")
_OUTCOME = {"resolve": "resolved", "defer": "deferred", "cancel": "canceled"}


def _open_real(repo_root: Path, input_key: str = "team_size") -> str:
    """Open a decision with the real emit so the log carries its opened row."""
    _setup_meta(repo_root)
    resp = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id=f"step-{input_key}",
        input_key=input_key,
        question="How large is the team?",
        options=("1-5", "6-20", "20+"),
        actor="alice",
    )
    return resp.decision_id


def _call(verb: str, repo_root: Path, did: str):
    if verb == "resolve":
        return resolve_decision(repo_root, MISSION_SLUG, did, final_answer="1-5", actor="alice")
    if verb == "defer":
        return defer_decision(repo_root, MISSION_SLUG, did, rationale="not sure yet", actor="alice")
    return cancel_decision(repo_root, MISSION_SLUG, did, rationale="no longer needed", actor="alice")


def _event_log(repo_root: Path) -> Path:
    return _mission_dir(repo_root) / "status.events.jsonl"


def _rows(repo_root: Path, did: str, outcome: str) -> list[dict]:
    path = _event_log(repo_root)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        payload = row.get("payload") or {}
        if (
            row.get("event_type") == "DecisionPointResolved"
            and payload.get("decision_point_id") == did
            and payload.get("terminal_outcome") == outcome
        ):
            out.append(row)
    return out


def _row_count(repo_root: Path) -> int:
    path = _event_log(repo_root)
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def _boom(*_a, **_k):
    raise OSError("simulated interruption")


def _interrupt_emit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("specify_cli.decisions.emit._append_raw_event", _boom)


def _interrupted(verb: str, repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Run *verb* so the index is saved but the terminal event never lands."""
    did = _open_real(repo_root)
    with monkeypatch.context() as m:
        _interrupt_emit(m)
        with pytest.raises(OSError, match="simulated interruption"):
            _call(verb, repo_root, did)
    entry = next(e for e in _store.load_index(_mission_dir(repo_root)).entries if e.decision_id == did)
    assert entry.status != DecisionStatus.OPEN
    assert _rows(repo_root, did, _OUTCOME[verb]) == []
    return did


@pytest.mark.parametrize("verb", _TERMINAL_VERBS)
def test_retried_terminal_call_writes_missing_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str) -> None:
    did = _interrupted(verb, tmp_path, monkeypatch)

    resp = _call(verb, tmp_path, did)

    rows = _rows(tmp_path, did, _OUTCOME[verb])
    assert len(rows) == 1
    assert resp.idempotent is True
    assert resp.event_lamport == _row_count(tmp_path)
    if verb == "resolve":
        assert rows[0]["payload"]["final_answer"] == "1-5"
        assert "1-5" in (_mission_dir(tmp_path) / "decisions" / f"DM-{did}.md").read_text(encoding="utf-8")
    else:
        assert rows[0]["payload"]["rationale"]


def test_retried_resolve_after_defer_repairs_missing_resolved_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _open_real(tmp_path)
    defer_decision(tmp_path, MISSION_SLUG, did, rationale="not sure yet", actor="alice")
    with monkeypatch.context() as m:
        _interrupt_emit(m)
        with pytest.raises(OSError, match="simulated interruption"):
            _call("resolve", tmp_path, did)
    assert len(_rows(tmp_path, did, "deferred")) == 1
    assert _rows(tmp_path, did, "resolved") == []

    resp = _call("resolve", tmp_path, did)

    assert resp.idempotent is True
    assert resp.event_lamport is not None
    assert len(_rows(tmp_path, did, "resolved")) == 1
    assert len(_rows(tmp_path, did, "deferred")) == 1


def test_repair_event_write_failure_raises_event_repair_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _interrupted("resolve", tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        _interrupt_emit(m)
        with pytest.raises(DecisionError) as exc_info:
            _call("resolve", tmp_path, did)
    assert exc_info.value.code == DecisionErrorCode.EVENT_REPAIR_FAILED
    assert _rows(tmp_path, did, "resolved") == []

    resp = _call("resolve", tmp_path, did)

    assert resp.event_lamport is not None
    assert len(_rows(tmp_path, did, "resolved")) == 1


def test_repair_artifact_rewrite_failure_raises_event_repair_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _interrupted("resolve", tmp_path, monkeypatch)
    monkeypatch.setattr("specify_cli.decisions.store.write_artifact", _boom)

    with pytest.raises(DecisionError) as exc_info:
        _call("resolve", tmp_path, did)

    assert exc_info.value.code == DecisionErrorCode.EVENT_REPAIR_FAILED
    assert _rows(tmp_path, did, "resolved") == []


def test_retry_heals_artifact_after_interrupted_artifact_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _open_real(tmp_path)
    with monkeypatch.context() as m:
        m.setattr("specify_cli.decisions.store.write_artifact", _boom)
        with pytest.raises(OSError, match="simulated interruption"):
            _call("resolve", tmp_path, did)
    artifact = _mission_dir(tmp_path) / "decisions" / f"DM-{did}.md"
    assert "1-5" not in artifact.read_text(encoding="utf-8").split("Final answer", 1)[-1]
    assert _rows(tmp_path, did, "resolved") == []

    resp = _call("resolve", tmp_path, did)

    assert resp.event_lamport is not None
    assert len(_rows(tmp_path, did, "resolved")) == 1
    assert "1-5" in artifact.read_text(encoding="utf-8").split("Final answer", 1)[-1]


@pytest.mark.parametrize("verb", _TERMINAL_VERBS)
def test_retry_on_consistent_decision_writes_nothing(tmp_path: Path, verb: str) -> None:
    """Ratchet (green on the base): a consistent retry touches nothing."""
    did = _open_real(tmp_path)
    _call(verb, tmp_path, did)
    paths = [
        _mission_dir(tmp_path) / "decisions" / "index.json",
        _mission_dir(tmp_path) / "decisions" / f"DM-{did}.md",
        _event_log(tmp_path),
    ]
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
    count = len(_rows(tmp_path, did, _OUTCOME[verb]))

    resp = _call(verb, tmp_path, did)

    assert resp.idempotent is True
    assert resp.event_lamport is None
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths] == before
    assert len(_rows(tmp_path, did, _OUTCOME[verb])) == count == 1


def test_retry_with_unreadable_log_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.decisions.service import DecisionEventLogReadError

    did = _interrupted("resolve", tmp_path, monkeypatch)
    log = _event_log(tmp_path)
    with log.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    before = log.read_bytes()
    artifact = _mission_dir(tmp_path) / "decisions" / f"DM-{did}.md"
    artifact_before = artifact.read_bytes()

    with pytest.raises(DecisionEventLogReadError):
        _call("resolve", tmp_path, did)

    assert log.read_bytes() == before
    assert artifact.read_bytes() == artifact_before


def test_retry_with_absent_log_writes_one_terminal_event(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    did = _interrupted("resolve", tmp_path, monkeypatch)
    _event_log(tmp_path).unlink()

    resp = _call("resolve", tmp_path, did)

    assert resp.event_lamport is not None
    assert len(_rows(tmp_path, did, "resolved")) == 1


@pytest.mark.parametrize("verb", _TERMINAL_VERBS)
def test_retry_repair_ignores_other_decisions_terminal_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str) -> None:
    """FR-003: another decision's terminal row must not mask B's missing event."""
    did_a = _open_real(tmp_path, "team_size")
    did_b = _open_real(tmp_path, "budget")
    _call(verb, tmp_path, did_a)
    with monkeypatch.context() as m:
        _interrupt_emit(m)
        with pytest.raises(OSError, match="simulated interruption"):
            _call(verb, tmp_path, did_b)
    outcome = _OUTCOME[verb]
    assert _rows(tmp_path, did_b, outcome) == []

    resp = _call(verb, tmp_path, did_b)

    assert resp.event_lamport is not None
    assert len(_rows(tmp_path, did_b, outcome)) == 1
    assert len(_rows(tmp_path, did_a, outcome)) == 1
