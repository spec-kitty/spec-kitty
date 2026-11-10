"""#7346: the ``abandoned`` lifecycle phase closes a stale lifecycle record.

``doctor ops --close-stale`` writes an ``abandoned`` record paired with an orphaned
``started`` record, so the record is closed without ``spec-kitty next`` reporting a
result (which would also advance the Mission). Pairing counts it as a completion.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from specify_cli.invocation.lifecycle import (
    compute_pairing_rate,
    doctor_orphan_report,
    find_latest_unpaired_started,
    find_orphans,
    lifecycle_records_dir,
    read_lifecycle_records,
    write_abandoned_completion,
    write_paired_completion,
    write_started,
)
from specify_cli.invocation.record import ProfileInvocationRecord

pytestmark = pytest.mark.unit

_AT = datetime(2026, 11, 7, 10, 0, tzinfo=UTC)
_REASON = "abandoned by doctor ops --close-stale (older than 24h)"


def _record(phase: str, *, at: datetime = _AT, wp_id: str | None = "WP04") -> ProfileInvocationRecord:
    return ProfileInvocationRecord.from_dict(
        {
            "canonical_action_id": "implement::implement",
            "phase": phase,
            "at": at.isoformat(),
            "agent": "claude",
            "mission_id": "01M6VYS1MISSION0000000000",
            "wp_id": wp_id,
            "reason": _REASON if phase == "abandoned" else None,
            "metadata": {"closed_by": "doctor_sweep"} if phase == "abandoned" else {},
        }
    )


def _snapshot(directory: Path) -> dict[str, bytes]:
    return {path.name: path.read_bytes() for path in sorted(directory.glob("*.json"))}


def test_the_abandoned_phase_round_trips() -> None:
    record = _record("abandoned")
    payload = record.to_dict()
    assert payload["phase"] == "abandoned"
    assert payload["reason"] == _REASON
    assert payload["metadata"] == {"closed_by": "doctor_sweep"}
    assert ProfileInvocationRecord.from_dict(payload) == record


def test_an_abandoned_record_pairs_its_started_record() -> None:
    records = [_record("started"), _record("abandoned", at=_AT + timedelta(days=2))]
    assert find_orphans(records) == []
    assert compute_pairing_rate(records) == 1.0
    assert find_latest_unpaired_started(records) is None


def test_a_second_started_record_stays_unpaired() -> None:
    later = _record("started", at=_AT + timedelta(hours=1))
    records = [_record("started"), later, _record("abandoned", at=_AT + timedelta(days=2))]
    assert find_latest_unpaired_started(records) == later
    assert compute_pairing_rate(records) == 0.5


def test_the_writer_appends_one_abandoned_file_and_changes_nothing_else(tmp_path: Path) -> None:
    started = write_started(tmp_path, canonical_action_id="implement::implement", agent="claude", mission_id="01M6VYS1MISSION0000000000", wp_id="WP04")
    directory = lifecycle_records_dir(tmp_path)
    before = _snapshot(directory)

    path = write_abandoned_completion(tmp_path, started=started, reason=_REASON)

    assert path.parent == directory
    after = _snapshot(directory)
    assert {name: content for name, content in after.items() if name in before} == before
    assert set(after) - set(before) == {path.name}
    (written,) = [record for record in read_lifecycle_records(tmp_path) if record.phase == "abandoned"]
    assert (written.canonical_action_id, written.agent, written.mission_id, written.wp_id) == (
        started.canonical_action_id,
        started.agent,
        started.mission_id,
        started.wp_id,
    )
    assert written.reason == _REASON
    assert written.metadata == {"closed_by": "doctor_sweep"}
    assert doctor_orphan_report(tmp_path)["orphan_count"] == 0


def test_the_writer_refuses_a_record_that_is_not_started(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="started"):
        write_abandoned_completion(tmp_path, started=_record("completed"), reason=_REASON)
    assert not lifecycle_records_dir(tmp_path).exists()


def test_next_never_writes_an_abandoned_record(tmp_path: Path) -> None:
    """Only the doctor sweep writes ``abandoned`` (WP01 review finding L2)."""
    started = write_started(tmp_path, canonical_action_id="implement::implement", agent="claude", mission_id="01M6VYS1MISSION0000000000")
    with pytest.raises(ValueError, match="completed"):
        write_paired_completion(tmp_path, started=started, phase="abandoned")
