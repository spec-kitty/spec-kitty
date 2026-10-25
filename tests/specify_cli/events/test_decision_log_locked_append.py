"""``decisions.events.jsonl`` (committed, merge-driver-carried) takes the interim lock.

#6606: the append takes the interim event-log lock (``kernel.event_log_append``),
refuses a torn last line and writes the row bytes it wrote before.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kernel.event_log_append import EventLogTornTailError
from runtime.next._internal_runtime.events import NullEmitter
from specify_cli.events.decision_log import DecisionGitLog

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_TORN = b'{"whole":1}\n{"torn":'
_SLUG = "my-mission"


def _log(tmp_path: Path) -> DecisionGitLog:
    return DecisionGitLog(
        repo_root=tmp_path,
        worktree_root=tmp_path,
        destination_ref=f"kitty/mission-{_SLUG}",
        mission_slug=_SLUG,
        mission_dir=tmp_path / "kitty-specs" / _SLUG,
        inner=NullEmitter(),
    )


def _file(tmp_path: Path) -> Path:
    return tmp_path / "kitty-specs" / _SLUG / "decisions.events.jsonl"


def test_appends_the_same_compact_line(tmp_path: Path) -> None:
    record = {"b": 2, "a": {"z": 1}}
    _log(tmp_path)._append_to_file(record)
    assert _file(tmp_path).read_text(encoding="utf-8") == json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def test_refuses_a_torn_tail_so_no_torn_row_is_committed(tmp_path: Path) -> None:
    path = _file(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(_TORN)
    with pytest.raises(EventLogTornTailError):
        _log(tmp_path)._append_to_file({"a": 1})
    assert path.read_bytes() == _TORN
