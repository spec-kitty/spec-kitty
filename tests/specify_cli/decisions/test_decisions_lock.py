"""The decisions lock's one refusal contract (#6763).

``decisions/lock.py`` is the single owner of the decisions lock. These rows pin what
every holder relies on: the code, the message, the ``details`` keys (the
orchestrator-api ``data`` shape, contract 1.19.0) and that the refusal is retryable and
recognised by exactly one predicate. The command-level rows that render it live beside
each command (``tests/decisions/test_decisions_reconciler.py``,
``tests/specify_cli/cli/commands/test_next_owned_lock_timeout.py``,
``tests/integration/test_owned_decision_runtime_lock.py``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.locks import machine_file_lock
from specify_cli.decisions import lock as _lock
from specify_cli.decisions import service as _service
from specify_cli.decisions.models import DecisionError, DecisionErrorCode

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_refusal_carries_the_contract_code_message_and_details(tmp_path: Path) -> None:
    held = tmp_path / "decisions" / "index.json.lock"

    error = _lock.lock_timeout_error(held, timeout_s=0.25, mission_slug="m-slug", decision_id="01DEC")

    assert error.code is DecisionErrorCode.LOCK_TIMEOUT
    assert error.code.value == "DECISION_LOCK_TIMEOUT"
    assert str(error) == (
        f"Timed out after 0.25s waiting for the decisions lock {str(held)!r}; another decision command is holding it. Nothing was written; retry the command."
    )
    assert error.details == {
        "decision_id": "01DEC",
        "mission_slug": "m-slug",
        "lock_path": str(held),
        "timeout_seconds": 0.25,
    }
    assert _lock.is_lock_timeout(error)


def test_refusal_renders_without_a_slug_decision_or_bound(tmp_path: Path) -> None:
    """``doctor --repair`` and owned ``next`` have no decision id; an unbounded wait names no seconds."""
    error = _lock.lock_timeout_error(tmp_path / "x.lock", timeout_s=None, mission_slug=None, decision_id=None)

    assert "Timed out after the bounded wait waiting" in str(error)
    assert error.details["mission_slug"] is None
    assert error.details["decision_id"] is None
    assert error.details["timeout_seconds"] is None


@pytest.mark.parametrize(
    "exc",
    [
        DecisionError(DecisionErrorCode.NOT_FOUND),
        DecisionError(DecisionErrorCode.EVENT_REPAIR_FAILED, message="Timed out after 1s waiting for the decisions lock"),
        TimeoutError("decisions lock"),
        ValueError("DECISION_LOCK_TIMEOUT"),
    ],
)
def test_only_the_lock_refusal_is_recognised(exc: BaseException) -> None:
    """The predicate keys on the code, never on text, and never on another DecisionError."""
    assert not _lock.is_lock_timeout(exc)


def test_service_decision_error_is_the_same_class() -> None:
    """Moving ``DecisionError`` beside its code kept one class, so every ``except`` still matches."""
    assert _service.DecisionError is DecisionError


def test_lock_path_is_the_ledger_sidecar(tmp_path: Path) -> None:
    assert _lock.lock_path(tmp_path) == tmp_path / "decisions" / _lock.LOCK_FILENAME


def test_a_busy_sidecar_raises_the_refusal_and_runs_nothing(tmp_path: Path) -> None:
    held = _lock.lock_path(tmp_path)
    held.parent.mkdir(parents=True)
    ran: list[str] = []

    with (
        machine_file_lock(held, blocking=True, timeout_s=5.0),
        pytest.raises(DecisionError) as raised,
        _lock.decisions_lock(held, timeout_s=0.1, mission_slug="m", decision_id=None),
    ):
        ran.append("critical section")

    assert ran == []
    assert _lock.is_lock_timeout(raised.value)
    assert str(raised.value) == str(_lock.lock_timeout_error(held, timeout_s=0.1, mission_slug="m", decision_id=None))
    assert isinstance(raised.value.__cause__, Exception)


def test_an_error_inside_the_held_section_is_not_translated(tmp_path: Path) -> None:
    """Only the ACQUIRE becomes the refusal; the critical section's own errors propagate as they are."""
    held = _lock.lock_path(tmp_path)
    held.parent.mkdir(parents=True)

    with pytest.raises(KeyError, match="inner"), _lock.decisions_lock(held, timeout_s=1.0, mission_slug="m", decision_id=None):
        raise KeyError("inner")


def test_the_lock_is_released_after_the_section(tmp_path: Path) -> None:
    held = _lock.lock_path(tmp_path)
    held.parent.mkdir(parents=True)

    with _lock.decisions_lock(held, timeout_s=1.0, mission_slug="m", decision_id=None):
        pass
    with _lock.decisions_lock(held, timeout_s=0.1, mission_slug="m", decision_id=None):
        pass


def test_write_locks_refuse_through_the_same_contract_on_a_busy_anchor(tmp_path: Path) -> None:
    """The event-log anchor leg renders the SAME refusal, naming the anchor lock file."""
    from kernel.event_log_append import event_log_lock

    events_path = tmp_path / "status.events.jsonl"
    events_path.touch()
    anchor = _lock.anchor_lock_path(events_path)
    seen: list[DecisionError] = []

    def _contend() -> None:
        try:
            with _lock.decisions_write_locks(events_path=events_path, ledger_dir=tmp_path, timeout_s=0.1, mission_slug="m", decision_id="d"):
                pass
        except DecisionError as exc:
            seen.append(exc)

    import threading

    with event_log_lock(events_path, timeout_s=5.0):
        # The anchor lock is re-entrant per thread, so contend from another thread.
        worker = threading.Thread(target=_contend)
        worker.start()
        worker.join(10)

    assert len(seen) == 1
    assert str(seen[0]) == str(_lock.lock_timeout_error(anchor, timeout_s=0.1, mission_slug="m", decision_id="d"))
