"""Repairing an interrupted open (#4848 pre-PR squad folds S2 and S3).

An open that is cut off after its index entry was saved can leave the
decision without its ``DM-<id>.md`` artifact (S2) or without its
``DecisionPointOpened`` row (S3). The open retry rewrites the artifact as
well as the row, and resolve / defer / cancel record a missing opening under
the same decisions-lock hold before they write the terminal row, so the log
folds.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from specify_cli.decisions import emit as _emit
from specify_cli.decisions import service as _service
from specify_cli.decisions import store as _store
from specify_cli.decisions.index_fold import fold_events
from specify_cli.decisions.models import DecisionOpenResponse, DecisionStatus, DecisionTerminalResponse, OriginFlow
from specify_cli.decisions.service import (
    cancel_decision,
    defer_decision,
    open_decision,
    resolve_decision,
)

pytestmark = [pytest.mark.unit]

MISSION_ID = "01KTEST_MISSION_ID_000004"
MISSION_SLUG = "open-repair-mission"


def _mission_dir(repo_root: Path) -> Path:
    return repo_root / "kitty-specs" / MISSION_SLUG


def _setup(repo_root: Path) -> None:
    mission_dir = _mission_dir(repo_root)
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _open(repo_root: Path) -> DecisionOpenResponse:
    resp: DecisionOpenResponse = open_decision(
        repo_root,
        MISSION_SLUG,
        origin_flow=OriginFlow.CHARTER,
        step_id="step-team-size",
        input_key="team_size",
        question="How large is the team?",
        options=("1-5", "6-20"),
        actor="alice",
    )
    return resp


def _events(repo_root: Path) -> list[dict[str, Any]]:
    path = _mission_dir(repo_root) / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _event_types(repo_root: Path) -> list[str]:
    return [str(e["event_type"]) for e in _events(repo_root)]


def _only_decision_id(repo_root: Path) -> str:
    entries = _store.load_index(_mission_dir(repo_root)).entries
    assert len(entries) == 1
    return entries[0].decision_id


def _raise_oserror(*_a: Any, **_k: Any) -> None:
    raise OSError("simulated interruption")


def _interrupted_open(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Open with the event append failing: index entry and artifact saved, no row."""
    with monkeypatch.context() as m:
        m.setattr(_emit, "_append_raw_event", _raise_oserror)
        with pytest.raises(OSError, match="simulated interruption"):
            _open(repo_root)
    assert _events(repo_root) == []
    return _only_decision_id(repo_root)


def _resolve(repo_root: Path, did: str) -> DecisionTerminalResponse:
    resp: DecisionTerminalResponse = resolve_decision(repo_root, MISSION_SLUG, did, final_answer="1-5", actor="bob")
    return resp


def _defer(repo_root: Path, did: str) -> DecisionTerminalResponse:
    resp: DecisionTerminalResponse = defer_decision(repo_root, MISSION_SLUG, did, rationale="later", actor="bob")
    return resp


def _cancel(repo_root: Path, did: str) -> DecisionTerminalResponse:
    resp: DecisionTerminalResponse = cancel_decision(repo_root, MISSION_SLUG, did, rationale="not needed", actor="bob")
    return resp


_TERMINAL_CALLS: dict[str, tuple[Callable[[Path, str], DecisionTerminalResponse], DecisionStatus]] = {
    "resolve": (_resolve, DecisionStatus.RESOLVED),
    "defer": (_defer, DecisionStatus.DEFERRED),
    "cancel": (_cancel, DecisionStatus.CANCELED),
}


# ---------------------------------------------------------------------------
# S3: terminal verbs record a missing opening first
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("verb", sorted(_TERMINAL_CALLS))
def test_terminal_verb_after_interrupted_open_records_the_opening_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, verb: str) -> None:
    """Red on 581b5c46: the log held only the terminal row and did not fold."""
    call, status = _TERMINAL_CALLS[verb]
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)

    resp = call(tmp_path, did)

    assert resp.idempotent is False
    assert _event_types(tmp_path) == ["DecisionPointOpened", "DecisionPointResolved"]
    assert fold_events(_events(tmp_path)).status == status


def test_terminal_retry_after_interrupted_open_and_terminal_repairs_both_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted open, then a resolve interrupted after its index save: one row of each, once."""
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(_emit, "emit_decision_resolved", _raise_oserror)
        with pytest.raises(OSError, match="simulated interruption"):
            _resolve(tmp_path, did)
    assert _event_types(tmp_path) == ["DecisionPointOpened"]

    retry = _resolve(tmp_path, did)
    again = _resolve(tmp_path, did)

    assert retry.idempotent is True and retry.event_lamport is not None
    assert again.idempotent is True and again.event_lamport is None
    assert _event_types(tmp_path) == ["DecisionPointOpened", "DecisionPointResolved"]
    assert fold_events(_events(tmp_path)).status == DecisionStatus.RESOLVED


def test_idempotent_terminal_retry_records_an_opening_missing_before_the_fix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A log already holding only the terminal row (written before the fix) gets its opening on retry."""
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)
    with monkeypatch.context() as m:
        m.setattr(_service, "_repair_opening_before_terminal", lambda *_a, **_k: None)
        _resolve(tmp_path, did)
    assert _event_types(tmp_path) == ["DecisionPointResolved"]

    retry = _resolve(tmp_path, did)

    assert retry.idempotent is True
    assert _event_types(tmp_path) == ["DecisionPointResolved", "DecisionPointOpened"]
    assert fold_events(_events(tmp_path)).status == DecisionStatus.RESOLVED


def test_terminal_verb_after_complete_open_writes_no_second_opening(tmp_path: Path) -> None:
    """Control: an opening already in the log is not repeated."""
    _setup(tmp_path)
    did = _open(tmp_path).decision_id

    _resolve(tmp_path, did)

    assert _event_types(tmp_path) == ["DecisionPointOpened", "DecisionPointResolved"]


def test_terminal_verb_skips_opening_repair_when_opening_actor_was_not_persisted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A legacy entry without ``opened_by`` cannot be repaired; the terminal verb still succeeds as before."""
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)
    index_path = _mission_dir(tmp_path) / "decisions" / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["entries"][0]["opened_by"] = None
    index_path.write_text(json.dumps(index), encoding="utf-8")

    resp = _resolve(tmp_path, did)

    assert resp.idempotent is False
    assert _event_types(tmp_path) == ["DecisionPointResolved"]


def test_terminal_verb_reports_repair_failed_when_opening_append_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failed opening repair stops the terminal verb before its index save."""
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)
    index_path = _mission_dir(tmp_path) / "decisions" / "index.json"
    before = index_path.read_bytes()

    with monkeypatch.context() as m:
        m.setattr(_emit, "_append_raw_event", _raise_oserror)
        with pytest.raises(_service.DecisionError) as exc_info:
            _resolve(tmp_path, did)

    assert exc_info.value.code.value == "DECISION_EVENT_REPAIR_FAILED"
    assert index_path.read_bytes() == before
    assert _events(tmp_path) == []


# ---------------------------------------------------------------------------
# S2: the open retry rewrites a missing artifact
# ---------------------------------------------------------------------------


def test_open_retry_after_failed_artifact_write_restores_artifact_and_opening(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Red on 581b5c46: the retry appended the row but left ``DM-<id>.md`` missing."""
    _setup(tmp_path)
    with monkeypatch.context() as m:
        m.setattr(_store, "write_artifact", _raise_oserror)
        with pytest.raises(OSError, match="simulated interruption"):
            _open(tmp_path)
    did = _only_decision_id(tmp_path)
    assert not _store.artifact_path(_mission_dir(tmp_path), did).exists()

    retry = _open(tmp_path)
    again = _open(tmp_path)

    assert retry.idempotent is True and retry.event_lamport is not None
    assert Path(retry.artifact_path).exists()
    assert again.idempotent is True and again.event_lamport is None
    assert _event_types(tmp_path) == ["DecisionPointOpened"]


def test_open_retry_rewrites_a_missing_artifact_when_the_opening_is_present(tmp_path: Path) -> None:
    """The artifact alone is missing: the retry rewrites it and appends nothing."""
    _setup(tmp_path)
    first = _open(tmp_path)
    Path(first.artifact_path).unlink()

    retry = _open(tmp_path)

    assert retry.idempotent is True and retry.event_lamport is None
    assert Path(retry.artifact_path).exists()
    assert _event_types(tmp_path) == ["DecisionPointOpened"]


def test_open_retry_reports_repair_failed_when_artifact_rewrite_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A failing artifact rewrite on the retry is a structured repair failure that appends nothing."""
    _setup(tmp_path)
    did = _interrupted_open(tmp_path, monkeypatch)
    _store.artifact_path(_mission_dir(tmp_path), did).unlink()

    with monkeypatch.context() as m:
        m.setattr(_store, "write_artifact", _raise_oserror)
        with pytest.raises(_service.DecisionError) as exc_info:
            _open(tmp_path)

    assert exc_info.value.code.value == "DECISION_EVENT_REPAIR_FAILED"
    assert _events(tmp_path) == []
