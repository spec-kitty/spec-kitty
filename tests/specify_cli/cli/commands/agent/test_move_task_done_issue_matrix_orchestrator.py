"""``move-task --to done`` refuses an uncited ``in-mission`` row end to end (#6712, #6653).

``test_move_task_done_issue_matrix.py`` drives the late fact
(``_mt_issue_matrix_facts``) directly. This file drives the real
``_do_move_task`` orchestrator, the one ``spec-kitty agent tasks move-task``
uses, with a real Git checkout, and proves the blocker actually refuses the
transition. The ``approved`` control runs on the same matrix.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import typer

from tests.specify_cli.cli.commands.agent.test_move_task_approval_body_collision import (
    _MISSION,
    _WP_ID,
    _build_wp_file,
    _fake_ports,
    _init_repo,
    _run_move,
    _seed_lanes_json,
    _seed_wp_event,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_UNCITED = "#5678"


def _mission_with_uncited_in_mission_row(tmp_path: Path) -> Path:
    feature_dir, _wp_file = _build_wp_file(tmp_path, _MISSION, _WP_ID)
    (feature_dir / "spec.md").write_text("Fixes #1234 in this mission.\n", encoding="utf-8")
    rows = {"#1234": "fixed", _UNCITED: "in-mission"}
    payload = {"rows": {issue: {"verdict": verdict, "evidence_ref": "PR #1"} for issue, verdict in rows.items()}}
    (feature_dir / "issue-matrix.json").write_text(json.dumps(payload), encoding="utf-8")
    _init_repo(tmp_path)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "seed done issue-matrix fixture"], cwd=tmp_path, check=True, capture_output=True)
    _seed_lanes_json(feature_dir, _MISSION, _WP_ID)
    return feature_dir


def test_move_task_done_refuses_uncited_in_mission_row(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    feature_dir = _mission_with_uncited_in_mission_row(tmp_path)
    _seed_wp_event(feature_dir, _WP_ID, "approved")

    with pytest.raises(typer.Exit) as exc_info:
        _run_move(
            tmp_path,
            to="done",
            ports=_fake_ports(feature_dir),
            note="Merged",
            done_override_reason="no lane branch in this fixture",
        )

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr()
    refusal = output.out + output.err
    assert _UNCITED in refusal
    assert "spec-kitty agent issue-verdict --mission" in refusal


def test_move_task_approved_accepts_the_same_in_mission_row(tmp_path: Path) -> None:
    """C-001 control on the same matrix: ``in-mission`` is still fine at ``approved``."""
    feature_dir = _mission_with_uncited_in_mission_row(tmp_path)
    _seed_wp_event(feature_dir, _WP_ID, "in_review")

    _run_move(tmp_path, to="approved", ports=_fake_ports(feature_dir), note="Review passed")
