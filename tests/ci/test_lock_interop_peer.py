"""Unit tests for ``scripts/ci/lock_interop_peer.py``, the Python side of the #6193 lock-interop spike.

The cross-language scenarios run in ``LockInteropSpikeTest`` (``services/mission-status-api/event-log``) on the ``lock-interop`` job of
``mission-status-api.yml``. These tests pin the peer's own contract, Python against Python: the rows it writes are today's status
row shape and pass the status reader, its lock commands exclude a second holder of the same lock, and an append refusal is reported
rather than raised. The module is loaded by file path (``scripts/ci`` is not an importable package).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import threading
from pathlib import Path
from types import ModuleType

import pytest

from kernel.event_log_append import event_log_lock_path
from kernel.locks import machine_file_lock

pytestmark = pytest.mark.fast

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "ci" / "lock_interop_peer.py"
_ULID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lock_interop_peer", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def peer() -> ModuleType:
    return _load_module()


@pytest.fixture
def log(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path / "status.events.jsonl"


def _out(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    result: dict[str, object] = json.loads(capsys.readouterr().out)
    return result


def test_event_ids_are_ulid_shaped_and_unique_per_writer_and_index(peer: ModuleType) -> None:
    ids = {peer.event_id(writer, index) for writer in (1, 2, 9) for index in range(200)}
    assert len(ids) == 600
    assert all(_ULID.match(event_id) for event_id in ids)


def test_rendered_row_is_a_sorted_status_row_with_no_terminator(peer: ModuleType) -> None:
    row = peer.render_row(2, 7)
    parsed = json.loads(row)
    assert row == json.dumps(parsed, sort_keys=True)
    assert "\n" not in row
    assert (parsed["actor"], parsed["wp_id"], parsed["from_lane"], parsed["to_lane"]) == ("lock-interop-2", "WP02", "planned", "claimed")


def test_lock_path_is_the_kernel_lock_path(peer: ModuleType, log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert peer.main(["lock-path", str(log)]) == 0
    assert _out(capsys) == {"lock_path": str(event_log_lock_path(log))}


def test_try_acquires_a_free_lock_and_is_excluded_by_a_held_one(peer: ModuleType, log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert peer.main(["try", str(log)]) == 0
    assert _out(capsys) == {"acquired": True}
    with machine_file_lock(event_log_lock_path(log)):
        assert peer.main(["try", str(log)]) == 0
    assert _out(capsys) == {"acquired": False}


def test_a_probe_reports_a_held_lock_as_contended(peer: ModuleType, log: Path) -> None:
    assert peer.lock_was_free(log) is True
    with machine_file_lock(event_log_lock_path(log)):
        assert peer.lock_was_free(log) is False


def test_hold_keeps_the_lock_until_released(peer: ModuleType, log: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    ready, release = tmp_path / "ready", tmp_path / "release"
    holder = threading.Thread(target=peer.main, args=(["hold", str(log), "--ready", str(ready), "--release", str(release)],))
    holder.start()
    try:
        peer._wait_for(ready, 30)
        assert peer.cmd_try(log) == 0
        assert '"acquired": false' in capsys.readouterr().out
    finally:
        release.touch()
        holder.join(30)
    assert not holder.is_alive()


def test_contend_counts_no_overlap_for_a_single_holder(peer: ModuleType, log: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    start = tmp_path / "start"
    start.touch()
    args = ["contend", str(log), "--sentinel", str(tmp_path / "inside"), "--rounds", "5", "--ready", str(tmp_path / "ready"), "--start", str(start)]
    assert peer.main(args) == 0
    assert _out(capsys) == {"contended": 0, "overlaps": 0, "rounds": 5}
    assert (tmp_path / "ready").exists()
    assert not (tmp_path / "inside").exists()


def test_a_present_sentinel_is_an_overlap(peer: ModuleType, tmp_path: Path) -> None:
    sentinel = tmp_path / "inside"
    sentinel.touch()
    assert peer.enter_critical_section(sentinel) is False


def test_appended_rows_pass_the_status_reader(peer: ModuleType, log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert peer.main(["append", str(log), "--writer", "3", "--count", "4"]) == 0
    assert _out(capsys) == {"appended": 4, "codes": [], "refused": [], "writer": 3}
    assert log.read_bytes() == b"".join(f"{peer.render_row(3, index)}\n".encode() for index in range(4))
    assert peer.main(["read", str(log)]) == 0
    assert _out(capsys)["events"] == 4


def test_a_refused_append_is_reported_not_raised(peer: ModuleType, log: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log.write_bytes(b'{"torn": ')
    assert peer.main(["append", str(log), "--writer", "1", "--count", "2"]) == 0
    assert _out(capsys) == {"appended": 0, "codes": ["EVENT_LOG_TORN_TAIL"], "refused": [0, 1], "writer": 1}


def test_render_row_command_prints_the_row(peer: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    assert peer.main(["render-row", "--writer", "1", "--index", "7"]) == 0
    assert capsys.readouterr().out == peer.render_row(1, 7) + "\n"


def test_waiting_for_a_file_that_never_appears_times_out(peer: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(TimeoutError):
        peer._wait_for(tmp_path / "never", 0.05)
