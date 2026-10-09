"""Regression tests for mark-status ID resolution strategies."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.core.wps_manifest import (
    WorkPackageEntry,
    WpsManifest,
    generate_tasks_md_from_manifest,
)

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]
runner = CliRunner()


def _write_mission(
    repo: Path,
    slug: str,
    tasks_content: str,
    wp_ids: tuple[str, ...] = (),
    *,
    status_phase: str | None = None,
) -> Path:
    mission_dir = repo / "kitty-specs" / slug
    mission_dir.mkdir(parents=True)
    # ``status_phase="1"`` cuts the mission over to the phase-1 snapshot authority
    # (event-sourced subtask completion). Default (None) = flag OFF, the
    # pre-cutover legacy state where tasks.md remains the completion authority
    # (#2684 flag-OFF dual-write: the CHECKBOX byte is written at flag OFF).
    meta: dict[str, str] = {"mission_id": "01TESTMISSION"}
    if status_phase is not None:
        meta["status_phase"] = status_phase
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (mission_dir / "tasks.md").write_text(tasks_content, encoding="utf-8")
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir()
    for wp_id in wp_ids:
        (tasks_dir / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\n---\n\n# {wp_id}\n",
            encoding="utf-8",
        )
    return mission_dir


@contextmanager
def _null_lock(repo_root: Path, mission_slug: str):  # type: ignore[no-untyped-def]
    del repo_root, mission_slug
    yield


def _invoke_mark_status(repo: Path, slug: str, *ids: str, expected_exit_code: int = 0) -> dict[str, Any]:
    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=repo),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(repo, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
    ):
        result = runner.invoke(
            app,
            [
                "mark-status",
                *ids,
                "--status",
                "done",
                "--mission",
                slug,
                "--json",
                "--no-auto-commit",
            ],
        )
    assert result.exit_code == expected_exit_code, result.output
    return json.loads(result.stdout)


def _result_by_id(payload: dict[str, Any], task_id: str) -> dict[str, Any]:
    return next(result for result in payload["results"] if result["id"] == task_id)


def test_repeated_subtask_requires_wp_and_scoped_mark_is_idempotent(tmp_path: Path) -> None:
    slug = "5067-repeated"
    mission_dir = _write_mission(tmp_path, slug, "# Tasks\n\n## WP01\nSubtasks: T001\n\n## WP02\nSubtasks: T001\n", wp_ids=("WP01", "WP02"))
    for wp_id in ("WP01", "WP02"):
        (mission_dir / "tasks" / f"{wp_id}-test.md").write_text(
            f"---\nwork_package_id: {wp_id}\nsubtasks:\n  - T001\n---\n", encoding="utf-8"
        )

    def invoke(*extra: str) -> Any:
        with (
            patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=tmp_path),
            patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
            patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(tmp_path, "main")),
            patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
            patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
        ):
            return runner.invoke(app, ["mark-status", "T001", "--status", "done", "--mission", slug, "--json", "--no-auto-commit", *extra])

    ambiguous = invoke()
    assert ambiguous.exit_code == 1
    assert "--wp" in ambiguous.output
    assert not (mission_dir / "status.events.jsonl").exists()

    first = invoke("--wp", "WP02")
    assert first.exit_code == 0, first.output
    assert json.loads(first.stdout)["summary"]["updated"] == 1
    again = invoke("--wp", "WP02")
    assert again.exit_code == 0, again.output
    assert json.loads(again.stdout)["summary"] == {"updated": 0, "already_satisfied": 1, "not_found": 0}


def test_skipped_subtask_is_terminal_for_review_gate(tmp_path: Path) -> None:
    from specify_cli.core.subtask_rows import unchecked_subtask_ids_from_snapshot
    from specify_cli.status import WPInnerStateDelta

    delta = WPInnerStateDelta(subtasks={"T001": "skipped"})
    assert WPInnerStateDelta.from_dict(delta.to_dict()).to_dict() == delta.to_dict()
    with patch("specify_cli.status.wp_snapshot_state", return_value={"subtasks": {"T001": "skipped"}}):
        assert unchecked_subtask_ids_from_snapshot(tmp_path, "WP01", ["T001"]) == []


def test_inline_subtasks_single(tmp_path: Path) -> None:
    """WP04/T015: inline-Subtasks completion is event-sourced, not a tasks.md
    byte-write — the row stays byte-identical (no checkbox is materialized)."""
    slug = "001-inline-single"
    original = "# Tasks\n\n## WP01\nSubtasks: T001\n"
    mission_dir = _write_mission(tmp_path, slug, original)

    payload = _invoke_mark_status(tmp_path, slug, "T001")

    result = _result_by_id(payload, "T001")
    assert result["outcome"] == "updated"
    assert result["format"] == "inline_subtasks"
    assert (mission_dir / "tasks.md").read_text(encoding="utf-8") == original


def test_inline_subtasks_multiple(tmp_path: Path) -> None:
    """WP04/T015: a batch inline-Subtasks mark resolves every id but leaves
    tasks.md byte-stable (completion is event-sourced, not materialized)."""
    slug = "002-inline-multiple"
    original = "# Tasks\n\n## WP01\nSubtasks: T001, T002, T003\n"
    mission_dir = _write_mission(tmp_path, slug, original)

    payload = _invoke_mark_status(tmp_path, slug, "T001", "T002", "T003")

    assert payload["summary"] == {"updated": 3, "already_satisfied": 0, "not_found": 0}
    content = (mission_dir / "tasks.md").read_text(encoding="utf-8")
    assert content == original
    for task_id in ("T001", "T002", "T003"):
        result = _result_by_id(payload, task_id)
        assert result["outcome"] == "updated"
        assert result["format"] == "inline_subtasks"


def test_generated_bold_inline_subtasks_are_markable(tmp_path: Path) -> None:
    """WP04/T015: resolution still succeeds for the generated bold-Subtasks
    surface, but tasks.md stays byte-stable (event-sourced completion)."""
    slug = "003-generated-bold-inline"
    tasks_md = generate_tasks_md_from_manifest(
        WpsManifest(
            work_packages=[
                WorkPackageEntry(
                    id="WP01",
                    title="Generated",
                    subtasks=["T014", "T015", "T016", "T017"],
                )
            ]
        ),
        "Generated Feature",
    )
    assert "**Subtasks**: T014, T015, T016, T017" in tasks_md
    mission_dir = _write_mission(tmp_path, slug, tasks_md)

    payload = _invoke_mark_status(tmp_path, slug, "T014")

    result = _result_by_id(payload, "T014")
    assert result["outcome"] == "updated"
    assert result["format"] == "inline_subtasks"
    assert (mission_dir / "tasks.md").read_text(encoding="utf-8") == tasks_md


def test_wp_id_rejected_with_move_task_guidance(tmp_path: Path) -> None:
    slug = "003-wp-mark-done"
    _write_mission(tmp_path, slug, "# Tasks\n\n## WP02\n", wp_ids=("WP02",))

    with patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional") as emit_mock:
        payload = _invoke_mark_status(tmp_path, slug, "WP02", expected_exit_code=1)

    result = _result_by_id(payload, "WP02")
    assert result["outcome"] == "not_found"
    assert result["format"] == "wp_id"
    assert "mark-status does not change work-package lanes" in result["message"]
    assert "move-task" in result["message"]
    emit_mock.assert_not_called()


def test_wp_id_rejection_is_actionable_in_human_output(tmp_path: Path) -> None:
    slug = "003-wp-mark-done-human"
    _write_mission(tmp_path, slug, "# Tasks\n\n## WP05\n", wp_ids=("WP05",))

    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch("specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out", return_value=(tmp_path, "main")),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
        patch("specify_cli.cli.commands.agent.tasks.emit_status_transition_transactional") as emit_mock,
    ):
        result = runner.invoke(
            app,
            [
                "mark-status",
                "WP05",
                "--status",
                "done",
                "--mission",
                slug,
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 1
    assert "mark-status does not change work-package lanes" in result.output
    normalized_output = " ".join(result.output.split())
    assert "spec-kitty agent tasks move-task <WP_ID> --to <lane>" in normalized_output
    emit_mock.assert_not_called()


def test_wp_id_rejection_does_not_consult_lane_state(tmp_path: Path) -> None:
    slug = "004-wp-already-done"
    _write_mission(tmp_path, slug, "# Tasks\n\n## WP02\n", wp_ids=("WP02",))

    payload = _invoke_mark_status(tmp_path, slug, "WP02", expected_exit_code=1)

    result = _result_by_id(payload, "WP02")
    assert result["outcome"] == "not_found"
    assert result["format"] == "wp_id"
    assert "move-task" in result["message"]


def test_unknown_id_not_found(tmp_path: Path) -> None:
    slug = "005-unknown-id"
    _write_mission(tmp_path, slug, "# Tasks\n\n## WP01\n- [ ] T001 First task\n")

    payload = _invoke_mark_status(tmp_path, slug, "T001", "T999")

    assert _result_by_id(payload, "T001")["outcome"] == "updated"
    assert _result_by_id(payload, "T999")["outcome"] == "not_found"
    assert payload["summary"] == {"updated": 1, "already_satisfied": 0, "not_found": 1}


def test_mixed_formats(tmp_path: Path) -> None:
    """WP04/T015 (flag ON): checkbox + inline resolution both succeed, but neither
    mutates tasks.md — completion for the canonical subtask surface is
    event-sourced, not a markdown byte-write.

    #2684: this byte-stability holds only once the mission is cut over to the
    phase-1 snapshot authority (``status_phase=1``); at flag OFF the CHECKBOX byte
    is the completion authority BOTH readers (``_infer_subtasks_complete`` and the
    review gate ``_check_unchecked_subtasks``) consult, so it is dual-written.
    This test pins the event-sourced (flag ON) surface explicitly.
    """
    slug = "006-mixed-formats"
    original = "# Tasks\n\n## WP01\n- [ ] T001 Checkbox\nSubtasks: T002\n\n## WP03\n"
    mission_dir = _write_mission(
        tmp_path,
        slug,
        original,
        wp_ids=("WP03",),
        status_phase="1",
    )

    payload = _invoke_mark_status(tmp_path, slug, "T001", "T002", "WP03")

    assert _result_by_id(payload, "T001")["format"] == "checkbox"
    assert _result_by_id(payload, "T001")["outcome"] == "updated"
    assert _result_by_id(payload, "T002")["format"] == "inline_subtasks"
    assert _result_by_id(payload, "T002")["outcome"] == "updated"
    assert _result_by_id(payload, "WP03")["format"] == "wp_id"
    assert _result_by_id(payload, "WP03")["outcome"] == "not_found"
    assert "move-task" in _result_by_id(payload, "WP03")["message"]
    content = (mission_dir / "tasks.md").read_text(encoding="utf-8")
    assert content == original
    assert "- [ ] T001 Checkbox" in content


def test_existing_checkbox_unchanged(tmp_path: Path) -> None:
    """WP04/T015 (flag ON): the canonical checkbox row is genuinely left unchanged —
    resolution succeeds (mapping the id to its owning WP + target Status),
    but the durable completion record is the InnerStateChanged emit, not a
    tasks.md byte-write (C-001).

    #2684: byte-stability holds under the phase-1 snapshot authority
    (``status_phase=1``). At flag OFF the checkbox is the legacy completion
    authority and is dual-written (see ``test_atomic_status_commits_unit`` and
    ``test_mark_status_checkbox_dual_written_at_flag_off`` below).
    """
    slug = "007-checkbox"
    original = "# Tasks\n\n## WP01\n- [ ] T001 First task\n"
    mission_dir = _write_mission(tmp_path, slug, original, status_phase="1")

    payload = _invoke_mark_status(tmp_path, slug, "T001")

    result = _result_by_id(payload, "T001")
    assert result["outcome"] == "updated"
    assert result["format"] == "checkbox"
    assert (mission_dir / "tasks.md").read_text(encoding="utf-8") == original


def test_existing_pipe_table_unchanged(tmp_path: Path) -> None:
    slug = "008-pipe-table"
    original = (
        "# Tasks\n\n| ID | Description | WP | Status |\n"
        "|----|-------------|----|--------|\n"
        "| T001 | First task | WP01 | [ ] |\n"
    )
    mission_dir = _write_mission(
        tmp_path,
        slug,
        original,
    )

    payload = _invoke_mark_status(tmp_path, slug, "T001")

    result = _result_by_id(payload, "T001")
    assert result["outcome"] == "updated"
    assert result["format"] == "pipe_table"
    assert (mission_dir / "tasks.md").read_text(encoding="utf-8") == original


def test_event_append_failure_returns_error_without_mutating_tasks_md(tmp_path: Path) -> None:
    slug = "009-event-failure"
    original = (
        "# Tasks\n\n## WP01\n\n"
        "| ID | Description | WP | Status |\n"
        "|----|-------------|----|--------|\n"
        "| T001 | First task | WP01 | [ ] |\n"
    )
    mission_dir = _write_mission(tmp_path, slug, original)

    with (
        patch("specify_cli.cli.commands.agent.tasks.locate_project_root", return_value=tmp_path),
        patch("specify_cli.cli.commands.agent.tasks._find_mission_slug", return_value=slug),
        patch(
            "specify_cli.cli.commands.agent.tasks._ensure_target_branch_checked_out",
            return_value=(tmp_path, "main"),
        ),
        patch("specify_cli.cli.commands.agent.tasks._emit_sparse_session_warning"),
        patch("specify_cli.cli.commands.agent.tasks.feature_status_lock", _null_lock),
        patch(
            "specify_cli.status.emit_inner_state_changed",
            side_effect=OSError("canonical append failed"),
        ),
    ):
        result = runner.invoke(
            app,
            [
                "mark-status",
                "T001",
                "--status",
                "done",
                "--mission",
                slug,
                "--json",
                "--no-auto-commit",
            ],
        )

    assert result.exit_code == 1
    assert "canonical append failed" in result.output
    assert (mission_dir / "tasks.md").read_text(encoding="utf-8") == original
    assert not (mission_dir / "status.events.jsonl").exists()
