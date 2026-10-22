"""Single home of the accept-time birth-cutover tests shared by a lift and its source (#5015).

``tests/specify_cli/cli/test_accept_birth_cutover.py`` (out of matrix) and its
always-on lift ``tests/architectural/test_lifted_cli_accept_birth_cutover.py``
both import these two fixture-only invariants, so the per-PR gate always runs
exactly what the source suite runs:

* **Idempotency (T010 / FR-006)** -- re-running the stamp on an already-cut-
  over mission is a no-op: byte-identical ``status.events.jsonl``, no error.
* **Fail-closed (T008 / NFR-003 / R6)** -- an absent ``mission_id`` refuses to
  stamp (raises, non-zero), and writes no seed events at all.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.runtime_state_cutover import (
    MissingMissionIdError,
    stamp_accept_cutover,
)
from tests.migration.test_birth_cutover import _write_legacy_mission


def _read_events(feature_dir: Path) -> str:
    events_path = feature_dir / "status.events.jsonl"
    return events_path.read_text(encoding="utf-8") if events_path.exists() else ""


def test_accept_stamp_idempotent_rerun_is_byte_identical(tmp_path: Path) -> None:
    """T010 / FR-006: re-running the accept-time stamp on an already-cut-over
    mission seeds nothing new and leaves ``status.events.jsonl`` byte-stable.
    """
    feature_dir = tmp_path / "kitty-specs" / "legacy-accept-stamp-demo"
    _write_legacy_mission(feature_dir)

    first = stamp_accept_cutover(feature_dir)
    assert first.flipped and first.seeded_count > 0, (
        "precondition: the legacy fixture must actually seed real events, or this test proves nothing about idempotency"
    )
    events_after_first = _read_events(feature_dir)
    meta_after_first = (feature_dir / "meta.json").read_text(encoding="utf-8")

    second = stamp_accept_cutover(feature_dir)

    assert second.seeded_count == 0, "resume/idempotent re-run must seed nothing new"
    assert second.error is None
    assert _read_events(feature_dir) == events_after_first, "a second stamp over an already-cut-over mission must be byte-stable"
    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == meta_after_first


def test_accept_stamp_fails_closed_when_mission_id_absent(tmp_path: Path) -> None:
    """T008 / NFR-003 / R6: an absent ``mission_id`` refuses to stamp -- no
    seed events written, no ``status_phase`` flip -- rather than falling back
    to a slug-namespaced seed identity.
    """
    feature_dir = tmp_path / "kitty-specs" / "no-mission-id-demo"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": feature_dir.name, "target_branch": "main"}),
        encoding="utf-8",
    )
    (tasks_dir / "WP01-work.md").write_text(
        '---\nwork_package_id: WP01\ntitle: WP01 legacy work\nagent: implementer-ivan\nshell_pid: "4242"\nshell_pid_created_at: "1735689600.0"\n---\n# WP01\n',
        encoding="utf-8",
    )
    (feature_dir / "tasks.md").write_text(
        "## WP01 legacy work\n\n- [x] T001 Legacy completed task\n",
        encoding="utf-8",
    )

    with pytest.raises(MissingMissionIdError):
        stamp_accept_cutover(feature_dir)

    assert not (feature_dir / "status.events.jsonl").exists(), "fail-closed on absent mission_id must write NO seed events"
    meta_after = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta_after.get("status_phase") is None, "fail-closed on absent mission_id must never flip status_phase"
