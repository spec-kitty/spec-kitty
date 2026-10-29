"""Regression guard for GitHub issue #6651 -- ``move-task --json`` stdout contract.

``spec-kitty agent tasks move-task <WP> --to for_review --json`` could write
``Note: N unrelated dirty file(s) ignored (not owned by <WP>)`` to **stdout**
ahead of the JSON document and exit 0, so ``json.load`` on stdout failed with
``Expecting value: line 1 column 1``. The trigger is ordinary: the step that
``agent action implement`` lists right before this one, ``agent tasks
mark-status``, leaves spec-kitty's own bookkeeping (``status.json`` /
``status.events.jsonl``) uncommitted in the primary checkout, the readiness
check classifies it as benign and printed the note through the stdout console
with no ``--json`` gate. Every other human note in ``move-task`` is already
suppressed under ``--json``.

The fixture is the ``lanes``-topology mission of the #4905 guard (planning
artifacts and status in the primary checkout, WP01 implemented in a
``.worktrees/`` lane), i.e. the reporter's setup: the dirty bookkeeping sits in
the primary checkout, where only the research-artifact gate sees it, and the
lane worktree stays clean so the move succeeds.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli import app as root_app
from tests.specify_cli.cli.commands.agent.test_issue_4905_coord_staging import (
    _build_flat_two_lane_mission,
    _git,
    _run_implement,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()

_NOTE = "unrelated dirty file(s) ignored (not owned by WP01)"


def _claim_wp01_and_dirty_bookkeeping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mission_slug: str) -> tuple[Path, str]:
    # WP01 owns ``src/**``, so the lane commit below is the implementation evidence the #6715
    # move-into-review gate reads (the fixture's intent, the #6651 stdout contract, is unchanged).
    repo_root, mission_dirname = _build_flat_two_lane_mission(tmp_path, monkeypatch, mission_slug=mission_slug, own_src=True)
    claim = _run_implement(mission_dirname, "WP01")
    assert claim.exit_code == 0, claim.output

    # The implementation commit the review hand-off requires, in the lane
    # worktree (inside the lane's ``src/**`` write scope).
    lane_worktree = repo_root / ".worktrees" / f"{mission_dirname}-lane-a"
    (lane_worktree / "src").mkdir(exist_ok=True)
    (lane_worktree / "src" / "alpha.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(lane_worktree, "add", "src/alpha.py")
    _git(lane_worktree, "commit", "-q", "-m", "feat(WP01): add alpha")

    # Leave spec-kitty's own bookkeeping dirty in the primary checkout, the
    # way ``mark-status`` leaves the status files right before this step.
    # ``meta.json`` is tracked, committed by the planning commit, and benign
    # for the readiness check (toolchain-generated churn), so it exercises
    # exactly the note path without blocking the move.
    meta_json = repo_root / "kitty-specs" / mission_dirname / "meta.json"
    meta_json.write_text(meta_json.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    porcelain = _git(repo_root, "status", "--porcelain").stdout
    assert f" M kitty-specs/{mission_dirname}/meta.json" in porcelain, porcelain
    return repo_root, mission_dirname


def _move_to_for_review(mission_dirname: str, *extra: str):
    return runner.invoke(
        root_app,
        ["agent", "tasks", "move-task", "WP01", "--to", "for_review", "--mission", mission_dirname, *extra],
    )


@pytest.mark.regression
@pytest.mark.parametrize("auto_commit_flag", ["--auto-commit", "--no-auto-commit"])
def test_move_task_for_review_json_stdout_is_one_document_despite_benign_dirty_bookkeeping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, auto_commit_flag: str
) -> None:
    """RED on pre-fix code: stdout opened with the prose note, then the JSON.

    Both readiness call sites are exercised: deferred after the auto-commit,
    and up front under ``--no-auto-commit``."""
    _repo_root, mission_dirname = _claim_wp01_and_dirty_bookkeeping(tmp_path, monkeypatch, mission_slug="move-task-json-6651")

    result = _move_to_for_review(mission_dirname, auto_commit_flag, "--json")

    assert result.exit_code == 0, result.output
    assert _NOTE not in result.stdout, result.stdout
    payload = json.loads(result.stdout)
    assert payload["result"] == "success"
    assert payload["transition_applied"] is True
    assert payload["new_lane"] == "for_review"


def test_move_task_for_review_human_mode_still_prints_the_benign_dirty_note(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: without ``--json`` the note is still shown, so the gate only
    changes what reaches a JSON consumer, not what a human sees."""
    _repo_root, mission_dirname = _claim_wp01_and_dirty_bookkeeping(tmp_path, monkeypatch, mission_slug="move-task-human-6651")

    result = _move_to_for_review(mission_dirname)

    assert result.exit_code == 0, result.output
    assert f"Note: 1 {_NOTE}" in result.stdout, result.stdout
