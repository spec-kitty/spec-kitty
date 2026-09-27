"""Unit coverage for the #2709 merge-driver command WRAPPERS (FR-003 / FR-004).

The pure reconcilers (``reconcile_meta_payloads`` / ``union_trace_texts`` /
``_union_acceptance_history``) are exercised directly in
``test_squash_reconcilers_2709``. This module covers the thin git-merge-driver
command bodies around them — ``merge_driver_event_log`` / ``merge_driver_meta`` /
``merge_driver_traces`` and the ``_load_json_object`` loader — with in-memory
``%O/%A/%B`` (base/ours/theirs) files, since under a real ``git merge`` those run
in a SUBPROCESS the coverage instrument cannot see. Each wrapper's happy path and
its error-to-``typer.Exit(1)`` translation is pinned here (#2709).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.merge_driver import (
    merge_driver_event_log,
    merge_driver_meta,
    merge_driver_traces,
)
from specify_cli.merge import drivers
from specify_cli.merge.drivers import _load_json_object
from specify_cli.status import EventLogMergeError

pytestmark = pytest.mark.fast

_EVENT_APPROVED: dict[str, object] = {
    "actor": "claude",
    "at": "2026-02-08T12:00:00+00:00",
    "event_id": "01HXYZ00000000000000000001",
    "evidence": None,
    "execution_mode": "worktree",
    "feature_slug": "m-01ab",
    "force": False,
    "from_lane": "in_review",
    "reason": None,
    "review_ref": None,
    "to_lane": "approved",
    "wp_id": "WP01",
}
_EVENT_DONE: dict[str, object] = {
    **_EVENT_APPROVED,
    "event_id": "01HXYZ00000000000000000002",
    "from_lane": "approved",
    "to_lane": "done",
}


def _write_lines(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in events), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# merge_driver_event_log (lines 74-82)
# ---------------------------------------------------------------------------


def test_event_log_wrapper_unions_ours_and_theirs(tmp_path: Path) -> None:
    base, ours, theirs = tmp_path / "O", tmp_path / "A", tmp_path / "B"
    base.write_text("", encoding="utf-8")
    _write_lines(ours, [_EVENT_APPROVED])
    _write_lines(theirs, [_EVENT_APPROVED, _EVENT_DONE])

    merge_driver_event_log(str(base), str(ours), str(theirs))

    merged_ids = {json.loads(line)["event_id"] for line in ours.read_text().splitlines()}
    assert merged_ids == {_EVENT_APPROVED["event_id"], _EVENT_DONE["event_id"]}


def test_event_log_wrapper_translates_merge_error_to_exit1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ``EventLogMergeError`` from the merger becomes ``typer.Exit(1)``."""

    calls: list[object] = []

    def _boom(**kwargs: object) -> None:
        calls.append(kwargs)
        raise EventLogMergeError("corrupt event log")

    # Patch where the body now looks it up (#5119): merge_event_log_files is
    # imported by name at module level in merge/drivers.py, not in the CLI
    # shell any more.
    monkeypatch.setattr(drivers, "merge_event_log_files", _boom)
    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_event_log(str(tmp_path / "O"), str(tmp_path / "A"), str(tmp_path / "B"))
    assert excinfo.value.exit_code == 1
    assert calls, "the patched merge_event_log_files stub was never called -- monkeypatch target missed"


# ---------------------------------------------------------------------------
# _load_json_object (lines 92-100)
# ---------------------------------------------------------------------------


def test_load_json_object_missing_returns_empty(tmp_path: Path) -> None:
    assert _load_json_object(tmp_path / "absent.json") == {}


def test_load_json_object_blank_returns_empty(tmp_path: Path) -> None:
    path = tmp_path / "meta.json"
    path.write_text("   \n", encoding="utf-8")
    assert _load_json_object(path) == {}


def test_load_json_object_reads_object(tmp_path: Path) -> None:
    path = tmp_path / "meta.json"
    path.write_text(json.dumps({"mission_slug": "m"}), encoding="utf-8")
    assert _load_json_object(path) == {"mission_slug": "m"}


def test_load_json_object_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "meta.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(EventLogMergeError, match="not a JSON object"):
        _load_json_object(path)


# ---------------------------------------------------------------------------
# merge_driver_meta (lines 162-172)
# ---------------------------------------------------------------------------


def test_meta_wrapper_writes_reconciled_blob(tmp_path: Path) -> None:
    ours = tmp_path / "A"  # target checkout (accepted-newer authority)
    theirs = tmp_path / "B"  # mission branch (planning authority)
    ours.write_text(json.dumps({"mission_number": 7, "status": "accepted"}), encoding="utf-8")
    theirs.write_text(
        json.dumps({"mission_slug": "m", "mission_number": None}), encoding="utf-8"
    )

    merge_driver_meta(str(tmp_path / "O"), str(ours), str(theirs))

    merged = json.loads(ours.read_text())
    assert merged["mission_number"] == 7  # target-authoritative wins
    assert merged["status"] == "accepted"
    assert merged["mission_slug"] == "m"  # planning key preserved from theirs
    assert ours.read_text().endswith("\n")  # canonical writer trailing newline


def test_meta_wrapper_translates_bad_json_to_exit1(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("{ not json", encoding="utf-8")
    theirs.write_text("{}", encoding="utf-8")
    with pytest.raises(typer.Exit) as excinfo:
        merge_driver_meta(str(tmp_path / "O"), str(ours), str(theirs))
    assert excinfo.value.exit_code == 1


# ---------------------------------------------------------------------------
# merge_driver_traces (lines 210-215)
# ---------------------------------------------------------------------------


def test_traces_wrapper_unions_both_sides(tmp_path: Path) -> None:
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    ours.write_text("<!-- section:target -->\ntarget line\n", encoding="utf-8")
    theirs.write_text("<!-- section:coord -->\ncoord line\n", encoding="utf-8")

    merge_driver_traces(str(tmp_path / "O"), str(ours), str(theirs))

    merged = ours.read_text()
    assert "target line" in merged
    assert "coord line" in merged
    assert "<!-- section:target -->" in merged
    assert "<!-- section:coord -->" in merged


def test_traces_wrapper_handles_missing_sides(tmp_path: Path) -> None:
    """Missing ours/theirs read as empty; the union of two empties is empty."""
    ours = tmp_path / "A"  # does not exist
    theirs = tmp_path / "B"  # does not exist
    merge_driver_traces(str(tmp_path / "O"), str(ours), str(theirs))
    assert ours.read_text() == ""
