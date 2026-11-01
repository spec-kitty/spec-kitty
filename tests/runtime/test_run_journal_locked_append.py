"""The run journal and the ``next`` lifecycle pairing take the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import specify_cli.invocation.lifecycle as lifecycle_module
from kernel.event_log_append import EventLogTornTailError
from runtime.next._internal_runtime.engine import _append_event

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'


def test_journal_line_is_unchanged(tmp_path: Path) -> None:
    _append_event(tmp_path, "MissionRunStarted", {"n": 1})
    row = json.loads((tmp_path / "run.events.jsonl").read_text(encoding="utf-8"))
    assert row["event_type"] == "MissionRunStarted"
    assert row["payload"] == {"n": 1}


def test_journal_refuses_a_torn_tail(tmp_path: Path) -> None:
    journal = tmp_path / "run.events.jsonl"
    journal.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        _append_event(tmp_path, "NextStepIssued", {"n": 2})
    assert journal.read_bytes() == _TORN


@pytest.mark.parametrize(
    "error",
    [
        EventLogTornTailError("torn"),
        # #7003: a non-directory at ``kitty-ops/lifecycle`` or an unwritable one is a plain OSError.
        FileExistsError("kitty-ops/lifecycle is a file"),
        PermissionError("kitty-ops/lifecycle is read-only"),
    ],
)
def test_next_pairing_warns_and_continues_on_a_refused_append(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture, error: OSError
) -> None:
    """Review finding 9: a refused or failed lifecycle write must not fail ``spec-kitty next --result``."""
    import runtime.next.next_invocation_lifecycle as next_lifecycle
    import specify_cli.mission_metadata as mission_metadata

    class _Identity:
        mission_id = "01HMISSION0000000000000000"

    class _Context:
        def artifact(self, _kind: object) -> object:
            return type("A", (), {"read_dir": tmp_path})()

    def _refuse(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(next_lifecycle, "mission_context_for", lambda *_a: _Context())
    monkeypatch.setattr(mission_metadata, "resolve_mission_identity", lambda _d: _Identity())
    monkeypatch.setattr(lifecycle_module, "read_lifecycle_records", lambda _root: [])
    monkeypatch.setattr(lifecycle_module, "find_latest_unpaired_started", lambda *_a, **_k: object())
    monkeypatch.setattr(lifecycle_module, "write_paired_completion", _refuse)
    with caplog.at_level("WARNING"):
        next_lifecycle.pair_previous_lifecycle_record("claude", "m", "success", tmp_path)
    assert "Lifecycle completion not recorded" in caplog.text
