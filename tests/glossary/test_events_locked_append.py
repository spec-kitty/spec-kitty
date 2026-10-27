"""The glossary contract append runs under the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import glossary.events as glossary_events
import kernel.event_log_append as event_log_append
from glossary.models import ConflictType, SemanticConflict, SenseRef, Severity, TermSurface

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_append_and_repair_run_under_the_event_log_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "events" / "glossary" / "m.events.jsonl"
    observed: list[str] = []

    @contextmanager
    def recording_lock(anchor: Path) -> Iterator[Path]:
        observed.append(f"lock:{anchor.name}")
        yield anchor
        observed.append("unlock")

    def fake_append(_event: object, _path: object) -> None:
        observed.append("append")

    monkeypatch.setattr(glossary_events, "event_log_lock", recording_lock)
    monkeypatch.setattr(glossary_events, "_ledger_append", fake_append)
    glossary_events.append_event({"event_type": "X"}, log)
    assert observed == ["lock:m.events.jsonl", "append", "unlock"]
    assert log.parent.is_dir()


# ---------------------------------------------------------------------------
# One ledger lock across a loop of emits (#6706)
# ---------------------------------------------------------------------------


@dataclass
class _Context:
    step_id: str = "step-001"
    mission_id: str = "m-6706"
    run_id: str = "run-001"
    conflicts: list[SemanticConflict] = field(default_factory=list)


def _conflict(surface: str) -> SemanticConflict:
    return SemanticConflict(
        term=TermSurface(surface),
        conflict_type=ConflictType.AMBIGUOUS,
        severity=Severity.HIGH,
        confidence=0.9,
        candidate_senses=[SenseRef(surface, "team_domain", "one", 0.9), SenseRef(surface, "team_domain", "two", 0.7)],
        context="description field",
    )


def _count_acquires(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    acquired: list[Path] = []
    real = event_log_append.machine_file_lock

    def counting(path: Path, **kwargs: Any) -> Any:
        acquired.append(path)
        return real(path, **kwargs)

    monkeypatch.setattr(event_log_append, "machine_file_lock", counting)
    return acquired


def _ledger_rows(tmp_path: Path) -> list[str]:
    log = glossary_events.get_event_log_path(tmp_path, "m-6706")
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_held_event_log_takes_the_ledger_lock_once_for_many_emits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    acquired = _count_acquires(monkeypatch)
    context = _Context()
    with glossary_events.held_event_log(tmp_path, context):
        for index in range(5):
            glossary_events.emit_clarification_requested(_conflict(f"t{index}"), context, repo_root=tmp_path)
    assert len(acquired) == 1
    assert len(_ledger_rows(tmp_path)) == 5


def test_held_event_log_falls_back_to_per_emit_locks_when_the_batch_lock_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    real = glossary_events.event_log_lock
    calls: list[Path] = []

    def first_call_fails(anchor: Path) -> Any:
        calls.append(anchor)
        if len(calls) == 1:
            raise event_log_append.EventLogLockTimeoutError("held elsewhere")
        return real(anchor)

    monkeypatch.setattr(glossary_events, "event_log_lock", first_call_fails)
    context = _Context()
    with glossary_events.held_event_log(tmp_path, context):
        for index in range(3):
            glossary_events.emit_clarification_requested(_conflict(f"t{index}"), context, repo_root=tmp_path)
    assert len(calls) == 4
    assert len(_ledger_rows(tmp_path)) == 3


def test_held_event_log_without_a_repo_root_takes_no_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    acquired = _count_acquires(monkeypatch)
    with glossary_events.held_event_log(None, _Context()):
        pass
    assert acquired == []


def test_interactive_clarification_emits_every_request_before_prompting_without_the_lock(tmp_path: Path) -> None:
    from glossary.clarification import ClarificationMiddleware

    seen: list[tuple[int, bool]] = []

    def prompt(conflict: SemanticConflict, candidates: list[SenseRef]) -> tuple[str, None]:
        seen.append((len(_ledger_rows(tmp_path)), bool(event_log_append._held.__dict__.get("locks"))))
        return ("defer", None)

    context = _Context(conflicts=[_conflict(f"t{index}") for index in range(3)])
    ClarificationMiddleware(repo_root=tmp_path, prompt_fn=prompt).process(context)
    assert seen == [(3, False)] * 3
    assert len(context.conflicts) == 3
    assert context.resolved_conflicts == []
