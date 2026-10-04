"""Focused tests for the extracted ``tasks_move_task_executor`` seam (#5629)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.cli.commands.agent import tasks, tasks_move_task_executor
from specify_cli.status import Lane

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_release_review_lock_is_noop_when_no_lock_edge() -> None:
    st = SimpleNamespace(old_lane=Lane.PLANNED, target_lane=Lane.CLAIMED, owned=None)
    with patch("specify_cli.review.lock.ReviewLock.release") as release:
        tasks_move_task_executor._mt_release_review_lock(st)  # type: ignore[arg-type]
    release.assert_not_called()


def test_release_review_lock_releases_on_approval_edge() -> None:
    st = SimpleNamespace(
        old_lane=Lane.IN_REVIEW,
        target_lane=Lane.APPROVED,
        owned=None,
        main_repo_root="/repo",
        mission_slug="m",
        task_id="WP01",
    )
    ws = SimpleNamespace(worktree_path="/repo/.worktrees/x")
    with (
        patch.object(tasks, "resolve_workspace_for_wp", return_value=ws),
        patch("specify_cli.review.lock.ReviewLock.release") as release,
    ):
        tasks_move_task_executor._mt_release_review_lock(st)  # type: ignore[arg-type]
    release.assert_called_once()


def test_build_rollback_summary_empty_roster() -> None:
    st = SimpleNamespace(main_repo_root="/repo", mission_slug="m", task_id="WP01", owned=None)
    summary = tasks_move_task_executor._mt_build_rollback_summary(st, MagicMock(), {})  # type: ignore[arg-type]
    assert summary.reset_ids == ()
    assert summary.reset_count == 0
    assert summary.previously_completed == ()
    assert summary.never_completed == ()
    assert summary.claim_released is True
    assert summary.review_override_cleared is True


def test_build_rollback_summary_splits_done_from_never_completed(tmp_path) -> None:
    st = SimpleNamespace(main_repo_root=tmp_path, mission_slug="m", task_id="WP01", owned=None)
    ports = MagicMock()
    ports.fs.planning_read_dir.return_value = tmp_path
    reset = {"T001": Lane.PLANNED, "T002": Lane.PLANNED}
    with patch("specify_cli.core.subtask_rows.unchecked_subtask_ids_from_snapshot", return_value=["T002"]):
        summary = tasks_move_task_executor._mt_build_rollback_summary(st, ports, reset)  # type: ignore[arg-type]
    assert summary.reset_ids == ("T001", "T002")
    assert summary.previously_completed == ("T001",)
    assert summary.never_completed == ("T002",)


def _execute_with_recorded_order(*, emit_raises: bool) -> list[str]:
    calls: list[str] = []

    class _Lock:
        def __enter__(self) -> None:
            calls.append("lock-enter")

        def __exit__(self, *exc: object) -> None:
            calls.append("lock-exit")

    def _emit(st: object, ports: object) -> None:
        calls.append("emit")
        if emit_raises:
            raise RuntimeError("emit failed")

    st = SimpleNamespace(owned=None, main_repo_root="/repo", mission_slug="m", self_review_fallback=False)
    with (
        patch.object(tasks, "feature_status_lock", lambda root, slug: _Lock()),
        patch.object(tasks_move_task_executor, "_mt_emit_transitions", side_effect=_emit),
        patch.object(tasks_move_task_executor, "_mt_persist_wp_file", side_effect=lambda st, ports: calls.append("persist")),
        patch.object(tasks_move_task_executor, "_mt_release_review_lock", side_effect=lambda st: calls.append("release")),
    ):
        try:
            tasks_move_task_executor._mt_execute(st, MagicMock())  # type: ignore[arg-type]  # SimpleNamespace stands in for _MoveTaskState
        except RuntimeError:
            calls.append("raised")
    return calls


def test_review_lock_released_after_emits() -> None:
    assert _execute_with_recorded_order(emit_raises=False) == ["lock-enter", "emit", "persist", "lock-exit", "release"]


def test_review_lock_not_released_when_emit_fails() -> None:
    assert _execute_with_recorded_order(emit_raises=True) == ["lock-enter", "emit", "lock-exit", "raised"]
