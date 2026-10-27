"""``move-task --to done`` judges every issue-matrix row (#6653, FR-006).

Drives ``tasks_move_task._mt_issue_matrix_facts`` -- the late fact
``move-task`` feeds into its transition request -- on a minimal
``_MoveTaskState`` with a real mission dir. Only the placement seam is
replaced (it resolves the PRIMARY ``spec.md`` dir from a real repository);
the issue-matrix blocker itself runs for real.

One wiring smoke test: an uncited ``in-mission`` row refuses ``done`` and
names the row and the ``agent issue-verdict`` remedy. The full blocker matrix
(approved lane, zero gating refs, no matrix) lives in
``test_tasks_parsing_validation.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.cli.commands.agent import tasks_move_task
from specify_cli.cli.commands.agent.tasks_move_task import _MoveTaskState, _mt_issue_matrix_facts
from specify_cli.status import Lane

pytestmark = pytest.mark.fast


def _mission_dir(tmp_path: Path, spec_text: str, rows: dict[str, str] | None) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(spec_text, encoding="utf-8")
    if rows is not None:
        payload = {"rows": {issue: {"verdict": verdict, "evidence_ref": "PR #1"} for issue, verdict in rows.items()}}
        (feature_dir / "issue-matrix.json").write_text(json.dumps(payload), encoding="utf-8")
    return feature_dir


def _facts(monkeypatch: pytest.MonkeyPatch, feature_dir: Path, target_lane: Lane) -> str | None:
    def _seam(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(read_dir=lambda _kind: feature_dir)

    monkeypatch.setattr(tasks_move_task, "placement_seam", _seam)
    st = _MoveTaskState(
        task_id="WP01",
        to=str(target_lane),
        mission="demo",
        agent=None,
        assignee=None,
        shell_pid=None,
        note=None,
        review_feedback_file=None,
        approval_ref=None,
        reviewer=None,
        self_review_fallback=False,
        intended_reviewer=None,
        reviewer_failure_reason=None,
        done_override_reason=None,
        force=False,
        tracker_ref=None,
        skip_review_artifact_check=False,
        auto_commit=None,
        json_output=True,
        target_lane=target_lane,
        main_repo_root=feature_dir.parent.parent,
        mission_slug="demo",
        feature_dir=feature_dir,
    )
    blocker: str | None = _mt_issue_matrix_facts(st)
    return blocker


def test_done_refuses_uncited_in_mission_row(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = _mission_dir(tmp_path, "Fixes #1234 in this mission.\n", {"#1234": "fixed", "#5678": "in-mission"})

    blocker = _facts(monkeypatch, feature_dir, Lane.DONE)

    assert blocker is not None
    assert "#5678" in blocker
    assert "spec-kitty agent issue-verdict --mission" in blocker
