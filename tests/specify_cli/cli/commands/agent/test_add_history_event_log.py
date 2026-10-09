"""`add-history` records to the event log, not the markdown Activity Log (#2334).

ATDD contract for end state (ii) of #2334 (operator ruling 2026-10-09): the WP
prompt file's ``## Activity Log`` markdown section is retired in favour of
``status.events.jsonl``. The CLI ``add-history`` must therefore:

* record the note as an ``InnerStateChanged`` ``note`` annotation in the event
  log (the single canonical surface, matching the orchestrator-api
  ``append_history`` path), and
* NOT append a ``## Activity Log`` section to the WP prompt body (no second,
  cwd-sensitive markdown writer — the #2334 cross-worktree dual-writer drift).

Red-first: before the implementation these assertions fail because
``add-history`` wrote the markdown body and emitted no event.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import specify_cli.cli.commands.agent.tasks as tasks_module
from mission_runtime import MissionTopology
from specify_cli.status import read_event_stream
from tests.integration.test_placement_partition_golden_path import (
    _create_mission,
    _init_git_repo,
    _write_wp_and_lanes,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

NOTE = "IMPLEMENTED-THE-THING"


def _lanes_mission(tmp_path: Path) -> tuple[Path, str, Path]:
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    _init_git_repo(repo)
    result = _create_mission(repo, "history-event-demo", MissionTopology.LANES)
    meta = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    _write_wp_and_lanes(result.feature_dir, result.mission_slug, str(meta["mission_id"]), "main")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "seed WP01"],
        check=True,
        capture_output=True,
        text=True,
    )
    return repo, result.mission_slug, result.feature_dir


def test_add_history_records_note_as_event_annotation(tmp_path: Path) -> None:
    repo, slug, feature_dir = _lanes_mission(tmp_path)

    with patch.object(tasks_module, "locate_project_root", return_value=repo):
        tasks_module.add_history(task_id="WP01", note=NOTE, mission=slug, agent="claude", shell_pid=None, json_output=True)

    stream = read_event_stream(feature_dir)
    notes = [a.delta.note for a in stream.annotations if a.wp_id == "WP01" and a.delta.note]
    assert any(NOTE in (note or "") for note in notes), f"note not recorded in the event log; annotations={notes!r}"


def test_add_history_does_not_write_markdown_activity_log(tmp_path: Path) -> None:
    repo, slug, feature_dir = _lanes_mission(tmp_path)
    wp_file = feature_dir / "tasks" / "WP01.md"
    before = wp_file.read_text(encoding="utf-8")

    with patch.object(tasks_module, "locate_project_root", return_value=repo):
        tasks_module.add_history(task_id="WP01", note=NOTE, mission=slug, agent="claude", shell_pid=None, json_output=True)

    after = wp_file.read_text(encoding="utf-8")
    # The invariant is that add-history does not WRITE to the WP prompt body at
    # all (the note goes to the event log). Any ``## Activity Log`` text present
    # is pre-existing fixture scaffolding, not something add-history authored.
    assert NOTE not in after, "the note must land in the event log, not the WP prompt body"
    assert after == before, "add-history must not mutate the WP prompt body at all"


def test_add_history_on_a_coord_mission_records_to_the_coord_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The note lands on the authoritative COORD status surface, not the primary.

    add-history resolves its STATUS write surface through ``write_dir`` (the
    single write-location accessor, materialized/seeded as needed), never the
    read resolver -- so on a coordination-routed mission the annotation is
    recorded on the coordination ``status.events.jsonl``, under the coord lock
    key, exactly like move-task's own note deltas. A read-resolver fallback would
    land the note on the primary surface in the create-window (the read-as-write
    gap this asserts against).
    """
    from tests.integration.coord_topology_fixture import _build_coord_topology

    ctx = _build_coord_topology(tmp_path, write_husk_meta=False)
    wp_path = ctx.primary_feature_dir / "tasks" / "WP01.md"
    monkeypatch.setattr(tasks_module, "locate_project_root", lambda: ctx.repo)
    monkeypatch.setattr(tasks_module, "_emit_sparse_session_warning", lambda *_a, **_k: None)
    monkeypatch.setattr(tasks_module, "_find_mission_slug", lambda **_k: ctx.slug)
    monkeypatch.setattr(tasks_module, "_ensure_target_branch_checked_out", lambda root, *_a, **_k: (root, None))
    monkeypatch.setattr(tasks_module, "check_pre30_layout", lambda *_a, **_k: None)
    monkeypatch.setattr(tasks_module, "locate_work_package", lambda *_a, **_k: SimpleNamespace(path=wp_path, agent="a", shell_pid=""))

    tasks_module.add_history(task_id="WP01", note="COORD-NOTE", mission=ctx.slug, agent="a", shell_pid=None, json_output=True)

    coord_notes = [annotation.delta.note or "" for annotation in read_event_stream(ctx.coord_feature_dir).annotations if annotation.wp_id == "WP01"]
    assert any("COORD-NOTE" in note for note in coord_notes), f"note not recorded on the coord surface; coord_notes={coord_notes!r}"
    primary_notes = [annotation.delta.note or "" for annotation in read_event_stream(ctx.primary_feature_dir).annotations if annotation.wp_id == "WP01"]
    assert all("COORD-NOTE" not in note for note in primary_notes), "note leaked onto the primary status surface"
