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
    assert "## Activity Log" not in after, "add-history must not author a markdown Activity Log section"
    assert NOTE not in after, "the note must land in the event log, not the WP prompt body"
    assert after == before, "add-history must not mutate the WP prompt body at all"
