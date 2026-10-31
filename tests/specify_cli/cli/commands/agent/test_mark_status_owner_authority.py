"""Ownership authority for ``agent tasks mark-status`` (#6463).

Three collision classes are pinned here, each reproduced against the pre-fix code:

1. an id claimed by an authored roster in one WP and by a structured ``tasks.md``
   row in a legacy WP resolved as *unique* (roster-or-history) and landed on the
   wrong WP;
2. a bare ``WP<digits>`` id skipped the ownership check and a WP index-table row
   claimed it, recording the WP id as its own subtask;
3. the completion emit re-derived the owner by first match when the resolution
   phase recorded none.

The last test pins the invariant directly on the emit seam, because after the fix
the command refuses before that state can be reached through the CLI.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.cli.commands.agent.tasks_mark_status import _MarkStatusState, _ms_emit_subtask_state

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


def _write_mission(
    repo: Path,
    slug: str,
    tasks_content: str,
    rosters: dict[str, tuple[str, ...] | None],
) -> Path:
    """Write a mission dir; ``rosters[wp] is None`` authors no ``subtasks:`` key (legacy)."""
    mission_dir = repo / "kitty-specs" / slug
    (mission_dir / "tasks").mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_id": "01TESTMISSION", "status_phase": "1"}), encoding="utf-8")
    (mission_dir / "tasks.md").write_text(tasks_content, encoding="utf-8")
    for wp_id, roster in rosters.items():
        body = f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\n"
        if roster is not None:
            body += "subtasks:\n" + "".join(f"  - {task_id}\n" for task_id in roster)
        body += f"---\n\n# {wp_id}\n"
        (mission_dir / "tasks" / f"{wp_id}-test.md").write_text(body, encoding="utf-8")
    return mission_dir


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
    del repo_root, mission_slug
    yield


def _invoke(
    repo: Path,
    slug: str,
    *args: str,
    status: str = "done",
) -> tuple[int, str]:
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(repo, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = runner.invoke(
            app,
            ["mark-status", *args, "--status", status, "--mission", slug, "--json", "--no-auto-commit"],
        )
    return result.exit_code, result.output


def _events(mission_dir: Path) -> list[dict[str, Any]]:
    path = mission_dir / "status.events.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# 1. Mixed ownership sources are ambiguous, not roster-wins
# ---------------------------------------------------------------------------

#: WP01 authors T001 in its roster; WP02 is a legacy WP file (no ``subtasks:``
#: key) that claims T001 through a structured inline ``Subtasks:`` row.
_MIXED_TASKS_MD = "# Tasks\n\n## WP01\nSubtasks: T001, T002\n\n## WP02\nSubtasks: T001\n"


def test_mixed_sources_refuse_unscoped_and_scope_per_wp(tmp_path: Path) -> None:
    slug = "6463-mixed"
    mission_dir = _write_mission(tmp_path, slug, _MIXED_TASKS_MD, {"WP01": ("T001", "T002"), "WP02": None})

    # Pre-fix this wrote {'T001': 'done'} on WP01 and exited 0: the roster owner
    # replaced WP02's structured claim, so the id looked unique.
    exit_code, output = _invoke(tmp_path, slug, "T001")
    assert exit_code == 1, output
    assert "T001 is a subtask of WP01, WP02" in output
    assert "pass --wp to select one." in output
    assert _events(mission_dir) == []

    exit_code, output = _invoke(tmp_path, slug, "T001", "--wp", "WP02")
    assert exit_code == 0, output
    events = _events(mission_dir)
    assert [event["wp_id"] for event in events] == ["WP02"]
    assert events[0]["delta"]["subtasks"] == {"T001": "done"}

    # A --wp that owns none of the ids refuses with the owner list and writes nothing new.
    before = list(events)
    exit_code, output = _invoke(tmp_path, slug, "T001", "--wp", "WP09")
    assert exit_code == 1, output
    assert "T001 is not a subtask of WP09" in output
    assert "(owners: WP01, WP02)" in output
    assert _events(mission_dir) == before

    # Scoping to the roster owner still works and stays isolated.
    exit_code, output = _invoke(tmp_path, slug, "T002", "--wp", "WP01")
    assert exit_code == 0, output
    assert [event["wp_id"] for event in _events(mission_dir)] == ["WP02", "WP01"]


@pytest.mark.parametrize("task_id", ["T001", "t001"])
def test_mixed_sources_refuse_unscoped_whatever_the_id_case(tmp_path: Path, task_id: str) -> None:
    """Both ownership sources upper-case the id, so a lower-case spelling is still shared."""
    slug = "6463-mixed-case"
    mission_dir = _write_mission(tmp_path, slug, _MIXED_TASKS_MD, {"WP01": ("T001", "T002"), "WP02": None})

    exit_code, output = _invoke(tmp_path, slug, task_id)
    assert exit_code == 1, output
    assert "is a subtask of WP01, WP02" in output
    assert _events(mission_dir) == []


# ---------------------------------------------------------------------------
# 2. A WP-shaped id is never claimed by a legacy row shape
# ---------------------------------------------------------------------------

_WP_INDEX_TASKS_MD = "# Tasks\n\n| WP | Title | Subtasks |\n|----|-------|----------|\n| WP01 | Setup | T001 |\n| WP02 | Foundation | T002 |\n"


def test_wp_index_row_cannot_claim_a_work_package_id(tmp_path: Path) -> None:
    slug = "6463-wp-index"
    mission_dir = _write_mission(tmp_path, slug, _WP_INDEX_TASKS_MD, {"WP01": ("T001",), "WP02": ("T002",)})

    # Pre-fix the pipe-table resolver claimed the row and recorded
    # {"WP02": "done"} on WP02, exit 0 — a work package as its own subtask.
    exit_code, output = _invoke(tmp_path, slug, "WP02")
    assert exit_code == 1, output
    assert "WP02: mark-status does not change work-package lanes." in output
    assert "move-task" in output and "--to <lane>" in output
    assert _events(mission_dir) == []


def test_wp_shaped_authored_subtask_needs_wp_scope(tmp_path: Path) -> None:
    slug = "6463-wp-shaped-subtask"
    tasks_md = "# Tasks\n\n## WP01\nSubtasks: WP02, T001\n\n## WP02\nSubtasks: T001\n"
    mission_dir = _write_mission(tmp_path, slug, tasks_md, {"WP01": ("WP02", "T001"), "WP02": ("T001",)})

    # Unscoped this id reads as the work package *and* as WP01's subtask.
    exit_code, output = _invoke(tmp_path, slug, "WP02")
    assert exit_code == 1, output
    assert "WP02 is a work-package id and a subtask of WP01" in output
    assert "pass --wp WP01" in output
    assert "move-task" in output and "--to <lane>" in output
    assert _events(mission_dir) == []

    # The scoped mark records the subtask on its owner, not on the id itself.
    exit_code, output = _invoke(tmp_path, slug, "WP02", "--wp", "WP01")
    assert exit_code == 0, output
    events = _events(mission_dir)
    assert [event["wp_id"] for event in events] == ["WP01"]
    assert events[0]["delta"]["subtasks"] == {"WP02": "done"}

    # A scope that does not own it still refuses.
    exit_code, output = _invoke(tmp_path, slug, "WP02", "--wp", "WP02")
    assert exit_code == 1, output
    assert "WP02 is not a subtask of WP02" in output
    assert len(_events(mission_dir)) == 1


# ---------------------------------------------------------------------------
# 3. The shipped single-authority shape keeps today's behaviour
# ---------------------------------------------------------------------------


def test_single_owner_mark_is_unchanged_and_repeat_is_idempotent(tmp_path: Path) -> None:
    slug = "6463-single-owner"
    tasks_md = "# Tasks\n\n## Work Package WP01: Setup\n\nT001 Create the project skeleton\n"
    mission_dir = _write_mission(tmp_path, slug, tasks_md, {"WP01": ("T001",)})

    exit_code, output = _invoke(tmp_path, slug, "T001")
    assert exit_code == 0, output
    events = _events(mission_dir)
    assert [event["wp_id"] for event in events] == ["WP01"]

    exit_code, output = _invoke(tmp_path, slug, "T001")
    assert exit_code == 0, output
    assert json.loads(output.strip().splitlines()[-1])["summary"] == {
        "updated": 0,
        "already_satisfied": 1,
        "not_found": 0,
    }
    assert _events(mission_dir) == events


# ---------------------------------------------------------------------------
# 4. The emit has one ownership authority
# ---------------------------------------------------------------------------


def test_emit_refuses_an_unattributable_updated_id(tmp_path: Path) -> None:
    slug = "6463-emit-authority"
    # WP01's roster owns T001, so the pre-fix fallback
    # (``owning_wp_from_authored_roster``) would have attributed the event to WP01.
    mission_dir = _write_mission(tmp_path, slug, "# Tasks\n\n## WP01\nSubtasks: T001\n", {"WP01": ("T001",)})
    state = _MarkStatusState(
        task_ids=["T001"],
        status="done",
        mission=None,
        auto_commit=False,
        json_output=True,
        mission_slug=slug,
        feature_dir=mission_dir,
        status_dir=mission_dir,
        tasks_md=mission_dir / "tasks.md",
        updated_tasks=["T001"],
        task_wps={},
        actor={"tool": "user", "role": "implementer", "profile": None, "model": None},
    )

    with pytest.raises(ValueError, match="Could not resolve owning work package for subtask event: T001"):
        _ms_emit_subtask_state(state)
    assert _events(mission_dir) == []
